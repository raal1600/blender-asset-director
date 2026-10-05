/** Real direct-glTF cache bytes; native Blender reuse has its own generated E2E. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {EmbeddedPreviews,MAX_PREVIEW_METADATA_BYTES} from '../lib/embedded-preview.mjs';
import {fileHash,json,writeJson} from '../lib/storage.mjs';
import {PreviewCache} from '../lib/preview-cache.mjs';
import {PreviewCleanup} from '../lib/preview-cleanup.mjs';
import {previewStorageView,storageConfirmation} from '../public/workbench-preview-storage.mjs';
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
test('shared view lifetimes protect active copies; explicit cleanup retains evidence and supports rebuilding',async t=>{
 const f=await fixture(t),one='viewer_00000000-0000-4000-8000-000000000001',two=one.replace(/1$/,'2');
 const prepare=id=>f.viewers.prepare('project','scene',1,f.request(1),id);
 const record=await prepare(one);assert.equal((await prepare(two)).previewId,record.previewId);
 const cleanup=new PreviewCleanup(f.viewers),directory=path.join(f.base,record.previewId),source=path.join(f.work.config.library,'model.gltf'),sourceBefore=await fileHash(source);
 assert.equal((await cleanup.plan()).eligible.length,0);f.viewers.release('project','scene',one);assert.equal((await cleanup.plan()).eligible.length,0);
 assert.throws(()=>f.viewers.release('project','wrong',two),/another scene/);f.viewers.release('project','scene',two);
 assert.equal(f.viewers.release('project','scene',two).released,false);
 assert.equal(f.viewers.protectedPreview(record.previewId),false);
 assert.equal((await f.viewers.bytes('project','scene',record.previewId)).length,record.size,'Closing the last view releases cleanup protection, not the bounded session media grant');
 const plan=await cleanup.plan();assert.equal(plan.eligible.length,1);assert.deepEqual(plan.eligible[0].files,['model.glb']);
 const preserved=await Promise.all(['request.json','viewer.json'].map(n=>fileHash(path.join(directory,n))));
 await assert.rejects(cleanup.apply({...plan,confirmed:false,closedNativePreviews:true}),/explicitly confirm/);
 await assert.rejects(cleanup.apply({...plan,confirmed:true,closedNativePreviews:false}),/explicitly confirm/);
 assert.equal((await fileHash(path.join(directory,'model.glb'))).sha256,record.sha256);
 const result=await cleanup.apply({...plan,confirmed:true,closedNativePreviews:true});assert.equal(result.state,'SUCCEEDED');assert.equal(result.removedBytes,record.size);
 await assert.rejects(fs.access(path.join(directory,'model.glb')));
 await assert.rejects(f.viewers.bytes('project','scene',record.previewId),e=>e.status===404);
 assert.deepEqual(await Promise.all(['request.json','viewer.json'].map(n=>fileHash(path.join(directory,n)))),preserved);assert.deepEqual(await fileHash(source),sourceBefore);
 const rebuilt=await prepare(one);assert.notEqual(rebuilt.previewId,record.previewId);assert.equal(rebuilt.sha256,record.sha256);
 const journal=await json(path.join(f.base,result.journal));assert.equal(journal.state,'SUCCEEDED');assert.equal(journal.removed.length,2);assert.equal(journal.review.eligible[0].indexRecord.previewId,record.previewId);
});
test('unknown files, active views and source drift protect copies and invalidate an older review',async t=>{
 const f=await fixture(t),id='viewer_00000000-0000-4000-8000-000000000001',record=await f.viewers.prepare('project','scene',1,f.request(1),id);f.viewers.release('project','scene',id);
 const cleanup=new PreviewCleanup(f.viewers),directory=path.join(f.base,record.previewId),model=path.join(directory,'model.glb');
 let plan=await cleanup.plan();await fs.writeFile(path.join(directory,'user-note.txt'),'user-owned test note');
 await assert.rejects(cleanup.apply({...plan,confirmed:true,closedNativePreviews:true}),/protected/);assert.equal((await cleanup.plan()).eligible.length,0);await fs.unlink(path.join(directory,'user-note.txt'));
 plan=await cleanup.plan();await f.viewers.prepare('project','scene',1,f.request(1),id);
 await assert.rejects(cleanup.apply({...plan,confirmed:true,closedNativePreviews:true}),/Active/);f.viewers.release('project','scene',id);
 plan=await cleanup.plan();await fs.appendFile(path.join(f.work.config.library,'mesh.bin'),'changed');
 await assert.rejects(cleanup.apply({...plan,confirmed:true,closedNativePreviews:true}),/source changed/);assert.equal((await fileHash(model)).sha256,record.sha256);assert.equal((await cleanup.plan()).eligible.length,0);
});

test('reviewed cleanup waits for an existing media read, then revokes the descriptor before removal',async t=>{
 const f=await fixture(t),id='viewer_00000000-0000-4000-8000-000000000001',record=await f.viewers.prepare('project','scene',1,f.request(1),id);f.viewers.release('project','scene',id);
 const cleanup=new PreviewCleanup(f.viewers),plan=await cleanup.plan(),original=f.work.project;
 let entered,resume,applying=false;
 const started=new Promise(resolve=>{entered=resolve;}),gate=new Promise(resolve=>{resume=resolve;});
 f.work.project=async(...args)=>{entered();await gate;return original(...args);};
 const reading=f.viewers.bytes('project','scene',record.previewId);await started;
 const removing=f.viewers.exclusive(()=>{applying=true;return cleanup.apply({...plan,confirmed:true,closedNativePreviews:true});});
 await new Promise(setImmediate);assert.equal(applying,false);assert.equal((await fileHash(path.join(f.base,record.previewId,'model.glb'))).sha256,record.sha256);
 resume();assert.equal((await reading).length,record.size);assert.equal((await removing).state,'SUCCEEDED');
 await assert.rejects(f.viewers.bytes('project','scene',record.previewId),e=>e.status===404);
});
test('changed payload and shared file identities cannot be removed from an old cleanup review',async t=>{
 const f=await fixture(t),id='viewer_00000000-0000-4000-8000-000000000001',record=await f.viewers.prepare('project','scene',1,f.request(1),id);f.viewers.release('project','scene',id);
 const cleanup=new PreviewCleanup(f.viewers),model=path.join(f.base,record.previewId,'model.glb'),bytes=await fs.readFile(model),plan=await cleanup.plan();
 await fs.appendFile(model,'changed');await assert.rejects(cleanup.apply({...plan,confirmed:true,closedNativePreviews:true}),/changed/);assert.equal((await fs.readFile(model)).length,bytes.length+7);
 await fs.writeFile(model,bytes);await fs.link(model,path.join(f.work.store.root,'retained-hardlink.glb'));assert.equal((await cleanup.plan()).eligible.length,0);assert.equal((await fileHash(model)).sha256,record.sha256);
});
test('a simulated file-removal failure stops cleanup with a retained partial journal and remaining bytes',async t=>{
 const f=await fixture(t),id='viewer_00000000-0000-4000-8000-000000000001',record=await f.viewers.prepare('project','scene',1,f.request(1),id);f.viewers.release('project','scene',id);
 const cleanup=new PreviewCleanup(f.viewers),plan=await cleanup.plan(),originalUnlink=fs.unlink;
 const rawModel=path.join(f.base,record.previewId,'model.glb'),model=process.platform==='win32'?rawModel.toLowerCase():rawModel;
 const canonicalModel=await fs.realpath(model);let injected=0;
 const hook=t.mock.method(fs,'unlink',async filename=>{if(path.relative(canonicalModel,await fs.realpath(filename))===''){injected++;throw Object.assign(Error('Synthetic locked payload'),{code:'EACCES'});}return originalUnlink(filename);});
 const result=await cleanup.apply({...plan,confirmed:true,closedNativePreviews:true});hook.mock.restore();
 assert.equal(injected,1);assert.equal(result.state,'PARTIAL');assert.equal(result.removedBytes,0);assert.match(result.error,/Synthetic locked/);
 assert.equal((await json(path.join(f.base,result.journal))).pending.path,record.previewId+'/model.glb');
 assert.equal((await fileHash(model)).sha256,record.sha256);const journal=await json(path.join(f.base,result.journal));assert.equal(journal.state,'PARTIAL');assert.equal(journal.removed.length,1);assert.equal(journal.removed[0].kind,'cache-index');
 await assert.rejects(cleanup.apply({...plan,confirmed:true,closedNativePreviews:true}),/Review/);assert.equal((await cleanup.plan()).eligible.length,0);
});
test('storage review separates protected evidence, exact paths and explicit removal confirmation',()=>{
 const plan={usedBytes:1024**3,removableBytes:1024**2,eligible:[{previewId:'view_test',title:'Synthetic',bytes:1024**2,files:['model.glb']}],protected:[{previewId:'view_active',reason:'Active preview is protected.'}],preserved:'Originals and logs retained'};
 const result=previewStorageView(plan,String,(text,action)=>`<button data-action="${action}">${text}</button>`);
 assert.match(result.body,/view_test\/model.glb/);assert.match(result.body,/Active preview/);assert.match(result.buttons,/preview-storage-apply/);
 assert.match(storageConfirmation(plan),/not open in Blender/);assert.match(storageConfirmation(plan),/Originals, saved checkpoints, databases, receipts and logs stay intact/);assert.match(storageConfirmation(plan),/cannot be undone/);
});

test('an abandoned queued preview never resolves sources or allocates a conversion attempt',async t=>{
 const f=await fixture(t),controller=new AbortController();let resume,lookups=0;
 const blocker=f.viewers.exclusive(()=>new Promise(resolve=>{resume=resolve;}));await new Promise(setImmediate);
 const original=f.work.catalogDetail;f.work.catalogDetail=(...args)=>{lookups++;return original(...args);};
 const preparing=f.viewers.prepare('project','scene',1,f.request(1),'viewer_00000000-0000-4000-8000-000000000001',controller.signal);
 const refused=assert.rejects(preparing,e=>e.status===499&&/cancelled/.test(e.message));controller.abort();resume();await blocker;await refused;
 assert.equal(lookups,0);assert.equal(f.viewers.owned.size,0);assert.equal(await fs.access(f.base).then(()=>true,()=>false),false);
 assert.equal((await f.prepare()).profile,'world-static-v1','Cancellation must not poison subsequent queue work');
});

test('cancellation during source verification refuses before conversion allocation',async t=>{
 const f=await fixture(t),controller=new AbortController(),original=f.work.catalogDetail;let entered,resume;
 const started=new Promise(resolve=>{entered=resolve;}),gate=new Promise(resolve=>{resume=resolve;});
 f.work.catalogDetail=async(...args)=>{entered();await gate;return original(...args);};
 const preparing=f.viewers.prepare('project','scene',1,f.request(1),'viewer_00000000-0000-4000-8000-000000000001',controller.signal);
 const refused=assert.rejects(preparing,e=>e.status===499);await started;controller.abort();resume();await refused;
 assert.equal(f.viewers.owned.size,0);assert.equal(await fs.access(f.base).then(()=>true,()=>false),false);
});
/** Contract regression: actual native browser evidence is in preview_cleanup_check. */
test('native cleanup retains only the exact successful worker identity marker',async t=>{
 const f=await fixture(t),direct=await f.prepare(),directory=path.join(f.base,direct.previewId),source=await json(path.join(directory,'request.json'));
 const jobId='j_'+'1'.repeat(24),assetId='a_'+'2'.repeat(24),implementation='3'.repeat(64),jobBase=`library/jobs/${jobId}`;
 const converter={implementation,blender:{sha256:'4'.repeat(64),size:123}},record={...direct,adapter:'isolated-blender-gltf',nativeJob:jobId,nativeImplementation:implementation,converter};
 const native=[];
 for(const member of source.files){const relative='incoming/package/'+member.path,filename=path.join(directory,'library',relative);await fs.mkdir(path.dirname(filename),{recursive:true});await fs.copyFile(path.join(source.root,member.path),filename);native.push({...member,path:relative});}
 for(const relative of ['PREVIEW_COPY.blend',`${jobBase}/result.blend`,'library/catalog.sqlite',`library/manifests/${assetId}.json`,`${jobBase}/worker.log`]){const file=path.join(directory,relative);await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file,'synthetic contract bytes');}
 await fs.copyFile(path.join(directory,'model.glb'),path.join(directory,jobBase,'preview.glb'));
 const marker={job_id:jobId,implementation,pid:123,started_at:1001},markerName=`${jobBase}/worker-process.json`,markerFile=path.join(directory,markerName);
 await writeJson(markerFile,marker);
 const markerHash=await fileHash(markerFile),job={id:jobId,state:'SUCCEEDED',worker_pid:123,started_at:1000,finished_at:1002,specification:{implementation,operation:'asset-preview',options:{embedded:true},inputs:[],asset_id:assetId,source_files:native},outputs:[{path:`jobs/${jobId}/preview.glb`,sha256:record.sha256,size:record.size},{path:`jobs/${jobId}/worker-process.json`,...markerHash}]};
 const member=async relative=>({path:relative,...await fileHash(path.join(directory,relative))});
 const receipt={state:'READY',job_id:jobId,source_id:source.id,source_version:source.version,blend:await member('PREVIEW_COPY.blend'),job_blend:await member(`${jobBase}/result.blend`),model:await member(`${jobBase}/preview.glb`)};
 await writeJson(path.join(directory,'viewer.json'),record);await writeJson(path.join(directory,'receipt.json'),receipt);
 await writeJson(path.join(directory,jobBase,'job.json'),job);await writeJson(path.join(directory,jobBase,'result.json'),{status:'OK',job_id:jobId});
 const indexName=(await fs.readdir(path.join(f.base,'Index')))[0],key=indexName.slice(0,-5),cache=new PreviewCache(f.base);
 await cache.publish(key,source,record);
 const cleanup=new PreviewCleanup(new EmbeddedPreviews(f.work),async()=>[]);
 let plan=await cleanup.plan();assert.equal(plan.eligible.length,1,JSON.stringify(plan.protected));assert(!plan.eligible[0].files.includes(markerName));
 await writeJson(markerFile,{...marker,pid:124});
 await assert.rejects(cleanup.apply({...plan,confirmed:true,closedNativePreviews:true}),/worker|changed/i);
 assert.equal((await cleanup.plan()).eligible.length,0,'Altered process marker stays protected');
 await writeJson(markerFile,marker);
 await fs.unlink(markerFile);assert.equal((await cleanup.plan()).eligible.length,0,'Missing recorded marker stays protected');await writeJson(markerFile,marker);
 for(const changed of [{...marker,job_id:'j_'+'9'.repeat(24)},{...marker,pid:124},{...marker,started_at:999},{...marker,unexpected:true}]){
  await writeJson(markerFile,changed);const changedJob=structuredClone(job);
  changedJob.outputs[1]={...changedJob.outputs[1],...await fileHash(markerFile)};await writeJson(path.join(directory,jobBase,'job.json'),changedJob);await cache.publish(key,source,record);
  assert.equal((await cleanup.plan()).eligible.length,0,'Rehashed but incorrectly bound worker marker stays protected');
 }
 await writeJson(markerFile,marker);await writeJson(path.join(directory,jobBase,'job.json'),job);await cache.publish(key,source,record);
 await fs.writeFile(path.join(directory,jobBase,'unknown.json'),'{}');assert.equal((await cleanup.plan()).eligible.length,0,'Unknown sibling stays protected');await fs.unlink(path.join(directory,jobBase,'unknown.json'));
 plan=await cleanup.plan();assert.equal(plan.eligible.length,1);assert.equal((await cleanup.apply({...plan,confirmed:true,closedNativePreviews:true})).state,'SUCCEEDED');
 assert.deepEqual(await fileHash(markerFile),markerHash,'Successful cleanup preserves worker identity evidence byte-for-byte');
});
