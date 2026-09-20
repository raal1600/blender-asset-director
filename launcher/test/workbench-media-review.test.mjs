/** Synthetic byte/HTTP contracts; actual Blender/browser coverage lives in studio_e2e. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {createApp} from '../server.mjs';
import {fileHash,writeJson,json} from '../lib/storage.mjs';

async function fixture(t) {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-media-review-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
  for(const dir of ['Animations','Characters','Meshes','AssetDirector'])await fs.mkdir(path.join(root,'Database',dir),{recursive:true});
  const store=new Store(root);await store.init();let p=await store.create('Synthetic preview review','Only generated test data.');
  const config={library:path.join(root,'Database/AssetDirector'),blender:process.execPath};let prepared=0,gate=true,release;
  const job={id:'j_'+'c'.repeat(24),state:'PLANNED',outputs:[]};
  const runtime={config,health:null,job:async()=>job,harness:async args=>{
    if(args[0]==='workbench-capabilities')return {render_frames:true,task_workspace:true};
    if(args[0]==='job-prepare'){
      prepared++;const input=args[args.indexOf('--input')+1];job.specification={operation:args[1],inputs:[{path:input,...await fileHash(input)}]};return job;
    }
    if(args[0]==='job-run'){
      await new Promise(r=>release=r);const dir=path.join(config.library,'jobs',job.id);await fs.mkdir(dir,{recursive:true});
      await writeJson(path.join(dir,'result.json'),{job_id:job.id,status:'OK',data:{}});await fs.writeFile(path.join(dir,'preview_0001.png'),'SYNTHETIC IMAGE BYTES');
      for(const name of ['result.json','preview_0001.png'])job.outputs.push({path:`jobs/${job.id}/${name}`,...await fileHash(path.join(dir,name))});
      job.state='SUCCEEDED';return job;
    }
    throw Error('Unexpected synthetic command '+args[0]);
  }};
  const work=new Workbench(store,runtime,config);work.interactions=()=>({sourceStatus:async()=>({ready:gate})});
  p=(await work.create(p.id,p.revision,'Candidate world')).project;const sid=p.workbench.scenes[0].id;
  const original=path.join(p.directory,'Scenes/original.blend');await fs.writeFile(original,'BLENDER-v420 SYNTHETIC ONLY');
  p=await work.importCheckpoint(p.id,sid,p.revision,'Scenes/original.blend');
  const fresh=()=>store.get(p.id),cp=p.workbench.scenes[0].checkpoints[0];
  return {root,store,work,runtime,config,p,sid,cp,job,original,fresh,prepared:()=>prepared,setGate:value=>gate=value,
    finish:async()=>{release();for(let i=0;i<400&&work.running.size;i++)await new Promise(r=>setTimeout(r,5));assert.equal(work.running.size,0);return fresh();}};
}

test('candidate preview requires explicit authorization and rights; delivery remains blocked',async t=>{
  const f=await fixture(t),{p,sid}=f;
  await assert.rejects(f.work.startJob(p.id,sid,p.revision,'preview',{frame:1},false),/authorization/);
  f.setGate(false);await assert.rejects(f.work.startJob(p.id,sid,p.revision,'preview',{frame:1},true),/source use/);f.setGate(true);
  await assert.rejects(f.work.startJob(p.id,sid,p.revision,'render-frames',{},true),/candidate/);
  await assert.rejects(f.work.startJob(p.id,sid,p.revision-1,'preview',{frame:1},true),/Project changed/);
  assert.equal(f.prepared(),0);
});
test('candidate preview binds exact bytes, appears as media, and never keeps or approves',async t=>{
  const f=await fixture(t),{p,sid,cp}=f,original=await fileHash(f.original);
  await f.work.startJob(p.id,sid,p.revision,'preview',{frame:1},true);const q=await f.finish(),s=q.workbench.scenes[0];
  assert.equal(s.candidate,cp.id);assert.equal(s.current,null);assert.deepEqual(s.completed,{});assert.equal(s.renders.length,0);
  assert.equal(s.preview.checkpointId,cp.id);assert.equal(s.preview.jobId,f.job.id);
  assert.equal((await fileHash(path.join(p.directory,cp.path))).sha256,cp.sha256);assert.deepEqual(await fileHash(f.original),original);
  const media=await f.work.media(p.id,{sceneId:sid,kind:'preview'});assert.match(media.path,/preview_0001\.png$/);
  const run=(await f.store.runs(p.id))[0];assert.equal(run.state,'SUCCEEDED');assert.equal(run.checkpointId,cp.id);
  await fs.appendFile(path.join(p.directory,cp.path),'tampered');await assert.rejects(f.work.media(p.id,{sceneId:sid,kind:'preview'}),/checkpoint changed/i);
});
test('changed candidate during execution preserves output but refuses attaching it',async t=>{
  const f=await fixture(t),{p,sid,cp}=f;
  await f.work.startJob(p.id,sid,p.revision,'preview',{frame:1},true);
  await fs.appendFile(path.join(p.directory,cp.path),'external change');const q=await f.finish();
  assert.equal(q.workbench.scenes[0].preview,undefined);assert.equal((await f.store.runs(p.id))[0].state,'FAILED');
  assert.equal((await fs.stat(path.join(f.config.library,'jobs',f.job.id,'preview_0001.png'))).isFile(),true);
});
test('discarded candidate and changed shot cannot expose stale preview as current media',async t=>{
  const f=await fixture(t),{p,sid}=f;
  await f.work.startJob(p.id,sid,p.revision,'preview',{frame:1},true);let q=await f.finish();
  q.workbench.scenes[0].preview.shotId='foreign-shot';q=await f.store.save(q,q.revision);
  await assert.rejects(f.work.media(p.id,{sceneId:sid,kind:'preview'}),/another checkpoint or shot/);
  await f.work.discard(p.id,sid,q.revision);await assert.rejects(f.work.media(p.id,{sceneId:sid,kind:'preview'}),/checkpoint first/);
});
test('optional source image absence is HTTP 204, but auth, unknown source and tamper still fail',async t=>{
  const f=await fixture(t);
  await fs.writeFile(path.join(f.root,'Database/Meshes/synthetic.obj'),'synthetic no-image model');
  await fs.mkdir(path.join(f.root,'Database/Characters/with-image'));
  await fs.writeFile(path.join(f.root,'Database/Characters/with-image/model.obj'),'synthetic model');
  const image=path.join(f.root,'Database/Characters/with-image/thumbnail.png');await fs.writeFile(image,'synthetic image');
  const inventory=await f.store.scan(),missing=inventory.sources.find(s=>s.relative.endsWith('.obj')),present=inventory.sources.find(s=>s.relative.endsWith('with-image'));
  const app=await createApp({root:f.root,config:f.config,runtime:f.runtime,port:0});t.after(()=>new Promise(r=>app.server.close(r)));
  const url=id=>app.origin+'/api/workbench/source-image?'+new URLSearchParams({projectId:f.p.id,sourceId:id});
  const headers={Authorization:'Bearer '+app.token};
  assert.equal((await fetch(url(missing.id))).status,401);
  const absent=await fetch(url(missing.id),{headers});assert.equal(absent.status,204);assert.equal(await absent.text(),'');
  assert.equal((await fetch(url('unknown'),{headers})).status,404);
  assert.equal((await fetch(url(present.id),{headers})).status,200);
  await fs.appendFile(image,'changed');assert.equal((await fetch(url(present.id),{headers})).status,409);
  assert.equal((await fetch(app.origin+'/workbench-images.mjs')).status,200);
});
