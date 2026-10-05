/** Shared native scene transaction. Policies are server-owned, never client code. */
import fs from 'node:fs/promises';
import {constants} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {assert,digest,exists,fileHash,json,now,safe,writeJson} from './storage.mjs';
import {approveCheckpoint} from './workbench-model.mjs';
import {checkpointScenePath} from './checkpoint-paths.mjs';

export async function checkpointJob(work,id,sceneId,revision,request,policy) {
  const {stage,operation,options,readOnly=false,candidateOnly=false,cancellation}=policy;
  const checkCancelled=()=>assert(!cancellation?.cancelled,'Action Save cancelled; prior scene and local draft retained.',499);
  assert(!(readOnly&&candidateOnly),'Read-only inspection cannot publish a candidate.');
  const p=await work.project(id),scene=work.scene(p,sceneId),runId=request.requestId;
  const identity=digest({projectId:id,sceneId,revision,request});
  const receipt=await safe(p.directory,`Runs/${runId}.json`);
  if(await exists(receipt)){
    const prior=await json(receipt);
    assert(prior.projectId===id&&prior.sceneId===sceneId&&prior.action===operation&&prior.requestIdentity===identity,'Save request identity conflicts with an earlier operation.',409);
    assert(['PREPARING','RUNNING','SUCCEEDED'].includes(prior.state),'Previous Save failed; inspect its retained attempt before retrying.',409);
    if(policy.implementation)assert(prior.implementation===await policy.implementation(),'Inspection runtime changed; request a new inspection without rewriting the old receipt.',409);
    return {run:prior,reused:true};
  }
  assert(p.revision===revision,'Project changed. Refresh before saving this draft.',409);
  assert(scene.stage===stage&&!scene.task&&!scene.run,'Finish the active scene task before saving '+stage+' changes.',409);
  await work.unlocked(p);
  assert(request.checkpointId===(scene.candidate||scene.current),'This draft belongs to an older checkpoint. Refresh before saving.',409);
  const cp=await work.verify(p,scene,request.checkpointId);
  assert(cp.sha256===request.sha256,'The draft checkpoint changed.',409);
  // Blender's embedded Python can reject paths that Node/standalone Python can
  // read. Check the new immutable destination before taking a lease or running.
  const cpId=readOnly?null:'cp_'+randomUUID();
  const relative=readOnly?null:checkpointScenePath(p.directory,sceneId,cpId);
  if(!readOnly)assert((await work.interactions(id).sourceStatus()).ready,'Review the exact production source use before saving.',409);
  await policy.check?.({p,scene,cp});
  const implementation=policy.implementation?await policy.implementation():null;
  const savedBase=scene.current,draftBase=scene.candidate;
  const record={schema:1,id:runId,projectId:id,sceneId,action:operation,state:'PREPARING',
    requestIdentity:identity,checkpointId:cp.id,checkpointSha256:cp.sha256,requestedRevision:revision,
    ...(implementation?{implementation}:{}),
    startedAt:now(),authorization:readOnly?'explicit-launcher-inspection':candidateOnly?'explicit-launcher-preparation':'explicit-launcher-save',options,
    ...(candidateOnly?{publication:'SEPARATE_CANDIDATE_ONLY'}:{}),
    ...(policy.context?{context:policy.context}:{})};
  if(cancellation?.cancelled){record.state='CANCELLED';record.finishedAt=now();record.error='Action Save cancelled before native execution; prior scene and local draft retained.';await writeJson(receipt,record);return {run:record,reused:false};}
  await work.lock(p,runId);
  try {
    await writeJson(receipt,record);checkCancelled();
    const optionsFile=await safe(p.directory,`Docs/Workbench/${runId}-options.json`);await writeJson(optionsFile,options);
    const job=await work.runtime.harness(['job-prepare',operation,'--input',await safe(p.directory,cp.path),'--options',optionsFile]);
    record.jobId=job.id;if(cancellation)cancellation.jobId=job.id;
    if(implementation)assert(job.specification?.implementation===implementation,'Native inspection runtime changed before execution.',409);
    assert(['PLANNED','SUCCEEDED'].includes(job.state),'Native Save needs explicit retry/recovery before execution.',409);
    await work.store.bindJob(id,job,q=>{
      const s=work.scene(q,sceneId);
      assert(s.current===savedBase&&s.candidate===draftBase&&s.stage===stage&&!s.task&&!s.run,'Scene changed before Save.',409);s.run=runId;
    });
    record.state='RUNNING';await writeJson(receipt,record);work.running.add(runId);
    const complete=async()=>{
      try {
        if(cancellation?.cancelled)await work.runtime.harness(['job-cancel',job.id]);
        const output=await work.runtime.harness(['job-run',job.id,'--blender',work.config.blender,'--timeout','180'],195000);
        checkCancelled();
        if(implementation)assert(output.specification?.implementation===implementation,'Native inspection runtime identity changed.',409);
        const data=await work.result(output);await policy.verify(data);
        let source,actual;
        if(!readOnly){
          const member=output.outputs.find(f=>f.path===`jobs/${job.id}/result.blend`);assert(member,'Native Save omitted its scene.');
          source=await safe(work.config.library,member.path);actual=await fileHash(source);
          assert(actual.sha256===member.sha256&&actual.size===member.size,'Native saved output changed.',409);
        }
        await work.serialize(async()=>{
          checkCancelled();if(cancellation)cancellation.committing=true;
          const q=await work.project(id),s=work.scene(q,sceneId);
          assert(s.run===runId&&s.current===savedBase&&s.candidate===draftBase&&s.stage===stage,'Scene changed during Save.',409);
          await work.verify(q,s,cp.id);
          if(readOnly){record.inspection=data;return;}
          assert((await work.interactions(id).sourceStatus()).ready,'Source-use scope changed during Save.',409);
          const destination=await safe(q.directory,relative);
          await fs.copyFile(source,destination,constants.COPYFILE_EXCL);
          const copied=await fileHash(destination);
          assert(copied.sha256===actual.sha256&&copied.size===actual.size,'New saved checkpoint differs from the verified output.',409);
          const checkpoint={id:cpId,path:relative,...copied,parent:cp.id,stage,createdAt:now(),
            source:operation+'-job',jobId:job.id,audit:data.scene_audit};
          await writeJson(await safe(q.directory,`Docs/Workbench/${cpId}.json`),checkpoint);
          s.checkpoints.push(checkpoint);
          if(candidateOnly)s.candidate=cpId;else approveCheckpoint(s,stage,cpId,false);
          s.run=null;
          await work.store.save(q,q.revision);record.resultCheckpointId=cpId;
        });
        record.state='SUCCEEDED';
      }catch(error){record.state=cancellation?.cancelled?'CANCELLED':'FAILED';record.error=cancellation?.cancelled?'Action Save cancelled; prior scene and local draft retained.':error.message;}
      finally{
        record.finishedAt=now();await writeJson(receipt,record);
        await work.serialize(async()=>{const q=await work.project(id),s=work.scene(q,sceneId);if(s.run===runId){s.run=null;await work.store.save(q,q.revision);}});
        await work.unlock(p,runId);work.running.delete(runId);if(cancellation)work.actionSaves.delete(runId);
      }
    };
    void complete().catch(error=>console.error(operation+' needs recovery: '+error.message));
    return {run:record,reused:false};
  }catch(error){
    record.state=cancellation?.cancelled?'CANCELLED':'FAILED';record.error=error.message;record.finishedAt=now();await writeJson(receipt,record);
    const q=await work.project(id),s=work.scene(q,sceneId);if(s.run===runId){s.run=null;await work.store.save(q,q.revision);}
    await work.unlock(p,runId);throw error;
  }
}
