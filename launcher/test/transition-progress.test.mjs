import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {nativeTransitionProgress} from '../lib/transition-review.mjs';
import {progressLabel,progressKey,transitionPhase} from '../public/workbench-progress.mjs';

test('native phase belongs to the running transition job and is presentation only',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'transition-progress-'));
 try{
  const run={state:'RUNNING',publication:'TRANSITION_REVIEW_ONLY',jobId:'j_'+'a'.repeat(24),phase:'blender-worker'};
  const folder=path.join(root,'jobs',run.jobId),file=path.join(folder,'motion-progress.json');await fs.mkdir(folder,{recursive:true});
  assert.equal(await nativeTransitionProgress(root,run),null);
  const value={schema:'motion-job-progress-v1',native_job_id:run.jobId,stage:'fresh_reopen_quality_validation',observed_at:1};
  const put=v=>fs.writeFile(file,JSON.stringify(v));await put(value);
  const before=structuredClone(run),progress=await nativeTransitionProgress(root,run);assert.deepEqual(run,before);
  const display={...run,nativeProgress:progress};assert.equal(transitionPhase(display),'Validating');assert.match(progressLabel(display),/Validating the reopened/);
  assert.notEqual(progressKey([run]),progressKey([display]));
  assert.equal(await nativeTransitionProgress(root,{...run,state:'SUCCEEDED'}),null);
  assert.equal(await nativeTransitionProgress(root,{...run,publication:'NORMAL'}),null);
  for(const patch of [{native_job_id:'j_'+'b'.repeat(24)},{schema:'unknown'},{stage:'<invented>'},{observed_at:null}]){
   await put({...value,...patch});assert.equal(await nativeTransitionProgress(root,run),null);
  }
  await fs.writeFile(file,' '.repeat(9000));assert.equal(await nativeTransitionProgress(root,run),null);
  await fs.writeFile(file,'{');assert.equal(await nativeTransitionProgress(root,run),null);
  assert.equal(await nativeTransitionProgress(root,{...run,jobId:'../outside'}),null);
 }finally{await fs.rm(root,{recursive:true,force:true});}
});

test('raw provider validation never claims final quality validation',()=>{
 const run={state:'RUNNING',phase:'blender-worker',nativeProgress:{stage:'validated_candidate'}};
 assert.equal(transitionPhase(run),'Generating');assert.match(progressLabel(run),/retargeting remains/);
 assert.equal(transitionPhase({...run,nativeProgress:{stage:'queued'}}),'Queued');
 assert.equal(transitionPhase({...run,phase:'verify-result'}),'Validating');
 assert.equal(transitionPhase({...run,nativeProgress:{stage:'unknown'}}),'Generating');
});
