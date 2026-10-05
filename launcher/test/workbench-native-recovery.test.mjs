// Contract transport only; real executor death/restart is verified in installed acceptance.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {exists,json,writeJson} from '../lib/storage.mjs';
async function fixture(t){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-native-recovery-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const store=new Store(root);await store.init();let p=await store.create('Synthetic recovery contract');
 const library=path.join(root,'Database/AssetDirector');await fs.mkdir(library,{recursive:true});
 const calls=[],runtime={harness:async args=>{calls.push(args);const job=await json(native);job.state='INTERRUPTED';await writeJson(native,job);return job;}};
 const work=new Workbench(store,runtime,{library});const created=await work.create(p.id,p.revision,'Test scene');p=created.project;
 const run={id:'run_'+randomUUID(),projectId:p.id,sceneId:created.sceneId,action:'action-edit',state:'RUNNING',jobId:'j_'+'a'.repeat(24)};
 const native=path.join(library,'jobs',run.jobId,'job.json');await writeJson(native,{id:run.jobId,state:'RUNNING',outputs:[]});
 await work.lock(p,run.id);await writeJson(path.join(p.directory,'Runs',run.id+'.json'),run);
 p.workbench.scenes[0].run=run.id;p=await store.save(p,p.revision);
 return {root,store,work,runtime,calls,p,run,native};
}
test('confirmed stopped native execution recovers before releasing the project writer',async t=>{
 const f=await fixture(t);const after=await f.work.resolve(f.p.id,f.run.sceneId,f.p.revision,f.run.id,true);
 assert.deepEqual(f.calls,[['job-recover',f.run.jobId,'--confirm-stopped']]);assert.equal(after.workbench.scenes[0].run,null);
 assert.equal((await json(path.join(f.p.directory,'Runs',f.run.id+'.json'))).state,'INTERRUPTED');
 assert.equal(await exists(path.join(f.p.directory,'Runs/.workbench-writer.lock')),false);
 assert.deepEqual(after.workbench.scenes[0].checkpoints,[]);
});
test('live or unverifiable native execution preserves running receipt and writer',async t=>{
 const f=await fixture(t);f.runtime.harness=async()=>{throw Error('Native worker is still running');};
 await assert.rejects(f.work.resolve(f.p.id,f.run.sceneId,f.p.revision,f.run.id,true),/still running/);
 assert.equal((await json(path.join(f.p.directory,'Runs',f.run.id+'.json'))).state,'RUNNING');
 assert.equal((await f.store.get(f.p.id)).workbench.scenes[0].run,f.run.id);
 assert.equal(await exists(path.join(f.p.directory,'Runs/.workbench-writer.lock')),true);
 await assert.rejects(f.work.resolve(f.p.id,f.run.sceneId,f.p.revision,f.run.id,false),/Confirm/);
});

test('malformed or falsely successful native recovery cannot release a project writer',async t=>{
 for(const response of [{state:'INTERRUPTED',outputs:[]},{id:'j_'+'a'.repeat(24),state:'SUCCEEDED',outputs:[]},{id:'j_'+'a'.repeat(24),state:'INTERRUPTED',outputs:[{path:'partial.blend'}]}]){
  const f=await fixture(t);f.runtime.harness=async()=>response;
  await assert.rejects(f.work.resolve(f.p.id,f.run.sceneId,f.p.revision,f.run.id,true),/not verified/);
  assert.equal(await exists(path.join(f.p.directory,'Runs/.workbench-writer.lock')),true);
 }
});
