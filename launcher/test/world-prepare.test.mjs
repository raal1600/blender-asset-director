/** Synthetic transport/persistence contracts. Real Blender is tested separately. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {validateWorldPrepare} from '../lib/world-prepare.mjs';
import {fileHash,json,writeJson,exists} from '../lib/storage.mjs';
const uid=p=>p+randomUUID(),group={asset_id:'a_'+'1'.repeat(24),import_job:'j_'+'2'.repeat(24)};
async function fixture(t){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'world-prepare-test-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const store=new Store(root);await store.init();let p=await store.create('Synthetic compatibility');
 const config={library:path.join(root,'Database/AssetDirector'),blender:process.execPath},jobs=new Map(),calls=[],control={fail:false,wrongResult:false};
 const audit={version:'world-prepare-v1',sha256:'b'.repeat(64),preserved:'c'.repeat(64),ownership:{SyntheticMesh:[group.asset_id,group.import_job,null,null]},settings:{},groups:[{...group,members:['SyntheticMesh'],roots:['SyntheticMesh'],status:'PREPARABLE'}]};
 const runtime={config,job:async id=>jobs.get(id),harness:async args=>{
  calls.push(args);
  if(args[0]==='job-prepare'){
   const input=args[args.indexOf('--input')+1],options=await json(args[args.indexOf('--options')+1]);
   const job={id:'j_'+randomUUID().replaceAll('-','').slice(0,24),state:'PLANNED',outputs:[],specification:{operation:args[1],options,inputs:[{path:input,...await fileHash(input)}]}};jobs.set(job.id,job);return job;
  }
  if(args[0]==='job-run'){
   const job=jobs.get(args[1]),inspect=job.specification.operation==='world-prepare-audit';
   if(control.fail&&!inspect){job.state='FAILED';throw Error('Synthetic preparation worker failed');}
   const dir=path.join(config.library,'jobs',job.id);await fs.mkdir(dir,{recursive:true});
   const data=inspect?structuredClone(audit):{version:'world-prepare-v1',request:job.specification.options,reopened:true,publication:'SEPARATE_CANDIDATE_ONLY',visual_acceptance:'NOT_EVALUATED',scene_audit:{objects:[]},world_placement:{instances:[]}};
   if(control.wrongResult&&!inspect)data.request={...data.request,groups:[]};
   await writeJson(path.join(dir,'result.json'),{status:'OK',job_id:job.id,data});
   const files=['result.json'];if(!inspect){await fs.writeFile(path.join(dir,'result.blend'),'BLENDER SYNTHETIC PREPARATION');files.push('result.blend');}
   for(const name of files)job.outputs.push({path:`jobs/${job.id}/${name}`,...await fileHash(path.join(dir,name))});job.state='SUCCEEDED';return job;
  }
  throw Error('Unexpected synthetic harness call');
 }};
 const work=new Workbench(store,runtime,config),made=await work.create(p.id,p.revision,'Synthetic older world');p=made.project;
 const source=path.join(p.directory,'Scenes/synthetic.blend');await fs.writeFile(source,'BLENDER SYNTHETIC ORIGINAL');
 const cp={id:uid('cp_'),path:'Scenes/synthetic.blend',...await fileHash(source),parent:null,stage:'world',audit:{objects:[{name:'SyntheticMesh',type:'MESH',asset_id:group.asset_id,import_job:group.import_job}]}};
 const s=p.workbench.scenes[0];s.checkpoints.push(cp);s.current=cp.id;s.completed={world:cp.id,action:cp.id};p=await store.save(p,p.revision);
 const base={version:'world-prepare-v1',requestId:uid('run_'),checkpointId:cp.id,sha256:cp.sha256};
 const wait=async()=>{for(let i=0;i<300;i++){if(!work.running.size)return store.get(p.id);await new Promise(r=>setTimeout(r,5));}throw Error('Synthetic job did not finish');};
 await work.inspectWorldPreparation(p.id,s.id,p.revision,base);p=await wait();
 const request={...base,requestId:uid('run_'),inspectionId:base.requestId,audit_sha256:audit.sha256,groups:[group]};
 return {store,work,p,sceneId:s.id,cp,source,base,request,audit,calls,control,wait};
}

test('preparation transport binds exact inspection and groups, never arbitrary scripts',()=>{
 const base={version:'world-prepare-v1',requestId:uid('run_'),checkpointId:uid('cp_'),sha256:'a'.repeat(64)};
 validateWorldPrepare(base,true);const request={...base,inspectionId:uid('run_'),audit_sha256:'b'.repeat(64),groups:[group]};validateWorldPrepare(request);
 for(const bad of [null,{}, {...request,script:'no'},{...request,groups:[]},{...request,groups:[group,group]},{...request,inspectionId:'foreign'},{...request,groups:[{...group,members:['guessed']}]}])assert.throws(()=>validateWorldPrepare(bad));
});

test('inspection keeps saved state; preparation publishes only a review candidate until explicit Save',async t=>{
 const f=await fixture(t),before=await fileHash(f.source),baseline=f.p.workbench.scenes[0];
 assert.equal(baseline.current,f.cp.id);assert.equal(baseline.candidate,null);assert.equal(baseline.checkpoints.length,1);
 await f.work.prepareWorld(f.p.id,f.sceneId,f.p.revision,f.request);let p=await f.wait(),s=p.workbench.scenes[0];
 assert.equal(s.current,f.cp.id);assert.notEqual(s.candidate,f.cp.id);assert(s.candidate);assert.deepEqual(s.completed,baseline.completed);
 const candidate=s.candidate;assert.equal(s.checkpoints.at(-1).source,'world-prepare-job');assert.equal(s.checkpoints.at(-1).parent,f.cp.id);
 assert.deepEqual(await fileHash(f.source),before);assert.equal(s.run,null);assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),false);
 const replay=await f.work.prepareWorld(f.p.id,f.sceneId,f.p.revision,f.request);assert.equal(replay.reused,true);assert.equal(replay.run.resultCheckpointId,candidate);
 p=await f.work.keepBuilding(p.id,f.sceneId,p.revision);s=p.workbench.scenes[0];assert.equal(s.current,candidate);assert.equal(s.candidate,null);assert.deepEqual(s.completed,{});
 assert.deepEqual(await fileHash(f.source),before);
});

test('stale or foreign inspection and unobserved groups never prepare a candidate',async t=>{
 const f=await fixture(t),count=f.calls.length;
 for(const patch of [{sha256:'f'.repeat(64)},{audit_sha256:'f'.repeat(64)},{groups:[{...group,import_job:'foreign'}]}])await assert.rejects(f.work.prepareWorld(f.p.id,f.sceneId,f.p.revision,{...f.request,...patch}));
 const file=path.join(f.p.directory,'Runs',f.base.requestId+'.json'),run=await json(file);
 await writeJson(file,{...run,sceneId:uid('sc_')});await assert.rejects(f.work.prepareWorld(f.p.id,f.sceneId,f.p.revision,f.request),/another scene/);
 await writeJson(file,{...run,inspection:{...run.inspection,settings:{tampered:true}}});await assert.rejects(f.work.prepareWorld(f.p.id,f.sceneId,f.p.revision,f.request),/changed after execution/);
 assert.equal(f.calls.length,count);assert.equal((await f.store.get(f.p.id)).workbench.scenes[0].current,f.cp.id);
});

test('source-use refusal and existing manual writer prevent preparation',async t=>{
 const f=await fixture(t),count=f.calls.length,original=f.work.interactions.bind(f.work);
 f.work.interactions=()=>({sourceStatus:async()=>({ready:false})});await assert.rejects(f.work.prepareWorld(f.p.id,f.sceneId,f.p.revision,f.request),/source use/);f.work.interactions=original;
 const task=uid('task_');await f.work.lock(f.p,task);await assert.rejects(f.work.prepareWorld(f.p.id,f.sceneId,f.p.revision,f.request),/unfinished/);await f.work.unlock(f.p,task);
 assert.equal(f.calls.length,count);
});

test('failed or mismatched preparation preserves baseline, reviews and retained failure',async t=>{
 for(const failure of ['fail','wrongResult']){
  const f=await fixture(t);f.control[failure]=true;
  await f.work.prepareWorld(f.p.id,f.sceneId,f.p.revision,f.request);const p=await f.wait(),s=p.workbench.scenes[0];
  assert.equal(s.current,f.cp.id);assert.equal(s.candidate,null);assert.equal(s.checkpoints.length,1);assert.deepEqual(s.completed,f.p.workbench.scenes[0].completed);
  assert.equal((await json(path.join(p.directory,'Runs',f.request.requestId+'.json'))).state,'FAILED');assert.deepEqual(await fileHash(f.source),{sha256:f.cp.sha256,size:f.cp.size});
  await assert.rejects(f.work.prepareWorld(f.p.id,f.sceneId,f.p.revision,f.request),/failed/);
 }
});
