import test from 'node:test';
import assert from 'node:assert/strict';
import {timelineDraft,suggestedPath} from '../public/action-timeline-draft.mjs';
import {validateTimeline,timelineTiming} from '../public/action-timeline-contract.mjs';
const take='take_'+'a'.repeat(64),other='take_'+'b'.repeat(64);
const cp={id:'cp_saved',sha256:'a'.repeat(64)},run={id:'run_saved',inspection:{sha256:'b'.repeat(64),frame_range:[1,250],fps:24,reference_frame:1,performers:['One','Two'].map((name,i)=>({name,takes:[{id:i?other:take,action:'Native',range:[1,25],travel_blocker:null}],timeline:{version:'action-timeline-v1',clips:[],origin_m:[0,0,0],meters_per_unit:1}}))}};
test('travel derives occupancy; append starts after the inclusive last frame',()=>{
 const d=timelineDraft(cp,run);d.add(take,'clip_one');d.edit('travel',true);assert(d.invalid);d.edit('distance','5');d.edit('pace','2.5');assert(d.invalid);d.edit('repeat_reviewed',true);assert(!d.invalid);
 assert.equal(d.selectedClip.frames,49);assert.equal(d.nextFrame(),50);assert.deepEqual(d.arrow().delta_m.map(v=>Math.round(v)),[0,5]);
 d.add(take,'clip_two');assert.equal(d.selectedClip.start,50);assert.equal(d.request('run_save').changes[0].clips.length,2);
 d.select('Two');d.add(other,'clip_other');assert.equal(d.selectedClip.start,1);assert.equal(d.count,2);
 assert.equal(run.inspection.performers[0].timeline.clips.length,0);
});
test('editing, explicit ripple, delete, undo and invalid raw input remain local',()=>{
 const d=timelineDraft(cp,run);d.add(take,'clip_one');d.add(take,'clip_two');d.select('One','clip_one');d.edit('frames','40');d.edit('repeat_reviewed',true);assert(d.invalid);d.shiftFollowing();assert(!d.invalid);assert.equal(d.clips('One')[1].start,41);
 d.edit('speed','');assert(d.invalid);assert.equal(d.input('speed'),'');d.finishEdit();d.select('Two');assert.throws(()=>d.request('run_save'));d.select('One','clip_one');d.undo();assert(!d.invalid);
 d.remove();assert.equal(d.clips('One').length,1);d.undo();assert.equal(d.clips('One').length,2);d.discard();assert(!d.dirty);
});
test('saved timeline reload preserves clips; revisions cannot mutate original receipt',()=>{
 const d=timelineDraft(cp,run);d.add(take,'clip_one');const saved=structuredClone(run);saved.inspection.performers[0].timeline.clips=d.clips('One');const reloaded=timelineDraft(cp,saved);assert(!reloaded.dirty);assert.equal(reloaded.nextFrame(),26);reloaded.select('One','clip_one');reloaded.edit('start','10');assert.equal(saved.inspection.performers[0].timeline.clips[0].start,1);assert.throws(()=>reloaded.handoff(1),/Save or discard/);
});
test('wire bounds, overlap, cross-take and unreviewed repeat refuse',()=>{
 const d=timelineDraft(cp,run);assert.throws(()=>d.add(other,'clip_wrong'));d.add(take,'clip_one');const c=d.selectedClip;
 assert.throws(()=>validateTimeline({performer:'One',mode:'timeline',clips:[c,{...c,id:'clip_two',start:25}]}),/overlap/);
 assert.throws(()=>timelineTiming({...c,frames:60},run.inspection.performers[0].takes[0]),/repeatable/);
 for(const patch of [{frames:NaN},{speed:Infinity},{start:1.2},{repeat_reviewed:1},{travel:{delta_m:[0,0],meters_per_cycle:1}}])assert.throws(()=>validateTimeline({performer:'One',mode:'timeline',clips:[{...c,...patch}]}));
});
test('label hints are editable suggestions; drag is one undo group and pace reuses an authored cycle',()=>{
 assert.deepEqual(suggestedPath('walk_back'),[0,-1]);assert.deepEqual(suggestedPath('walk:right'),[1,0]);assert.deepEqual(suggestedPath('walk left'),[-1,0]);
 const d=timelineDraft(cp,run);d.add(take,'clip_one');d.edit('travel',true);d.edit('pace','2.5');const before=d.selectedClip;d.finishEdit();d.moveEndpoint([2,3]);d.moveEndpoint([3,4]);d.finishEdit();d.undo();assert.deepEqual(d.selectedClip,before);
 d.add(take,'clip_two');d.edit('travel',true);assert.equal(d.selectedClip.travel.meters_per_cycle,2.5);
});

test('turning travel off restores non-travel duration including authored trims and Undo',()=>{
 const d=timelineDraft(cp,run);d.add(take,'clip_one');d.edit('travel',true);d.edit('pace','2.5');
 d.add(take,'clip_two');d.edit('travel',true);assert.equal(d.selectedClip.frames,11);d.finishEdit();d.edit('travel',false);assert.equal(d.selectedClip.frames,25);
 d.undo();assert.equal(d.selectedClip.frames,11);assert(d.selectedClip.travel);d.finishEdit();d.edit('travel',false);
 d.edit('frames','15');d.edit('travel',true);assert.equal(d.selectedClip.frames,11);d.finishEdit();d.edit('travel',false);assert.equal(d.selectedClip.frames,15);
 d.discard();assert(!d.dirty);
});

test('disabling a reloaded saved path uses the native take duration at its current speed',()=>{
 const saved=structuredClone(run);saved.inspection.performers[0].timeline.clips=[{id:'clip_saved',take_id:take,start:1,frames:49,speed:.5,repeat_reviewed:true,travel:{delta_m:[0,5],meters_per_cycle:5}}];
 const d=timelineDraft(cp,saved);d.select('One','clip_saved');d.edit('travel',false);assert.equal(d.selectedClip.frames,49);assert.equal(d.selectedClip.travel,null);d.undo();assert.deepEqual(d.selectedClip,saved.inspection.performers[0].timeline.clips[0]);
});

test('automatic gait fills pace and observed heading; five metres adds cycles, not stretched strides',()=>{
 const inspected=structuredClone(run);inspected.inspection.performers[0].takes[0].gait={status:'estimated',id:'c'.repeat(64),meters_per_cycle:2,direction:[-1,0]};
 const d=timelineDraft(cp,inspected);d.add(take,'clip_auto');d.edit('travel',true);
 assert.deepEqual(d.selectedClip.travel.delta_m,[-2,0]);assert.equal(d.selectedClip.frames,25);assert(!d.invalid);
 d.edit('distance','5');assert.equal(d.selectedClip.frames,61);assert(d.invalid);assert.match(d.errors[0].message,/loop join/);
 d.edit('repeat_reviewed',true);assert(!d.invalid);assert.equal(d.nextFrame(),62);
 assert.throws(()=>d.edit('pace','5'),/Automatic travel/);d.moveEndpoint([-6,10]);assert.deepEqual(d.selectedClip.travel.delta_m,[-6,0]);
 d.moveEndpoint([2,10]);assert(d.selectedClip.travel.delta_m[0]<0); // Cannot reverse a backward gait.
 d.edit('automatic',false);assert(!d.selectedClip.travel.gait_id);assert(!d.selectedClip.repeat_reviewed);
 d.edit('pace','3');d.edit('direction','90');d.edit('automatic',true);assert.equal(d.selectedClip.travel.meters_per_cycle,2);assert.equal(d.selectedClip.travel.gait_id,'c'.repeat(64));
});

test('forged automatic profile, heading or pace refuses; legacy manual travel still works',()=>{
 const t={range:[1,25],gait:{status:'estimated',id:'c'.repeat(64),meters_per_cycle:2,direction:[0,1]}};
 const c={id:'clip_auto',take_id:take,start:1,frames:25,speed:1,repeat_reviewed:false,travel:{delta_m:[0,2],meters_per_cycle:2,gait_id:t.gait.id}};
 assert.equal(timelineTiming(c,t).cycles,1);
 for(const patch of [{gait_id:'d'.repeat(64)},{meters_per_cycle:5},{delta_m:[2,0]}])assert.throws(()=>timelineTiming({...c,travel:{...c.travel,...patch}},t));
 const d=timelineDraft(cp,run);d.add(take,'clip_manual');d.edit('travel',true);d.edit('pace','1');assert(!d.invalid);
});
