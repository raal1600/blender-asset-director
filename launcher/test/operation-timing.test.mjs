import test from 'node:test';
import assert from 'node:assert/strict';
import {operationTiming} from '../lib/operation-timing.mjs';
import {progressLabel,progressKey,statusPoller} from '../public/workbench-progress.mjs';

test('timings measure actual completed and failed boundaries without changing errors',async()=>{
 const record={};let clock=100;
 const timed=operationTiming(record,()=>clock);
 assert.equal(await timed('verify-result',async()=>{clock+=12;return 'result';}),'result');
 const failure=Error('failure');
 await assert.rejects(timed('save-checkpoint',async()=>{clock+=3;throw failure;}),e=>e===failure);
 assert.deepEqual(record.timings,[{phase:'verify-result',milliseconds:12,outcome:'SUCCEEDED'},{phase:'save-checkpoint',milliseconds:3,outcome:'FAILED'}]);
 assert.match(progressLabel(record),/Saving and verifying/);
 assert.notEqual(progressKey([{id:'same',phase:'verify-result'}]),progressKey([{id:'same',phase:'save-checkpoint'}]));
 assert.equal(progressLabel({phase:'untrusted arbitrary text'}),'Working from the frozen checkpoint');
});

test('active import polling is faster but cannot overlap requests',async()=>{
 const poll=statusPoller();let calls=0,release;
 const first=poll(true,0,()=>{calls++;return new Promise(r=>release=r);});
 await poll(true,1000,async()=>calls++);assert.equal(calls,1);
 release();await first;
 await poll(true,499,async()=>calls++);assert.equal(calls,1);
 await poll(true,500,async()=>calls++);assert.equal(calls,2);
 await poll(false,2000,async()=>calls++);assert.equal(calls,2);
 await poll(false,3000,async()=>calls++);assert.equal(calls,3);
 await assert.rejects(poll(true,3500,async()=>{throw Error('offline');}),/offline/);
 await poll(true,4000,async()=>calls++);assert.equal(calls,4);
});
