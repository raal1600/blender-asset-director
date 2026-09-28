import test from 'node:test';
import assert from 'node:assert/strict';
import {previewUsers} from '../lib/preview-processes.mjs';
const directories=[{previewId:'test',directory:'C:/generated-preview'}];
test('native query is scoped, bounded and returns only matching identities',async()=>{
 let seen;
 const rows=[{ProcessId:10,CommandLine:'blender C:/generated-preview/PREVIEW_COPY.blend'},{ProcessId:20,CommandLine:'blender C:/unrelated/scene.blend secret-value'}];
 const actual=await previewUsers(directories,{platform:'win32',run:async(...args)=>{seen=args;return {stdout:JSON.stringify(rows)};}});
 assert.deepEqual(actual,[{previewId:'test',processId:10}]);assert(!JSON.stringify(actual).includes('secret-value'));
 assert.match(seen[1].at(-1),/-Filter/);assert.match(seen[1].at(-1),/-ErrorAction Stop/);assert.equal(seen[2].timeout,30000);assert.equal(seen[2].windowsHide,true);
});
test('unknown, timed-out and malformed native state refuses with no raw query output',async()=>{
 for(const [failure,reason] of [[Object.assign(Error('private arguments'),{killed:true}),'QUERY_TIMEOUT'],[Error('private arguments'),'QUERY_FAILED']]){
  await assert.rejects(previewUsers(directories,{platform:'win32',run:async()=>{throw failure;}}),e=>e.status===409&&e.code==='NATIVE_PREVIEW_STATE_UNKNOWN'&&e.message.includes(reason)&&!e.message.includes('private arguments'));
 }
 for(const output of ['not json', 'null',JSON.stringify([{ProcessId:10,CommandLine:null}]),JSON.stringify([{ProcessId:0,CommandLine:'private arguments'}])]){
  await assert.rejects(previewUsers(directories,{platform:'win32',run:async()=>({stdout:output})}),e=>e.status===409&&!e.message.includes('private arguments'));
 }
 for(const stdout of ['','   ','[]'])assert.deepEqual(await previewUsers(directories,{platform:'win32',run:async()=>({stdout})}),[]);
});
test('POSIX absent Blender is distinct from an unreadable process query',async()=>{
 assert.deepEqual(await previewUsers(directories,{platform:'linux',run:async()=>{throw Object.assign(Error('none'),{code:1,stdout:''});}}),[]);
 await assert.rejects(previewUsers(directories,{platform:'linux',run:async()=>{throw Object.assign(Error('failed'),{code:2});}}),e=>e.status===409);
 assert.deepEqual(await previewUsers(directories,{platform:'linux',run:async()=>({stdout:'10 blender C:/generated-preview/PREVIEW_COPY.blend'})}),[{previewId:'test',processId:10}]);
});
