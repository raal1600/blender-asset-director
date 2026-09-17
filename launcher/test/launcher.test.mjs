import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {Runtime} from '../lib/runtime.mjs';
import { Store } from '../lib/projects.mjs';
import { safe, json } from '../lib/storage.mjs';
import { createApp } from '../server.mjs';

async function fixture(t) {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-launcher-test-'));
  t.after(()=>fs.rm(root,{recursive:true,force:true}));
  for(const kind of ['Animations','Characters','Meshes'])await fs.mkdir(path.join(root,'Database',kind),{recursive:true});
  const store=new Store(root);await store.init();return {root,store};
}
test('complete packages are pinned; changed textures block verification without changing originals or other projects',async t=>{
  const {root,store}=await fixture(t);const pkg=path.join(root,'Database/Characters/Hero');await fs.mkdir(pkg);
  await fs.writeFile(path.join(pkg,'hero.gltf'),'synthetic model');await fs.writeFile(path.join(pkg,'color.png'),'synthetic texture');
  const a=await store.create('Project A'),b=await store.create('Project B');let inventory=await store.scan();
  assert.equal(inventory.sources.length,1);assert.equal(inventory.sources[0].fileCount,2);
  await store.attach(a.id,inventory.sources[0].id,a.revision);assert.equal((await store.get(b.id)).assets.length,0);
  assert.equal((await store.verify(a.id)).ok,true);
  await fs.writeFile(path.join(pkg,'color.png'),'changed texture');assert.equal((await store.verify(a.id)).ok,false);
  const oldVersion=(await store.get(a.id)).assets[0].version;inventory=await store.scan();
  assert.notEqual(oldVersion,inventory.sources[0].version);assert.equal((await store.get(a.id)).assets[0].version,oldVersion);
  const a2=await store.get(a.id);await store.detach(a.id,inventory.sources[0].id,a2.revision);
  assert.equal(await fs.readFile(path.join(pkg,'hero.gltf'),'utf8'),'synthetic model');
});
test('revision checks reject stale edits and unknown manifest versions',async t=>{
  const {store}=await fixture(t);const p=await store.create('Revision test');
  await store.update(p.id,{revision:1,brief:'new brief'});
  await assert.rejects(store.update(p.id,{revision:1,brief:'lost update'}),/another window/);
  assert.equal((await store.get(p.id)).brief,'new brief');
  const data=await json(path.join(p.directory,'project.json'));data.schema=99;await fs.writeFile(path.join(p.directory,'project.json'),JSON.stringify(data));
  await assert.rejects(store.get(p.id),/invalid/);
});
test('project paths reject traversal, absolute paths and junction escapes',async t=>{
  const {root,store}=await fixture(t);const p=await store.create('Path test');
  for(const name of ['../outside','/outside','C:/outside','Scenes/../../outside','Scenes\\outside'])await assert.rejects(safe(p.directory,name));
  const outside=path.join(root,'outside');await fs.mkdir(outside);
  await fs.symlink(outside,path.join(p.directory,'linked'),process.platform==='win32'?'junction':'dir');
  await assert.rejects(safe(p.directory,'linked/file.json'),/leaves/);
});
test('jobs have one explicit project owner and cannot target another project',async t=>{
  const {store}=await fixture(t);const a=await store.create('Job A'),b=await store.create('Job B');
  const input=path.join(a.directory,'Scenes/test.blend');await fs.writeFile(input,'synthetic');
  const job={id:'j_'+'a'.repeat(24),specification:{operation:'scene-audit',inputs:[{path:input}]}};
  await assert.rejects(store.bindJob(b.id,job));await store.bindJob(a.id,job);await assert.rejects(store.bindJob(b.id,job),/another project/);
  assert.equal((await store.get(a.id)).jobs.length,1);await store.bindJob(a.id,job);assert.equal((await store.get(a.id)).jobs.length,1);
});
test('HTTP API requires token, blocks foreign origins and handles explicit project selection',async t=>{
  const {root}=await fixture(t);const runtime={health:null,blender:async()=>({connected:false}),jobs:async()=>[]};
  const app=await createApp({root,config:{},port:0,runtime});t.after(()=>new Promise(r=>app.server.close(r)));
  let r=await fetch(app.origin+'/api/state');assert.equal(r.status,401);
  const headers={Authorization:`Bearer ${app.token}`,'Content-Type':'application/json'};
  r=await fetch(app.origin+'/api/projects/create',{method:'POST',headers:{...headers,Origin:'https://untrusted.example'},body:JSON.stringify({name:'Should fail'})});assert.equal(r.status,403);
  const foreignHostStatus=await new Promise((resolve,reject)=>{const request=http.get(app.origin+'/api/state',{headers:{...headers,Host:'evil.example'}},response=>{response.resume();resolve(response.statusCode);});request.on('error',reject);});assert.equal(foreignHostStatus,403);
  r=await fetch(app.origin+'/api/projects/create',{method:'POST',headers,body:JSON.stringify({name:'HTTP project'})});assert.equal(r.status,200);const p=await r.json();
  r=await fetch(app.origin+'/api/projects/verify',{method:'POST',headers,body:'{}'});assert.equal(r.status,400);
  r=await fetch(app.origin+'/api/project?projectId='+p.id,{headers});assert.equal(r.status,200);assert.equal((await r.json()).project.id,p.id);
  r=await fetch(app.origin+'/api/projects/update',{method:'POST',headers,body:JSON.stringify({projectId:p.id,revision:1,scene:'../elsewhere.blend'})});assert.equal(r.status,400);
  r=await fetch(app.origin+'/api/arbitrary-command',{method:'POST',headers,body:'{}'});assert.equal(r.status,404);
});

test('trash is recoverable, preserves shared files and reserves job ownership',async t=>{
  const {root,store}=await fixture(t);let a=await store.create('Trash A');const b=await store.create('Trash B');
  const original=path.join(a.directory,'Scenes/owned.blend');await fs.writeFile(original,'original bytes');
  const shared=path.join(root,'Database/Characters/shared.glb');await fs.writeFile(shared,'shared bytes');
  const job={id:'j_'+'b'.repeat(24),specification:{operation:'inspect',inputs:[]}};
  await store.bindJob(a.id,job);a=await store.get(a.id);
  await assert.rejects(store.trash(a.id,1),/changed/);
  await store.trash(a.id,a.revision);
  assert.equal((await store.list()).projects.length,1);
  assert.equal((await store.trashList()).projects[0].id,a.id);
  assert.equal(await fs.readFile(shared,'utf8'),'shared bytes');
  await assert.rejects(store.bindJob(b.id,job),/another project/);
  await fs.mkdir(a.directory);await assert.rejects(store.restore(a.id),/occupied/);await fs.rmdir(a.directory);
  const restored=await store.restore(a.id);assert.equal(restored.directory,a.directory);
  assert.equal(await fs.readFile(original,'utf8'),'original bytes');
  assert.equal(restored.jobs[0].id,job.id);assert.equal((await store.trashList()).projects.length,0);
});
test('trash refuses unfinished operations and invalid project identifiers',async t=>{
  const {store}=await fixture(t);const p=await store.create('Busy project');
  await fs.writeFile(path.join(p.directory,'Runs/running.json'),JSON.stringify({projectId:p.id,state:'RUNNING'}));
  await assert.rejects(store.trash(p.id,p.revision),/unfinished/);
  await assert.rejects(store.restore('../outside'),/Invalid project/);
  assert.equal((await store.get(p.id)).id,p.id);
});

test('connected Blender is shown; invisible connections are not reported as an opened editor',async t=>{
 const {store}=await fixture(t);const p=await store.create('Window test');const runtime=new Runtime(store,{blender:'configured-blender'});
 runtime.blender=async()=>({connected:true});runtime.processes=async()=>[{ProcessId:123,ExecutablePath:'configured-blender'}];
 let shown=0;runtime.showBlender=async()=>{shown++;return {visible:true,focused:true};};
 const result=await runtime.startBlender(p.id);assert.equal(shown,1);assert.equal(result.visible,true);assert.equal(result.started,false);
 runtime.showBlender=async()=>({visible:false,focused:false});await assert.rejects(runtime.startBlender(p.id),/another Windows desktop/);
 runtime.blender=async()=>({connected:false});runtime.showBlender=async()=>({visible:true,focused:true});
 const offline=await runtime.startBlender(p.id);assert.equal(offline.connected,false);assert.equal(offline.visible,true);assert.match(offline.message,/MCP Server/);
});
