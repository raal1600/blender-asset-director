/** Native catalog selection and reviewed import. No alternate catalog or executor. */
import fs from 'node:fs/promises';
import {constants} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {assert,fileHash,now,safe,writeJson} from './storage.mjs';
import {startSpecialist} from './workbench-specialist.mjs';
import {approveCheckpoint,checkpointFor} from './workbench-model.mjs';
import {scopeKinds} from '../public/workbench-scope.mjs';

const assetId=id=>assert(typeof id==='string'&&/^a_[a-f0-9]{24}$/.test(id),'Invalid catalog asset.');
export async function verifyNative(store,runtime,p) {
  if(!p.workbench?.catalogPins?.length)return;
  const result=await runtime.harness(['workbench-verify','--project',await safe(p.directory,'project.json')]);
  assert(result.ok===true,'Native catalog sources changed; review their pinned versions.',409);
}
export const withCatalog=Base=>class extends Base {
  async catalogPage(id,{query='',offset=0,kind=null,activity='all'}={}) {
    await this.store.get(id);
    assert(typeof query==='string'&&query.length<=2000&&Number.isSafeInteger(offset)&&offset>=0,'Invalid catalog search.');
    assert(kind===null||['model','pack','animation','material','hdri'].includes(kind),'Invalid catalog type.');
    let kinds;try{kinds=scopeKinds(activity);}catch{assert(false,'Invalid workflow activity.');}
    if(!kinds.length||kind&&!kinds.includes(kind))return {schema:1,items:[],total:0,offset:0,next_offset:null};
    return this.runtime.harness(['workbench-catalog','--query',query,'--offset',String(offset),'--limit','24',...(kind?['--kind',kind]:[]),...(activity==='all'?[]:['--kinds',...kinds])]);
  }
  async catalogDetail(id,aid,verify=false) {
    await this.store.get(id);assetId(aid);
    return this.runtime.harness(['workbench-catalog','--asset',aid,...(verify?['--verify']:[])]);
  }
  async selectCatalog(id,sceneId,revision,aid,selected) {
    const p=await this.project(id,revision),s=this.scene(p,sceneId);await this.unlocked(p);assetId(aid);
    assert(typeof selected==='boolean','Selection must be explicit.');
    assert(!s.candidate,'Review the current candidate before changing ingredients.',409);
    p.workbench.catalogPins||=[];s.catalog||=[];
    if(selected) {
      const a=await this.catalogDetail(id,aid,true),prior=p.workbench.catalogPins.find(a=>a.id===aid);
      assert(!prior||prior.version===a.version,'This production pins an older version. Do not overwrite its lineage.',409);
      if(!prior)p.workbench.catalogPins.push({id:a.id,version:a.version,title:a.title,kind:a.kind,provider:a.provider,files:a.files});
      if(!s.catalog.includes(aid))s.catalog.push(aid);
      if(a.kind==='animation')s.selectedMotion=aid;
    }else {s.catalog=s.catalog.filter(x=>x!==aid);if(s.selectedMotion===aid)s.selectedMotion=null;}
    // Source pins survive deselection because previous checkpoints can use them.
    return this.store.save(p,p.revision);
  }
  async catalogImage(id,aid) {
    const a=await this.catalogDetail(id,aid),image=a.files.find(f=>/\.(png|jpe?g)$/i.test(f.path)&&f.size<=8*1024*1024);
    if(!image)return null;
    const filename=await safe(this.config.library,image.path),actual=await fileHash(filename);
    assert(actual.sha256===image.sha256&&actual.size===image.size,'Package image changed.',409);
    return {path:filename,type:/\.png$/i.test(filename)?'image/png':'image/jpeg'};
  }
  async verify(p,scene,checkpointId=scene.current){await verifyNative(this.store,this.runtime,p);return super.verify(p,scene,checkpointId);}
  async approve(...args){const p=await this.project(args[0],args[2]);await verifyNative(this.store,this.runtime,p);return super.approve(...args);}
  async openTask(...args){const p=await this.project(args[0],args[2]);await verifyNative(this.store,this.runtime,p);return super.openTask(...args);}
  async codex(id,sceneId,revision){const p=await this.project(id,revision);await verifyNative(this.store,this.runtime,p);return startSpecialist(this,p,sceneId);}
  async clips(p,refs){await verifyNative(this.store,this.runtime,p);return super.clips(p,refs);}
  async keepBuilding(id,sceneId,revision) {
    const p=await this.project(id,revision),s=this.scene(p,sceneId);await this.unlocked(p);
    assert(s.candidate&&s.stage!=='render','No development candidate to keep.',409);
    await verifyNative(this.store,this.runtime,p);
    assert((await this.store.verify(id)).ok,'Pinned source changed.',409);
    const cp=checkpointFor(s,s.candidate),bytes=await fileHash(await safe(p.directory,cp.path));
    assert(bytes.sha256===cp.sha256&&bytes.size===cp.size&&cp.stage===s.stage,'Candidate changed or belongs to another activity.',409);
    await writeJson(await safe(p.directory,`Docs/Workbench/review_${randomUUID()}.json`),{projectId:id,sceneId,checkpointId:cp.id,sha256:cp.sha256,stage:s.stage,decision:'KEEP_WORKING',createdAt:now(),transport:'launcher-ui'});
    approveCheckpoint(s,s.stage,cp.id,false);return this.store.save(p,p.revision);
  }
  async catalogJob(id,sceneId,revision,request={}) {
    assert(request&&typeof request==='object'&&!Array.isArray(request)&&Object.keys(request).every(k=>['assetId','file','selection','operation','confirmed'].includes(k)),'Unknown catalog request fields.');
    const {assetId:aid,file,selection,operation='import',confirmed=false}=request;
    assert(typeof confirmed==='boolean','Confirmation must be an explicit boolean.');
    assert(['import','asset-contents'].includes(operation),'Unsupported catalog operation.');assetId(aid);
    const p=await this.project(id,revision),s=this.scene(p,sceneId);
    await this.unlocked(p);assert(!s.candidate&&!s.task&&!s.run,'Finish the active task or candidate first.',409);
    assert((s.catalog||[]).includes(aid),'Select this catalog source for the scene first.',409);
    assert(operation!=='import'||s.stage==='world','Import ingredients inside Assemble world.',409);
    await verifyNative(this.store,this.runtime,p);
    const a=await this.catalogDetail(id,aid,true);
    assert(typeof file==='string'&&a.models.includes(file),'Choose an exact supported model member.');
    if(operation==='import') {
      assert(confirmed===true,'Import needs an explicit user action.');
      assert(a.policy?.eligible,'Native source policy blocks this import; selecting an asset is not permission.',409);
      assert((await this.interactions(id).sourceStatus()).ready,'Review the exact production source use first.',409);
      if(file.toLowerCase().endsWith('.blend')) {
        const prior=s.assetContents?.[aid];
        assert(prior?.version===a.version&&prior.file===file,'Inspect this exact Blender package first.',409);
        const observed=await this.result(await this.runtime.job(prior.jobId));
        assert(observed.asset_id===aid&&observed.file===file,'Collection evidence belongs to another asset.',409);
        assert(Array.isArray(selection)&&selection.length>0&&selection.length<=64&&new Set(selection).size===selection.length&&selection.every(n=>observed.collections.includes(n)),'Choose observed collections only.');
      }else assert(selection===undefined,'Collection selection only applies to Blender packages.');
    }
    const cp=s.current?await this.verify(p,s):null;
    const options=operation==='import'?{file,collection:sceneId,...(selection?{selection}: {})}:{file,request_scope:id+':'+sceneId};
    const runId='run_'+randomUUID(),record={schema:1,id:runId,projectId:id,sceneId,action:operation,state:'PREPARING',assetId:aid,sourceVersion:a.version,checkpointId:cp?.id||null,startedAt:now(),authorization:confirmed?'explicit-launcher-user-action':'read-only',options};
    await this.lock(p,runId);
    const receipt=await safe(p.directory,`Runs/${runId}.json`);
    try {
      await writeJson(receipt,record);
      const optionFile=await safe(p.directory,`Docs/Workbench/${runId}-options.json`);await writeJson(optionFile,options);
      const job=await this.runtime.harness(['job-prepare',operation,'--asset',aid,...(operation==='import'&&cp?['--input',await safe(p.directory,cp.path)]:[]),'--options',optionFile]);
      await this.store.bindJob(id,job);record.jobId=job.id;
      assert(!['FAILED','INTERRUPTED','RUNNING'].includes(job.state),'Native job needs explicit retry or recovery.',409);
      record.state='RUNNING';await writeJson(receipt,record);
      const q=await this.project(id);this.scene(q,sceneId).run=runId;await this.store.save(q,q.revision);
      this.running.add(runId);
      const complete=async()=>{
        try {
          const output=await this.runtime.harness(['job-run',job.id,'--blender',this.config.blender,'--timeout','180'],195000);
          const data=await this.result(output);
          await this.serialize(async()=>{
            const q=await this.project(id),scene=this.scene(q,sceneId);
            assert(scene.run===runId&&scene.current===(cp?.id||null)&&!scene.candidate,'Scene changed during this operation.',409);
            await verifyNative(this.store,this.runtime,q);
            if(operation==='asset-contents') {
              assert(data.asset_id===aid&&data.file===file&&Array.isArray(data.collections),'Invalid collection inspection result.');
              scene.assetContents||={};scene.assetContents[aid]={jobId:job.id,version:a.version,file,collections:data.collections};
            }else {
              assert(data.source===aid&&Array.isArray(data.objects)&&data.objects.length&&data.scene_audit,'Native import did not produce observed objects.');
              const created=data.scene_audit.objects.filter(o=>o.asset_id===aid&&o.import_job===job.id);
              assert(data.objects.every(n=>created.some(o=>o.name===n)),'Import provenance was not observed in Blender.');
              const member=output.outputs.find(f=>f.path===`jobs/${job.id}/result.blend`);assert(member,'Import omitted its working scene.');
              const source=await safe(this.config.library,member.path),actual=await fileHash(source);
              assert(actual.sha256===member.sha256&&actual.size===member.size,'Native output changed.',409);
              const cpId='cp_'+randomUUID(),relative=`Scenes/${sceneId}--${cpId}.blend`,destination=await safe(q.directory,relative);
              // The import worker made external references absolute before saving.
              // Byte-identical copying preserves native grant derivations keyed by hash.
              await fs.copyFile(source,destination,constants.COPYFILE_EXCL);
              assert((await fileHash(destination)).sha256===member.sha256,'Candidate copy failed verification.',409);
              const candidate={id:cpId,path:relative,...actual,parent:scene.current,stage:'world',createdAt:now(),source:'native-import-job',jobId:job.id,assetId:aid,audit:data.scene_audit};
              await writeJson(await safe(q.directory,`Docs/Workbench/${cpId}.json`),candidate);
              scene.checkpoints.push(candidate);scene.candidate=cpId;
            }
            scene.run=null;await this.store.save(q,q.revision);
          });
          record.state='SUCCEEDED';
        }catch(e){record.state='FAILED';record.error=e.message;}
        finally {
          record.finishedAt=now();await writeJson(receipt,record);
          await this.serialize(async()=>{const q=await this.project(id),scene=this.scene(q,sceneId);if(scene.run===runId){scene.run=null;await this.store.save(q,q.revision);}});
          await this.unlock(p,runId);this.running.delete(runId);
        }
      };
      void complete().catch(e=>console.error('Catalog operation requires recovery: '+e.message));
      return {run:record};
    }catch(e){record.state='FAILED';record.error=e.message;record.finishedAt=now();await writeJson(receipt,record);await this.unlock(p,runId);throw e;}
  }
};
