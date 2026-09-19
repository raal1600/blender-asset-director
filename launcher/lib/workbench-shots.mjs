/** Named shots reference observed cameras/ranges in one scene, not duplicate worlds. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {assert, now, safe, json, digest} from './storage.mjs';
import {validId, canEnter} from './workbench-model.mjs';
import {shotFor} from '../public/workbench-lineage.mjs';

export function validateShotInput(input) {
  assert(input&&typeof input==='object'&&!Array.isArray(input)&&
    Object.keys(input).every(k=>['id','revision','name','camera','start','end'].includes(k)), 'Invalid shot fields.');
  for(const key of ['name','camera'])assert(typeof input[key]==='string'&&input[key].trim().length>=1&&
    input[key].length<=(key==='name'?100:255)&&!/[\r\n\0]/.test(input[key]),'Choose a valid shot name and observed camera.');
  assert(Number.isInteger(input.start)&&Number.isInteger(input.end)&&input.start>=-100000&&
    input.end<=100000&&input.end>=input.start&&input.end-input.start<360,'A shot must contain 1–360 ordered frames.');
  if(input.id!==undefined)assert(validId(input.id,'shot_')&&Number.isInteger(input.revision)&&input.revision>=1,'Invalid shot identity or revision.');
  else assert(input.revision===undefined,'New shots cannot supply a revision.');
}
export function assertObservedShot(scene, checkpoint, shot) {
  assert(checkpoint,'Save a scene checkpoint before defining shots.',409);
  const audit=checkpoint.audit;
  const readiness=scene.readiness?.checkpointId===checkpoint.id?scene.readiness.data:null;
  const cameras=audit?.objects?.filter(o=>o.type==='CAMERA').map(o=>o.name)||readiness?.cameras;
  const range=audit?.frame_range||readiness?.frame_range;
  assert(Array.isArray(cameras)&&cameras.includes(shot.camera),'Inspect the saved scene and choose an observed camera; no camera was invented.',409);
  assert(Array.isArray(range)&&range.length===2&&shot.start>=range[0]&&shot.end<=range[1],
    'The shot range is outside the observed scene. Extend the action in Blender first.',409);
}
export async function saveShot(work,id,sceneId,revision,input) {
  validateShotInput(input);
  const p=await work.project(id,revision),scene=work.scene(p,sceneId);await work.unlocked(p);
  assert(canEnter(scene,'shots')&&scene.stage==='shots'&&!scene.candidate&&!scene.task&&!scene.run,
    'Save shot decisions in Capture shots after reviewing the scene candidate.',409);
  const cp=await work.verify(p,scene);assertObservedShot(scene,cp,input);
  scene.shots||=[];
  const previous=input.id?shotFor(scene,input.id):null;
  assert(!input.id||previous&&previous.revision===input.revision,'Shot changed. Refresh before editing.',409);
  assert(previous||scene.shots.length<200,'Scene has reached the shot limit.');
  const record={id:previous?.id||'shot_'+randomUUID(),revision:(previous?.revision||0)+1,
    name:input.name.trim(),camera:input.camera,start:input.start,end:input.end,
    checkpointId:cp.id,createdAt:previous?.createdAt||now(),updatedAt:now()};
  const evidencePath=await safe(p.directory,`Docs/Workbench/${record.id}-v${record.revision}.json`);
  const evidence={kind:'SHOT_DEFINITION',projectId:id,sceneId,checkpointSha256:cp.sha256,shot:record,transport:'launcher-ui'};
  await fs.mkdir(path.dirname(evidencePath),{recursive:true});
  try{await fs.writeFile(evidencePath,JSON.stringify(evidence,null,2)+'\n',{flag:'wx'});}
  catch(error){
    if(error.code!=='EEXIST')throw error;
    const retained=await json(evidencePath),semantic=shot=>({...shot,createdAt:null,updatedAt:null});
    assert(retained.projectId===id&&retained.sceneId===sceneId&&retained.checkpointSha256===cp.sha256&&
      digest(semantic(retained.shot))===digest(semantic(record)),
      'A different shot decision occupies this revision. Preserve its evidence and reconcile before retrying.',409);
    Object.assign(record,retained.shot); // Crash after evidence write, before manifest update.
  }
  if(previous)scene.shots[scene.shots.indexOf(previous)]=record;else scene.shots.push(record);
  scene.selectedShot=record.id;scene.preview=null;
  for(const key of ['shots','light','render'])delete scene.completed[key];
  return work.store.save(p,p.revision);
}
export async function selectShot(work,id,sceneId,revision,shotId) {
  const p=await work.project(id,revision),scene=work.scene(p,sceneId);await work.unlocked(p);
  assert(!scene.candidate&&!scene.task&&!scene.run,'Finish the current scene task before changing the shot.',409);
  assert(shotId===null||validId(shotId,'shot_')&&shotFor(scene,shotId),'Shot does not belong to this scene.',404);
  scene.selectedShot=shotId;return work.store.save(p,p.revision);
}
export function taskShotContext(scene,checkpoint,context={}) {
  const shot=shotFor(scene);
  if(!shot||!['shots','light','render'].includes(scene.stage))return context;
  assertObservedShot(scene,checkpoint,shot);
  assert(context.camera==null||context.camera===shot.camera,'Task camera differs from the selected shot. Select the intended shot first.',409);
  const frame=context.frame??shot.start;
  assert(Number.isInteger(frame)&&frame>=shot.start&&frame<=shot.end,'Task frame is outside this shot.',409);
  return {...context,camera:shot.camera,frame,frameRange:[shot.start,shot.end],
    targets:scene.stage==='shots'?[shot.camera]:(context.targets||[])};
}
