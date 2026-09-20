import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createApp} from '../server.mjs';
import {fileHash,writeJson} from '../lib/storage.mjs';
import {catalogDialog} from '../public/workbench-library.mjs';
import {sourcePage} from '../lib/source-browser.mjs';
import {referenceImage,typeLabel,motionSummary} from '../public/asset-presentation.mjs';
import {previewEnvironment} from '../lib/asset-preview-launch.mjs';

test('preview process isolates recovery files and excludes provider credentials',()=>{
  const env=previewEnvironment('/synthetic/preview/native-temp',{PATH:'existing-tools',SystemRoot:'system',TEMP:'shared',Tmp:'shared',TMPDIR:'shared',OPENAI_API_KEY:'synthetic-do-not-inherit',CODEX_HOME:'private'});
  assert.deepEqual(env,{PATH:'existing-tools',SystemRoot:'system',TEMP:'/synthetic/preview/native-temp',TMP:'/synthetic/preview/native-temp',TMPDIR:'/synthetic/preview/native-temp'});
});

test('preview is authenticated, exact-member/version bound, preselection and project-read-only',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'synthetic-asset-preview-'));
  const library=path.join(root,'Database/AssetDirector');await fs.mkdir(library,{recursive:true});
  const source=path.join(library,'source.glb');await fs.writeFile(source,'synthetic contract bytes');
  const asset={id:'a_'+'1'.repeat(24),version:'2'.repeat(64),kind:'model',title:'Synthetic model',files:[{path:'source.glb',...await fileHash(source)}],metadata:{}};
  let calls=0,launches=0;
  const runtime={harness:async args=>{
    if(args[0]==='workbench-catalog')return asset;
    if(args[0]==='workbench-preview'){calls++;throw Error('Synthetic native failure: no Blender launched');}
    throw Error('Unexpected operation');
  },launchAssetPreview:async()=>{launches++;throw Error('Must not launch');}};
  const app=await createApp({root,config:{library,blender:'synthetic'},runtime,port:0});
  t.after(async()=>{await new Promise(r=>app.server.close(r));await fs.rm(root,{recursive:true,force:true});});
  let p=await app.store.create('Synthetic preview');const created=await app.workbench.create(p.id,p.revision,'Preview scene');p=await app.store.get(p.id);
  const before=await fileHash(path.join(p.directory,'project.json'));
  const request={kind:'catalog',id:asset.id,version:asset.version,file:'source.glb'};
  const body={projectId:p.id,sceneId:created.sceneId,revision:p.revision,request};
  const post=async(value,authorized=true)=>fetch(app.origin+'/api/workbench/asset-preview',{method:'POST',headers:{'Content-Type':'application/json',...(authorized?{Authorization:'Bearer '+app.token}:{})},body:JSON.stringify(value)});
  assert.equal((await post(body,false)).status,401);
  for(const patch of [{file:'../private.glb'},{version:'3'.repeat(64)},{script:'evil'}])assert.equal((await post({...body,request:{...request,...patch}})).ok,false);
  assert.equal(calls,0);assert.equal(launches,0);
  const failed=await post(body);assert.equal(failed.status,500);assert.match((await failed.json()).error,/retained: preview_/);
  assert.equal(calls,1);assert.equal(launches,0);assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),before);
  const after=await app.store.get(p.id);assert.equal(after.workbench.scenes[0].catalog,undefined);assert.equal(after.jobs.length,0);
  const folders=await fs.readdir(path.join(root,'SystemRuntime/UserData/AssetPreviews'));
  assert.equal(folders.length,1);assert.ok((await fs.stat(path.join(root,'SystemRuntime/UserData/AssetPreviews',folders[0],'launch-failure.json'))).isFile());
  // Labels are explicit, authenticated display metadata, never a source rewrite.
  const label=await fetch(app.origin+'/api/workbench/catalog-label',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+app.token},body:JSON.stringify({...body,request:{assetId:asset.id,version:asset.version,subcategory:'character'}})});
  assert.equal(label.status,200);assert.equal((await label.json()).rightsApproved,false);
  const labels=JSON.parse(await fs.readFile(path.join(root,'SystemRuntime/UserData/Launcher/asset-labels.json'),'utf8'));
  assert.equal(labels.labels[asset.id].subcategory,'character');
  assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),before);
  assert.equal((await fs.readdir(path.join(root,'SystemRuntime/UserData/Launcher/AssetLabelHistory'))).length,1);
  // Original-registry preview also binds an exact package member and version.
  for(const kind of ['Animations','Characters','Meshes'])await fs.mkdir(path.join(root,'Database',kind),{recursive:true});
  const packageRoot=path.join(root,'Database/Characters/SyntheticOriginal');await fs.mkdir(packageRoot);
  await fs.copyFile(source,path.join(packageRoot,'source.glb'));
  const original=(await app.store.scan()).sources[0];
  const raw={...body,request:{kind:'source',id:original.id,version:original.version,file:original.entrypoints[0]}};
  assert.equal((await post({...raw,request:{...raw.request,file:'Characters/Other/source.glb'}})).ok,false);
  assert.equal(calls,1);
  assert.equal((await post(raw)).status,500);assert.equal(calls,2);assert.equal(launches,0);
  assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),before);
  assert.deepEqual(await fileHash(path.join(packageRoot,'source.glb')),await fileHash(source));
});

test('motion Details previews before selection but never offers World import',()=>{
  const esc=String,b=(text,action,data,cls,disabled)=>'<button data-action="'+action+'" '+(disabled?'disabled':'')+'>'+text+'</button>';
  const asset={id:'motion',version:'a'.repeat(64),kind:'animation',models:['clip.fbx'],files:[{path:'clip.fbx',size:100}],policy:{eligible:false},metadata:{fps:24,frame_start:1,frame_end:49,source_object:'ObservedRig'}};
  const view=catalogDialog({asset,scene:{stage:'world',catalog:[]},locked:true,sourceReady:false,esc,b});
  assert.match(view.buttons,/asset-preview-open" >Preview in Blender/);assert.ok(!view.buttons.includes('catalog-import'));
  assert.match(view.body,/2.00 s · 24 fps · Performer: ObservedRig/);assert.match(view.body,/no selection, import, retargeting or rights approval/);
});

test('subcategories use registry collections, retain unknowns and filter before paging',()=>{
  const sources=Array.from({length:60},(_,i)=>({id:String(i),name:'Fixture '+i,kind:'Meshes',relative:i%2?'Meshes/Terrain/fixture'+i:'Meshes/Props/fixture'+i}));
  assert.equal(sourcePage({sources},{subcategory:'environment'}).total,30);
  assert.equal(sourcePage({sources},{subcategory:'environment',offset:24}).items.length,6);
  assert.equal(typeLabel({kind:'model'}),'Model · unclassified');
  assert.equal(referenceImage('atlas.png'),false);assert.equal(referenceImage('thumbnail.png'),true);
  assert.equal(motionSummary({metadata:{}}),'');
});
