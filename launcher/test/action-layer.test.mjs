/** Synthetic boundary tests, not Blender execution or human approval. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {randomUUID} from 'node:crypto';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {validateActionRequest} from '../lib/action-layer.mjs';
import {exists,fileHash,json,writeJson} from '../lib/storage.mjs';
const uid=p=>p+randomUUID(),take='take_'+'b'.repeat(64);
const inspection={version:'action-layer-v1',sha256:'a'.repeat(64),frame_range:[1,48],fps:24,unassigned:[],
  performers:[{name:'Performer',unsupported:null,takes:[{id:take,performer:'Performer'}]},{name:'Other',unsupported:null,takes:[]},{name:'Constrained',unsupported:'Manual review',takes:[]}]};
async function fixture(t){
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'action-layer-test-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
  for(const name of ['Animations','Characters','Meshes','AssetDirector'])await fs.mkdir(path.join(root,'Database',name),{recursive:true});
  const store=new Store(root);await store.init();let project=await store.create('Action test','Generated transport fixture');
  const config={library:path.join(root,'Database/AssetDirector'),blender:process.execPath};
  const jobs=new Map(),calls=[],control={fail:false,wrong:false,pause:null};
  const runtime={config,harness:async args=>{
    calls.push(args);if(args[0]==='job-prepare'){
      const job={id:'j_'+randomUUID().replaceAll('-','').slice(0,24),state:'PLANNED',outputs:[],specification:{operation:args[1],options:await json(args[args.indexOf('--options')+1]),inputs:[]}};jobs.set(job.id,job);return job;
    }
    assert.equal(args[0],'job-run');const job=jobs.get(args[1]);if(control.pause)await control.pause;
    if(control.fail)throw Error('Synthetic native failure');
    const folder=path.join(config.library,'jobs',job.id);await fs.mkdir(folder,{recursive:true});
    let data=inspection;
    if(job.specification.operation==='action-edit'){
      data={version:inspection.version,request:job.specification.options,reopened:!control.wrong,performance_acceptance:'NOT_EVALUATED',scene_audit:{objects:[]},action_audit:inspection};
      await fs.writeFile(path.join(folder,'result.blend'),'BLENDER SYNTHETIC ACTION RESULT');
      job.outputs.push({path:`jobs/${job.id}/result.blend`,...await fileHash(path.join(folder,'result.blend'))});
    }
    await writeJson(path.join(folder,'result.json'),{status:'OK',job_id:job.id,data});job.outputs.push({path:`jobs/${job.id}/result.json`,...await fileHash(path.join(folder,'result.json'))});job.state='SUCCEEDED';return job;
  }};
  const work=new Workbench(store,runtime,config),created=await work.create(project.id,project.revision,'Action scene');project=created.project;
  const scene=project.workbench.scenes[0];scene.stage='action';const source=path.join(project.directory,'Scenes/source.blend');await fs.writeFile(source,'BLENDER SYNTHETIC ACTION SOURCE');
  const cp={id:uid('cp_'),path:'Scenes/source.blend',...await fileHash(source),stage:'world',parent:null};scene.checkpoints=[cp];scene.current=cp.id;scene.completed={world:cp.id,action:cp.id,shots:cp.id};
  project=await store.save(project,project.revision);
  const base={version:inspection.version,requestId:uid('run_'),checkpointId:cp.id,sha256:cp.sha256};
  const wait=async()=>{for(let n=0;n<300;n++){if(!work.running.size)return store.get(project.id);await new Promise(r=>setTimeout(r,5));}throw Error('Fixture job did not finish');};
  const inspect=async()=>{await work.inspectAction(project.id,scene.id,project.revision,base);return wait();};
  const request={...base,requestId:uid('run_'),inspectionId:base.requestId,audit_sha256:inspection.sha256,changes:[{performer:'Performer',mode:'clip',take_id:take,start:3,speed:2}]};
  return {project,scene,cp,work,store,config,source,base,request,inspect,wait,calls,control};
}
test('Action contract refuses guessed transfers, duplicate performers and bad timing',()=>{
  const request={version:inspection.version,requestId:uid('run_'),checkpointId:uid('cp_'),sha256:'c'.repeat(64),inspectionId:uid('run_'),audit_sha256:inspection.sha256,changes:[{performer:'Performer',mode:'clip',take_id:take,start:1,speed:1}]};
  validateActionRequest(request);
  for(const c of [{mode:'retarget'},{slot:'guessed'},{speed:NaN},{speed:true},{speed:5},{start:1.5},{take_id:'Idle'}])assert.throws(()=>validateActionRequest({...request,changes:[{...request.changes[0],...c}]}));
  assert.throws(()=>validateActionRequest({...request,changes:[...request.changes,...request.changes]}));
  assert.throws(()=>validateActionRequest({...request,frame_range:[1,4000]}));
  assert.throws(()=>validateActionRequest({...request,script:'no'}));
  validateActionRequest({...request,changes:[{performer:'Performer',mode:'hold',frame:5}]});
});
test('inspection is read-only and Save keeps World completion but invalidates later layers',async t=>{
  const f=await fixture(t),before=await fileHash(f.source),p=await f.inspect();
  assert.equal(p.workbench.scenes[0].current,f.cp.id);assert.equal(p.workbench.scenes[0].checkpoints.length,1);assert.deepEqual(p.workbench.scenes[0].completed,f.scene.completed);
  const read=await json(path.join(p.directory,`Runs/${f.base.requestId}.json`));assert.deepEqual(read.inspection,inspection);
  const result=await f.work.saveAction(p.id,f.scene.id,p.revision,f.request);const saved=await f.wait(),s=saved.workbench.scenes[0];
  assert.notEqual(s.current,f.cp.id);assert.equal(s.stage,'action');assert.deepEqual(s.completed,{world:f.cp.id});assert.equal(s.checkpoints.at(-1).source,'action-edit-job');assert.equal(s.candidate,null);
  assert.deepEqual(await fileHash(f.source),before);assert.equal(await exists(path.join(p.directory,'Runs/.interactive-execution.lock')),false);
  assert.equal((await f.work.saveAction(p.id,f.scene.id,p.revision,f.request)).reused,true);assert.equal(f.calls.filter(c=>c[0]==='job-run').length,2);
  assert.equal((await json(path.join(p.directory,`Runs/${result.run.id}.json`))).resultCheckpointId,s.current);
});
test('stale inspection, foreign performer take, unsupported performer and source refusal launch no edit',async t=>{
  const f=await fixture(t),p=await f.inspect(),count=f.calls.length;
  for(const patch of [{audit_sha256:'0'.repeat(64)},{changes:[{...f.request.changes[0],performer:'Other'}]},{changes:[{performer:'Constrained',mode:'hold',frame:5}]},{changes:[{performer:'Performer',mode:'hold',frame:99}]}])await assert.rejects(f.work.saveAction(p.id,f.scene.id,p.revision,{...f.request,...patch}));
  f.work.interactions=()=>({sourceStatus:async()=>({ready:false})});await assert.rejects(f.work.saveAction(p.id,f.scene.id,p.revision,f.request),/source use/);assert.equal(f.calls.length,count);
});
test('inspection also respects manual writer ownership and wrong activity',async t=>{
  const f=await fixture(t);let p=await f.store.get(f.project.id);p.workbench.scenes[0].stage='world';p=await f.store.save(p,p.revision);
  await assert.rejects(f.work.inspectAction(p.id,f.scene.id,p.revision,f.base),/active scene task/);
  p.workbench.scenes[0].stage='action';p=await f.store.save(p,p.revision);await f.work.lock(p,'task_'+randomUUID());
  await assert.rejects(f.work.inspectAction(p.id,f.scene.id,p.revision,f.base),/unfinished/);assert.equal(f.calls.length,0);
});
test('failed or unverified native Action retains checkpoint and review history',async t=>{
  for(const reason of ['fail','wrong']){
    const f=await fixture(t),p=await f.inspect();f.control[reason]=true;await f.work.saveAction(p.id,f.scene.id,p.revision,f.request);const after=await f.wait();
    assert.equal(after.workbench.scenes[0].current,f.cp.id);assert.deepEqual(after.workbench.scenes[0].completed,f.scene.completed);
    assert.equal((await json(path.join(p.directory,`Runs/${f.request.requestId}.json`))).state,'FAILED');assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),false);
    await assert.rejects(f.work.saveAction(p.id,f.scene.id,p.revision,f.request),/failed/);
  }
});
test('inflight Action retry reuses receipt and cannot run a second writer',async t=>{
  const f=await fixture(t),p=await f.inspect();let finish;f.control.pause=new Promise(resolve=>{finish=resolve;});
  await f.work.saveAction(p.id,f.scene.id,p.revision,f.request);assert.equal((await f.work.saveAction(p.id,f.scene.id,p.revision,f.request)).reused,true);
  await assert.rejects(f.work.saveAction(p.id,f.scene.id,p.revision,{...f.request,audit_sha256:'f'.repeat(64)}),/conflicts/);
  const current=await f.store.get(p.id);await assert.rejects(f.work.saveAction(p.id,f.scene.id,current.revision,{...f.request,requestId:uid('run_')}),/active scene task/);
  finish();await f.wait();assert.equal(f.calls.filter(c=>c[0]==='job-run').length,2);
});
