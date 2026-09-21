import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {writeJson,fileHash,exists,json} from '../lib/storage.mjs';
import {libraryUsage,libraryAvailability} from '../public/library-usage.mjs';
import {pinnedPage} from '../public/workbench-browser.mjs';
import {preparationDialog} from '../public/library-preparation.mjs';

test('production membership never upgrades selection or historical evidence to current presence',()=>{
 const a='a',s={id:'one',sources:[],catalog:[a],checkpoints:[],current:null,candidate:null};
 const p={assets:[],workbench:{scenes:[s],catalogPins:[{id:a,title:'Model',kind:'model'}]}};
 assert.equal(libraryUsage(p,s,a).label,'Chosen · not imported');
 s.current='cp';s.checkpoints.push({id:'cp',audit:null});
 assert.equal(libraryUsage(p,s,a).action,'inspect');
 s.catalog=[];p.workbench.scenes.push({id:'two',catalog:[a],checkpoints:[{id:'other',audit:{objects:[{asset_id:a}]}}],current:'other'});
 assert.equal(libraryUsage(p,s,a).label,'Used in 1 other scene');
 assert.equal(pinnedPage(p,s,{production:true}).total,1);assert.equal(pinnedPage(p,s).total,0);
 s.candidate='new';s.checkpoints.push({id:'new',audit:{objects:[{asset_id:a}]}});
 assert.equal(libraryUsage(p,s,a).action,'review');
 assert.equal(libraryAvailability({available:true},{source:true}),'Local · needs preparation');
 assert.equal(libraryAvailability({available:false},{source:true}),'Files unavailable');
});

test('preparation form has no default permission or invented license',()=>{
 const esc=s=>String(s??'').replaceAll('<','&lt;'),b=(s,a)=>'<button data-action="'+a+'">'+s+'</button>';
 const view=preparationDialog({source:{name:'<source>',id:'id',version:'v'},file:'model.blend',esc,b});
 assert.match(view.body,/&lt;source>/);assert.match(view.body,/value="">Choose the verified license/);
 assert.doesNotMatch(view.body,/\bchecked\b|value="https:/);assert.match(view.body,/No download/);
});

async function fixture(t){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-preparation-test-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 for(const name of ['Meshes/Terrain/Synthetic','Characters','Animations','AssetDirector/incoming'])await fs.mkdir(path.join(root,'Database',name),{recursive:true});
 const input=path.join(root,'Database/Meshes/Terrain/Synthetic/model.glb');await fs.writeFile(input,'synthetic boundary bytes - not a real Blender fixture');
 const store=new Store(root);await store.init();const source=(await store.scan()).sources[0];
 const library=path.join(root,'Database/AssetDirector'),file='incoming/model.glb';await fs.copyFile(input,path.join(library,file));
 const asset={id:'a_'+'a'.repeat(24),version:'b'.repeat(64),kind:'model',title:'Synthetic',provider:'local',files:[{path:file,...await fileHash(input)}],models:[file],policy:{eligible:true},subcategory:{id:'environment'}};
 const calls=[];let fail=false;
 const runtime={harness:async args=>{calls.push(args[0]);if(args[0]==='workbench-catalog')return structuredClone(asset);
   if(args[0]==='workbench-intake'){if(fail)throw Error('Synthetic dependency refusal');const request=await json(args[2]);return {state:'READY',source_id:source.id,source_version:source.version,source_file:request.file,asset_id:asset.id,asset_version:asset.version,file};}
   if(args[0]==='workbench-verify')return {ok:true};throw Error('Unexpected command');}};
 const work=new Workbench(store,runtime,{library,blender:process.execPath});let p=await store.create('Preparation test','Generated unit boundary only');const created=await work.create(p.id,p.revision,'Test world');p=await store.get(p.id);
 const request={id:source.id,version:source.version,file:source.entrypoints[0],confirmed:true,evidence:{source_url:'https://example.invalid/generated',license_id:'CC0-1.0',license_url:'https://example.invalid/terms',author:'Synthetic generator'}};
 const wait=async()=>{for(let i=0;i<400;i++){if(!work.running.size)return store.get(p.id);await new Promise(r=>setTimeout(r,5));}throw Error('Did not settle');};
 return {root,work,store,source,p,sid:created.sceneId,request,input,asset,calls,wait,setFail:()=>{fail=true;}};
}
test('decline, changed version, nonmember and unsupported rights create no job or preparation copy',async t=>{
 const f=await fixture(t);
 for(const request of [{...f.request,confirmed:false},{...f.request,version:'c'.repeat(64)},{...f.request,file:'../../secret.blend'},{...f.request,evidence:{...f.request.evidence,license_id:'UNKNOWN'}}])
   await assert.rejects(f.work.prepareSource(f.p.id,f.sid,f.p.revision,request));
 assert.deepEqual(f.calls,[]);assert.equal(await exists(path.join(f.root,'SystemRuntime/UserData/LibraryPreparations')),false);
 assert.equal((await f.store.get(f.p.id)).revision,f.p.revision);
});
test('successful preparation creates a shared reference, never a candidate or permission; second use reuses catalog bytes',async t=>{
 const f=await fixture(t),before=await fileHash(f.input);
 const other=await f.store.create('Other production');
 assert.equal((await f.work.sourcePage(f.p.id,{excludeProduction:true})).total,1);
 await f.work.prepareSource(f.p.id,f.sid,f.p.revision,f.request);let p=await f.wait(),s=p.workbench.scenes[0];
 assert.equal(s.current,null);assert.equal(s.candidate,null);assert.equal(s.checkpoints.length,0);assert.deepEqual(s.catalog,[f.asset.id]);
 assert.equal((await f.work.interactions(p.id).sourceStatus()).ready,false);assert.deepEqual(await fileHash(f.input),before);
 const source=await f.work.sourceDetail(p.id,f.source.id);assert.equal(source.prepared.assetId,f.asset.id);
 const result=await f.work.create(p.id,p.revision,'Second world');p=await f.store.get(p.id);
 await f.work.prepareSource(p.id,result.sceneId,p.revision,f.request);p=await f.wait();
 assert.equal(f.calls.filter(c=>c==='workbench-intake').length,1);assert.equal(p.workbench.catalogPins.length,1);
 assert.equal((await f.work.sourcePage(p.id,{sceneId:result.sceneId,production:true})).total,1,'Prepared package is associated through its exact catalog version, not a guessed name');
 assert.equal((await f.work.sourcePage(p.id,{excludeProduction:true})).total,0,'Added package is not repeated in available-to-add');
 assert.equal((await f.work.sourcePage(other.id,{excludeProduction:true})).total,1,'Other productions can still reuse the shared package');
 assert.equal((await f.work.sourcePage(p.id)).total,1,'Full read-only API remains compatible');
 await assert.rejects(f.work.sourcePage(p.id,{excludeProduction:true,production:true}),/Invalid library scope/);
 assert.deepEqual(p.assets,[],'The original source reference is not silently attached');
 assert.equal(await exists(path.join(p.directory,'Runs/.interactive-execution.lock')),false);
});

test('source membership excludes historical and other-scene references without relying on matching names',async t=>{
 const f=await fixture(t),p=await f.store.get(f.p.id);
 p.assets.push({sourceId:f.source.id,version:f.source.version});
 await f.store.save(p,p.revision);
 assert.equal((await f.work.sourcePage(p.id,{production:true})).total,1);
 assert.equal((await f.work.sourcePage(p.id,{excludeProduction:true})).total,0);
 assert.equal((await fileHash(f.input)).sha256,f.asset.files[0].sha256);
});
test('failed preparation retains its attempt and releases only its own writer without adding a catalog pin',async t=>{
 const f=await fixture(t);f.setFail();await f.work.prepareSource(f.p.id,f.sid,f.p.revision,f.request);const p=await f.wait();
 assert.equal(p.workbench.catalogPins,undefined);assert.equal(p.workbench.scenes[0].candidate,null);
 const run=(await f.store.runs(p.id))[0];assert.equal(run.state,'FAILED');assert.match(run.error,/dependency/);
 assert.equal(await exists(path.join(f.root,'SystemRuntime/UserData/LibraryPreparations',run.id,'authorization.json')),true);
 assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),false);
});

test('source changes during worker execution refuse the production pin and keep the current scene unchanged',async t=>{
 const f=await fixture(t),run=f.work.runtime.harness;
 f.work.runtime.harness=async args=>{const result=await run(args);if(args[0]==='workbench-intake')await fs.writeFile(f.input,'changed synthetic original');return result;};
 await f.work.prepareSource(f.p.id,f.sid,f.p.revision,f.request);const p=await f.wait();
 assert.equal(p.workbench.catalogPins,undefined);assert.equal(p.workbench.scenes[0].candidate,null);
 assert.equal((await f.store.runs(p.id))[0].state,'FAILED');
 assert.equal((await f.work.sourceDetail(p.id,f.source.id)).prepared,null);
});

test('explicit recovery cannot release a preparation with a native worker still recorded RUNNING',async t=>{
 const f=await fixture(t);f.setFail();await f.work.prepareSource(f.p.id,f.sid,f.p.revision,f.request);const p=await f.wait(),run=(await f.store.runs(p.id))[0];
 await writeJson(path.join(f.root,'SystemRuntime/UserData/LibraryPreparations',run.id,'library/jobs/j_'+'c'.repeat(24)+'/job.json'),{state:'RUNNING'});
 await assert.rejects(f.work.resolve(p.id,f.sid,p.revision,run.id,true),/still RUNNING/);
 assert.equal((await f.store.runs(p.id))[0].state,'FAILED');
});
