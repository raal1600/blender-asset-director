/** Explicit exit assistance. Inspection never releases a writer lease. */
import {assert,exists,json,safe} from './storage.mjs';
import {validId} from './workbench-model.mjs';

export async function taskForExit(work,projectId,runId) {
  assert(validId(runId,'task_'),'Expected a dedicated Blender task.',400);
  const project=await work.project(projectId);
  const run=await json(await safe(project.directory,`Runs/${runId}.json`));
  const scene=work.scene(project,run.sceneId);
  assert(run.id===runId&&run.projectId===projectId&&run.action==='workbench-edit'&&scene.task===runId&&
    ['RUNNING','PREPARING','FAILED'].includes(run.state),'Task is no longer the active scene writer. Refresh before continuing.',409);
  const statusFile=await safe(project.directory,`Docs/Workbench/${runId}-status.json`);
  const status=await exists(statusFile)?await json(statusFile):null;
  assert(!status||(status.taskId===runId&&status.projectId===projectId&&status.sceneId===scene.id),
    'Task status identity changed.',409);
  const process=work.runtime.inspectWorkbenchTask
    ?await work.runtime.inspectWorkbenchTask(project,run).catch(()=>({state:'unknown'})):{state:'unknown'};
  // Never recover over a checkpoint that might be collected, even if its receipt is damaged.
  const saved=await exists(await safe(project.directory,run.returnFile))||await exists(await safe(project.directory,run.checkpointScene));
  const canClose=process.state==='verified'&&process.hasWindow===true;
  const canRecover=process.state==='stopped'&&!saved&&!work.running.has(runId);
  const canCollect=await exists(await safe(project.directory,run.returnFile))&&status?.state!=='FAILED';
  const detail=[
    `${project.name} / ${scene.name}`,
    status?.state==='FAILED'?'Task setup failed: '+String(status.message||'Unknown setup failure').slice(0,1000):'Dedicated Blender editing task.',
    process.state==='stopped'?'Its Blender process has stopped. Waiting will not complete this task.':
      process.state==='verified'?'Its Blender process is still open. Closing it may show Blender’s Save Changes prompt.':
      'The task process could not be safely identified. No process will be closed or task recovered.',
    saved?'Saved checkpoint evidence exists. Collect it for review; recovery will not discard it.':
      'Recovery retains all working files and failure evidence. It does not approve any scene.',
    'You may also exit only Director and leave the backend and other applications running.'
  ].join('\n\n');
  return {projectId,runId,sceneId:scene.id,revision:project.revision,process,canClose,canRecover,canCollect,detail};
}

export async function actOnExitTask(work,body,action) {
  assert(body.confirmed===true,'Explicit confirmation is required.',400);
  const state=await taskForExit(work,body.projectId,body.runId);
  assert(body.revision===state.revision,'Project changed. Inspect the task again.',409);
  if(action==='close') {
    assert(state.canClose&&typeof body.processIdentity==='string'&&body.processIdentity===state.process.identity,
      'Blender process changed or cannot be identified. Nothing was closed.',409);
    const project=await work.project(body.projectId,state.revision);
    const run=await json(await safe(project.directory,`Runs/${body.runId}.json`));
    const result=await work.runtime.closeWorkbenchTask(project,run,body.processIdentity);
    assert(result.requested===true,'Blender did not accept a normal window-close request. Check its window; no force termination was attempted.',409);
    return {message:'Close requested only for this task’s Blender window. Respond to any Save Changes prompt there, then inspect this task again. Nothing was force-terminated.'};
  }
  assert(action==='recover'&&state.canRecover,'Only a confirmed stopped task without a saved checkpoint can be recovered here.',409);
  await work.resolve(state.projectId,state.sceneId,state.revision,state.runId,true);
  return {message:'Stopped task recovered. Working files and failure evidence retained; no scene approval was recorded.'};
}
