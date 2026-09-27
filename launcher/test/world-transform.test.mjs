/** Synthetic transport only. Real Blender save/reopen is world_transform_fixture.py. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {validateWorldSave} from '../lib/world-transform.mjs';
import {fileHash,json,writeJson,exists} from '../lib/storage.mjs';

const matrix=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
async function fixture(t){
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'world-save-test-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
  for(const kind of ['Animations','Characters','Meshes','AssetDirector'])await fs.mkdir(path.join(root,'Database',kind),{recursive:true});
  const store=new Store(root);await store.init();let p=await store.create('World save test','Synthetic boundaries only');
  const config={library:path.join(root,'Database/AssetDirector'),blender:process.execPath};
  const calls=[],jobs=new Map(),control={pause:null,fail:false,wrongResult:false};
  const instance='instance_'+randomUUID();
  const audit=m=>({objects:[{name:'SyntheticControl',type:'EMPTY',placement_control:true,placement_instance:instance,matrix_world:m}]});
  const runtime={config,job:async id=>jobs.get(id),harness:async args=>{
    calls.push(args);
    if(args[0]==='job-prepare'){
      const options=await json(args[args.indexOf('--options')+1]);
      const job={id:'j_'+randomUUID().replaceAll('-','').slice(0,24),state:'PLANNED',outputs:[],
        specification:{operation:args[1],options,inputs:[{path:args[args.indexOf('--input')+1]}]}};
      jobs.set(job.id,job);return job;
    }
    if(args[0]==='job-run'){
      const job=jobs.get(args[1]);if(control.pause)await control.pause;
      if(control.fail){job.state='FAILED';throw Error('Synthetic worker failure');}
      const directory=path.join(config.library,'jobs',job.id);await fs.mkdir(directory,{recursive:true});
      const options=job.specification.options;
      const transforms=options.transforms.map(x=>({instance:x.instance,control:'SyntheticControl',before:x.expected_matrix,after:x.matrix}));
      if(control.wrongResult)transforms[0].after=matrix;
      const data={version:options.version,reopened:true,transforms,scene_audit:audit(transforms[0].after)};
      await writeJson(path.join(directory,'result.json'),{status:'OK',job_id:job.id,data});
      await fs.writeFile(path.join(directory,'result.blend'),'BLENDER SYNTHETIC SAVED OUTPUT');
      for(const name of ['result.json','result.blend'])job.outputs.push({path:`jobs/${job.id}/${name}`,...await fileHash(path.join(directory,name))});
      job.state='SUCCEEDED';return job;
    }
    throw Error('Unexpected synthetic call: '+args[0]);
  }};
  const work=new Workbench(store,runtime,config);
  const created=await work.create(p.id,p.revision,'World test');p=created.project;const sceneId=created.sceneId;
  const source=path.join(p.directory,'Scenes/synthetic.blend');await fs.writeFile(source,'BLENDER SYNTHETIC BASELINE');
  const cp={id:'cp_'+randomUUID(),path:'Scenes/synthetic.blend',...await fileHash(source),parent:null,stage:'world',audit:audit(matrix)};
  const s=p.workbench.scenes[0];s.checkpoints.push(cp);s.current=cp.id;s.completed={world:cp.id,action:cp.id};p=await store.save(p,p.revision);
  const request={version:'world-transform-v1',requestId:'run_'+randomUUID(),checkpointId:cp.id,sha256:cp.sha256,
    transforms:[{instance,expected_matrix:matrix,matrix:matrix.map((x,i)=>i===3?2:x)}]};
  const wait=async()=>{for(let i=0;i<250;i++){if(!work.running.size)return store.get(p.id);await new Promise(r=>setTimeout(r,5));}throw Error('Synthetic save did not finish');};
  return {store,work,runtime,calls,control,p,cp,source,sceneId,request,wait};
}

test('request schema rejects unknown fields, unbounded or duplicate instance batches',()=>{
  const request={version:'world-transform-v1',requestId:'run_'+randomUUID(),checkpointId:'cp_'+randomUUID(),sha256:'a'.repeat(64),
    transforms:[{instance:'instance_'+randomUUID(),expected_matrix:matrix,matrix}]};
  validateWorldSave(request);
  for(const bad of [null,{}, {...request,script:'no'}, {...request,transforms:[]}, {...request,transforms:[...request.transforms,...request.transforms]},
    {...request,transforms:[{...request.transforms[0],matrix:[NaN,...matrix.slice(1)]}]}])assert.throws(()=>validateWorldSave(bad));
});

test('one Save publishes verified checkpoint without approving stages and keeps original',async t=>{
  const f=await fixture(t),before=await fileHash(f.source);
  const started=await f.work.saveWorld(f.p.id,f.sceneId,f.p.revision,f.request);const p=await f.wait(),s=p.workbench.scenes[0];
  assert.notEqual(s.current,f.cp.id);assert.equal(s.candidate,null);assert.equal(s.stage,'world');assert.deepEqual(s.completed,{});
  assert.equal(s.checkpoints.at(-1).parent,f.cp.id);assert.equal(s.checkpoints.at(-1).source,'world-transform-job');
  assert.deepEqual(await fileHash(f.source),before);assert.equal(s.run,null);
  assert.equal(await exists(path.join(p.directory,'Runs/.interactive-execution.lock')),false);
  const result=await json(path.join(p.directory,`Runs/${started.run.id}.json`));assert.equal(result.state,'SUCCEEDED');
  const replay=await f.work.saveWorld(f.p.id,f.sceneId,f.p.revision,f.request);assert.equal(replay.reused,true);
  assert.equal(replay.run.resultCheckpointId,s.current);assert.equal(f.calls.filter(x=>x[0]==='job-run').length,1);
});

test('stale revision, checkpoint, unknown instance and wrong activity never launch a worker',async t=>{
  const f=await fixture(t);
  await assert.rejects(f.work.saveWorld(f.p.id,f.sceneId,f.p.revision-1,f.request),/changed/);
  await assert.rejects(f.work.saveWorld(f.p.id,f.sceneId,f.p.revision,{...f.request,sha256:'0'.repeat(64)}),/changed/);
  await assert.rejects(f.work.saveWorld(f.p.id,f.sceneId,f.p.revision,{...f.request,checkpointId:'cp_'+randomUUID()}),/older checkpoint/);
  await assert.rejects(f.work.saveWorld(f.p.id,f.sceneId,f.p.revision,{...f.request,transforms:[{...f.request.transforms[0],instance:'instance_'+randomUUID()}]}),/no verified placement/);
  const p=await f.store.get(f.p.id);p.workbench.scenes[0].stage='action';const changed=await f.store.save(p,p.revision);
  await assert.rejects(f.work.saveWorld(p.id,f.sceneId,changed.revision,f.request),/active scene task/);
  assert.equal(f.calls.length,0);
});

test('source-use refusal and a manual writer prevent dependent native execution',async t=>{
  const f=await fixture(t);const original=f.work.interactions.bind(f.work);
  f.work.interactions=()=>({sourceStatus:async()=>({ready:false})});
  await assert.rejects(f.work.saveWorld(f.p.id,f.sceneId,f.p.revision,f.request),/source use/);
  f.work.interactions=original;
  const task='task_'+randomUUID();await f.work.lock(f.p,task);
  await assert.rejects(f.work.saveWorld(f.p.id,f.sceneId,f.p.revision,f.request),/unfinished/);
  assert.equal(f.calls.length,0);await f.work.unlock(f.p,task);
});

test('inflight replay is idempotent and a conflicting request cannot acquire a second writer',async t=>{
  const f=await fixture(t);let finish;f.control.pause=new Promise(resolve=>{finish=resolve;});
  await f.work.saveWorld(f.p.id,f.sceneId,f.p.revision,f.request);
  assert.equal((await f.work.saveWorld(f.p.id,f.sceneId,f.p.revision,f.request)).reused,true);
  await assert.rejects(f.work.saveWorld(f.p.id,f.sceneId,f.p.revision,{...f.request,sha256:'f'.repeat(64)}),/conflicts/);
  const p=await f.store.get(f.p.id);
  await assert.rejects(f.work.saveWorld(p.id,f.sceneId,p.revision,{...f.request,requestId:'run_'+randomUUID()}),/active scene task/);
  finish();await f.wait();assert.equal(f.calls.filter(x=>x[0]==='job-run').length,1);
});

test('failed worker or mismatched result preserves saved state and retained attempt',async t=>{
  for(const reason of ['fail','wrongResult']){
    const f=await fixture(t);f.control[reason]=true;
    await f.work.saveWorld(f.p.id,f.sceneId,f.p.revision,f.request);const p=await f.wait(),s=p.workbench.scenes[0];
    assert.equal(s.current,f.cp.id);assert.equal(s.checkpoints.length,1);assert.deepEqual(s.completed,f.p.workbench.scenes[0].completed);
    assert.equal((await json(path.join(p.directory,`Runs/${f.request.requestId}.json`))).state,'FAILED');
    assert.deepEqual(await fileHash(f.source),{sha256:f.cp.sha256,size:f.cp.size});
    assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),false);
    await assert.rejects(f.work.saveWorld(p.id,f.sceneId,f.p.revision,f.request),/failed/);
  }
});
