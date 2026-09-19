// File preparation and argument boundaries; native execution is tested separately.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {taskArguments} from '../lib/workbench-launch.mjs';
import {fileHash} from '../lib/storage.mjs';
async function fixture(t){
 const created=await fs.mkdtemp(path.join(os.tmpdir(),'ad-preload-'));t.after(()=>fs.rm(created,{recursive:true,force:true}));
 // Production Store.get returns a canonical directory. Windows short-name temp
 // paths (and macOS temp symlinks) must use that same namespace in this fixture.
 const directory=await fs.realpath(created);
 await fs.mkdir(path.join(directory,'Scenes'));await fs.mkdir(path.join(directory,'Runs'));
 const source=path.join(directory,'Scenes/frozen.blend');await fs.writeFile(source,'BLENDER SYNTHETIC INPUT');
 const input={path:'Scenes/frozen.blend',sha256:(await fileHash(source)).sha256};
 return {project:{id:'p',directory},task:{id:'t',projectId:'p',input,workingScene:'Scenes/working.blend'},manifest:path.join(directory,'Runs/t.json'),source};
}
test('task CLI opens a verified copy before the fixed Python entry, not the original',async t=>{
 const f=await fixture(t);const args=await taskArguments(f.project,f.task,f.manifest,'fixed-helper.py');
 assert.deepEqual(args,['--factory-startup','--disable-autoexec',path.join(f.project.directory,'Scenes/working.blend'),'--python','fixed-helper.py','--',f.manifest]);
 assert.equal((await fileHash(f.source)).sha256,f.task.input.sha256);
 assert.equal((await fileHash(args[2])).sha256,f.task.input.sha256);
 await assert.rejects(taskArguments(f.project,f.task,f.manifest,'fixed-helper.py'),/exist/i);
});
test('changed input, original overwrite and escaping references are rejected',async t=>{
 const f=await fixture(t);
 await assert.rejects(taskArguments(f.project,{...f.task,workingScene:f.task.input.path},f.manifest,'fixed'),/original/);
 await assert.rejects(taskArguments(f.project,{...f.task,input:{...f.task.input,path:'../outside.blend'}},f.manifest,'fixed'),/frozen task input/);
 await fs.writeFile(f.source,'CHANGED');await assert.rejects(taskArguments(f.project,f.task,f.manifest,'fixed'),/changed/i);
});
test('a new empty task passes no positional file and preserves the fixed argument boundary',async t=>{
 const f=await fixture(t);const args=await taskArguments(f.project,{...f.task,input:null},f.manifest,'fixed');
 assert.deepEqual(args,['--factory-startup','--disable-autoexec','--python','fixed','--',f.manifest]);
});
