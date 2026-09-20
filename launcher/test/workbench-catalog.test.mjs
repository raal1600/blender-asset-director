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
  const before=await fs.readFile(f.source);
  await f.work.catalogJob(p.id,f.sceneId,p.revision,{assetId:f.aid,file:f.file,confirmed:true});p=await f.wait();
  const s=p.workbench.scenes[0];assert.equal(s.current,null);assert.ok(s.candidate);assert.equal(s.completed.world,undefined);
  assert.equal(s.checkpoints[0].audit.objects[0].asset_id,f.aid);assert.deepEqual(await fs.readFile(f.source),before);
  assert.equal(await exists(path.join(p.directory,'Runs/.interactive-execution.lock')),false);
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

test('animation found through Entire library cannot use World import',async t=>{
  const f=await fixture(t);f.asset.kind='animation';let p=await f.select();
  await f.work.attest(p.id,p.revision,true);
  await assert.rejects(f.work.catalogJob(p.id,f.sceneId,p.revision,{assetId:f.aid,file:f.file,confirmed:true}),/models and packs/);
  assert.equal(f.calls.some(a=>a[0]==='job-prepare'),false);
});
