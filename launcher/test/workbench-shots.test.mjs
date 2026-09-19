// Synthetic storage/HTTP contracts. This file does not claim Blender or model execution.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {validateWorkbench} from '../lib/workbench-model.mjs';
import {validateShotInput,taskShotContext} from '../lib/workbench-shots.mjs';
import {shotFor,renderIsCurrent,previewIsCurrent,cutIsCurrent} from '../public/workbench-lineage.mjs';
import {fileHash,json,writeJson} from '../lib/storage.mjs';
import {createApp} from '../server.mjs';
const uid=prefix=>prefix+randomUUID();
const input={name:'Arrival',camera:'Camera A',start:1,end:4};
async function fixture(t){
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-shots-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
  for(const kind of ['Animations','Characters','Meshes','AssetDirector'])await fs.mkdir(path.join(root,'Database',kind),{recursive:true});
  const store=new Store(root);await store.init();let p=await store.create('Shot contracts','Synthetic scene; no model request.');
  const config={library:path.join(root,'Database/AssetDirector'),ffmpeg:process.execPath,ffprobe:process.execPath};
  const runtime={config,launchWorkbenchTask:async()=>123,launchReview:async()=>234,
    harness:async args=>{if(args[0]==='workbench-capabilities')return {schema:1,task_workspace:true,render_frames:true,preview_camera:true};throw Error('No synthetic executor for '+args[0]);}};
  const work=new Workbench(store,runtime,config),created=await work.create(p.id,p.revision,'Shared world');p=created.project;
  const scene=p.workbench.scenes[0],rel='Scenes/synthetic.blend';await fs.writeFile(path.join(p.directory,rel),'BLENDER-v420 SYNTHETIC UNIT FIXTURE');
  const cp={id:uid('cp_'),path:rel,...await fileHash(path.join(p.directory,rel)),stage:'world',audit:{objects:[{name:'Camera A',type:'CAMERA'},{name:'Camera B',type:'CAMERA'},{name:'Rig',type:'ARMATURE'}],frame_range:[1,12]}};
  scene.checkpoints=[cp];scene.current=cp.id;scene.completed={world:cp.id,action:cp.id};scene.stage='shots';p=await store.save(p,p.revision);
  return {root,store,work,runtime,config,cp,id:p.id,sid:scene.id,p,scene:()=>store.get(p.id).then(v=>v.workbench.scenes[0]),fresh:()=>store.get(p.id)};
}
async function save(f,value=input){const p=await f.fresh();return f.work.saveShot(f.id,f.sid,p.revision,value);}
async function advance(f){let p=await f.fresh();for(const stage of ['shots','light'])p=await f.work.approve(f.id,f.sid,p.revision,stage,f.cp.id);return p;}
function rendered(scene,shot){return {id:uid('rnd_'),jobId:'j_'+'b'.repeat(24),checkpointId:scene.current,shotId:shot.id,shotRevision:shot.revision,options:{camera:shot.camera,start:shot.start,end:shot.end},approved:true};}

test('shot schema rejects arbitrary commands, guessed identities and unbounded timings',()=>{
  validateShotInput(input);
  for(const value of [null,[],{...input,script:'x'},{...input,name:''},{...input,camera:'x\n'},{...input,start:true},{...input,start:-100001},{...input,end:361},{...input,end:0},{...input,revision:1},{...input,id:uid('sc_'),revision:1}])assert.throws(()=>validateShotInput(value));
});
test('two named shots reference the same checkpoint; no world copy or silent retiming',async t=>{
  const f=await fixture(t);let p=await save(f);const first=shotFor(p.workbench.scenes[0]);
  p=await save(f,{...input,name:'Reveal',camera:'Camera B',start:5,end:8});const scene=p.workbench.scenes[0];
  assert.equal(scene.shots.length,2);assert.equal(scene.checkpoints.length,1);assert.equal(scene.current,f.cp.id);
  assert.equal((await fs.readdir(path.join(p.directory,'Scenes'))).length,1);
  assert.equal((await fileHash(path.join(p.directory,f.cp.path))).sha256,f.cp.sha256);
  const record=await json(path.join(p.directory,`Docs/Workbench/${first.id}-v1.json`));assert.equal(record.checkpointSha256,f.cp.sha256);assert.equal(record.transport,'launcher-ui');
  validateWorkbench(p.workbench);
});
test('only observed cameras and ranges can be saved, and metadata needs inspection',async t=>{
  const f=await fixture(t);await assert.rejects(save(f,{...input,camera:'Guessed Camera'}),/observed camera/);
  await assert.rejects(save(f,{...input,end:13}),/outside/);
  let p=await f.fresh();p.workbench.scenes[0].checkpoints[0].audit=null;await f.store.save(p,p.revision);
  await assert.rejects(save(f),/Inspect/);
});
test('wrong activity, stale project/shot revisions and cross-scene IDs are refused',async t=>{
  const f=await fixture(t);let p=await save(f),shot=shotFor(p.workbench.scenes[0]);
  await assert.rejects(f.work.saveShot(f.id,f.sid,p.revision-1,input),/changed/);
  await assert.rejects(save(f,{...input,id:shot.id,revision:2}),/Shot changed/);
  await assert.rejects(save(f,{...input,id:uid('shot_'),revision:1}),/Shot changed/);
  p=await advance(f);await assert.rejects(save(f),/Capture shots/);
  await assert.rejects(f.work.selectShot(f.id,f.sid,p.revision,uid('shot_')),/does not belong/);
});
test('writer semaphore and candidate review prevent shot changes',async t=>{
  const f=await fixture(t);let p=await save(f),shot=shotFor(p.workbench.scenes[0]),lock=uid('task_');
  await f.work.lock(p,lock);await assert.rejects(save(f),/unfinished/);
  await assert.rejects(f.work.selectShot(f.id,f.sid,p.revision,shot.id),/unfinished/);await f.work.unlock(p,lock);
  p=await f.fresh();p.workbench.scenes[0].candidate=f.cp.id;await f.store.save(p,p.revision);await assert.rejects(save(f),/candidate/);
});
test('task context carries exact camera and playback range; conflicts are not silently ignored',async t=>{
  const f=await fixture(t);let p=await save(f),scene=p.workbench.scenes[0];
  assert.deepEqual(taskShotContext(scene,f.cp),{camera:'Camera A',frame:1,frameRange:[1,4],targets:['Camera A']});
  assert.throws(()=>taskShotContext(scene,f.cp,{camera:'Camera B'}),/differs/);
  assert.throws(()=>taskShotContext(scene,f.cp,{frame:5}),/outside/);
  const opened=await f.work.openTask(f.id,f.sid,p.revision);
  assert.equal(opened.task.camera,'Camera A');assert.deepEqual(opened.task.frameRange,[1,4]);assert.equal(opened.task.input.sha256,f.cp.sha256);
});
test('shot revision invalidates its old render and cut, without deleting either',async t=>{
  const f=await fixture(t);let p=await save(f),scene=p.workbench.scenes[0],shot=shotFor(scene),render=rendered(scene,shot);
  scene.renders.push(render);scene.completed.light=f.cp.id;scene.completed.render=f.cp.id;
  p.workbench.film.clips=[{sceneId:f.sid,renderId:render.id}];const cut={id:uid('cut_'),refs:structuredClone(p.workbench.film.clips),approved:true};p.workbench.film.cuts.push(cut);
  assert.equal(cutIsCurrent(p.workbench,cut),true);await f.store.save(p,p.revision);
  p=await save(f,{...input,id:shot.id,revision:1,end:3});scene=p.workbench.scenes[0];
  assert.equal(shotFor(scene).revision,2);assert.equal(renderIsCurrent(scene,render),false);assert.equal(cutIsCurrent(p.workbench,cut),false);
  assert.equal(scene.renders[0].approved,true);assert.equal(p.workbench.film.cuts[0].approved,true);assert.equal(scene.completed.light,undefined);
  p=await advance(f);await assert.rejects(f.work.approveRender(f.id,f.sid,p.revision,render.id),/shot revision/);
  await assert.rejects(f.work.clips(p,p.workbench.film.clips),/outdated/);
  assert.equal((await json(path.join(p.directory,`Docs/Workbench/${shot.id}-v1.json`))).shot.end,4);
});
test('changing selected shot does not reuse another camera preview',async t=>{
  const f=await fixture(t);let p=await save(f),scene=p.workbench.scenes[0],shot=shotFor(scene);
  scene.preview={checkpointId:f.cp.id,shotId:shot.id,shotRevision:1,camera:shot.camera};await f.store.save(p,p.revision);
  assert.equal(previewIsCurrent(scene),true);
  p=await save(f,{...input,name:'Second angle',camera:'Camera B'});assert.equal(previewIsCurrent(p.workbench.scenes[0]),false);
  assert.equal(previewIsCurrent({...scene,selectedShot:null}),false);
  assert.equal(renderIsCurrent(scene,{checkpointId:f.cp.id}),true); // Old explicit-camera render.
});
test('render request must agree with shot definition before native preparation',async t=>{
  const f=await fixture(t);await save(f);let p=await advance(f);p.workbench.scenes[0].readiness={checkpointId:f.cp.id,jobId:'j_'+'a'.repeat(24)};await f.store.save(p,p.revision);
  f.work.interactions=()=>({sourceStatus:async()=>({ready:true})});p=await f.fresh();
  await assert.rejects(f.work.startJob(f.id,f.sid,p.revision,'render-frames',{camera:'Camera B',start:1,end:4},true),/differs from the selected shot/);
  await assert.rejects(f.work.startJob(f.id,f.sid,p.revision,'preview',{frame:5},true),/outside the selected shot/);
});
test('multiple outdated film references can be removed incrementally, but not built or newly added',async t=>{
  const f=await fixture(t);let p=await save(f),scene=p.workbench.scenes[0],shot=shotFor(scene);
  const a=rendered(scene,shot),b=rendered(scene,shot);a.shotRevision=99;b.shotRevision=99;scene.renders.push(a,b);
  p.workbench.film.clips=[{sceneId:f.sid,renderId:a.id},{sceneId:f.sid,renderId:b.id}];p=await f.store.save(p,p.revision);
  p=await f.work.arrange(f.id,p.revision,[p.workbench.film.clips[1]]);assert.equal(p.workbench.film.clips.length,1);
  await assert.rejects(f.work.clips(p,p.workbench.film.clips),/outdated/);
  await assert.rejects(f.work.arrange(f.id,p.revision,[{sceneId:f.sid,renderId:a.id}]),/outdated/);
  p=await f.work.arrange(f.id,p.revision,[]);assert.deepEqual(p.workbench.film.clips,[]);
});
test('shot evidence retry reconciles same decision without overwriting immutable history',async t=>{
  const f=await fixture(t);let p=await save(f),shot=shotFor(p.workbench.scenes[0]);const originalSave=f.store.save.bind(f.store);
  f.store.save=async()=>{throw Error('Synthetic crash before manifest');};
  await assert.rejects(save(f,{...input,id:shot.id,revision:1,end:3}),/Synthetic crash/);f.store.save=originalSave;
  await assert.rejects(save(f,{...input,id:shot.id,revision:1,end:2}),/different shot decision/);
  p=await save(f,{...input,id:shot.id,revision:1,end:3});assert.equal(shotFor(p.workbench.scenes[0]).revision,2);
});
test('shot routes require authentication and stale revisions fail over real local HTTP',async t=>{
  const f=await fixture(t),app=await createApp({root:f.root,config:f.config,port:0,runtime:f.runtime});t.after(()=>new Promise(resolve=>app.server.close(resolve)));
  const body={projectId:f.id,sceneId:f.sid,revision:f.p.revision,shot:input};
  const send=token=>fetch(app.origin+'/api/workbench/shot-save',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify(body)});
  assert.equal((await send('wrong')).status,401);assert.equal((await send(app.token)).status,200);assert.equal((await send(app.token)).status,409);
  for(const file of ['workbench-shots.mjs','workbench-lineage.mjs'])assert.equal((await fetch(app.origin+'/'+file)).status,200);
});
