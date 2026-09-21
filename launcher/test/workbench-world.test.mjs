import test from 'node:test';
import assert from 'node:assert/strict';
import {worldState,worldView,worldIngredients,addWorldAsset} from '../public/workbench-world.mjs';
import {worldCatalogDialog} from '../public/workbench-library.mjs';
const esc=v=>String(v??'').replaceAll('<','&lt;').replaceAll('"','&quot;');
const b=(label,action,data={},cls='',disabled=false)=>`<button class="${cls}" data-action="${action}" ${disabled?'disabled':''}>${esc(label)}</button>`;
const asset={id:'a_test',title:'Synthetic prop',kind:'model',version:'a'.repeat(64),models:['model.glb'],files:[{path:'model.glb',size:100}],policy:{eligible:true}};
const scene={id:'sc_test',name:'Test World',stage:'world',sources:[],catalog:[],checkpoints:[],completed:{},current:null,candidate:null};
const project={workbench:{scenes:[scene],catalogPins:[asset]}};
const base={project,scene,locked:false,sourceUse:{ready:true},runs:[]};
const checkpoint={id:'cp_test',sha256:'c'.repeat(64),audit:{objects:[{name:'Prop',asset_id:asset.id,type:'MESH'}]}};
const stages=['world','action','shots','light','render'].map(id=>({id,short:id,label:id}));
const view=patch=>worldView({...base,stages,cap:{task_workspace:true,render_frames:true},esc,b,...patch});

test('World guide derives each next step from saved evidence, not selection or completion flags',()=>{
  assert.equal(worldState(base).kind,'empty');
  assert.equal(worldState({...base,scene:{...scene,catalog:[asset.id]}}).kind,'add');
  assert.equal(worldState({...base,scene:{...scene,sources:['src_test']}}).kind,'package');
  assert.equal(worldState({...base,sourceUse:{ready:false}}).kind,'rights');
  const kept={...scene,catalog:[asset.id],current:checkpoint.id,checkpoints:[checkpoint]};
  assert.equal(worldState({...base,scene:kept}).kind,'ready');
  assert.equal(worldState({...base,scene:{...kept,candidate:checkpoint.id}}).kind,'review');
  assert.equal(worldState({...base,scene:{...kept,task:'task_test',candidate:checkpoint.id}}).kind,'editing');
  assert.equal(worldState({...base,scene:{...kept,run:'run_test'}}).kind,'working');
  assert.equal(worldState({...base,scene:kept,locked:true}).kind,'locked');
  assert.equal(worldState({...base,scene:{...scene,completed:{world:'historical'}}}).kind,'empty');
  assert.equal(worldState({...base,scene:kept}).pending.length,0);
  const unaudited={...kept,checkpoints:[{id:checkpoint.id,sha256:checkpoint.sha256}]};
  assert.equal(worldState({...base,scene:unaudited}).pending.length,0,'unknown audit must not prompt duplicate imports');
});

test('World stays compact, escapes data, retains details and offers one primary next action',()=>{
  for(const patch of [{},{scene:{...scene,catalog:[asset.id]}},{sourceUse:{ready:false}},{scene:{...scene,candidate:checkpoint.id,checkpoints:[checkpoint]}},{scene:{...scene,current:checkpoint.id,checkpoints:[checkpoint]}}]){
    const html=view(patch);assert.equal((html.match(/class="primary"/g)||[]).length,1);
    assert.match(html,/aria-label="Selected scene"/);assert.match(html,/Details|Scene details/);
    assert.match(html,/aria-current="step"/);assert.doesNotMatch(html,/data-action="codex"[^>]*class="primary"/);
  }
  assert.match(view({project:{...project,workbench:{...project.workbench,scenes:[{...scene,name:'<unsafe> name'}]}}}),/&lt;unsafe>/);
  const review=view({scene:{...scene,candidate:checkpoint.id,checkpoints:[checkpoint]}});
  assert.match(review,/New change · not kept/);assert.match(review,/Keep this change/);assert.match(review,/Discard change/);
  assert.doesNotMatch(review,/data-action="approve"/);
  const locked=view({locked:true});assert.doesNotMatch(locked,/class="primary"/);
  assert.match(view({cap:{task_workspace:false}}),/data-action="browse-assets" disabled/);
  assert.match(view({runs:[{id:'failed',sceneId:scene.id,state:'FAILED',error:'<unsafe failure>'}]}),/&lt;unsafe failure>/);
  assert.match(view({runs:[{id:'failed',sceneId:scene.id,state:'FAILED'}]}),/Inspect \/ recover attempt/);
  assert.doesNotMatch(view({runs:[{id:'failed',sceneId:scene.id,state:'FAILED',recovery:{state:'RECOVERED'}}]}),/Inspect \/ recover attempt/);
});

test('cancelled add has no pin, rights approval, job or import side effects',async()=>{
  const calls=[];const result=await addWorldAsset({selected:false,confirm:()=>false,pin:()=>calls.push('pin'),reload:()=>calls.push('reload'),run:()=>calls.push('run')});
  assert.equal(result,'cancelled');assert.deepEqual(calls,[]);
});

test('add may pin exact source but stops for fresh rights review; no dependent job runs',async()=>{
  const calls=[];const result=await addWorldAsset({selected:false,confirm:()=>true,pin:()=>calls.push('pin'),reload:()=>{calls.push('reload');return {sourceUse:{ready:false}};},sourceReady:true,run:()=>calls.push('run')});
  assert.equal(result,'needs-rights');assert.deepEqual(calls,['pin','reload']);
  await assert.rejects(addWorldAsset({selected:false,confirm:()=>true,pin:async()=>{throw Error('stale revision');},run:()=>calls.push('run')}),/stale revision/);
  assert.ok(!calls.includes('run'));
});

test('confirmed, already selected and reviewed source executes exactly once',async()=>{
  let calls=0;const result=await addWorldAsset({selected:true,sourceReady:true,confirm:()=>true,pin:()=>assert.fail('already pinned'),run:()=>calls++});
  assert.equal(result,'started');assert.equal(calls,1);
});

test('World detail keeps rights, active-work and exact collection requirements visible',()=>{
  const args={asset,scene,locked:false,sourceReady:true,esc,b};
  assert.match(worldCatalogDialog(args).buttons,/Add to world/);
  assert.match(worldCatalogDialog({...args,scene:{...scene,catalog:[asset.id]},sourceReady:false}).buttons,/Review source use/);
  assert.match(worldCatalogDialog({...args,asset:{...asset,policy:{eligible:false}}}).buttons,/disabled/);
  assert.match(worldCatalogDialog({...args,scene:{...scene,candidate:'cp'}}).buttons,/disabled/);
  assert.match(worldCatalogDialog({...args,scene:{...scene,run:'run'}}).buttons,/disabled/);
  const blend={...asset,models:['first.blend','second.blend'],files:[{path:'first.blend',size:1},{path:'second.blend',size:1}]};
  const inspected={...scene,assetContents:{[asset.id]:{version:asset.version,file:'first.blend',collections:['Observed']}}};
  assert.match(worldCatalogDialog({...args,asset:blend,scene:inspected}).body,/name="catalog-collection"/);
  const other=worldCatalogDialog({...args,asset:blend,scene:inspected,fileChoice:'second.blend'});
  assert.match(other.buttons,/Inspect collections/);assert.doesNotMatch(other.body,/name="catalog-collection"/);
  assert.match(worldCatalogDialog({...args,scene:{...scene,current:checkpoint.id,checkpoints:[checkpoint]}}).buttons,/Add another copy/);
});

test('multiple choices, observed imports, packages and unknown saved files have distinct status',()=>{
  const second={...asset,id:'a_second',title:'Second prop'},source={id:'src_package',name:'Terrain package',kind:'Meshes'};
  const p={workbench:{catalogPins:[asset,second]}};
  const chosen={...scene,catalog:[asset.id,second.id],sources:[source.id]};
  let rows=worldIngredients({project:p,scene:chosen,inventory:{sources:[source]}});
  assert.equal(rows.toAdd,2);assert.equal(rows.inScene,0);assert.equal(rows.packages,1);
  assert.ok(rows.rows.slice(0,2).every(r=>r.status==='Selected · not imported'));
  const kept={...chosen,current:checkpoint.id,checkpoints:[checkpoint]};
  rows=worldIngredients({project:p,scene:kept});assert.equal(rows.inScene,1);assert.equal(rows.toAdd,1);
  const combined={id:'cp_combined',parent:checkpoint.id,audit:{objects:[...checkpoint.audit.objects,{asset_id:second.id,type:'MESH'}]}};
  rows=worldIngredients({project:p,scene:{...kept,candidate:combined.id,checkpoints:[checkpoint,combined]}});
  assert.equal(rows.inScene,2);assert.equal(rows.toAdd,0);assert.ok(rows.rows.every(r=>r.status==='In candidate'));
  rows=worldIngredients({project:p,scene:{...kept,checkpoints:[{id:checkpoint.id,audit:null}]}});
  assert.equal(rows.inScene,0);assert.equal(rows.toAdd,0);assert.equal(rows.unknown,2);
  assert.ok(rows.rows.every(r=>r.status==='Presence not verified'));
  rows=worldIngredients({project:p,scene:{...kept,catalog:[]}});
  assert.equal(rows.inScene,1,'deselecting a reference does not remove observed scene geometry');
});

test('Add assets is consistently discoverable without bypassing review or active writers',()=>{
  for(const patch of [{},{sourceUse:{ready:false}},{scene:{...scene,candidate:checkpoint.id,checkpoints:[checkpoint]}},{scene:{...scene,current:checkpoint.id,checkpoints:[checkpoint]}}]){
    const html=view(patch);
    assert.match(html,/data-action="browse-assets"[^>]*>Add assets<\/button>/);
    assert.match(html,/imported assets appear together here/);
    assert.match(html,/Only imported objects appear together/);
    assert.doesNotMatch(html,/Choose another asset/);
  }
  for(const patch of [{locked:true},{scene:{...scene,task:'task'}},{scene:{...scene,run:'run'}},{cap:{task_workspace:false}}]){
    assert.match(view(patch),/data-action="browse-assets" disabled>Add assets<\/button>/);
  }
});

test('ingredient strip is bounded, escaped and never guesses presence from a parent checkpoint',()=>{
  const pins=Array.from({length:100},(_,i)=>({...asset,id:'a_'+i,title:'<unsafe>'+i}));
  const html=view({project:{workbench:{scenes:[scene],catalogPins:pins}},scene:{...scene,catalog:pins.map(a=>a.id)}});
  assert.equal((html.match(/class="world-ingredient"/g)||[]).length,4);
  assert.match(html,/Ingredients \(100\)/);assert.match(html,/Browse all chosen ingredients/);assert.match(html,/&lt;unsafe>/);
  const unknown={...scene,current:checkpoint.id,catalog:[asset.id],candidate:'cp_unknown',checkpoints:[checkpoint,{id:'cp_unknown',parent:checkpoint.id,audit:null}]};
  assert.equal(worldIngredients({project,scene:unknown}).unknown,1);
  const detail=worldCatalogDialog({asset,scene:unknown,locked:false,sourceReady:true,esc,b});
  assert.match(detail.body,/Presence in saved scene not verified/);assert.doesNotMatch(detail.body,/Preview · not in scene/);
  assert.match(detail.body,/Single-asset preview/);assert.match(detail.body,/combines this asset with your existing saved scene/);
});
