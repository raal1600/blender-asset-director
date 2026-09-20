import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {scopeKinds,inScope} from '../public/workbench-scope.mjs';
import {sourcePage} from '../lib/source-browser.mjs';
import {pinnedPage,ingredientsView} from '../public/workbench-browser.mjs';
import {catalogDialog} from '../public/workbench-library.mjs';
import {evidenceView} from '../public/workbench-evidence.mjs';
import {createApp} from '../server.mjs';
import {Runtime} from '../lib/runtime.mjs';
const esc=v=>String(v??''),b=(label,action,data,cls,disabled)=>'<button data-action="'+action+'" '+(disabled?'disabled':'')+'>'+label+'</button>';
test('workflow kinds separate world ingredients, movement and look without moving originals',()=>{
  assert.deepEqual(scopeKinds('world'),['model','pack']);
  assert.deepEqual(scopeKinds('world',true),['Meshes','Characters']);
  assert.deepEqual(scopeKinds('action'),['animation']);
  assert.deepEqual(scopeKinds('action',true),['Animations']);
  assert.deepEqual(scopeKinds('light'),['material','hdri']);
  assert.deepEqual(scopeKinds('light',true),[]);
  assert.ok(!inScope({kind:'animation'},'world'));
  assert.ok(inScope({kind:'animation'},'all'));
  assert.throws(()=>scopeKinds('wrong'));
});
test('workflow filtering happens before source pagination and selection filtering',()=>{
  const sources=Array.from({length:1000},(_,i)=>({id:String(i),name:String(i).padStart(4,'0'),kind:i%2?'Animations':'Meshes'}));
  const before=JSON.stringify(sources);
  const world=sourcePage({sources},{activity:'world',offset:24});
  assert.equal(world.total,500);assert.equal(world.items.length,24);assert.equal(world.items[0].id,'48');
  assert.equal(sourcePage({sources},{activity:'action',query:'0999'}).total,1);
  assert.equal(sourcePage({sources},{activity:'world',query:'0999'}).total,0);
  assert.equal(sourcePage({sources},{activity:'action',selectedIds:['0','1']}).items[0].id,'1');
  assert.equal(sourcePage({sources},{activity:'light'}).total,0);
  assert.throws(()=>sourcePage({sources},{activity:'wrong'}));assert.equal(JSON.stringify(sources),before);
});
test('selected summaries keep animation out of World without dropping its pin',()=>{
  const pins=[{id:'model',title:'Prop',kind:'model'},{id:'motion',title:'Walk',kind:'animation'}];
  const scene={stage:'world',sources:[],catalog:['model','motion'],checkpoints:[]};
  const project={workbench:{catalogPins:pins}};
  assert.equal(pinnedPage(project,scene,{activity:'world'}).total,1);
  assert.equal(pinnedPage(project,scene,{activity:'action'}).items[0].id,'motion');
  const html=ingredientsView({project,scene,inventory:{sources:[]},esc,b});
  assert.match(html,/Other activities: 1 selected/);assert.ok(!html.includes('>Walk<'));
  assert.equal(project.workbench.catalogPins.length,2);
});
test('Action inspector offers reviewed motion guidance, not World import',()=>{
  const asset={id:'motion',version:'b'.repeat(64),kind:'animation',models:['motion.fbx'],policy:{eligible:true}};
  const scene={stage:'action',catalog:['motion']};
  const view=catalogDialog({asset,scene,locked:false,sourceReady:true,esc,b});
  assert.match(view.body,/Selection does not apply motion/);
  assert.match(view.body,/exact reviewed transfer plan/);assert.ok(!view.buttons.includes('catalog-import'));
});
test('checkpoint panel explains actual saved evidence and does not fake animation',()=>{
  const scene={stage:'world',renders:[],checkpoints:[],current:null,candidate:null};
  const blank=evidenceView({scene,checkpoint:null,esc,b});
  assert.match(blank,/No saved scene yet/);assert.ok(!blank.includes('<img')&&!blank.includes('data-action="preview"'));
  const checkpoint={id:'cp_example'};scene.current=checkpoint.id;
  const missing=evidenceView({scene,checkpoint,esc,b,canPreview:true});
  assert.match(missing,/No preview for this checkpoint/);assert.match(missing,/View saved scene in 3D/);
  assert.match(missing,/No verified camera/);assert.match(missing,/data-action="preview" disabled/);
  scene.stage='action';scene.preview={checkpointId:checkpoint.id};
  const still=evidenceView({scene,checkpoint,esc,b,canPreview:false});
  assert.match(still,/data-media="preview"/);assert.match(still,/Playback is inspection, not approval/);assert.match(still,/disabled/);
  checkpoint.audit={objects:[{name:'RealCamera',type:'CAMERA'}]};
  assert.match(evidenceView({scene,checkpoint,esc,b,canPreview:true}),/data-action="preview" >/);
  scene.preview.checkpointId='old';assert.ok(!evidenceView({scene,checkpoint,esc,b}).includes('<img'));
});
test('only new workbench is served; authenticated grouped catalog queries preserve detail API',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-scoped-http-')),calls=[];
  const runtime={health:null,harness:async args=>{calls.push(args);return args.includes('--asset')?{id:args[args.indexOf('--asset')+1]}:{items:[],total:0,offset:0,next_offset:null};}};
  const app=await createApp({root,config:{},runtime,port:0});
  t.after(async()=>{await new Promise(r=>app.server.close(r));await fs.rm(root,{recursive:true,force:true});});
  const p=await app.store.create('Synthetic scope production'),headers={Authorization:'Bearer '+app.token};
  for(const route of ['/','/index.html','/workbench']){
    const r=await fetch(app.origin+route);assert.equal(r.status,200);const html=await r.text();
    assert.match(html,/workbench.mjs/);assert.ok(!html.includes('Legacy launcher'));
  }
  for(const route of ['/app.mjs','/style.css'])assert.equal((await fetch(app.origin+route)).status,404);
  const url=app.origin+'/api/workbench/catalog?projectId='+p.id;
  assert.equal((await fetch(url+'&activity=world')).status,401);
  assert.equal((await fetch(url+'&activity=world',{headers})).status,200);
  assert.deepEqual(calls.at(-1).slice(-3),['--kinds','model','pack']);
  await fetch(url+'&activity=action',{headers});assert.deepEqual(calls.at(-1).slice(-2),['--kinds','animation']);
  assert.equal((await fetch(url+'&activity=wrong',{headers})).status,400);
  const count=calls.length;
  const none=await (await fetch(url+'&activity=world&kind=animation',{headers})).json();
  assert.equal(none.total,0);assert.equal(calls.length,count);
  const aid='a_'+'a'.repeat(24);
  assert.equal((await fetch(app.origin+'/api/workbench/catalog-detail?projectId='+p.id+'&assetId='+aid,{headers})).status,200);
  assert.ok(calls.at(-1).includes('--asset'));
});
test('saved-file diagnostic audit refuses foreign and unknown files before native work',async()=>{
  let called=false;
  const fake={store:{get:async()=>({scene:null}),scenes:async()=>['Scenes/owned.blend']},harness:async()=>{called=true;}};
  for(const scene of ['../foreign.blend','Scenes/missing.blend',null,4]){
    await assert.rejects(Runtime.prototype.audit.call(fake,'project',scene),/saved file/);
  }
  assert.equal(called,false);
});
