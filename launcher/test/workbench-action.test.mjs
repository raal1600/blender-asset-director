import test from 'node:test';
import assert from 'node:assert/strict';
import {actionDraft,actionInspection,actionView} from '../public/workbench-action.mjs';
const cp={id:'cp_saved',sha256:'hash'},run={id:'run_inspect',inspection:{sha256:'audit',fps:24,reference_frame:5,frame_range:[1,9],unassigned:[],performers:[{name:'One',takes:[{id:'take_one',action:'Observed',range:[1,9]}]},{name:'Two',takes:[{id:'take_two',action:'Other',range:[1,9]}]}]}};
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
 assert.equal(actionInspection(rows,{id:'scene'},cp),rows[0]);assert.equal(actionInspection(rows,{id:'other'},cp),null);assert.equal(actionInspection(rows,{id:'scene'},{...cp,sha256:'new'}),null);
});
test('timing drafts show and explicitly save an expanded full-take range instead of silent clipping',()=>{
 const d=actionDraft(cp,run);d.change('One',{mode:'clip',take_id:'take_one',start:20,speed:.5});assert.deepEqual(d.playbackRange,[1,36]);assert.deepEqual(d.request('run_save').frame_range,[1,36]);
 d.undo();assert.deepEqual(d.playbackRange,[1,9]);d.change('One',{mode:'clip',take_id:'take_one',start:4000,speed:1});assert.throws(()=>d.request('run_save'),/3600-frame/);
});
test('Action presentation stays performer-first and labels unsaved playback honestly',()=>{
 const d=actionDraft(cp,run);d.change('One',{mode:'hold',frame:5});
 const scene={id:'scene',stage:'action',name:'Generated',completed:{world:cp.id},checkpoints:[cp]};
 const html=actionView({project:{workbench:{scenes:[scene]}},scene,stages:[{id:'world',short:'World'},{id:'action',short:'Action'}],checkpoint:cp,runs:[],locked:false,cap:{task_workspace:true,action_layer:'action-layer-v1'},draft:d,esc:v=>String(v??''),b:(t,a)=>'<button data-action="'+a+'">'+t+'</button>'});
 assert.match(html,/Performer<select/);assert.match(html,/Playback shows the saved scene/);assert.match(html,/Save changes to preview the new motion/);assert.match(html,/Hold a pose/);assert.doesNotMatch(html,/Inspect saved candidate|Keep checkpoint/);
});
