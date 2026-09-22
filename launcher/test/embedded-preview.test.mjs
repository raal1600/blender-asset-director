import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {createApp} from '../server.mjs';
import {fileHash} from '../lib/storage.mjs';
import {packageGLTF,validateGLB} from '../lib/viewer-gltf.mjs';
import {animationEntries,previewFailure} from '../public/viewer-3d.mjs';
import {MAX_PREVIEW_STORAGE_BYTES,assertPreviewStorageBudget} from '../lib/embedded-preview.mjs';
import {MAX_VIEWER_BYTES} from '../lib/viewer-gltf.mjs';

test('preview storage permits more than 2 GiB but reserves copies and output below 100 GiB',()=>{
  const gib=1024**3,sourceBytes=160*1024**2;
  assert.equal(MAX_PREVIEW_STORAGE_BYTES,100*gib);
  assert.doesNotThrow(()=>assertPreviewStorageBudget(2*gib,sourceBytes));
  const boundary=MAX_PREVIEW_STORAGE_BYTES-sourceBytes*2-MAX_VIEWER_BYTES;
  assert.doesNotThrow(()=>assertPreviewStorageBudget(boundary-1,sourceBytes));
  for(const disk of [boundary,boundary+1,MAX_PREVIEW_STORAGE_BYTES])
    assert.throws(()=>assertPreviewStorageBudget(disk,sourceBytes),/exceed 100 GiB.*nothing was deleted/);
});

test('preview failure explains texture limits without hiding retained technical evidence',()=>{
  const raw='Command failed (2): Textures exceed the interactive preview budget; retained attempt view_test';
  const result=previewFailure(new Error(raw));assert.match(result.message,/texture conversion limits/);assert.equal(result.detail,raw);
  assert.match(previewFailure(Error('GPU unavailable')).message,/could not prepare/);
});

test('static poses remain inspectable, distinguished from actual timed animation',()=>{
  const entries=animationEntries([{name:'walk',duration:2,tracks:[{}]},{name:'rest pose',duration:0,tracks:[{}]},{name:'empty',duration:0,tracks:[]}]);
  assert.deepEqual(entries.map(e=>e.staticPose),[false,true]);assert.equal(entries[1].clip.name,'rest pose');
  assert.throws(()=>animationEntries([{duration:NaN,tracks:[{}]}]),/Invalid animation/);
});

export async function triangle(folder) {
  const bytes=Buffer.from(new Float32Array([-1,0,0,1,0,0,0,1,0]).buffer);
  const doc={asset:{version:'2.0'},scene:0,scenes:[{nodes:[0]}],nodes:[{name:'Synthetic triangle',mesh:0}],meshes:[{primitives:[{attributes:{POSITION:0}}]}],buffers:[{uri:'geometry.bin',byteLength:bytes.length}],bufferViews:[{buffer:0,byteLength:bytes.length}],accessors:[{bufferView:0,componentType:5126,count:3,type:'VEC3',min:[-1,0,0],max:[1,1,0]}]};
  await fs.mkdir(folder,{recursive:true});await fs.writeFile(path.join(folder,'model.gltf'),JSON.stringify(doc));await fs.writeFile(path.join(folder,'geometry.bin'),bytes);
  return {root:folder,file:'model.gltf',files:await Promise.all(['model.gltf','geometry.bin'].map(async p=>({path:p,...await fileHash(path.join(folder,p))})))};
}

test('embedded viewer is authenticated, scoped, cached by exact bytes and cannot select/import/approve',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'synthetic-embedded-viewer-')),library=path.join(root,'Database/AssetDirector');
  const source=await triangle(library),asset={id:'a_'+'1'.repeat(24),version:'2'.repeat(64),kind:'model',title:'Synthetic triangle',files:source.files,metadata:{}};
  let native=0;const runtime={harness:async args=>{if(args[0]==='workbench-catalog')return asset;native++;throw Error('Native execution is not permitted in this direct glTF test');}};
  const app=await createApp({root,config:{library},runtime,port:0});
  t.after(async()=>{app.server.closeAllConnections();await new Promise(r=>app.server.close(r));await fs.rm(root,{recursive:true,force:true});});
  let p=await app.store.create('Synthetic embedded inspection');const created=await app.workbench.create(p.id,p.revision,'Viewer scene');p=await app.store.get(p.id);
  const before=await fileHash(path.join(p.directory,'project.json')),headers={'Content-Type':'application/json',Authorization:'Bearer '+app.token};
  const request={kind:'catalog',id:asset.id,version:asset.version,file:source.file},body={projectId:p.id,sceneId:created.sceneId,revision:p.revision,request};
  const post=(value=body,auth=headers)=>fetch(app.origin+'/api/workbench/viewer-prepare',{method:'POST',headers:auth,body:JSON.stringify(value)});
  assert.equal((await post(body,{'Content-Type':'application/json'})).status,401);
  for(const change of [{file:'../private.gltf'},{version:'3'.repeat(64)},{url:'https://example.invalid'}])assert.equal((await post({...body,request:{...request,...change}})).ok,false);
  const response=await post();assert.equal(response.status,200,await response.clone().text());const prepared=await response.json();
  assert.equal(prepared.observed.vertices,3);assert.equal(prepared.selectionChanged,false);assert.equal(prepared.approved,false);assert.equal(native,0);
  const media=new URL('/api/workbench/viewer-model',app.origin);media.search=new URLSearchParams({projectId:p.id,sceneId:created.sceneId,previewId:prepared.previewId});
  assert.equal((await fetch(media)).status,401);const read=await fetch(media,{headers});assert.equal(read.status,200);
  const bytes=Buffer.from(await read.arrayBuffer());assert.equal(createHash('sha256').update(bytes).digest('hex'),prepared.sha256);assert.equal(validateGLB(bytes).vertices,3);
  const again=await (await post()).json();assert.equal(again.previewId,prepared.previewId);assert.equal(again.cached,true);
  assert.equal((await post({...body,revision:p.revision-1})).status,409);
  const cachedFile=path.join(root,'SystemRuntime/UserData/ViewerPreviews',prepared.previewId,'model.glb');
  await fs.appendFile(cachedFile,'tamper');assert.equal((await fetch(media,{headers})).status,409);
  await fs.writeFile(cachedFile,bytes);
  media.searchParams.set('sceneId','sc_foreign');assert.equal((await fetch(media,{headers})).status,404);
  assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),before);
  await fs.appendFile(path.join(library,'geometry.bin'),'changed');assert.equal((await post()).status,409);
  media.searchParams.set('sceneId',created.sceneId);assert.equal((await fetch(media,{headers})).status,409);
});

test('glTF package conversion refuses external, escaped and unrecorded resource URIs',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'synthetic-gltf-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));const source=await triangle(root);
  const filename=path.join(root,'model.gltf'),document=JSON.parse(await fs.readFile(filename));
  for(const uri of ['https://example.invalid/texture','file:///private','../secret.bin','%2e%2e/private','C:/private.bin','missing.bin']){document.buffers[0].uri=uri;await fs.writeFile(filename,JSON.stringify(document));await assert.rejects(packageGLTF(source));}
});

test('retained preview refusal preserves its client-error status and changes no project data',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'synthetic-viewer-refusal-')),library=path.join(root,'Database/AssetDirector');
  const source=await triangle(library),filename=path.join(library,'model.gltf'),doc=JSON.parse(await fs.readFile(filename));
  doc.nodes[0].children=[0];await fs.writeFile(filename,JSON.stringify(doc));
  source.files[0]={path:'model.gltf',...await fileHash(filename)};
  const asset={id:'a_'+'3'.repeat(24),version:'4'.repeat(64),kind:'model',title:'Synthetic refusal',files:source.files,metadata:{}};
  const app=await createApp({root,config:{library},runtime:{harness:async args=>{assert.equal(args[0],'workbench-catalog');return asset;}},port:0});
  t.after(async()=>{app.server.closeAllConnections();await new Promise(r=>app.server.close(r));await fs.rm(root,{recursive:true,force:true});});
  let p=await app.store.create('Synthetic refusal');const created=await app.workbench.create(p.id,p.revision,'Refusal scene');p=await app.store.get(p.id);
  const manifest=path.join(p.directory,'project.json'),before=await fileHash(manifest);
  const response=await fetch(app.origin+'/api/workbench/viewer-prepare',{method:'POST',headers:{Authorization:'Bearer '+app.token,'Content-Type':'application/json'},body:JSON.stringify({projectId:p.id,sceneId:created.sceneId,revision:p.revision,request:{kind:'catalog',id:asset.id,version:asset.version,file:'model.gltf'}})});
  assert.equal(response.status,400);const failure=await response.json();assert.match(failure.error,/Invalid\/cyclic node hierarchy.*3D attempt retained:/);
  const folder=path.join(root,'SystemRuntime/UserData/ViewerPreviews'),copies=await fs.readdir(folder);assert.equal(copies.length,1);
  const record=JSON.parse(await fs.readFile(path.join(folder,copies[0],'viewer-failure.json')));assert.equal(record.state,'FAILED');
  assert.deepEqual(await fileHash(manifest),before);
});

test('vendor payload exactly matches pinned integrity records and local module dependencies',async()=>{
  const folder=fileURLToPath(new URL('../public/vendor/three/',import.meta.url));const manifest=JSON.parse(await fs.readFile(path.join(folder,'VENDOR.json')));
  assert.equal(manifest.version,'0.186.0');assert.equal(manifest.license,'MIT');
  for(const [name,record] of Object.entries(manifest.files)){const bytes=await fs.readFile(path.join(folder,name));assert.equal(createHash('sha256').update(bytes).digest('hex'),record.sha256,name);
    if(name.endsWith('.js'))for(const match of bytes.toString().replace(/\/\*[\s\S]*?\*\//g,'').matchAll(/^(?:import|export)\s*\{[^}]*\}\s*from\s*['"]([^'"]+)['"]/gm)){assert.ok(match[1].startsWith('.'),match[1]);await fs.access(path.resolve(folder,path.dirname(name),match[1]));}}
});

test('interactive format refuses cyclic graphs, compressed streams and oversized decoded textures',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'synthetic-viewer-limits-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));const source=await triangle(root);
  const filename=path.join(root,'model.gltf'),base=JSON.parse(await fs.readFile(filename));
  for(const change of [{nodes:[{mesh:0,children:[0]}]},{extensionsUsed:['KHR_draco_mesh_compression']},{extensionsUsed:['EXT_mesh_gpu_instancing']}]){
    await fs.writeFile(filename,JSON.stringify({...base,...change}));await assert.rejects(packageGLTF(source));
  }
  const png=Buffer.alloc(24);Buffer.from([137,80,78,71,13,10,26,10]).copy(png);png.write('IHDR',12);png.writeUInt32BE(9000,16);png.writeUInt32BE(9000,20);
  await fs.writeFile(path.join(root,'oversized.png'),png);source.files.push({path:'oversized.png',...await fileHash(path.join(root,'oversized.png'))});
  await fs.writeFile(filename,JSON.stringify({...base,images:[{uri:'oversized.png'}]}));await assert.rejects(packageGLTF(source),/Texture width/);
});
