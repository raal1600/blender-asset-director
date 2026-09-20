// Synthetic identity/transport regressions. Native close is tested separately.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createApp} from '../server.mjs';

async function fixture(t) {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-exit-'));
  const library=path.join(root,'Database/AssetDirector');await fs.mkdir(library,{recursive:true});
  let process={state:'stopped'},closed=0;
  const runtime={health:null,harness:async()=>({task_workspace:true}),launchWorkbenchTask:async()=>54321,
    inspectWorkbenchTask:async()=>process,closeWorkbenchTask:async()=>{closed++;return {requested:true};}};
  const app=await createApp({root,config:{library},runtime,port:0});
  t.after(async()=>{app.server.closeAllConnections();if(app.server.listening)await new Promise(r=>app.server.close(r));await fs.rm(root,{recursive:true,force:true});});
  const p=await app.store.create('Synthetic exit project');
  const scene=await app.workbench.create(p.id,p.revision,'Synthetic failed scene');
  const opened=await app.workbench.openTask(p.id,scene.sceneId,scene.project.revision);
  const run=opened.task,project=opened.project;
  const headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
  const call=(route,body)=>fetch(app.origin+'/api/'+route,{headers,method:body?'POST':'GET',...(body?{body:JSON.stringify(body)}:{})});
  const inspect=async()=>{const response=await call('lifecycle/task?projectId='+p.id+'&runId='+run.id);return {code:response.status,...await response.json()};};
  const statusFile=path.join(p.directory,'Docs/Workbench/'+run.id+'-status.json');
  await fs.mkdir(path.dirname(statusFile),{recursive:true});
  const failed={taskId:run.id,projectId:p.id,sceneId:scene.sceneId,state:'FAILED',message:'Synthetic startup failure'};
  await fs.writeFile(statusFile,JSON.stringify(failed));
  return {...app,call,inspect,project,run,statusFile,failed,setProcess:p=>process=p,closed:()=>closed,
    body:()=>({projectId:p.id,runId:run.id,revision:project.revision,confirmed:true})};
}
test('failed setup is named at exit without pretending its lease is an active render',async t=>{
  const f=await fixture(t),state=await (await f.call('lifecycle')).json();
  assert.equal(state.busy,true);assert.equal(state.needsAttention,true);assert.equal(state.tasks.length,1);
  assert.equal(state.reasons.length,1); // both writer semaphores belong to this one task
  assert.match(state.tasks[0].label,/Synthetic exit project \/ Synthetic failed scene: Blender task failed/);
  const details=await f.inspect();assert.equal(details.canRecover,true);assert.equal(details.canClose,false);
  assert.equal((await f.call('stop',{})).status,409);
  assert.equal((await f.store.runs(f.project.id))[0].state,'RUNNING'); // inspection is read-only
});
test('explicit stopped-task recovery retains working files and original failure evidence',async t=>{
  const f=await fixture(t),working=path.join(f.project.directory,f.run.workingScene);
  await fs.writeFile(working,'synthetic retained work');
  const before=await fs.readFile(f.statusFile);
  assert.equal((await f.call('lifecycle/task-recover',f.body())).status,200);
  assert.equal(await fs.readFile(working,'utf8'),'synthetic retained work');
  assert.deepEqual(await fs.readFile(f.statusFile),before);
  const state=await f.workbench.state(f.project.id);assert.equal(state.locked,false);
  assert.equal(state.project.workbench.scenes[0].candidate,null);
  assert.equal(state.runs[0].state,'INTERRUPTED');assert.equal(f.closed(),0);
  assert.equal((await (await f.call('lifecycle')).json()).busy,false);
});
test('live or unknown task process cannot be recovered even after setup failure',async t=>{
  const f=await fixture(t);
  for(const state of [{state:'verified',identity:'123',hasWindow:true},{state:'unknown'}]) {
    f.setProcess(state);assert.equal((await f.inspect()).canRecover,false);
    assert.equal((await f.call('lifecycle/task-recover',f.body())).status,409);
  }
  assert.equal((await f.workbench.state(f.project.id)).locked,true);assert.equal(f.closed(),0);
});
test('normal close requires explicit confirmation, unchanged revision and exact process identity',async t=>{
  const f=await fixture(t);f.setProcess({state:'verified',identity:'123',hasWindow:true});
  for(const body of [{...f.body(),confirmed:false,processIdentity:'123'},
    {...f.body(),revision:f.project.revision-1,processIdentity:'123'},{...f.body(),processIdentity:'recycled'}]) {
    assert.ok((await f.call('lifecycle/task-close',body)).status>=400);
  }
  assert.equal(f.closed(),0);
  assert.equal((await f.call('lifecycle/task-close',{...f.body(),processIdentity:'123'})).status,200);
  assert.equal(f.closed(),1);assert.equal((await f.workbench.state(f.project.id)).locked,true);
  assert.equal((await f.store.runs(f.project.id))[0].state,'RUNNING'); // close request is not exit proof
});
test('disconnected observations and completed saves are not silently discarded',async t=>{
  const f=await fixture(t);f.runtime.inspectWorkbenchTask=async()=>{throw Error('Unavailable')};
  assert.equal((await f.inspect()).process.state,'unknown');
  assert.equal((await f.call('lifecycle/task-recover',f.body())).status,409);
  f.runtime.inspectWorkbenchTask=async()=>({state:'stopped'});
  await fs.writeFile(path.join(f.project.directory,f.run.checkpointScene),'uncollected checkpoint');
  assert.equal((await f.inspect()).canRecover,false);
  assert.equal((await f.call('lifecycle/task-recover',f.body())).status,409);
});
test('saved return receipt offers collect, never recovery or automatic approval',async t=>{
  const f=await fixture(t);
  await fs.writeFile(f.statusFile,JSON.stringify({...f.failed,state:'CHECKPOINT_SAVED'}));
  await fs.writeFile(path.join(f.project.directory,f.run.returnFile),'{}');
  const state=await f.inspect();assert.equal(state.canCollect,true);assert.equal(state.canRecover,false);
  assert.equal((await f.workbench.state(f.project.id)).project.workbench.scenes[0].current,null);
});
test('exit assistance retains authentication and refuses mismatched task status',async t=>{
  const f=await fixture(t);
  assert.equal((await fetch(f.origin+'/api/lifecycle/task?projectId='+f.project.id+'&runId='+f.run.id)).status,401);
  await fs.writeFile(f.statusFile,JSON.stringify({...f.failed,projectId:'foreign'}));
  assert.equal((await f.inspect()).code,409);
  assert.equal((await f.call('lifecycle/task-close',{...f.body(),processIdentity:'123'})).status,409);
  assert.equal(f.closed(),0);
});
test('recovery rechecks process status after inspection and rejects stale or missing consent',async t=>{
  const f=await fixture(t);assert.equal((await f.inspect()).canRecover,true);
  assert.equal((await f.call('lifecycle/task-recover',{...f.body(),confirmed:false})).status,400);
  assert.equal((await f.call('lifecycle/task-recover',{...f.body(),revision:0})).status,409);
  f.setProcess({state:'verified',identity:'new',hasWindow:true});
  assert.equal((await f.call('lifecycle/task-recover',f.body())).status,409);
  assert.equal((await f.workbench.state(f.project.id)).locked,true);
});
