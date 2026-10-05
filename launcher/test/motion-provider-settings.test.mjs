import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {Runtime} from '../lib/runtime.mjs';

async function fixture(t){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'director provider settings - '));
 t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const skill=path.join(root,'skill');await fs.mkdir(path.join(skill,'scripts'),{recursive:true});
 // Isolated handoff contract only; this does not represent model execution.
 await fs.writeFile(path.join(skill,'scripts/director.py'),"process.stdout.write(JSON.stringify({provider:process.env.ASSET_DIRECTOR_MOTION_BRICKS_CONFIG??null}));");
 return {root,store:{root},config:{skill,python:process.execPath,library:path.join(root,'Database')}};
}

test('saved studio provider path reaches independently launched runtimes without changing host environment',async t=>{
 const f=await fixture(t),before=process.env.ASSET_DIRECTOR_MOTION_BRICKS_CONFIG;
 const provider=path.join(f.root,'SystemRuntime/UserData/MotionBricks/provider.json');
 await fs.mkdir(path.dirname(provider),{recursive:true});await fs.writeFile(provider,'{}');
 for(let i=0;i<2;i++)assert.equal((await new Runtime(f.store,f.config).harness(['contract-only'])).provider,provider);
 assert.equal(process.env.ASSET_DIRECTOR_MOTION_BRICKS_CONFIG,before);
});

test('explicit studio provider configuration overrides the conventional path and relative paths are refused',async t=>{
 const f=await fixture(t),provider=path.join(f.root,'separate provider.json');
 assert.equal((await new Runtime(f.store,{...f.config,motionBricksConfig:provider}).harness([])).provider,provider);
 await assert.rejects(new Runtime(f.store,{...f.config,motionBricksConfig:'relative.json'}).harness([]),/absolute local file/);
});
