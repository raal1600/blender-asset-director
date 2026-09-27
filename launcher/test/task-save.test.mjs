// Contract tests; native Save/Don't Save behavior is a separate Blender gate.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {randomUUID} from 'node:crypto';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {fileHash,json,writeJson,exists} from '../lib/storage.mjs';
import {taskObservation,taskBanner} from '../public/workbench-task.mjs';

async function fixture(t) {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-explicit-save-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
  const store=new Store(root);await store.init();let p=await store.create('Synthetic saves');
  let processState='verified';
  const runtime={harness:async()=>({task_workspace:true,explicit_save_handoff:true}),launchWorkbenchTask:async()=>98765,
    inspectWorkbenchTask:async()=>({state:processState})};
  const work=new Workbench(store,runtime,{}),created=await work.create(p.id,p.revision,'Scene');p=created.project;
  await fs.writeFile(path.join(p.directory,'Scenes/source.blend'),'BLENDER synthetic original');
  p=await work.importCheckpoint(p.id,created.sceneId,p.revision,'Scenes/source.blend');
  p=await work.keepBuilding(p.id,created.sceneId,p.revision);
  const previous=structuredClone(p.workbench.scenes[0]),opened=await work.openTask(p.id,created.sceneId,p.revision),task=opened.task;
  const working=path.join(p.directory,task.workingScene);await fs.writeFile(working,'BLENDER initialized working copy');
  const identity={schema:1,taskId:task.id,projectId:p.id,sceneId:created.sceneId,stage:'world',processId:98765,mode:'explicit-save-v1'};
  const sessionFile=path.join(p.directory,`Docs/Workbench/${task.id}-save-session.json`);
  const session={...identity,state:'READY',workingScene:task.workingScene,initial_sha256:(await fileHash(working)).sha256};await writeJson(sessionFile,session);
  const receipt=path.join(p.directory,`Docs/Workbench/${task.id}-explicit-save.json`);
  const sync=async()=>work.syncTask(p.id,created.sceneId,(await store.get(p.id)).revision);
  const save=async()=>{await fs.writeFile(working,'BLENDER user saved edits');const record={...identity,saveId:randomUUID(),path:task.workingScene,...await fileHash(working),source:'blender-explicit-save',human_acceptance:'PENDING',audit:{objects:[{name:'Saved cube'}]}};await writeJson(receipt,record);await writeJson(sessionFile,{...session,state:'SAVED'});return record;};
  return {store,work,p,task,working,previous,session,sessionFile,receipt,sync,save,stop:()=>{processState='stopped';},unknown:()=>{processState='unknown';},fresh:()=>store.get(p.id)};
}
test('save then close adopts one saved draft without approval and preserves original',async t=>{
  const f=await fixture(t);const saved=await f.save();assert.equal((await f.sync()).changed,false);
  assert.equal((await f.fresh()).workbench.scenes[0].current,f.previous.current);
  f.stop();assert.equal((await f.sync()).outcome,'saved');const s=(await f.fresh()).workbench.scenes[0];
  assert.equal(s.task,null);assert.equal(s.candidate,null);assert.equal(s.stage,'world');assert.deepEqual(s.completed,{});
  assert.notEqual(s.current,f.previous.current);assert.equal(s.checkpoints.at(-1).sha256,saved.sha256);
  assert.deepEqual(s.checkpoints[0],f.previous.checkpoints[0]);
  assert.equal((await f.sync()).changed,false);assert.equal(s.checkpoints.length,2);
  assert.equal(await exists(path.join(f.p.directory,'Runs/.interactive-execution.lock')),false);
});
test('close without Save preserves the original scene and approval state',async t=>{
  const f=await fixture(t);f.stop();assert.equal((await f.sync()).outcome,'no-save');const s=(await f.fresh()).workbench.scenes[0];
  assert.equal(s.current,f.previous.current);assert.deepEqual(s.checkpoints,f.previous.checkpoints);assert.deepEqual(s.completed,f.previous.completed);
  assert.equal(s.task,null);assert.equal(await exists(path.join(f.p.directory,f.task.checkpointScene)),false);
});
test('unknown or running process never releases the writer even with a valid save',async t=>{
  const f=await fixture(t);await f.save();f.unknown();assert.equal((await f.sync()).changed,false);
  assert.equal((await f.fresh()).workbench.scenes[0].task,f.task.id);
});
for(const kind of ['wrong-project','changed-bytes','save-failure','context-drift','missing-observation','unexpected-file'])test('refuses '+kind+' and retains files and writer',async t=>{
  const f=await fixture(t);const r=await f.save();f.stop();
  if(kind==='wrong-project')await writeJson(f.receipt,{...r,projectId:'prj_'+randomUUID()});
  if(kind==='changed-bytes')await fs.appendFile(f.working,'not observed');
  if(kind==='save-failure')await writeJson(f.sessionFile,{...f.session,state:'SAVE_FAILED'});
  if(kind==='context-drift')await writeJson(f.sessionFile,{...f.session,state:'DISCONNECTED'});
  if(kind==='missing-observation')await fs.unlink(f.receipt);
  if(kind==='unexpected-file'){await fs.unlink(f.receipt);await writeJson(f.sessionFile,f.session);}
  await assert.rejects(f.sync());assert.equal((await f.fresh()).workbench.scenes[0].current,f.previous.current);
  assert.equal(await exists(f.working),true);assert.equal(await exists(path.join(f.p.directory,'Runs/.interactive-execution.lock')),true);
});
test('restart after draft persistence retries without duplicate checkpoints or approval',async t=>{
  const f=await fixture(t);await f.save();f.stop();const original=f.work.unlock.bind(f.work);f.work.unlock=async()=>{throw Error('synthetic interruption');};
  await assert.rejects(f.sync(),/synthetic interruption/);assert.equal((await f.fresh()).workbench.scenes[0].checkpoints.length,2);
  f.work.unlock=original;await f.sync();const s=(await f.fresh()).workbench.scenes[0];assert.equal(s.task,null);assert.equal(s.checkpoints.length,2);assert.deepEqual(s.completed,{});
});
test('new handoff banner does not require checkpoint collection',()=>{
  const status={taskId:'task',handoff:'explicit-save-v1',state:'READY',expected_file:true,observed_at:Date.now()/1000,gui_configured:true,dirty:true};
  assert.equal(taskObservation(status,'task').focus,true);
  const html=taskBanner({name:'Scene',task:'task'},status,x=>x,label=>label);
  assert.match(html,/Save &amp; return/);assert.doesNotMatch(html,/Collect saved checkpoint/);
  assert.equal(taskObservation({...status,observed_at:0},'task').kind,'returning');
});
