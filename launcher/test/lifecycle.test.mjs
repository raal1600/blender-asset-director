import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createApp} from '../server.mjs';

async function fixture(t,runtime={health:null}) {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-lifecycle-'));
  const library=path.join(root,'Database/AssetDirector');await fs.mkdir(library,{recursive:true});
  const app=await createApp({root,config:{library},port:0,runtime});
  t.after(async()=>{if(app.server.listening)await new Promise(r=>app.server.close(r));await fs.rm(root,{recursive:true,force:true});});
  const headers={Authorization:`Bearer ${app.token}`,'Content-Type':'application/json'};
  return {...app,root,library,call:(url,post=false)=>fetch(app.origin+url,{headers,method:post?'POST':'GET',...(post?{body:'{}'}:{})})};
}
test('closing refuses active and queued operations without waiting for them',async t=>{
  let release,started;const began=new Promise(r=>started=r);
  const app=await fixture(t,{doctor:async()=>{started();await new Promise(r=>release=r);return {};}});
  const work=app.call('/api/health',true);await began;
  assert.equal((await (await app.call('/api/lifecycle')).json()).busy,true);
  assert.equal((await app.call('/api/stop',true)).status,409);
  assert.equal(app.server.listening,true);release();await work;
  assert.equal((await (await app.call('/api/lifecycle')).json()).busy,false);
  assert.equal((await app.call('/api/stop',true)).status,200);
  await new Promise(r=>app.server.once('close',r));assert.equal(app.server.listening,false);
});
test('close checks all historical unfinished receipts, external job locks and harness records',async t=>{
  const app=await fixture(t);const p=await app.store.create('Desktop test');
  for(let i=0;i<35;i++)await fs.writeFile(path.join(p.directory,`Runs/z-${i}.json`),JSON.stringify({projectId:p.id,state:'COMPLETE'}));
  const receipt=path.join(p.directory,'Runs/a-old.json');await fs.writeFile(receipt,JSON.stringify({projectId:p.id,state:'RUNNING'}));
  assert.equal((await app.call('/api/stop',true)).status,409);await fs.unlink(receipt);
  const lock=path.join(p.directory,'Runs/.interactive-execution.lock');await fs.mkdir(lock);
  assert.equal((await app.call('/api/stop',true)).status,409);await fs.rmdir(lock);
  const id='j_'+'a'.repeat(24);await app.store.bindJob(p.id,{id,specification:{operation:'inspect',inputs:[]}});
  const folder=path.join(app.library,'jobs',id);await fs.mkdir(folder,{recursive:true});
  await fs.writeFile(path.join(folder,'job.json'),JSON.stringify({state:'RUNNING'}));
  assert.equal((await app.call('/api/stop',true)).status,409);
  await fs.writeFile(path.join(folder,'job.json'),JSON.stringify({state:'COMPLETE'}));
  assert.equal((await (await app.call('/api/lifecycle')).json()).busy,false);
});
test('unreadable work state fails closed and shutdown retains authentication',async t=>{
  const app=await fixture(t);const p=await app.store.create('Broken receipt');
  await fs.writeFile(path.join(p.directory,'Runs/broken.json'),'not json');
  assert.equal((await app.call('/api/stop',true)).status,500);assert.equal(app.server.listening,true);
  assert.equal((await fetch(app.origin+'/api/lifecycle')).status,401);
});
