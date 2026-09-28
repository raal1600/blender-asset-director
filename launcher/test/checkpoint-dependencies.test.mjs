import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {checkpointFiles} from '../lib/checkpoint-dependencies.mjs';
const hash='a'.repeat(64),root=path.resolve('synthetic-dependencies');
const record=(name,size=12)=>({filename:path.join(root,name),sha256:hash,size});
const records=[record('scene.blend'),record('texture.png'),record('unrelated.blend',600*1024**2)];
const inventory=paths=>({version:'preview-dependencies-v1',mode:'EXACT_ABSOLUTE_FILES',source_sha256:hash,paths});
const cp=observation=>({sha256:hash,audit:{preview_dependencies:observation}});
test('byte-bound complete absolute inventory copies only checkpoint and observed pinned files',()=>{
 assert.deepEqual(checkpointFiles(cp(inventory([records[1].filename])),records),records.slice(0,2));
 assert.deepEqual(checkpointFiles(cp(inventory([])),records),records.slice(0,1));
 assert.deepEqual(checkpointFiles(cp(inventory([records[1].filename,records[1].filename])),records),records.slice(0,2));
});
test('legacy, unknown, complex and wrong-byte audits retain conservative copying',()=>{
 for(const observation of [undefined,{version:'future'}, {version:'preview-dependencies-v1',mode:'ALL_PINNED'},
   {...inventory([]),source_sha256:'b'.repeat(64)}])assert.deepEqual(checkpointFiles(cp(observation),records),records);
});
test('observation is never authorization to adopt an unpinned external file',()=>{
 assert.throws(()=>checkpointFiles(cp(inventory([path.join(root,'unrecorded.png')])),records),/unrecorded dependency/);
 for(const value of ['../other.png',null,3,'',path.join(root,'bad\npath')])assert.throws(()=>checkpointFiles(cp(inventory([value])),records),/Invalid observed/);
 for(const observation of [{...inventory([]),paths:null},{...inventory([]),mode:'invented'},{...inventory([]),source_sha256:'x'}])assert.throws(()=>checkpointFiles(cp(observation),records),/Invalid checkpoint/);
});
test('conflicting overlapping package identities refuse before any dependency is omitted',()=>{
 assert.throws(()=>checkpointFiles(cp(inventory([])),[...records,{...records[1],sha256:'b'.repeat(64)}]),/identities conflict/);
 assert.deepEqual(checkpointFiles(cp(inventory([])),[...records,records[1]]),records.slice(0,1));
});
