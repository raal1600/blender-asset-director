/** Consume only explicit saves after the exact owned process has stopped.
 * GET state stays read-only; UI polling calls the serialized task-sync POST.
 */
import fs from 'node:fs/promises';
import {constants} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {assert,exists,fileHash,json,now,safe,writeJson} from './storage.mjs';
import {approveCheckpoint,validHash,validId} from './workbench-model.mjs';
import {validTaskScenePaths} from './task-paths.mjs';
export const SAVE_MODE='explicit-save-v1';

export async function syncTask(work,id,sceneId,revision) {
  const p=await work.project(id,revision),s=work.scene(p,sceneId);
  if(!s.task)return {changed:false};
  const task=await json(await safe(p.directory,`Runs/${s.task}.json`));
  if(task.handoff!==SAVE_MODE)return {changed:false,legacy:true};
  assert(task.id===s.task&&task.projectId===id&&task.sceneId===sceneId&&task.action==='workbench-edit','Wrong editing task identity.',409);
  assert(task.projectDirectory===p.directory&&task.stage===s.stage&&validTaskScenePaths(task),
    'Editing task paths or activity changed.',409);
  assert(Number.isSafeInteger(task.processId)&&task.processId>0,'Task process identity is unavailable.',409);
  assert(!work.running.has(task.id),'Task is still running.',409);
  const process=work.runtime.inspectWorkbenchTask?await work.runtime.inspectWorkbenchTask(p,task):{state:'unknown'};
  if(process.state!=='stopped')return {changed:false,process:process.state};
  const identity=r=>r&&r.schema===1&&r.taskId===task.id&&r.projectId===id&&r.sceneId===sceneId&&r.stage===task.stage&&r.processId===task.processId&&r.mode===SAVE_MODE;
  const session=await json(await safe(p.directory,`Docs/Workbench/${task.id}-save-session.json`));
  assert(identity(session)&&session.workingScene===task.workingScene,'Editing session identity changed; files are preserved.',409);
  assert(['READY','SAVED'].includes(session.state),'Blender save or context needs inspection. '+(session.message||session.state),409);
  const file=await safe(p.directory,task.workingScene),hash=await fileHash(file);
  const receiptFile=await safe(p.directory,`Docs/Workbench/${task.id}-explicit-save.json`);
  const hasSave=await exists(receiptFile);
  let cp=s.checkpoints.find(c=>c.taskId===task.id);
  const current=s.checkpoints.find(c=>c.id===s.current);
  assert(!s.candidate&&(cp?s.current===cp.id:task.input?current?.sha256===task.input.sha256&&current?.path===task.input.path:!s.current),
    'Scene changed while Blender was editing; automatic return refused.',409);
  if(hasSave) {
    const saved=await json(receiptFile);
    assert(identity(saved)&&saved.path===task.workingScene&&saved.source==='blender-explicit-save'&&saved.human_acceptance==='PENDING'&&
      validHash(saved.sha256)&&validId(saved.saveId,'')&&saved.audit&&Array.isArray(saved.audit.objects),'Invalid explicit save evidence.',409);
    assert(hash.sha256===saved.sha256&&hash.size===saved.size,'Saved editing file changed or is incomplete. Nothing was adopted.',409);
    if(task.input)await work.verify(p,s,cp?.parent||s.current);
    else assert((await work.store.verify(id)).ok,'Pinned sources changed; inspect before returning.',409);
    const frozen=await safe(p.directory,task.checkpointScene);
    if(!await exists(frozen))await fs.copyFile(file,frozen,constants.COPYFILE_EXCL);
    const frozenHash=await fileHash(frozen);
    assert(frozenHash.sha256===saved.sha256&&frozenHash.size===saved.size&&(await fileHash(file)).sha256===saved.sha256,
      'Saved editing file changed during return; evidence retained.',409);
    if(!cp) {
      cp={id:'cp_'+randomUUID(),taskId:task.id,path:task.checkpointScene,...frozenHash,parent:s.current,
        stage:task.stage,audit:saved.audit,source:'blender-explicit-save',saveId:saved.saveId,createdAt:now()};
      await writeJson(await safe(p.directory,`Docs/Workbench/${cp.id}.json`),cp);
      s.checkpoints.push(cp);
      // Adopt a saved draft without recording approval or advancing activities.
      approveCheckpoint(s,task.stage,cp.id,false);
      s.lastEdit={taskId:task.id,outcome:'saved',checkpointId:cp.id,at:now()};
      await work.store.save(p,p.revision);
    } else assert(cp.sha256===saved.sha256&&s.current===cp.id,'Returned draft identity changed.',409);
  } else {
    assert(session.state==='READY'&&validHash(session.initial_sha256)&&hash.sha256===session.initial_sha256,
      'Working file changed without a verified Save. Inspect recovery; nothing was adopted.',409);
    assert(!await exists(await safe(p.directory,task.returnFile))&&!await exists(await safe(p.directory,task.checkpointScene)),
      'Unexpected checkpoint evidence; inspect recovery instead.',409);
  }
  task.state='SUCCEEDED';task.finishedAt=now();task.outcome=hasSave?'saved':'no-save';
  if(cp)task.checkpointId=cp.id;
  await writeJson(await safe(p.directory,`Runs/${task.id}.json`),task);
  if(await exists(await safe(p.directory,'Runs/.workbench-writer.lock')))await work.unlock(p,task.id);
  const q=await work.project(id),scene=work.scene(q,sceneId);
  assert(scene.task===task.id,'Task ownership changed during return.',409);
  scene.task=null;
  if(!hasSave)scene.lastEdit={taskId:task.id,outcome:'no-save',at:now()};
  await work.store.save(q,q.revision);
  return {changed:true,outcome:task.outcome,message:hasSave?'Saved Blender changes are back in Director. The activity is not approved.':'Blender closed without saving. Your previous scene is unchanged.'};
}
