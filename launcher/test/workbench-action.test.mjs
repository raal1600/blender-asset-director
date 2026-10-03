import test from 'node:test';
import assert from 'node:assert/strict';
import {actionDraft,actionInspection,actionView,ensureActionInspection} from '../public/workbench-action.mjs';
const cap={implementation:'e'.repeat(64),action_layer:'action-layer-v1'};
const cp={id:'cp_saved',sha256:'hash'},run={id:'run_inspect',implementation:cap.implementation,inspection:{version:'action-layer-v1',sha256:'audit',fps:24,reference_frame:5,frame_range:[1,9],unassigned:[],performers:[{name:'One',takes:[{id:'take_one',action:'Observed',range:[1,9]}]},{name:'Two',takes:[{id:'take_two',action:'Other',range:[1,9]}]}]}};
test('automatic inspection refreshes stale read context once and reuses another tab receipt without duplicate execution',async()=>{
 const state={project:{revision:1,workbench:{scenes:[{id:'scene',stage:'action',current:cp.id,checkpoints:[cp]}]}},runs:[],locked:false};
 const args={sceneId:'scene',checkpointId:cp.id,sha256:cp.sha256,cap,read:async()=>structuredClone(state)};
 let calls=0;
 await ensureActionInspection({...args,create:async()=>{calls++;state.project.revision++;state.runs.push({implementation:cap.implementation,action:'action-audit',sceneId:'scene',checkpointId:cp.id,checkpointSha256:cp.sha256,state:'RUNNING'});throw Object.assign(Error('Project changed'),{status:409});}});
 assert.equal(calls,1);state.runs[0].state='FAILED';await ensureActionInspection({...args,create:async()=>{throw Error('Failed job must not be retried');}});
 state.runs=[];state.project.workbench.scenes[0].current='cp_new';await ensureActionInspection({...args,create:async()=>{throw Error('Checkpoint change must not execute');}});
 state.project.workbench.scenes[0].current=cp.id;calls=0;
 await assert.rejects(ensureActionInspection({...args,create:async()=>{calls++;throw Object.assign(Error('Still changed'),{status:409});}}),/Still changed/);assert.equal(calls,2);
});
test('Action draft selects real performers, batches edits and never changes the source audit',()=>{
 const source=structuredClone(run),d=actionDraft(cp,run);assert.equal(d.selected,'One');assert.equal(d.dirty,false);
 d.change('One',{mode:'clip',take_id:'take_one',start:3,speed:2});d.select('Two');d.change('Two',{mode:'hold',frame:5});assert.equal(d.count,2);
 assert.deepEqual(d.request('run_save').changes,[{performer:'One',mode:'clip',take_id:'take_one',start:3,speed:2},{performer:'Two',mode:'hold',frame:5}]);
 d.undo();assert.equal(d.count,1);d.discard();assert.equal(d.dirty,false);assert.deepEqual(run,source);
 assert.throws(()=>d.change('Two',{mode:'clip',take_id:'take_one'}),/belong/);
 d.holdAll(4);assert.equal(d.changes.length,2);assert(d.changes.every(c=>c.frame===4));d.undo();assert.equal(d.dirty,false);
});
test('Action inspection never crosses scene or checkpoint identities',()=>{
 const rows=[{...run,action:'action-audit',sceneId:'scene',checkpointId:cp.id,checkpointSha256:cp.sha256,state:'SUCCEEDED'}];
 assert.equal(actionInspection(rows,{id:'scene'},cp,cap),rows[0]);assert.equal(actionInspection(rows,{id:'other'},cp,cap),null);assert.equal(actionInspection(rows,{id:'scene'},{...cp,sha256:'new'},cap),null);
});

test('unchanged checkpoint gets a new read-only inspection after runtime upgrade, preserving old receipts',async()=>{
 const old={...run,implementation:undefined,action:'action-audit',sceneId:'scene',checkpointId:cp.id,checkpointSha256:cp.sha256,state:'SUCCEEDED'};
 const original=structuredClone(old),scene={id:'scene',stage:'action',current:cp.id,checkpoints:[cp]},state={project:{revision:7,workbench:{scenes:[scene]}},runs:[old],locked:false};
 let calls=0;const args={sceneId:scene.id,checkpointId:cp.id,sha256:cp.sha256,cap,read:async()=>state,create:async rev=>{assert.equal(rev,7);calls++;}};
 assert.equal(actionInspection(state.runs,scene,cp,cap),null);await ensureActionInspection(args);assert.equal(calls,1);assert.deepEqual(old,original);
 state.runs=[{...old,implementation:'f'.repeat(64),state:'FAILED'}];await ensureActionInspection(args);assert.equal(calls,2);
 state.runs=[{...old,implementation:cap.implementation,state:'FAILED'}];await ensureActionInspection(args);assert.equal(calls,2,'Never auto-retry current-runtime failure');
 const fresh={...old,implementation:cap.implementation};state.runs=[old,fresh];assert.equal(actionInspection(state.runs,scene,cp,cap),fresh);
 await ensureActionInspection(args);assert.equal(calls,2);
 assert.equal(actionInspection(state.runs,scene,cp,{}),null,'Unknown runtime must fail closed');
});
test('manual and specialist handoff uses the selected saved performer and refuses unsaved choices',()=>{
 const d=actionDraft(cp,run);d.select('Two');assert.deepEqual(d.handoff(7),{version:'action-layer-v1',checkpointId:cp.id,sha256:cp.sha256,inspectionId:run.id,audit_sha256:run.inspection.sha256,performer:'Two',frame:7});
 assert.throws(()=>d.handoff(20),/frame/);d.change('Two',{mode:'hold',frame:5});assert.throws(()=>d.handoff(5),/Save or discard/);
});
test('timing drafts show and explicitly save an expanded full-take range instead of silent clipping',()=>{
 const d=actionDraft(cp,run);d.change('One',{mode:'clip',take_id:'take_one',start:20,speed:.5});assert.deepEqual(d.playbackRange,[1,36]);assert.deepEqual(d.request('run_save').frame_range,[1,36]);
 d.undo();assert.deepEqual(d.playbackRange,[1,9]);d.change('One',{mode:'clip',take_id:'take_one',start:4000,speed:1});assert.throws(()=>d.request('run_save'),/3600-frame/);
});
test('Action presentation stays performer-first and labels unsaved playback honestly',()=>{
 const d=actionDraft(cp,run);d.change('One',{mode:'hold',frame:5});
 const scene={id:'scene',stage:'action',name:'Generated',completed:{world:cp.id},checkpoints:[cp]};
 const html=actionView({project:{workbench:{scenes:[scene]}},scene,stages:[{id:'world',short:'World'},{id:'action',short:'Action'}],checkpoint:cp,runs:[],locked:false,cap:{...cap,task_workspace:true},draft:d,esc:v=>String(v??''),b:(t,a)=>'<button data-action="'+a+'">'+t+'</button>'});
 assert.match(html,/Performer<select/);assert.match(html,/Playback shows the saved scene/);assert.match(html,/Save changes to preview the new motion/);assert.match(html,/Hold a pose/);assert.doesNotMatch(html,/Inspect saved candidate|Keep checkpoint/);
});
test('Action timing rejects invalid direct changes before draft or history mutation',()=>{
 const d=actionDraft(cp,run),valid={mode:'clip',take_id:'take_one',start:1,speed:1};
 for(const patch of [{start:.1},{start:100001},{speed:0},{speed:4.1},{speed:Infinity},{speed:NaN},{speed:''},{speed:true}])assert.throws(()=>d.change('One',{...valid,...patch}),/Start frame|Speed/);
 assert.equal(d.dirty,false);assert.equal(d.canUndo,false);
 for(const frame of [0,10,1.5,NaN])assert.throws(()=>d.change('One',{mode:'hold',frame}),/Hold frame/);
 assert.throws(()=>d.holdAll(1.5),/Hold frame/);assert.equal(d.dirty,false);
});
test('invalid Action field text survives selection but cannot enter a request or make an infinite range',()=>{
 const d=actionDraft(cp,run);d.change('One',{mode:'clip',take_id:'take_one',start:1,speed:1});
 d.editTiming('One','speed','');assert.equal(d.invalid,true);assert.equal(d.input('One','speed'),'');assert.equal(d.value('One').speed,1);assert.deepEqual(d.playbackRange,[1,9]);assert.throws(()=>d.request('run_save'),/Speed/);
 d.select('Two');assert.equal(d.invalid,true);d.select('One');assert.equal(d.input('One','speed'),'');
 for(const raw of ['0','5','Infinity','NaN']){d.editTiming('One','speed',raw);assert.equal(d.invalid,true);assert.equal(d.value('One').speed,1);}
 d.editTiming('One','speed','1.25');assert.equal(d.invalid,false);assert.equal(d.request('run_save').changes[0].speed,1.25);
 d.editTiming('One','start','0.1');assert.equal(d.invalid,true);assert.match(d.errors[0].message,/whole number/);assert.throws(()=>d.handoff(5),/Save or discard/);
 d.discard();assert.equal(d.dirty,false);assert.equal(d.invalid,false);assert.equal(d.canUndo,false);
});
test('continuous timing input is one undo step including invalid intermediate text',()=>{
 const d=actionDraft(cp,run);d.change('One',{mode:'clip',take_id:'take_one',start:1,speed:1});
 d.editTiming('One','start','');d.editTiming('One','start','2');d.editTiming('One','start','20');d.finishEdit();
 assert.equal(d.value('One').start,20);d.undo();assert.equal(d.value('One').start,1);assert.equal(d.invalid,false);
 d.editTiming('One','speed','0');d.finishEdit();d.editTiming('One','speed','2');d.finishEdit();d.undo();assert.equal(d.input('One','speed'),'0');assert.equal(d.invalid,true);d.undo();assert.equal(d.value('One').speed,1);assert.equal(d.invalid,false);
 d.change('One',{mode:'hold',frame:5});d.editTiming('One','frame','10');assert.equal(d.invalid,true);assert.match(d.errors[0].message,/Hold frame/);d.change('One',{mode:'keep'});assert.equal(d.invalid,false);
});
