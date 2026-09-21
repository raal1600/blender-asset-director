/** Synthetic executor boundaries with real persistence, hash checks and authorization. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {fileHash,json,writeJson,exists} from '../lib/storage.mjs';

async function fixture(t) {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'native-catalog-ui-'));
  t.after(()=>fs.rm(root,{force:true,recursive:true}));
  for(const kind of ['Animations','Characters','Meshes','AssetDirector/incoming'])await fs.mkdir(path.join(root,'Database',kind),{recursive:true});
  const store=new Store(root);await store.init();const library=path.join(root,'Database/AssetDirector');
  const file='incoming/source.obj',source=path.join(library,file);await fs.writeFile(source,'synthetic source bytes, not a real mesh');
  const aid='a_'+'a'.repeat(24),asset={id:aid,version:'b'.repeat(64),title:'Synthetic mesh',kind:'model',provider:'local',files:[{path:file,...await fileHash(source)}],models:[file],policy:{eligible:true},metadata:{}};
  const jobs=new Map();let calls=[];
  const runtime={config:{library},harness:async args=>{
    calls.push(args);
    if(args[0]==='workbench-catalog')return args.includes('--asset')?structuredClone(asset):{schema:1,items:[asset],total:1,offset:0,next_offset:null};
    if(args[0]==='workbench-verify'){
      const p=await json(args[args.indexOf('--project')+1]);
      for(const pin of p.workbench.catalogPins){assert.equal(pin.version,asset.version,'catalog source changed');assert.equal((await fileHash(source)).sha256,asset.files[0].sha256,'source bytes changed');}
      return {ok:true};
    }
    if(args[0]==='job-prepare'){
      const options=await json(args[args.indexOf('--options')+1]),jid='j_'+randomUUID().replaceAll('-','').slice(0,24);
      const job={id:jid,state:'PLANNED',outputs:[],specification:{operation:args[1],options,inputs:args.includes('--input')?[{path:args[args.indexOf('--input')+1]}]:[]}};jobs.set(jid,job);return job;
    }
    if(args[0]==='job-run'){
      const job=jobs.get(args[1]),directory=path.join(library,'jobs',job.id);await fs.mkdir(directory,{recursive:true});
      const p=await store.get(projectId);assert.ok(p.jobs.some(j=>j.id===job.id),'must bind before execution');
      assert.equal(await exists(path.join(p.directory,'Runs/.interactive-execution.lock')),true);
      const data=job.specification.operation==='import'?{source:aid,objects:['ObservedSyntheticObject'],scene_audit:{objects:[{name:'ObservedSyntheticObject',type:'MESH',asset_id:aid,import_job:job.id}]}}:{asset_id:aid,file,collections:[]};
      await writeJson(path.join(directory,'result.json'),{status:'OK',job_id:job.id,data});
      job.outputs.push({path:`jobs/${job.id}/result.json`,...await fileHash(path.join(directory,'result.json'))});
      if(job.specification.operation==='import'){const blend=path.join(directory,'result.blend');await fs.writeFile(blend,'BLENDER-v405 SYNTHETIC OUTPUT ONLY');job.outputs.push({path:`jobs/${job.id}/result.blend`,...await fileHash(blend)});}
      job.state='SUCCEEDED';return job;
    }
    throw Error('Unexpected synthetic command '+args[0]);
  },job:async id=>jobs.get(id)};
  const work=new Workbench(store,runtime,{library,blender:process.execPath});
  const production=await store.create('Native catalog test','Generated fixture only.');
  const created=await work.create(production.id,production.revision,'Assembly');const projectId=production.id,sceneId=created.sceneId;
  const fresh=()=>store.get(projectId),select=async()=>{const p=await fresh();return work.selectCatalog(projectId,sceneId,p.revision,aid,true);};
  const wait=async()=>{for(let i=0;i<200;i++){await new Promise(r=>setTimeout(r,5));if(!work.running.size)return fresh();}throw Error('Synthetic job did not settle');};
  return {root,store,work,runtime,asset,aid,file,source,projectId,sceneId,fresh,select,wait,calls};
}
test('selection pins native bytes but creates no imported instance or authorization',async t=>{
  const f=await fixture(t),p=await f.select(),s=p.workbench.scenes[0];
  assert.deepEqual(s.catalog,[f.aid]);assert.equal(s.checkpoints.length,0);assert.equal(p.workbench.catalogPins.length,1);
  const gate=await f.work.interactions(p.id).sourceStatus();assert.equal(gate.ready,false);assert.equal(gate.scope.sources[0].sourceId,f.aid);
  await assert.rejects(f.work.catalogJob(p.id,s.id,p.revision,{assetId:f.aid,file:f.file,confirmed:true}),/source use/);
  assert.equal(f.calls.some(a=>a[0]==='job-prepare'),false);
});
test('import runs through the bound native job and creates an unapproved audited checkpoint',async t=>{
  const f=await fixture(t);let p=await f.select();await f.work.attest(p.id,p.revision,true);
  const before=await fs.readFile(f.source);let saves=0;const save=f.store.save.bind(f.store);
  f.store.save=async(...args)=>{saves++;return save(...args);};
  await f.work.catalogJob(p.id,f.sceneId,p.revision,{assetId:f.aid,file:f.file,confirmed:true});p=await f.wait();
  const s=p.workbench.scenes[0];assert.equal(s.current,null);assert.ok(s.candidate);assert.equal(s.completed.world,undefined);
  assert.equal(s.checkpoints[0].audit.objects[0].asset_id,f.aid);assert.deepEqual(await fs.readFile(f.source),before);
  assert.equal(await exists(path.join(p.directory,'Runs/.interactive-execution.lock')),false);
  assert.equal(saves,2,'one atomic job/scene binding and one checkpoint publication');
  const run=(await f.store.runs(p.id))[0];
  assert.deepEqual(run.timings.map(t=>t.phase),['verify-sources','prepare-job','bind-job','blender-worker','verify-result','reverify-sources','save-checkpoint']);
  assert.ok(run.timings.every(t=>t.outcome==='SUCCEEDED'&&Number.isInteger(t.milliseconds)&&t.milliseconds>=0));
  p=await f.work.keepBuilding(p.id,s.id,p.revision);assert.equal(p.workbench.scenes[0].stage,'world');assert.equal(p.workbench.scenes[0].candidate,null);
});
test('declining import, unowned files and invalid operations cannot prepare a job',async t=>{
  const f=await fixture(t),p=await f.select();await f.work.attest(p.id,p.revision,true);
  for(const request of [{assetId:f.aid,file:f.file},{assetId:f.aid,file:'../../private.obj',confirmed:true},{assetId:f.aid,file:f.file,operation:'run_python',confirmed:true}])await assert.rejects(f.work.catalogJob(p.id,f.sceneId,p.revision,request));
  assert.equal(f.calls.some(a=>a[0]==='job-prepare'),false);
});
test('a changed native source or rights identity blocks confirmation and import',async t=>{
  const f=await fixture(t),p=await f.select();f.asset.version='c'.repeat(64);
  await assert.rejects(f.work.attest(p.id,p.revision,true),/catalog source changed/);
  await assert.rejects(f.work.catalogJob(p.id,f.sceneId,p.revision,{assetId:f.aid,file:f.file,confirmed:true}),/catalog source changed/);
});
test('native preparation failure preserves the run and releases its own writer',async t=>{
  const f=await fixture(t),p=await f.select();await f.work.attest(p.id,p.revision,true);const real=f.runtime.harness;
  f.runtime.harness=async args=>{if(args[0]==='job-prepare')throw Error('Synthetic refusal');return real(args);};
  await assert.rejects(f.work.catalogJob(p.id,f.sceneId,p.revision,{assetId:f.aid,file:f.file,confirmed:true}),/Synthetic refusal/);
  assert.equal((await f.store.runs(p.id))[0].state,'FAILED');assert.equal(await exists(path.join(p.directory,'Runs/.interactive-execution.lock')),false);
});
test('deselection retains the production pin and cannot silently replace its version',async t=>{
  const f=await fixture(t);let p=await f.select();p=await f.work.selectCatalog(p.id,f.sceneId,p.revision,f.aid,false);
  assert.deepEqual(p.workbench.scenes[0].catalog,[]);assert.equal(p.workbench.catalogPins.length,1);
  f.asset.version='c'.repeat(64);await assert.rejects(f.work.selectCatalog(p.id,f.sceneId,p.revision,f.aid,true),/older version/);
});

test('changed source after Blender completes refuses publication and preserves failed timing',async t=>{
 const f=await fixture(t),p=await f.select();await f.work.attest(p.id,p.revision,true);
 const real=f.runtime.harness;
 f.runtime.harness=async args=>{const result=await real(args);if(args[0]==='job-run')await fs.writeFile(f.source,'deliberately changed synthetic source');return result;};
 await f.work.catalogJob(p.id,f.sceneId,p.revision,{assetId:f.aid,file:f.file,confirmed:true});
 const after=await f.wait();assert.equal(after.workbench.scenes[0].candidate,null);
 const run=(await f.store.runs(p.id))[0];assert.equal(run.state,'FAILED');
 assert.equal(run.timings.at(-1).phase,'reverify-sources');assert.equal(run.timings.at(-1).outcome,'FAILED');
});

test('job and scene are already durably bound before worker execution',async t=>{
 const f=await fixture(t),p=await f.select();await f.work.attest(p.id,p.revision,true);
 const real=f.runtime.harness;let release,entered;
 const started=new Promise(r=>entered=r),waiting=new Promise(r=>release=r);
 f.runtime.harness=async args=>{if(args[0]==='job-run'){entered();await waiting;}return real(args);};
 const result=await f.work.catalogJob(p.id,f.sceneId,p.revision,{assetId:f.aid,file:f.file,confirmed:true});
 try{
  await started;const saved=await f.fresh();
  assert.ok(saved.jobs.some(j=>j.id===result.run.jobId));assert.equal(saved.workbench.scenes[0].run,result.run.id);
  const state=await f.work.state(p.id);assert.equal(state.runs.find(r=>r.id===result.run.id).phase,'blender-worker');
 }finally{release();await f.wait();}
 assert.equal(f.work.catalogProgress.size,0);
});

test('animation found through Entire library cannot use World import',async t=>{
  const f=await fixture(t);f.asset.kind='animation';let p=await f.select();
  await f.work.attest(p.id,p.revision,true);
  await assert.rejects(f.work.catalogJob(p.id,f.sceneId,p.revision,{assetId:f.aid,file:f.file,confirmed:true}),/models and packs/);
  assert.equal(f.calls.some(a=>a[0]==='job-prepare'),false);
});

test('import into a kept world still hashes its checkpoint and rechecks native sources',async t=>{
 const f=await fixture(t);let p=await f.select();await f.work.attest(p.id,p.revision,true);
 await f.work.catalogJob(p.id,f.sceneId,p.revision,{assetId:f.aid,file:f.file,confirmed:true});p=await f.wait();
 p=await f.work.keepBuilding(p.id,f.sceneId,p.revision);const cp=p.workbench.scenes[0].checkpoints[0];
 const before=await fs.readFile(path.join(p.directory,cp.path));f.calls.length=0;
 await f.work.catalogJob(p.id,f.sceneId,p.revision,{assetId:f.aid,file:f.file,confirmed:true});p=await f.wait();
 assert.equal(f.calls.filter(a=>a[0]==='workbench-verify').length,2,'preflight and publication both verify sources');
 assert.equal(p.workbench.scenes[0].checkpoints.at(-1).parent,cp.id);
 assert.deepEqual(await fs.readFile(path.join(p.directory,cp.path)),before);
 p=await f.work.discard(p.id,f.sceneId,p.revision);
 await fs.writeFile(path.join(p.directory,cp.path),'deliberately changed synthetic checkpoint');
 const prepared=f.calls.filter(a=>a[0]==='job-prepare').length;
 await assert.rejects(f.work.catalogJob(p.id,f.sceneId,p.revision,{assetId:f.aid,file:f.file,confirmed:true}),/checkpoint changed/);
 assert.equal(f.calls.filter(a=>a[0]==='job-prepare').length,prepared);
});
