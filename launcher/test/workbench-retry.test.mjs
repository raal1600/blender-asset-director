/** Contract-level synthetic transport; real interruption is world_recovery_check.mjs. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {fileHash} from '../lib/storage.mjs';

async function fixture(t,operation,state='FAILED'){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-retry-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const store=new Store(root);await store.init();let project=await store.create('Synthetic explicit retry');
 await fs.mkdir(path.join(root,'Database/AssetDirector'),{recursive:true});
 const job={id:'j_'+randomUUID().replaceAll('-','').slice(0,24),state,specification:{operation,inputs:[]},outputs:[]},calls=[];
 project=await store.bindJob(project.id,job);
 const runtime={job:async id=>{assert.equal(id,job.id);return job;},harness:async args=>{calls.push(args);assert.deepEqual(args,['job-retry',job.id]);job.state='PLANNED';return job;}};
 const work=new Workbench(store,runtime,{library:path.join(root,'Database/AssetDirector')});
 return {store,project,job,calls,work};
}

test('explicit reset supports bounded layer jobs without executing or changing the project',async t=>{
 for(const operation of ['world-transform','world-prepare-audit','world-prepare','action-audit','action-edit','scene-layer-audit','scene-layer-edit','render-readiness','preview','render-frames']){
  const f=await fixture(t,operation),before=await fileHash(path.join(f.project.directory,'project.json'));
  const result=await f.work.retry(f.project.id,f.project.revision,f.job.id,true);
  assert.equal(result.state,'PLANNED');assert.deepEqual(f.calls,[['job-retry',f.job.id]]);
  assert.deepEqual(await fileHash(path.join(f.project.directory,'project.json')),before);
 }
});

test('reset refuses active/successful jobs, unrelated operations, missing confirmation and wrong ownership',async t=>{
 for(const [operation,state] of [['world-transform','RUNNING'],['world-transform','SUCCEEDED'],['import','FAILED'],['retarget','INTERRUPTED']]){
  const f=await fixture(t,operation,state);await assert.rejects(f.work.retry(f.project.id,f.project.revision,f.job.id,true),/Only failed/);assert.deepEqual(f.calls,[]);
 }
 const f=await fixture(t,'world-transform');
 await assert.rejects(f.work.retry(f.project.id,f.project.revision,f.job.id,false),/Confirm/);
 await assert.rejects(f.work.retry(f.project.id,f.project.revision,'j_'+'0'.repeat(24),true),/Confirm/);
 await assert.rejects(f.work.retry(f.project.id,f.project.revision-1,f.job.id,true),/changed/);
 await f.work.lock(f.project,'run_'+randomUUID());
 await assert.rejects(f.work.retry(f.project.id,f.project.revision,f.job.id,true),/unfinished/);assert.deepEqual(f.calls,[]);
});
