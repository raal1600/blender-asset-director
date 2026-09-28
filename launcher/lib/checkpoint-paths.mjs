/** New checkpoints only; retain full identities and never rename saved history. */
import path from 'node:path';
import {assert} from './storage.mjs';
import {validId} from './workbench-model.mjs';

export function checkpointScenePath(directory,sceneId,checkpointId,platform=process.platform){
 assert(validId(sceneId,'sc_')&&validId(checkpointId,'cp_'),'Invalid checkpoint path identity.');
 const fits=relative=>path.resolve(directory,relative).length<=250;
 let relative=`Scenes/${sceneId}--${checkpointId}.blend`;
 if(platform==='win32'&&!fits(relative))relative=`Scenes/${checkpointId}.blend`;
 assert(platform!=='win32'||fits(relative),'This project path is too long for Blender on Windows. Use a shorter studio/project location; no Save job was started.',409);
 return relative;
}
