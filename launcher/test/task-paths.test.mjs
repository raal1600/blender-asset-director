import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {taskScenePaths,validTaskScenePaths} from '../lib/task-paths.mjs';
const sceneId='sc_00000000-0000-4000-8000-000000000001',id='task_00000000-0000-4000-8000-000000000002';
test('short paths retain the installed filename contract; deep Windows paths use compact full task IDs',()=>{
 const short=taskScenePaths(path.resolve('studio'),sceneId,id,'win32');assert(short.workingScene.includes(sceneId));assert(validTaskScenePaths({id,sceneId,...short}));
 const deep=path.parse(process.cwd()).root+'p'.repeat(170),value=taskScenePaths(deep,sceneId,id,'win32');assert.equal(value.workingScene,'Scenes/'+id+'.blend');assert(validTaskScenePaths({id,sceneId,...value}));
 assert.equal(taskScenePaths(deep,sceneId,id,'linux').workingScene,short.workingScene);
});
test('too-deep destinations refuse; arbitrary, mixed or foreign filenames cannot reconcile saves',()=>{
 assert.throws(()=>taskScenePaths(path.parse(process.cwd()).root+'p'.repeat(245),sceneId,id,'win32'),/too long/);
 const value=taskScenePaths(path.resolve('studio'),sceneId,id,'linux');
 assert(!validTaskScenePaths({id,sceneId,...value,workingScene:'Scenes/other.blend'}));
 assert(!validTaskScenePaths({id,sceneId,...value,checkpointScene:'Scenes/'+id+'-saved.blend'}));
 assert(!validTaskScenePaths({id:id.replace(/2$/,'3'),sceneId,...value}));
});
