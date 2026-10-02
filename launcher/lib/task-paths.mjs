/** New paths only. Existing records remain valid; never rename a user's files. */
import path from 'node:path';
import {assert} from './storage.mjs';
import {validId} from './workbench-model.mjs';
const legacy=(scene,id)=>({workingScene:`Scenes/${scene}--edit-${id}.blend`,checkpointScene:`Scenes/${scene}--saved-${id}.blend`});
const compact=id=>({workingScene:`Scenes/${id}.blend`,checkpointScene:`Scenes/${id}-saved.blend`});
export function taskScenePaths(directory,sceneId,taskId,platform=process.platform){
 assert(validId(sceneId,'sc_')&&validId(taskId,'task_'),'Invalid task path identity.');
 const shortEnough=value=>[...Object.values(value),`Docs/Workbench/${taskId}-explicit-save.json`,`Docs/Workbench/${taskId}-save-session.json`,`Docs/Workbench/${taskId}-return.json`].every(relative=>path.resolve(directory,relative).length<=250);
 let value=legacy(sceneId,taskId);
 if(platform==='win32'&&!shortEnough(value))value=compact(taskId);
 assert(platform!=='win32'||shortEnough(value),'This project path is too long for Blender on Windows. Use a shorter studio/project location; nothing was opened or moved.',409);
 return value;
}
export function validTaskScenePaths(task){
 if(!validId(task.sceneId,'sc_')||!validId(task.id,'task_'))return false;
 return [legacy(task.sceneId,task.id),compact(task.id)].some(value=>Object.entries(value).every(([key,path])=>task[key]===path));
}
