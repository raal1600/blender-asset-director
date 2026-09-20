import test from 'node:test';
import assert from 'node:assert/strict';
import {worldState,worldView,addWorldAsset} from '../public/workbench-world.mjs';
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
