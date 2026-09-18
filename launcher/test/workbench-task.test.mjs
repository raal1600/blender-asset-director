// Synthetic observation contracts; no native GUI acceptance claim.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {writeJson} from '../lib/storage.mjs';
import {taskObservation,observationKey} from '../public/workbench-task.mjs';
const at=1000000,status={taskId:'task-a',state:'READY',expected_file:true,observed_at:1000,gui_configured:true,dirty:false};
test('only a fresh, scoped working-file observation enables focus',()=>{
 assert.equal(taskObservation(status,'task-a',at).focus,true);
 for(const change of [{taskId:'other'},{observed_at:0},{observed_at:1060},{expected_file:false},{gui_configured:false},{checkpoint_available:true},{state:'FAILED'}])
  assert.equal(taskObservation({...status,...change},'task-a',at).focus,false);
 assert.equal(taskObservation({...status,checkpoint_available:true},'task-a',at).kind,'saved');
 assert.equal(taskObservation({...status,dirty:true},'task-a',at+20000).kind,'unavailable');
});
test('heartbeat timestamps do not cause full UI refreshes but expiry and meaningful state do',()=>{
 assert.equal(observationKey(status,'task-a',at),observationKey({...status,observed_at:1001},'task-a',at+1000));
 assert.notEqual(observationKey(status,'task-a',at),observationKey(status,'task-a',at+20000));
 assert.notEqual(observationKey(status,'task-a',at),observationKey({...status,dirty:true},'task-a',at));
});
test('new project instructions use the configured skill, not a stale install directory',()=>{
 const text=new Store(path.resolve(os.tmpdir(),'test-config')).instructions('synthetic');
 assert.match(text,/config.json/);assert.doesNotMatch(text,/Harness[\\/]Installed/);
});
test('focus rejects another PID, another scene, or an expired heartbeat',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-task-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const store=new Store(root);await store.init();const p=await store.create('Synthetic focus');
 const runtime={harness:async()=>({task_workspace:true}),launchWorkbenchTask:async()=>76543,showBlender:async pid=>({visible:true,focused:false,processId:pid})};
 const work=new Workbench(store,runtime,{});const created=await work.create(p.id,p.revision,'Scene');
 const result=await work.openTask(p.id,created.sceneId,created.project.revision);const fresh=await store.get(p.id);
 const filename=path.join(fresh.directory,`Docs/Workbench/${result.task.id}-status.json`);
 const base={...status,taskId:result.task.id,observed_at:Date.now()/1000,processId:76543,projectId:p.id,sceneId:created.sceneId};
 await writeJson(filename,base);assert.equal((await work.focusTask(p.id,created.sceneId,fresh.revision)).processId,76543);
 for(const change of [{processId:1},{sceneId:'other'},{observed_at:1},{expected_file:false}]){
  await writeJson(filename,{...base,...change});await assert.rejects(work.focusTask(p.id,created.sceneId,fresh.revision));
 }
});
