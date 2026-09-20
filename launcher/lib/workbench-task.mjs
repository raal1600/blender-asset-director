/** Exact process focus, never arbitrary process-name activation. */
import {assert,json,safe} from './storage.mjs';
import {validId} from './workbench-model.mjs';
import {taskObservation} from '../public/workbench-task.mjs';
export async function focusTask(work,id,sceneId,revision) {
  const p=await work.project(id,revision),scene=work.scene(p,sceneId);
  assert(validId(scene.task,'task_'),'No dedicated task is active.',409);
  const task=await json(await safe(p.directory,`Runs/${scene.task}.json`));
  const status=await json(await safe(p.directory,`Docs/Workbench/${scene.task}-status.json`));
  assert(task.id===scene.task&&task.projectId===id&&task.sceneId===sceneId&&status.projectId===id&&
    status.sceneId===sceneId&&status.processId===task.processId&&Number.isSafeInteger(task.processId)&&task.processId>0,
    'Blender task process identity was not established.',409);
  assert(taskObservation(status,task.id).focus,'Blender task is stale, saved, or no longer on the expected file.',409);
  return work.runtime.showBlender(task.processId);
}
