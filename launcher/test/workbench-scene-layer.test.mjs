import test from 'node:test';
import assert from 'node:assert/strict';
import {sceneLayerDraft,layerInspection,ensureLayerInspection,sceneLayerView,cameraForm} from '../public/workbench-scene-layer.mjs';
const cp={id:'cp_saved',sha256:'saved-hash'};
test('older scenes without optional shot metadata display Shots and Light without rewriting the scene',()=>{
 for(const stage of ['shots','light']){
  const scene={id:'scene',name:'Older scene',stage,current:cp.id,checkpoints:[cp],completed:{},renders:[]},original=structuredClone(scene);
  const html=sceneLayerView({project:{workbench:{scenes:[scene]}},scene,checkpoint:cp,stages:[],runs:[],locked:false,cap:{scene_layer:'scene-layer-v1'},draft:null,esc:v=>String(v??''),b:(t,a,d,c,disabled)=>'<button data-action="'+a+'" '+(disabled?'disabled':'')+'>'+t+'</button>'});
  assert.match(html,stage==='shots'?/Frame your story/:/Light your scene/);assert.deepEqual(scene,original);assert.equal(Object.hasOwn(scene,'shots'),false);
  assert.match(html,/data-action="layer-ready" disabled/);assert.doesNotMatch(html,/data-media="preview"/);
 }
});
const run={id:'run_inspect',inspection:{layer:'light',sha256:'audit-hash',scene:{frame_range:[1,9],objects:[{name:'Body',type:'MESH'},{name:'Camera',type:'CAMERA'}]},cameras:[],look:{state:{lights:[{name:'Key',type:'AREA',energy:200,size:2,color:[1,.5,.2],location:[1,2,3]},{name:'Fill',type:'POINT',energy:25,shadow_soft_size:1,color:[1,1,1],location:[0,0,1]},{name:'Linked',type:'AREA',energy:10,unsupported:'Linked data'}],world:{background_strength:.2},color_management:{exposure:.5}},editable:{world:['strength'],color_management:['exposure']}}}};
test('shared-light local draft batches only explicitly changed observed values, undo/discard and immutable request',()=>{
 const original=structuredClone(run),draft=sceneLayerDraft(cp,run);assert.equal(draft.selected,'Key');assert.equal(draft.dirty,false);
 draft.changeLight('Key','energy','300');draft.select('Fill');draft.changeLight('Fill','color',[.2,.4,.6]);draft.changeSetting('world','strength','.4');draft.changeSetting('look','exposure',1);
 assert.equal(draft.operations.length,3);const request=draft.request('run_save');assert.equal(request.inspectionId,run.id);assert.equal(request.checkpointId,cp.id);assert.equal(request.sha256,cp.sha256);assert.equal(request.audit_sha256,run.inspection.sha256);
 assert.deepEqual(request.operations[0].options.lights,[{name:'Key',energy:300},{name:'Fill',color:[.2,.4,.6]}]);
 request.operations[0].options.lights[0].energy=999;assert.equal(draft.value('Key').energy,300);draft.undo();assert.equal(draft.setting('look','exposure'),.5);
 draft.changeLight('Key','energy',200);assert.equal(draft.value('Key').energy,200);draft.discard();assert.equal(draft.dirty,false);assert.deepEqual(run,original);
});
test('draft refuses foreign/unsupported/type-inapplicable/nonfinite/empty edits without losing valid choices',()=>{
 const draft=sceneLayerDraft(cp,run);draft.changeLight('Key','energy',250);const valid=draft.operations;
 for(const [name,key,value] of [['Unknown','energy',1],['Linked','energy',1],['Key','script','x'],['Fill','size',1],['Key','energy',''],['Key','energy',Infinity],['Key','color',[1,2,0]],['Key','location',[1,2]]])assert.throws(()=>draft.changeLight(name,key,value));
 assert.throws(()=>draft.changeSetting('world','color',[1,1,1]));assert.throws(()=>draft.changeSetting('look','exposure',-101));assert.deepEqual(draft.operations,valid);
 const unsupported=structuredClone(run);unsupported.inspection.look.editable.world=[];assert.throws(()=>sceneLayerDraft(cp,unsupported).changeSetting('world','strength',1),/Blender/);
});
test('typing in a light field is one Undo gesture, while separate committed edits remain distinct',()=>{
 const draft=sceneLayerDraft(cp,run);draft.changeLight('Key','energy',3);draft.changeLight('Key','energy',35);draft.changeLight('Key','energy',350);draft.finishEdit();draft.undo();assert.equal(draft.value('Key').energy,200);
 draft.changeLight('Key','energy',300);draft.finishEdit();draft.changeLight('Key','energy',400);draft.finishEdit();draft.undo();assert.equal(draft.value('Key').energy,300);draft.undo();assert.equal(draft.dirty,false);
});
test('new camera binds observed subjects/range and explicit direction/lens; no orbit or existing camera mutation',()=>{
 const shotRun=structuredClone(run);shotRun.inspection.layer='shots';const draft=sceneLayerDraft(cp,shotRun),choice={name:'Close',subjects:['Body'],direction:[1,-2,1],lens:65,frame:5};
 draft.fitCamera(choice);assert.deepEqual(draft.request('run_save').operations,[{operation:'camera-fit',name:'Close',options:{subjects:['Body'],frames:[5],direction:[1,-2,1],lens_mm:65,margin:.1,projection:'PERSP'}}]);
 for(const change of [{name:'Camera'},{name:'é'.repeat(32)},{subjects:['Foreign']},{subjects:['Camera']},{subjects:['Body','Body']},{frame:20},{frame:1.5},{direction:[0,0,0]},{lens:''},{projection:'PANO'}])assert.throws(()=>draft.fitCamera({...choice,...change}));
 assert.throws(()=>draft.changeLight('Key','energy',400),/Light/);draft.undo();assert.equal(draft.dirty,false);
 assert.match(cameraForm(draft,String),/What should this camera frame/);assert.doesNotMatch(cameraForm(draft,String),/value="Body" checked/);
});
test('inspection reuse binds layer/scene/checkpoint/hash and retries only read-context conflict once',async()=>{
 const scene={id:'scene',stage:'light',current:cp.id,checkpoints:[cp]},row={...run,action:'scene-layer-audit',sceneId:'scene',checkpointId:cp.id,checkpointSha256:cp.sha256,state:'SUCCEEDED',options:{layer:'light'}};
 assert.equal(layerInspection([row],scene,cp),row);for(const wrong of [{...scene,id:'other'},{...scene,stage:'shots'}])assert.equal(layerInspection([row],wrong,cp),null);assert.equal(layerInspection([row],scene,{...cp,sha256:'other'}),null);
 const state={project:{revision:1,workbench:{scenes:[scene]}},runs:[],locked:false},args={sceneId:'scene',checkpointId:cp.id,sha256:cp.sha256,layer:'light',read:async()=>structuredClone(state)};let calls=0;
 await ensureLayerInspection({...args,create:async()=>{calls++;state.runs.push({...row,state:'RUNNING'});throw Object.assign(Error('Changed'),{status:409});}});assert.equal(calls,1);
 state.runs[0].state='FAILED';await ensureLayerInspection({...args,create:()=>assert.fail('No implicit failed-job retry')});state.runs=[];calls=0;
 await assert.rejects(ensureLayerInspection({...args,create:async()=>{calls++;throw Object.assign(Error('Changed'),{status:409});}}),/Changed/);assert.equal(calls,2);
 state.project.workbench.scenes[0].stage='world';await ensureLayerInspection({...args,create:()=>assert.fail('No foreign-layer inspection')});
});
test('progressive Light identifies shared scope and saved approximation, and keeps approvals separate',()=>{
 const draft=sceneLayerDraft(cp,run);draft.changeLight('Key','energy',300);const scene={id:'scene',name:'Synthetic',stage:'light',current:cp.id,checkpoints:[cp],shots:[{id:'shot',name:'Wide',camera:'Camera',start:1,end:9,revision:1},{id:'shot2',name:'Close',camera:'Camera2',start:1,end:9,revision:1}],selectedShot:'shot',completed:{},renders:[]};
 const html=sceneLayerView({project:{workbench:{scenes:[scene]}},scene,checkpoint:cp,stages:[],runs:[],locked:false,cap:{scene_layer:'scene-layer-v1'},draft,esc:v=>String(v??''),b:(t,a)=>'<button data-action="'+a+'">'+t+'</button>'});
 assert.match(html,/Light your scene/);assert.match(html,/still the saved scene/);assert.match(html,/Wide, Close/);assert.match(html,/not an approval|separate from marking/);assert.match(html,/Preview lighting/);assert.doesNotMatch(html,/asset shelf|Keep checkpoint|Collect checkpoint/);
});
