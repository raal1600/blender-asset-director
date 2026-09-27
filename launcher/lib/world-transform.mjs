/** One explicit Save -> one bounded job -> verified, unapproved checkpoint.
 * Browser drafts never own a writer lease. This module acquires it only on Save.
 */
import fs from 'node:fs/promises';
import {constants} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {assert,digest,exists,fileHash,json,now,safe,writeJson} from './storage.mjs';
import {approveCheckpoint,validHash,validId} from './workbench-model.mjs';

export function validateWorldSave(request) {
  assert(request&&typeof request==='object'&&!Array.isArray(request)&&
    Object.keys(request).every(k=>['version','requestId','checkpointId','sha256','transforms'].includes(k)), 'Invalid World save request.');
  assert(request.version==='world-transform-v1'&&validId(request.requestId,'run_')&&validId(request.checkpointId,'cp_')&&validHash(request.sha256), 'Invalid World save identity.');
  assert(Array.isArray(request.transforms)&&request.transforms.length>0&&request.transforms.length<=64, 'Save one to 64 whole assets.');
  const seen=new Set();
  for(const change of request.transforms){
    assert(change&&typeof change==='object'&&!Array.isArray(change)&&Object.keys(change).length===3&&
      Object.keys(change).every(k=>['instance','expected_matrix','matrix'].includes(k))&&validId(change.instance,'instance_')&&!seen.has(change.instance), 'Choose distinct observed asset instances.');
    seen.add(change.instance);
    for(const matrix of [change.expected_matrix,change.matrix])assert(Array.isArray(matrix)&&matrix.length===16&&matrix.every(x=>typeof x==='number'&&Number.isFinite(x)), 'Invalid placement matrix.');
  }
  return request;
}

export async function saveWorld(work,id,sceneId,revision,request) {
  validateWorldSave(request);
  const p=await work.project(id),scene=work.scene(p,sceneId),runId=request.requestId;
  const identity=digest({projectId:id,sceneId,revision,request});
  const receipt=await safe(p.directory,`Runs/${runId}.json`);
  // A repeated HTTP submission reuses its exact receipt even after revision changed.
  if(await exists(receipt)){
    const prior=await json(receipt);
    assert(prior.projectId===id&&prior.sceneId===sceneId&&prior.action==='world-transform'&&prior.requestIdentity===identity, 'Save request identity conflicts with an earlier operation.',409);
    assert(['PREPARING','RUNNING','SUCCEEDED'].includes(prior.state), 'Previous Save failed; inspect its retained attempt before retrying.',409);
    return {run:prior,reused:true};
  }
  assert(p.revision===revision,'Project changed. Refresh before saving this draft.',409);
  assert(scene.stage==='world'&&!scene.task&&!scene.run,'Finish the active scene task before saving World changes.',409);
  await work.unlocked(p);
  assert(request.checkpointId===(scene.candidate||scene.current),'This draft belongs to an older checkpoint. Refresh before saving.',409);
  const cp=await work.verify(p,scene,request.checkpointId);
  assert(cp.sha256===request.sha256,'The draft checkpoint changed.',409);
  assert((await work.interactions(id).sourceStatus()).ready,'Review the exact production source use before saving.',409);
  const observed=cp.audit?.objects||[];
  for(const change of request.transforms){
    const control=observed.filter(o=>o.placement_control&&o.placement_instance===change.instance);
    assert(control.length===1&&control[0].type==='EMPTY','This instance has no verified placement control. Arrange it in Blender first.',409);
  }
  const savedBase=scene.current,draftBase=scene.candidate,options={version:request.version,transforms:request.transforms};
  const record={schema:1,id:runId,projectId:id,sceneId,action:'world-transform',state:'PREPARING',
    requestIdentity:identity,checkpointId:cp.id,checkpointSha256:cp.sha256,requestedRevision:revision,
    startedAt:now(),authorization:'explicit-launcher-save',options};
  await work.lock(p,runId);
  try {
    await writeJson(receipt,record);
    const optionsFile=await safe(p.directory,`Docs/Workbench/${runId}-options.json`);await writeJson(optionsFile,options);
    const job=await work.runtime.harness(['job-prepare','world-transform','--input',await safe(p.directory,cp.path),'--options',optionsFile]);
    record.jobId=job.id;
    assert(['PLANNED','SUCCEEDED'].includes(job.state),'Native Save needs explicit retry/recovery before execution.',409);
    await work.store.bindJob(id,job,q=>{
      const s=work.scene(q,sceneId);
      assert(s.current===savedBase&&s.candidate===draftBase&&!s.task&&!s.run,'Scene changed before Save.',409);s.run=runId;
    });
    record.state='RUNNING';await writeJson(receipt,record);work.running.add(runId);
    const complete=async()=>{
      try {
        const output=await work.runtime.harness(['job-run',job.id,'--blender',work.config.blender,'--timeout','180'],195000);
        const data=await work.result(output);
        assert(data.version===request.version&&data.reopened===true&&data.scene_audit&&Array.isArray(data.transforms)&&
          digest(data.transforms.map(x=>({instance:x.instance,expected_matrix:x.before,matrix:x.after})))===digest(options.transforms), 'Native Save did not verify the exact placement batch.');
        const member=output.outputs.find(f=>f.path===`jobs/${job.id}/result.blend`);assert(member,'Native Save omitted its scene.');
        const source=await safe(work.config.library,member.path),actual=await fileHash(source);
        assert(actual.sha256===member.sha256&&actual.size===member.size,'Native saved output changed.',409);
        await work.serialize(async()=>{
          const q=await work.project(id),s=work.scene(q,sceneId);
          assert(s.run===runId&&s.current===savedBase&&s.candidate===draftBase,'Scene changed during Save.',409);
          await work.verify(q,s,cp.id);
          assert((await work.interactions(id).sourceStatus()).ready,'Source-use scope changed during Save.',409);
          const cpId='cp_'+randomUUID(),relative=`Scenes/${sceneId}--${cpId}.blend`,destination=await safe(q.directory,relative);
          await fs.copyFile(source,destination,constants.COPYFILE_EXCL);
          const copied=await fileHash(destination);
          assert(copied.sha256===actual.sha256&&copied.size===actual.size,'New saved checkpoint differs from the verified output.',409);
          const checkpoint={id:cpId,path:relative,...copied,parent:cp.id,stage:'world',createdAt:now(),
            source:'world-transform-job',jobId:job.id,audit:data.scene_audit};
          await writeJson(await safe(q.directory,`Docs/Workbench/${cpId}.json`),checkpoint);
          s.checkpoints.push(checkpoint);approveCheckpoint(s,'world',cpId,false);s.run=null;
          await work.store.save(q,q.revision);record.resultCheckpointId=cpId;
        });
        record.state='SUCCEEDED';
      }catch(error){record.state='FAILED';record.error=error.message;}
      finally{
        record.finishedAt=now();await writeJson(receipt,record);
        await work.serialize(async()=>{const q=await work.project(id),s=work.scene(q,sceneId);if(s.run===runId){s.run=null;await work.store.save(q,q.revision);}});
        await work.unlock(p,runId);work.running.delete(runId);
      }
    };
    void complete().catch(error=>console.error('World Save needs recovery: '+error.message));
    return {run:record,reused:false};
  }catch(error){
    record.state='FAILED';record.error=error.message;record.finishedAt=now();await writeJson(receipt,record);
    // Preparing/binding may have persisted a scene lease; release only our record.
    const q=await work.project(id),s=work.scene(q,sceneId);if(s.run===runId){s.run=null;await work.store.save(q,q.revision);}
    await work.unlock(p,runId);throw error;
  }
}
