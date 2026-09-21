// Synthetic transport and manifest tests. No Blender GUI or model execution claim.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {Interactions} from '../lib/interactions.mjs';
import {unfinishedWork} from '../lib/lifecycle.mjs';
import {approveCheckpoint,canEnter,validateWorkbench} from '../lib/workbench-model.mjs';
import {exists,fileHash,json,writeJson} from '../lib/storage.mjs';
import {createApp} from '../server.mjs';
const id=p=>p+randomUUID();
async function fixture(t){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-workbench-test-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 for(const kind of ['Animations','Characters','Meshes','AssetDirector'])await fs.mkdir(path.join(root,'Database',kind),{recursive:true});
 const store=new Store(root);await store.init();let p=await store.create('Synthetic production','Objects cross a stage.');
 const config={library:path.join(root,'Database/AssetDirector'),ffmpeg:process.execPath,ffprobe:process.execPath};
 const runtime={config,health:null,launchWorkbenchTask:async()=>123,launchReview:async()=>234,
   harness:async args=>{if(args[0]==='workbench-capabilities')return {schema:1,task_workspace:true,render_frames:true,film_assemble:true};throw Error('Synthetic executor not installed for '+args[0]);}};
 const work=new Workbench(store,runtime,config);const created=await work.create(p.id,p.revision,'First scene');p=created.project;
 const source=path.join(p.directory,'Scenes/original.blend');await fs.writeFile(source,'BLENDER-v420 SYNTHETIC FIXTURE ONLY');
 return {root,store,runtime,config,work,projectId:p.id,sceneId:created.sceneId,source,fresh:()=>store.get(p.id)};
}
async function candidate(f){const p=await f.fresh();return f.work.importCheckpoint(p.id,f.sceneId,p.revision,'Scenes/original.blend');}
async function approved(f){let p=await candidate(f),s=p.workbench.scenes[0];return f.work.approve(p.id,s.id,p.revision,'world',s.candidate);}

test('legacy schema remains unchanged until scene work is explicitly created',async t=>{
 const f=await fixture(t),legacy=await f.store.create('Legacy production');assert.equal(legacy.workbench,undefined);
 validateWorkbench(undefined);const p=await f.fresh();assert.equal(p.schema,1);assert.equal(p.scene,null);assert.equal(p.workbench.scenes[0].stage,'world');
 assert.equal(p.workbench.scenes[0].checkpoints.length,0);
});
test('scene navigation cannot skip prerequisites or accept an unrelated activity',async t=>{
 const f=await fixture(t);let p=await f.fresh();await assert.rejects(f.work.enter(p.id,f.sceneId,p.revision,'render'),/preceding/);
 p=await candidate(f);const s=p.workbench.scenes[0];await assert.rejects(f.work.approve(p.id,s.id,p.revision,'action',s.candidate),/current activity/);
 await assert.rejects(f.work.enter(p.id,s.id,p.revision,'action'),/Finish or resolve/);
 p=await f.work.approve(p.id,s.id,p.revision,'world',s.candidate);assert.equal(p.workbench.scenes[0].stage,'action');
 assert.equal(canEnter(p.workbench.scenes[0],'shots'),false);
});
test('source selection pins bytes but never manufactures imported object evidence',async t=>{
 const f=await fixture(t);await fs.writeFile(path.join(f.root,'Database/Meshes/box.glb'),'synthetic asset');
 const inventory=await f.store.scan();let p=await f.fresh();p=await f.work.selectSource(p.id,f.sceneId,p.revision,inventory.sources[0].id,true);
 const scene=p.workbench.scenes[0];assert.equal(scene.checkpoints.length,0);assert.deepEqual(scene.sources,[inventory.sources[0].id]);assert.equal(p.assets.length,1);
 await assert.rejects(f.store.detach(p.id,scene.sources[0],p.revision),/selected by a scene/);
 await fs.writeFile(path.join(f.root,'Database/Meshes/box.glb'),'changed asset');assert.equal((await f.store.verify(p.id)).ok,false);
 await assert.rejects(f.work.openTask(p.id,scene.id,p.revision),/Pinned sources changed/);
});
test('saved checkpoint copy preserves original bytes and stale revisions cannot overwrite it',async t=>{
 const f=await fixture(t),before=await fs.readFile(f.source);const p=await candidate(f),s=p.workbench.scenes[0],cp=s.checkpoints[0];
 assert.deepEqual(await fs.readFile(f.source),before);assert.deepEqual(await fs.readFile(path.join(p.directory,cp.path)),before);
 assert.equal(s.current,null);assert.equal(s.completed.world,undefined);
 await assert.rejects(f.work.approve(p.id,s.id,p.revision-1,'world',cp.id),/changed/);
 await fs.appendFile(path.join(p.directory,cp.path),'changed');await assert.rejects(f.work.approve(p.id,s.id,p.revision,'world',cp.id),/Checkpoint changed/);
});
test('inspection opens a separate disposable copy instead of the frozen checkpoint',async t=>{
 const f=await fixture(t);const p=await candidate(f),cp=p.workbench.scenes[0].checkpoints[0];let opened;
 f.runtime.launchReview=async(_,filename)=>{opened=filename;return 321;};await f.work.inspect(p.id,f.sceneId,p.revision,cp.id);
 assert.notEqual(opened,path.join(p.directory,cp.path));assert.deepEqual(await fs.readFile(opened),await fs.readFile(f.source));
 await fs.appendFile(opened,'human review edits');assert.equal((await fileHash(path.join(p.directory,cp.path))).sha256,cp.sha256);
});
test('one atomic semaphore blocks the existing Codex executor during manual Blender work',async t=>{
 const f=await fixture(t),jobId='j_'+'b'.repeat(24);await f.store.bindJob(f.projectId,{id:jobId,specification:{operation:'scene-audit',inputs:[]}});
 const p=await f.fresh(),runId=id('task_');await f.work.lock(p,runId);
 const interactions=new Interactions(f.store,f.runtime,p.id,randomUUID());
 await assert.rejects(interactions.runJob(jobId,async()=>{throw Error('Must not ask or execute');}),/pending or running/);
 await assert.rejects(f.work.lock(p,id('task_')),/unfinished/);
 assert.ok((await unfinishedWork(f.store,f.config)).length>0);await assert.rejects(f.store.trash(p.id,p.revision),/writer/);
 await f.work.unlock(p,runId);assert.equal(await exists(path.join(p.directory,'Runs/.interactive-execution.lock')),false);
});
test('an old unfinished receipt beyond the recent history view still blocks new work',async t=>{
 const f=await fixture(t),p=await f.fresh();await writeJson(path.join(p.directory,'Runs/000-old.json'),{projectId:p.id,state:'RUNNING'});
 for(let i=0;i<35;i++)await writeJson(path.join(p.directory,`Runs/zzz-${i}.json`),{projectId:p.id,state:'SUCCEEDED'});
 await assert.rejects(f.work.create(p.id,p.revision,'Blocked scene'),/unfinished/);
});
test('Blender task carries exact context, keeps both originals and requires a real return receipt',async t=>{
 const f=await fixture(t);let p=await approved(f);const cp=p.workbench.scenes[0].checkpoints[0];let launch;
 f.runtime.launchWorkbenchTask=async(project,file)=>{launch=await json(file);return 567;};
 await f.work.openTask(p.id,f.sceneId,p.revision,{targets:['Observed Rig'],frame:12});p=await f.fresh();
 assert.equal(launch.stage,'action');assert.equal(launch.input.sha256,cp.sha256);assert.deepEqual(launch.targets,['Observed Rig']);assert.equal(launch.frame,12);
 assert.notEqual(launch.workingScene,launch.input.path);assert.notEqual(launch.checkpointScene,launch.input.path);
 await assert.rejects(f.work.collectTask(p.id,f.sceneId,p.revision),/No checkpoint receipt/);
 await fs.writeFile(path.join(p.directory,launch.checkpointScene),'BLENDER saved synthetic candidate');
 const hash=await fileHash(path.join(p.directory,launch.checkpointScene));
 const returned={taskId:launch.id,projectId:p.id,sceneId:f.sceneId,stage:'action',path:launch.checkpointScene,...hash,audit:{objects:[]}};
 await writeJson(path.join(p.directory,launch.returnFile),{...returned,sceneId:id('sc_')});
 await assert.rejects(f.work.collectTask(p.id,f.sceneId,p.revision),/another task/);
 await writeJson(path.join(p.directory,launch.returnFile),returned);p=await f.work.collectTask(p.id,f.sceneId,p.revision);
 const scene=p.workbench.scenes[0];assert.equal(scene.task,null);assert.equal(scene.current,cp.id);assert.ok(scene.candidate);assert.equal(scene.completed.action,undefined);
 assert.equal((await fileHash(path.join(p.directory,cp.path))).sha256,cp.sha256);assert.equal(await exists(path.join(p.directory,'Runs/.interactive-execution.lock')),false);
});
test('launch failure retains evidence but releases its own writer lock',async t=>{
 const f=await fixture(t),p=await f.fresh();f.runtime.launchWorkbenchTask=async()=>{throw Error('Blender executable refused');};
 await assert.rejects(f.work.openTask(p.id,f.sceneId,p.revision),/refused/);
 const q=await f.fresh();assert.equal(q.workbench.scenes[0].task,null);assert.equal((await f.store.runs(p.id))[0].state,'FAILED');assert.equal(await exists(path.join(p.directory,'Runs/.interactive-execution.lock')),false);
});
test('recovery needs an explicit stopped-process confirmation and keeps working files',async t=>{
 const f=await fixture(t);let p=await f.fresh();const opened=await f.work.openTask(p.id,f.sceneId,p.revision);p=await f.fresh();
 const working=path.join(p.directory,opened.task.workingScene);await fs.writeFile(working,'synthetic unsaved-work stand-in');
 await assert.rejects(f.work.resolve(p.id,f.sceneId,p.revision,opened.task.id,false),/Confirm/);
 p=await f.work.resolve(p.id,f.sceneId,p.revision,opened.task.id,true);assert.equal(p.workbench.scenes[0].task,null);assert.equal(await exists(working),true);
 assert.equal((await json(path.join(p.directory,'Runs',opened.task.id+'.json'))).state,'INTERRUPTED');
});
test('upstream checkpoint revision invalidates downstream completion without deleting history',async t=>{
 const f=await fixture(t);let p=await approved(f),scene=p.workbench.scenes[0],first=scene.current;
 for(const stage of ['action','shots','light']){p=await f.work.approve(p.id,scene.id,p.revision,stage,first);scene=p.workbench.scenes[0];}
 assert.equal(scene.stage,'render');p=await f.work.enter(p.id,scene.id,p.revision,'world');
 await fs.writeFile(f.source,'BLENDER changed world');p=await candidate(f);scene=p.workbench.scenes[0];const second=scene.candidate;
 p=await f.work.approve(p.id,scene.id,p.revision,'world',second);scene=p.workbench.scenes[0];
 assert.equal(scene.current,second);assert.deepEqual(Object.keys(scene.completed),['world']);assert.equal(scene.checkpoints.length,2);
 assert.ok(scene.checkpoints.some(c=>c.id===first));assert.equal(canEnter(scene,'render'),false);
});
test('film arrangement rejects absent/unapproved outputs and can be cleared',async t=>{
 const f=await fixture(t);let p=await f.fresh();p=await f.work.arrange(p.id,p.revision,[]);assert.deepEqual(p.workbench.film.clips,[]);
 await assert.rejects(f.work.arrange(p.id,p.revision,[{sceneId:f.sceneId,renderId:id('rnd_')}]),/checkpoint|unapproved/);
});
test('manifest refuses escaped checkpoint paths and orphaned references',async t=>{
 const f=await fixture(t),p=await candidate(f);const w=structuredClone(p.workbench);w.scenes[0].checkpoints[0].path='../outside.blend';assert.throws(()=>validateWorkbench(w));
 w.scenes[0].checkpoints[0].path='Scenes/inside.blend';w.scenes[0].current=id('cp_');assert.throws(()=>validateWorkbench(w),/Unknown selected/);
});
test('HTTP workbench and media retain authentication, exact routes and legacy compatibility',async t=>{
 const f=await fixture(t);const app=await createApp({root:f.root,config:f.config,port:0,runtime:f.runtime});t.after(()=>new Promise(r=>app.server.close(r)));
 const headers={Authorization:`Bearer ${app.token}`,'Content-Type':'application/json'};
 assert.equal((await fetch(app.origin+'/workbench')).status,200);assert.equal((await fetch(app.origin+'/')).status,200);
 assert.equal((await fetch(app.origin+'/api/workbench/media?projectId='+f.projectId)).status,401);
 assert.equal((await fetch(app.origin+'/api/workbench/state?projectId='+f.projectId,{headers:{...headers,Origin:'https://foreign.invalid'}})).status,403);
 let result=await fetch(app.origin+'/api/workbench/state?projectId='+f.projectId,{headers});assert.equal(result.status,200);assert.equal((await result.json()).project.workbench.scenes.length,1);
 result=await fetch(app.origin+'/api/workbench/execute-python',{method:'POST',headers,body:JSON.stringify({projectId:f.projectId,revision:(await f.fresh()).revision,code:'print(1)'})});assert.equal(result.status,404);
 result=await fetch(app.origin+'/api/workbench/import',{method:'POST',headers,body:JSON.stringify({projectId:f.projectId,sceneId:f.sceneId,revision:(await f.fresh()).revision,sourceScene:'../foreign.blend'})});assert.equal(result.status,400);
 const p=await f.fresh();const task=await app.workbench.openTask(p.id,f.sceneId,p.revision);
 result=await fetch(app.origin+'/api/projects/update',{method:'POST',headers,body:JSON.stringify({projectId:p.id,revision:(await f.fresh()).revision,brief:'race'})});assert.equal(result.status,409);
 await app.workbench.resolve(p.id,f.sceneId,(await f.fresh()).revision,task.task.id,true);
});

test('launcher source confirmation preserves provider wording, has honest transport and is reused by MCP only at the exact scope',async t=>{
 const f=await fixture(t);await fs.mkdir(path.join(f.root,'Database/Animations/Mixamo'));const source=path.join(f.root,'Database/Animations/Mixamo/synthetic.fbx');await fs.writeFile(source,'SYNTHETIC ONLY');
 const inventory=await f.store.scan();let p=await f.fresh();p=await f.work.selectSource(p.id,f.sceneId,p.revision,inventory.sources[0].id,true);
 const status=await f.work.interactions(p.id).sourceStatus();assert.equal(status.ready,false);assert.match(status.message,/official Mixamo downloads/);assert.match(status.message,/not a harness license grant/);
 await assert.rejects(f.work.attest(p.id,p.revision,false),/explicit user/);assert.equal((await f.work.interactions(p.id).sourceStatus()).ready,false);
 const answer=await f.work.attest(p.id,p.revision,true);assert.equal(answer.ready,true);
 const record=await json(path.join(p.directory,'Docs/Interactions',answer.receipt+'.json'));assert.equal(record.transport,'launcher-ui-source-confirmation');assert.notEqual(record.transport,'mcp-elicitation-client-response');
 const interaction=f.work.interactions(p.id);assert.equal((await interaction.prepare(async()=>{throw Error('Should reuse this exact source answer');})).ready,true);
 p=await f.store.update(p.id,{revision:p.revision,brief:'Different project use'});assert.equal((await interaction.sourceStatus()).ready,false);
 await assert.rejects(f.work.attest(p.id,p.revision-1,true),/changed/);
 await fs.writeFile(source,'CHANGED SYNTHETIC ONLY');await assert.rejects(f.work.attest(p.id,p.revision,true),/bytes changed/);
});

test('checkpoint collection is idempotent after persistence succeeds but lease release fails',async t=>{
 const f=await fixture(t);let p=await f.fresh();const opened=await f.work.openTask(p.id,f.sceneId,p.revision),task=opened.task;p=await f.fresh();
 await fs.writeFile(path.join(p.directory,task.checkpointScene),'BLENDER SYNTHETIC CP');const hash=await fileHash(path.join(p.directory,task.checkpointScene));
 await writeJson(path.join(p.directory,task.returnFile),{taskId:task.id,projectId:p.id,sceneId:f.sceneId,stage:'world',path:task.checkpointScene,...hash,audit:{objects:[]}});
 const unlock=f.work.unlock.bind(f.work);f.work.unlock=async()=>{throw Error('Synthetic interruption after save');};
 await assert.rejects(f.work.collectTask(p.id,f.sceneId,p.revision),/Synthetic interruption/);p=await f.fresh();assert.equal(p.workbench.scenes[0].checkpoints.length,1);assert.equal(p.workbench.scenes[0].task,task.id);
 f.work.unlock=unlock;p=await f.work.collectTask(p.id,f.sceneId,p.revision);assert.equal(p.workbench.scenes[0].checkpoints.length,1);assert.equal(p.workbench.scenes[0].task,null);
});

test('an asynchronous native failure is persisted, clears the scene run and releases only its own semaphore',async t=>{
 const f=await fixture(t);let p=await approved(f);const jobId='j_'+'e'.repeat(24);let rejectRun;
 f.runtime.harness=async args=>{
  if(args[0]==='workbench-capabilities')return {render_frames:true,task_workspace:true};
  if(args[0]==='job-prepare')return {id:jobId,state:'PLANNED',specification:{operation:'render-readiness',inputs:[{path:args[3]}]}};
  if(args[0]==='job-run')return new Promise((_,reject)=>{rejectRun=reject;});
  throw Error('Unexpected synthetic command');
 };
 const result=await f.work.startJob(p.id,f.sceneId,p.revision,'render-readiness',{});assert.equal(result.run.state,'RUNNING');assert.ok(f.work.running.has(result.run.id));
 rejectRun(Error('Synthetic native render-readiness failure'));
 for(let i=0;i<100&&f.work.running.size;i++)await new Promise(r=>setTimeout(r,5));
 assert.equal(f.work.running.size,0);p=await f.fresh();assert.equal(p.workbench.scenes[0].run,null);assert.equal(await exists(path.join(p.directory,'Runs/.interactive-execution.lock')),false);
 const run=await json(path.join(p.directory,'Runs',result.run.id+'.json'));assert.equal(run.state,'FAILED');assert.match(run.error,/Synthetic native/);
});
