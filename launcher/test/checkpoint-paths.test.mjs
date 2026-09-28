import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {checkpointScenePath} from '../lib/checkpoint-paths.mjs';
const scene='sc_00000000-0000-4000-8000-000000000001',cp='cp_00000000-0000-4000-8000-000000000002';
test('new native checkpoints retain short paths and compact deep Windows paths without truncating identity',()=>{
 const root=path.parse(process.cwd()).root,short=checkpointScenePath(root+'studio',scene,cp,'win32');
 assert.equal(short,`Scenes/${scene}--${cp}.blend`);
 const deep=root+'p'.repeat(178),relative=checkpointScenePath(deep,scene,cp,'win32');
 assert(path.resolve(deep,short).length>260);assert(path.resolve(deep,relative).length<=250);
 assert.equal(relative,`Scenes/${cp}.blend`);
 assert.equal(checkpointScenePath(deep,scene,cp,'linux'),short);
 assert.notEqual(checkpointScenePath(deep,scene,cp.replace(/2$/,'3'),'win32'),relative);
});
test('unusable Windows checkpoint destinations and malformed identities refuse explicitly',()=>{
 assert.throws(()=>checkpointScenePath(path.parse(process.cwd()).root+'p'.repeat(240),scene,cp,'win32'),e=>e.status===409&&/no Save job was started/.test(e.message));
 assert.throws(()=>checkpointScenePath('studio','../scene',cp,'win32'),/identity/);
 assert.throws(()=>checkpointScenePath('studio',scene,'cp_../../other','win32'),/identity/);
});
