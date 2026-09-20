// Deterministic Windows-sharing fault injection; not native filesystem evidence.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {atomicRename} from '../lib/atomic-rename.mjs';
import {writeJson,json} from '../lib/storage.mjs';
const failure=code=>Object.assign(new Error(code),{code});
async function setup(t){const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-replace-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));const old=path.join(root,'project.json'),tmp=old+'.new.tmp';await fs.writeFile(old,'old');await fs.writeFile(tmp,'new');return {root,old,tmp};}
test('transient Windows reader locks retry atomic rename without exposing a missing destination',async t=>{
 const {old,tmp}=await setup(t);const delays=[];let attempts=0;
 await atomicRename(tmp,old,{platform:'win32',wait:async ms=>{delays.push(ms);assert.equal(await fs.readFile(old,'utf8'),'old');},rename:async(a,b)=>{assert.equal(a,tmp);assert.equal(b,old);if(attempts++<3)throw failure(['EPERM','EACCES','EBUSY'][attempts-1]);await fs.rename(a,b);}});
 assert.equal(attempts,4);assert.deepEqual(delays,[10,20,40]);assert.equal(await fs.readFile(old,'utf8'),'new');
});
test('persistent Windows conflict is bounded and preserves both old file and staged bytes',async t=>{
 const {old,tmp}=await setup(t);const delays=[];let attempts=0;const error=failure('EPERM');
 await assert.rejects(atomicRename(tmp,old,{platform:'win32',wait:async ms=>delays.push(ms),rename:async()=>{attempts++;throw error;}}),e=>e===error);
 assert.equal(attempts,9);assert.equal(delays.reduce((a,b)=>a+b,0),2270);assert.equal(await fs.readFile(old,'utf8'),'old');assert.equal(await fs.readFile(tmp,'utf8'),'new');
});
test('non-Windows and permanent storage errors are never retried or swallowed',async()=>{
 for(const [platform,code] of [['linux','EPERM'],['win32','ENOSPC'],['win32','EIO'],['win32','ENOENT']]){let calls=0;
  await assert.rejects(atomicRename('a','b',{platform,wait:async()=>assert.fail('Unexpected delay'),rename:async()=>{calls++;throw failure(code);}}),e=>e.code===code);assert.equal(calls,1);
 }
});
test('writeJson publishes valid content and cannot replace a directory as a fallback',async t=>{
 const {root,old}=await setup(t);await writeJson(old,{revision:2});assert.deepEqual(await json(old),{revision:2});
 const occupied=path.join(root,'occupied.json');await fs.mkdir(occupied);await fs.writeFile(path.join(occupied,'keep'),'sentinel');
 await assert.rejects(writeJson(occupied,{revision:3}),/uncommitted JSON snapshot retained/);
 assert.equal(await fs.readFile(path.join(occupied,'keep'),'utf8'),'sentinel');
 const snapshots=(await fs.readdir(root)).filter(n=>n.startsWith('occupied.json.')&&n.endsWith('.tmp'));
 assert.equal(snapshots.length,1);assert.deepEqual(await json(path.join(root,snapshots[0])),{revision:3});
});

test('Windows: a real .NET read handle blocks replacement, then the same atomic write recovers',
 {skip:process.platform!=='win32',timeout:15000},async t=>{
  const {spawn}=await import('node:child_process');
  const {old,tmp,root}=await setup(t);const release=path.join(root,'release.lock');
  const script="$ErrorActionPreference='Stop'; $stream=[IO.File]::Open($env:AD_LOCK_TARGET,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read); try { [Console]::Out.WriteLine('LOCKED'); [Console]::Out.Flush(); $clock=[Diagnostics.Stopwatch]::StartNew(); while(-not [IO.File]::Exists($env:AD_LOCK_RELEASE)) { if($clock.ElapsedMilliseconds -gt 10000) {throw 'test lock deadline'}; Start-Sleep -Milliseconds 10 } } finally {$stream.Dispose()}";
  const child=spawn('powershell.exe',['-NoProfile','-NonInteractive','-Command',script],{
   env:{...process.env,AD_LOCK_TARGET:old,AD_LOCK_RELEASE:release},stdio:['ignore','pipe','pipe'],windowsHide:true,shell:false});
  t.after(()=>{if(child.exitCode===null)child.kill();});
  let output='',errors='';child.stderr.on('data',data=>{errors+=data.toString();});
  const done=new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',code=>resolve(code));});
  await new Promise((resolve,reject)=>{
   child.once('error',reject);child.once('exit',code=>{if(!output.includes('LOCKED'))reject(Error('Lock process exited '+code+': '+errors));});
   child.stdout.on('data',data=>{output+=data.toString();if(output.includes('LOCKED'))resolve();});
  });
  let attempts=0,observed=null;
  await atomicRename(tmp,old,{rename:async(a,b)=>{
   attempts++;try{return await fs.rename(a,b);}catch(error){
    observed=error.code;assert.equal(await fs.readFile(old,'utf8'),'old');
    // Release a genuine OS sharing lock only after observing a genuine refusal.
    await fs.writeFile(release,'release');throw error;
   }
  }});
  assert.ok(['EPERM','EACCES','EBUSY'].includes(observed));assert.ok(attempts>=2);
  assert.equal(await done,0,errors);assert.equal(await fs.readFile(old,'utf8'),'new');
 });
