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
import {animationEntries} from '../public/viewer-3d.mjs';

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
