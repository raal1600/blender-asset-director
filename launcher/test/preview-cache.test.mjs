/** Real direct-glTF cache bytes; native Blender reuse has its own generated E2E. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {EmbeddedPreviews,MAX_PREVIEW_METADATA_BYTES} from '../lib/embedded-preview.mjs';
import {fileHash,json,writeJson} from '../lib/storage.mjs';
import {PreviewCache} from '../lib/preview-cache.mjs';
async function fixture(t){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-preview-cache-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const library=path.join(root,'Sources');await fs.mkdir(library);
 const bytes=Buffer.from(new Float32Array([-1,0,0,1,0,0,0,1,0]).buffer);
 const doc={asset:{version:'2.0'},scene:0,scenes:[{nodes:[0]}],nodes:[{mesh:0}],meshes:[{primitives:[{attributes:{POSITION:0}}]}],buffers:[{uri:'mesh.bin',byteLength:bytes.length}],bufferViews:[{buffer:0,byteLength:bytes.length}],accessors:[{bufferView:0,componentType:5126,count:3,type:'VEC3',min:[-1,0,0],max:[1,1,0]}]};
 await writeJson(path.join(library,'model.gltf'),doc);await fs.writeFile(path.join(library,'mesh.bin'),bytes);
 const files=await Promise.all(['model.gltf','mesh.bin'].map(async name=>({path:name,...await fileHash(path.join(library,name))})));
 const project={id:'project',revision:1,workbench:{scenes:[{id:'scene',stage:'world'}]}},version='a'.repeat(64);
 const work={store:{root},config:{library},project:async(id,revision)=>{assert.equal(id,project.id);if(revision!==undefined)assert.equal(revision,project.revision);return structuredClone(project);},scene:(p,id)=>{assert.equal(id,'scene');return p.workbench.scenes[0];},catalogDetail:async(id,asset)=>({id:asset,version,kind:'model',title:'Synthetic triangle',files,metadata:{}}),runtime:{harness:()=>assert.fail('No Blender job in direct-glTF test')}};
 const viewers=new EmbeddedPreviews(work),request=i=>({kind:'catalog',id:'a_'+i.toString(16).padStart(24,'0'),version,file:'model.gltf'});
 const base=path.join(root,'SystemRuntime/UserData/ViewerPreviews');
 return {work,viewers,project,request,base,prepare:(i=1,target=viewers)=>target.prepare('project','scene',1,request(i))};
}
test('fresh session reuses exact verified bytes; drift and cross-scope reuse refuse',async t=>{
 const f=await fixture(t),first=await f.prepare(),again=await f.prepare(1,new EmbeddedPreviews(f.work));
 assert.equal(again.previewId,first.previewId);assert.equal(again.cached,true);
 const member=path.join(f.base,first.previewId,'viewer.json'),original=await fs.readFile(member);
 await fs.appendFile(member,' ');await assert.rejects(f.prepare(1,new EmbeddedPreviews(f.work)),/cache (member size|evidence) changed/);assert.equal((await fs.readFile(member)).length,original.length+1);
 await fs.writeFile(member,original);
 const fresh=new EmbeddedPreviews(f.work);await f.prepare(1,fresh);await assert.rejects(fresh.bytes('project','foreign',first.previewId),e=>e.status===404);
 const prior=await fresh.bytes('project','scene',first.previewId);assert.equal(prior.length,first.size);
 await fs.appendFile(path.join(f.base,first.previewId,'model.glb'),'changed');await assert.rejects(f.prepare(1,new EmbeddedPreviews(f.work)),/cache (member size|evidence) changed/);
});
test('65+ previews retain bounded metadata without a restart or deleting any derivative',async t=>{
 const f=await fixture(t),records=[],baseline=structuredClone(f.project);
 for(let i=1;i<=66;i++)records.push(await f.prepare(i));
 assert.equal(f.viewers.owned.size,64);await assert.rejects(f.viewers.bytes('project','scene',records[0].previewId),/Reopen.*no restart/);
 const again=await f.prepare(1);assert.equal(again.cached,true);assert.equal(again.previewId,records[0].previewId);assert.equal(f.viewers.owned.size,64);
 for(const record of records)assert.equal((await fileHash(path.join(f.base,record.previewId,'model.glb'))).sha256,record.sha256);
 assert.equal((await fs.readdir(f.base)).filter(n=>n.startsWith('view_')).length,66);assert.deepEqual(f.project,baseline);
});
test('duplicate concurrent prepares coalesce through verified reuse; profiles do not cross-reuse',async t=>{
 const f=await fixture(t),rows=await Promise.all(Array.from({length:4},()=>f.prepare()));
 assert.equal(new Set(rows.map(r=>r.previewId)).size,1);assert.equal(rows.filter(r=>!r.cached).length,1);
 f.project.workbench.scenes[0].stage='action';const action=await f.prepare();assert.notEqual(action.previewId,rows[0].previewId);assert.equal(action.profile,'inspection-v1');
 f.project.workbench.scenes[0].stage='world';assert.equal((await f.prepare()).previewId,rows[0].previewId);
});
test('corrupt, oversized or escaped index metadata refuses without rewriting evidence',async t=>{
 const f=await fixture(t);await f.prepare();const indexFile=path.join(f.base,'Index',(await fs.readdir(path.join(f.base,'Index')))[0]),original=await fs.readFile(indexFile),index=await json(indexFile);
 for(const changed of [{...index,previewId:'../outside'},{...index,key:'f'.repeat(64)},{...index,sourceDigest:'0'.repeat(64)},{...index,files:[...index.files,index.files[0]]},{...index,files:[null,...index.files.slice(1)]},{...index,files:index.files.map((m,i)=>i?m:{...m,path:'../../source'})}]){
  await writeJson(indexFile,changed);const retained=await fileHash(indexFile);await assert.rejects(f.prepare(1,new EmbeddedPreviews(f.work)));assert.deepEqual(await fileHash(indexFile),retained);
 }
 await fs.writeFile(indexFile,Buffer.alloc(16385,32));await assert.rejects(f.prepare(1,new EmbeddedPreviews(f.work)),/metadata exceeds/);
 await fs.writeFile(indexFile,original);assert.equal((await f.prepare()).cached,true);
});
test('active descriptor retention also has a byte bound and rejects one oversized descriptor',async t=>{
 const f=await fixture(t),source={testOnly:'x'.repeat(1024*1024)};
 for(let i=0;i<40;i++)f.viewers.remember({record:{previewId:String(i)},source,filename:'not-opened-in-this-metadata-test'});
 assert(f.viewers.owned.size<40);assert(f.viewers.ownedBytes<=MAX_PREVIEW_METADATA_BYTES);
 const previous=[...f.viewers.owned.keys()];
 assert.throws(()=>f.viewers.remember({record:{previewId:'oversized'},source:{testOnly:'x'.repeat(MAX_PREVIEW_METADATA_BYTES)}}),/memory bound/);
 assert.deepEqual([...f.viewers.owned.keys()],previous);
});
test('changed launcher identity allocates a new derivative and retains the prior bytes',async t=>{
 const f=await fixture(t),before=await f.prepare(),changed=new EmbeddedPreviews(f.work);changed.identity=Promise.resolve('f'.repeat(64));
 const after=await f.prepare(1,changed);assert.notEqual(after.previewId,before.previewId);assert.equal(after.cached,false);
 assert.equal((await fileHash(path.join(f.base,before.previewId,'model.glb'))).sha256,before.sha256);
});
test('synthetic native receipt contract rejects failed status, changed converter and altered output binding',async t=>{
 const f=await fixture(t),direct=await f.prepare(),directory=path.join(f.base,direct.previewId),source=await json(path.join(directory,'request.json'));
 const jobId='j_'+'1'.repeat(24),converter={implementation:'2'.repeat(64),blender:{sha256:'3'.repeat(64),size:123}},key='4'.repeat(64);
 const record={...direct,adapter:'isolated-blender-gltf',nativeJob:jobId,nativeImplementation:converter.implementation,converter};
 const job={id:jobId,state:'SUCCEEDED',specification:{implementation:converter.implementation},outputs:[{path:`jobs/${jobId}/preview.glb`,sha256:record.sha256,size:record.size}]};
 const receipt={state:'READY',job_id:jobId,source_id:source.id,source_version:source.version,model:{sha256:record.sha256,size:record.size}};
 await writeJson(path.join(directory,'viewer.json'),record);await writeJson(path.join(directory,'receipt.json'),receipt);
 await writeJson(path.join(directory,`library/jobs/${jobId}/job.json`),job);await writeJson(path.join(directory,`library/jobs/${jobId}/result.json`),{status:'OK',job_id:jobId});
 const cache=new PreviewCache(f.base),expected={source,projectId:record.projectId,sceneId:record.sceneId,implementation:record.implementation,converter};
 await cache.publish(key,source,record);assert.equal((await cache.load(key,expected)).record.previewId,record.previewId);
 await assert.rejects(cache.load(key,{...expected,converter:{...converter,implementation:'5'.repeat(64)}}),/scope\/runtime/);
 for(const changed of [{...job,state:'FAILED'},{...job,outputs:[{...job.outputs[0],sha256:'6'.repeat(64)}]}]){
  await writeJson(path.join(directory,`library/jobs/${jobId}/job.json`),changed);await cache.publish(key,source,record);
  await assert.rejects(cache.load(key,expected),/Native (preview evidence|model evidence)/);
 }
});
