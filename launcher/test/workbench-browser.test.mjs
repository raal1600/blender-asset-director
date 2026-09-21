import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {sourcePage,selectedSourceSummary} from '../lib/source-browser.mjs';
import {pinnedPage,ingredientsView,browserView,ingredientStatus,sourceDialog,libraryViewCounts,browserPage} from '../public/workbench-browser.mjs';
import {createApp} from '../server.mjs';
import {writeJson,fileHash} from '../lib/storage.mjs';
const sid=i=>'src_00000000-0000-4000-8000-'+String(i).padStart(12,'0');
const aid=i=>'a_'+i.toString(16).padStart(24,'0');
const source=i=>({id:sid(i),name:'Package '+String(i).padStart(5,'0'),kind:i%2?'Animations':'Meshes',version:'a'.repeat(64),available:i!==3,review:'UNREVIEWED',fileCount:100,bytes:1000,entrypoints:Array(100).fill('private/original.obj')});
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const b=(label,action,data={},cls='',disabled=false)=>'<button data-action="'+action+'" '+(disabled?'disabled':'')+'>'+esc(label)+'</button>';
const scene={id:'scene',name:'Synthetic scene',sources:[sid(0)],catalog:[aid(0)],checkpoints:[],current:null,candidate:null};
const project={workbench:{catalogPins:[{id:aid(0),title:'Synthetic model',kind:'model',version:'b'.repeat(64),files:[{path:'not-for-summary'}]}],scenes:[scene]}};

const completePage=items=>({items,total:items.length,offset:0,next_offset:null});
const browserUI=extra=>({activity:'world',tab:'catalog',production:false,query:'',kind:{catalog:'',sources:''},offset:{catalog:0,sources:0},selected:false,layout:'grid',...extra});
test('distinct view counts use matching totals and keep unavailable counts unknown',()=>{
  const page={items:[],total:10000,offset:24,next_offset:48};
  assert.deepEqual(libraryViewCounts(completePage([]),page),{production:0,library:10000});
  assert.deepEqual(libraryViewCounts(page,{error:'Unavailable'}),{production:10000,library:null});
  assert.deepEqual(libraryViewCounts(null,completePage([])),{production:null,library:0});
});
test('catalog scope counts use full matching pins and one bounded shared-catalog query without mutation',async()=>{
  const before=JSON.stringify(project),calls=[];
  const api=async route=>{calls.push(route);assert.equal(new URL('http://fixture/'+route).searchParams.get('excludeProduction'),'true');return completePage([]);};
  for(const production of [false,true]){
    const result=await browserPage({project,scene,ui:browserUI({production}),api});
    assert.deepEqual(result.locations,{production:1,library:0});
    assert.equal(result.items.length,production?1:0);
    if(production)assert.equal(result.items[0].pinnedOnly,true);
  }
  assert.equal(calls.length,2);assert.ok(calls.every(r=>r.startsWith('workbench/catalog?')));
  assert.equal(JSON.stringify(project),before);
});
test('source scopes keep independent counts and use the same search/category/workflow before paging',async()=>{
  const calls=[],api=async route=>{
    calls.push(route);const q=new URL('http://fixture/'+route).searchParams;
    assert.equal(q.get('activity'),'world');assert.equal(q.get('query'),'Package');assert.equal(q.get('subcategory'),'environment');
    assert.equal(q.get('excludeProduction'),String(q.get('production')!=='true'));
    return completePage(q.get('production')==='true'?[source(0)]:[source(2)]);
  };
  const result=await browserPage({project,scene,ui:browserUI({tab:'sources',query:'Package',subcategory:'environment',production:true}),api});
  assert.deepEqual(result.locations,{production:1,library:1});assert.equal(result.items.length,1);assert.equal(calls.length,2);
});
test('unavailable comparison does not hide retained production references or pretend zero assets',async()=>{
  const api=async()=>{throw new Error('Synthetic library unavailable');};
  const result=await browserPage({project,scene,ui:browserUI({production:true}),api});
  assert.deepEqual(result.locations,{production:1,library:null});assert.equal(result.items.length,1);
  await assert.rejects(browserPage({project,scene,ui:browserUI(),api}),/Synthetic library unavailable/);
});
test('selected-only list does not redefine production membership or claim matching scene presence',async()=>{
  const s={...scene,catalog:[]},ui=browserUI({production:true,selected:true});
  const result=await browserPage({project,scene:s,ui,api:async()=>completePage(project.workbench.catalogPins)});
  assert.equal(result.total,0);assert.equal(result.locations.production,1);
  const html=browserView({ui,page:result,project,scene:s,locked:false,esc,b});
  assert.match(html,/Selected references for this scene/);assert.doesNotMatch(html,/class="browser-same"/);
});
test('scope controls present added versus available and never promise duplicate lists',()=>{
  const page={...completePage([]),locations:{production:1,library:0}};
  for(const production of [false,true]){
    const html=browserView({ui:browserUI({production}),page,project,scene,locked:false,esc,b});
    assert.match(html,/This production <span class="location-count">\(1\)/);
    assert.match(html,/My library <span class="location-count">\(0\)/);
    assert.match(html,/Added to production/);assert.match(html,/Available to add/);
    assert.doesNotMatch(html,/Same assets in both views/);assert.match(html,/Shared files stay in the library/);
    assert.doesNotMatch(html,/downloaded into this production/i);
  }
});
test('empty states offer the other distinct view and never treat a failed load as an exhausted library',()=>{
  const empty={...completePage([]),locations:{production:1,library:0}};
  const view=(ui,page)=>browserView({ui:browserUI(ui),page,project,scene,locked:false,esc,b});
  assert.match(view({},empty),/Already in this production/);
  assert.match(view({},empty),/View This production/);
  assert.match(view({production:true},empty),/Browse My library/);
  assert.match(view({query:'missing'},empty),/No matching assets/);
  assert.doesNotMatch(view({query:'missing'},empty),/Already in this production/);
  assert.doesNotMatch(view({},{error:'Synthetic failure'}),/Already in this production|No assets to add/);
});

test('source exclusions precede search, workflow and paging without dropping matching available records',()=>{
  const sources=Array.from({length:10000},(_,i)=>source(i)),before=JSON.stringify(sources);
  const excludedIds=sources.slice(0,48).map(a=>a.id);
  const page=sourcePage({sources},{activity:'world',excludedIds});
  assert.equal(page.total,4976);assert.equal(page.items.length,24);assert.equal(page.items[0].id,sid(48));
  assert.equal(sourcePage({sources},{query:'00002',excludedIds}).total,0);
  const last=sourcePage({sources},{excludedIds,offset:999999});assert.equal(last.next_offset,null);assert.ok(last.items.length);
  assert.equal(JSON.stringify(sources),before);
});
test('loading filters are disabled for keyboard as well as pointer interaction',()=>{
  const ui={tab:'catalog',query:'',kind:{catalog:'',sources:''},selected:false,layout:'grid'};
  const html=browserView({ui,page:null,project,scene,locked:false,esc,b});
  for(const id of ['browser-query','browser-activity','browser-kind','browser-subcategory','browser-scope'])assert.match(html,new RegExp('id="'+id+'" disabled'));
  assert.match(html,/aria-busy="true"/);
  assert.match(html,/Loading assets/);
  assert.doesNotMatch(html,/No matching assets/);
});
test('source paging bounds 0/1/24/25/1000/10000 records and does not expose file lists',()=>{
  for(const count of [0,1,24,25,1000,10000]){
    const registry={schema:1,sources:Array.from({length:count},(_,i)=>source(i))},before=JSON.stringify(registry);
    const first=sourcePage(registry);assert.equal(first.total,count);assert.equal(first.items.length,Math.min(count,24));
    assert.equal(first.next_offset,count>24?24:null);
    assert.ok(first.items.every(a=>!('entrypoints' in a)));
    const last=sourcePage(registry,{offset:999999});assert.ok(last.items.length<=24);
    assert.equal(last.next_offset,null);assert.equal(JSON.stringify(registry),before);
  }
});
test('source filters search the full registry, preserve unavailable records and stable ordering',()=>{
  const registry={sources:Array.from({length:1000},(_,i)=>source(i))};
  assert.equal(sourcePage(registry,{query:'00999',kind:'Animations'}).items[0].id,sid(999));
  assert.equal(sourcePage(registry,{query:'00999',kind:'Meshes'}).total,0);
  assert.deepEqual(sourcePage(registry,{selectedIds:[sid(3),sid(999)]}).items.map(a=>a.id),[sid(3),sid(999)]);
  for(const options of [{offset:-1},{offset:NaN},{offset:1.5},{query:'a'.repeat(2001)},{kind:'unknown'}])assert.throws(()=>sourcePage(registry,options));
});
test('compact inventory keeps only selected summaries; legacy registry is not changed',()=>{
  const inventory={schema:1,sources:Array.from({length:10000},(_,i)=>source(i))};
  const result=selectedSourceSummary(inventory,project);
  assert.equal(result.total,10000);assert.equal(result.sources.length,1);assert.equal(result.sources[0].id,sid(0));
  assert.equal(result.sources[0].entrypoints,undefined);assert.equal(inventory.sources.length,10000);
});
test('selected native view pages immutable pins, not rights or import authority',()=>{
  const p=structuredClone(project),s=structuredClone(scene);
  p.workbench.catalogPins=Array.from({length:60},(_,i)=>({id:aid(i),title:'Clip '+String(i).padStart(3,'0'),kind:'animation',files:[{path:'original'}]}));s.catalog=p.workbench.catalogPins.map(a=>a.id);
  const page=pinnedPage(p,s,{offset:24,kind:'animation'});assert.equal(page.items.length,24);assert.equal(page.next_offset,48);assert.ok(page.items.every(a=>a.pinnedOnly&&!a.files&&!a.policy));
  assert.equal(pinnedPage(p,s,{query:'059'}).total,1);assert.equal(pinnedPage(p,s,{kind:'model'}).total,0);
});
test('scene panel remains compact and never claims selection imported an object',()=>{
  const s={...scene,catalog:Array.from({length:100},(_,i)=>aid(i))};
  const p={workbench:{catalogPins:s.catalog.map(id=>({id,title:'<unsafe> source',kind:'model'}))}};
  const html=ingredientsView({project:p,scene:s,inventory:{sources:[source(0)]},esc,b});
  assert.equal((html.match(/class="ingredient"/g)||[]).length,4);assert.ok(html.includes('Selected for this activity (101)'));
  assert.ok(html.includes('&lt;unsafe&gt;'));assert.ok(!html.includes('data-catalog-image'));
  assert.equal(ingredientStatus(scene,aid(0)),'Selected · not imported');
  const observed={...scene,current:'cp',checkpoints:[{id:'cp',audit:{objects:[{asset_id:aid(0)}]}}]};
  assert.equal(ingredientStatus(observed,aid(0)),'In checkpoint');
  assert.equal(ingredientStatus({...observed,checkpoints:[{id:'cp',audit:null}]},aid(0)),'Presence not verified');
});
test('motion uses compact honest placeholders and browser exposes one search and explicit source tabs',()=>{
  const ui={tab:'catalog',query:'',kind:{catalog:'animation',sources:''},selected:false,layout:'grid'};
  const html=browserView({ui,page:{items:[{id:aid(0),title:'Motion <clip>',kind:'animation',package_images:['atlas.png']}],offset:0,total:1,next_offset:null},project,scene,locked:false,esc,b});
  assert.ok(!html.includes('data-catalog-image'));assert.ok(!html.includes('browser-results list'));
  assert.match(html,/data-layout="grid" aria-pressed="true"/);
  const list=browserView({ui:{...ui,layout:'list'},page:{items:[],total:0,offset:0,next_offset:null},project,scene,locked:false,esc,b});
  assert.match(list,/browser-results list/);assert.match(list,/data-layout="list" aria-pressed="true"/);
  assert.equal((html.match(/id="browser-query"/g)||[]).length,1);assert.match(html,/Source packages/);
  assert.match(html,/Motion &lt;clip&gt;/);
  const detail=sourceDialog({source:source(3),scene,locked:false,esc,b});
  assert.match(detail.buttons,/disabled/);assert.ok(!detail.buttons.includes('catalog-import'));
});
test('paged source HTTP is authenticated, read-only, compact opt-in and compatible with the legacy state',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-library-browser-'));
  const runtime={health:null,harness:async()=>({schema:1,catalog:true,task_workspace:true})};
  const app=await createApp({root,config:{},port:0,runtime});
  for(const module of ['library-usage.mjs','library-preparation.mjs']) {
    const response=await fetch(app.origin+'/'+module);assert.equal(response.status,200);
    assert.match(response.headers.get('content-type'),/javascript/);
  }
  t.after(async()=>{await new Promise(r=>app.server.close(r));await fs.rm(root,{recursive:true,force:true});});
  const p=await app.store.create('Synthetic browser production'),created=await app.workbench.create(p.id,p.revision,'Synthetic scene');
  const registry=path.join(root,'Database/Registry/sources.json');
  await writeJson(registry,{schema:1,sources:Array.from({length:1000},(_,i)=>source(i))});
  const before=await fileHash(registry),manifest=await fileHash(path.join(p.directory,'project.json'));
  const headers={Authorization:'Bearer '+app.token};
  assert.equal((await fetch(app.origin+'/api/workbench/sources?projectId='+p.id)).status,401);
  const progress=await fetch(app.origin+'/workbench-progress.mjs');assert.equal(progress.status,200);
  assert.match(await progress.text(),/export const progressLabel/);
  const get=async route=>{const r=await fetch(app.origin+'/api/'+route,{headers});assert.equal(r.status,200);return r.json();};
  assert.equal((await get('state?compact=true')).inventory,undefined);
  assert.equal((await get('state')).inventory.sources.length,1000);
  assert.equal((await get('workbench/state?compact=true&projectId='+p.id)).inventory.sources.length,0);
  assert.equal((await get('workbench/state?projectId='+p.id)).inventory.sources.length,1000);
  const page=await get('workbench/sources?projectId='+p.id+'&offset=24');assert.equal(page.items.length,24);assert.equal(page.total,1000);assert.equal(page.offset,24);
  const detail=await get('workbench/source-detail?projectId='+p.id+'&sourceId='+sid(3));assert.equal(detail.entrypoints.length,100);
  assert.equal((await get('workbench/sources?projectId='+p.id+'&sceneId='+created.sceneId+'&selected=true')).total,0);
  assert.equal((await fetch(app.origin+'/api/workbench/sources?projectId='+p.id+'&offset=-1',{headers})).status,400);
  assert.equal((await fetch(app.origin+'/api/workbench/source-detail?projectId='+p.id+'&sourceId=../../outside',{headers})).status,400);
  assert.deepEqual(await fileHash(registry),before);assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),manifest);
});
