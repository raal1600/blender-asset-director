/** Scene-bound performer handoff. Browser names never establish native ownership. */
import {assert,json,safe} from './storage.mjs';
import {validHash,validId} from './workbench-model.mjs';

export async function resolveActionContext(work,p,scene,request){
  assert(request&&typeof request==='object'&&!Array.isArray(request)&&Object.keys(request).length===7&&
    Object.keys(request).every(k=>['version','checkpointId','sha256','inspectionId','audit_sha256','performer','frame'].includes(k)), 'Invalid performer context.');
  assert(scene.stage==='action'&&!scene.candidate&&request.version==='action-layer-v1'&&validId(request.checkpointId,'cp_')&&
    validHash(request.sha256)&&validId(request.inspectionId,'run_')&&validHash(request.audit_sha256)&&
    typeof request.performer==='string'&&request.performer.length>0&&request.performer.length<=255&&Number.isInteger(request.frame), 'Invalid performer identity.');
  const cp=await work.verify(p,scene);
  assert(cp.id===request.checkpointId&&cp.sha256===request.sha256,'Performer context is stale. Refresh the saved scene.',409);
  const run=await json(await safe(p.directory,`Runs/${request.inspectionId}.json`));
  assert(run.projectId===p.id&&run.sceneId===scene.id&&run.action==='action-audit'&&run.state==='SUCCEEDED'&&
    run.checkpointId===cp.id&&run.checkpointSha256===cp.sha256&&run.inspection?.version===request.version&&
    run.inspection.sha256===request.audit_sha256,'Performer inspection is stale or belongs to another scene.',409);
  const performer=run.inspection.performers.find(v=>v.name===request.performer);
  assert(performer,'Select an observed performer.',409);
  assert(request.frame>=run.inspection.frame_range[0]&&request.frame<=run.inspection.frame_range[1],'Choose a frame in the inspected scene.',409);
  return {request:{...request},performer:structuredClone(performer),fps:run.inspection.fps,frameRange:[...run.inspection.frame_range]};
}
