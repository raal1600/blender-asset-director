import test from 'node:test';
import assert from 'node:assert/strict';
import {timelineDraft} from '../public/action-timeline-draft.mjs';
import {connection,validateTimeline} from '../public/action-timeline-contract.mjs';
import {timelineTracks,timelineControls} from '../public/action-timeline-view.mjs';
const cp={id:'cp_saved',sha256:'a'.repeat(64)},take='take_'+'b'.repeat(64);
function fixture(){return {id:'run_inspected',inspection:{sha256:'c'.repeat(64),frame_range:[1,250],fps:24,reference_frame:1,performers:[{name:'Observed',takes:[{id:take,action:'No semantic label',range:[1,25],stitch_blocker:null,stitch_channels:'d'.repeat(64),travel_blocker:null}],timeline:{version:'action-timeline-v1',stitch_version:'native-stitch-v1',clips:[],origin_m:[0,0,0],meters_per_unit:1}}]}};}
test('compatible append adds visible transition, connected ripple and reversible cut',()=>{
 const run=fixture(),d=timelineDraft(cp,run);d.add(take,'clip_a');d.add(take,'clip_b');assert.equal(d.selectedClip.start,32);assert.equal(d.selectedClip.transition.frames,6);assert(!d.invalid);
 assert.match(timelineTracks(d,String),/Connection 26 to 31/);assert.match(timelineControls(d,String),/Smooth connection/);
 d.edit('transition_frames','10');assert.equal(d.selectedClip.start,36);d.finishEdit();d.undo();assert.equal(d.selectedClip.start,32);
 d.select('Observed','clip_a');d.edit('speed','0.5');d.edit('frames','49');assert.equal(d.clips('Observed')[1].start,56);
 d.select('Observed','clip_b');d.edit('smooth',false);assert.equal(d.selectedClip.start,50);assert.equal(d.selectedClip.transition,undefined);d.finishEdit();d.undo();assert.equal(d.selectedClip.start,56);
 assert.equal(run.inspection.performers[0].timeline.clips.length,0);assert.equal(d.request('run_save').changes[0].clips.length,2);
});
test('bad transitions refuse, raw errors persist, phase review is never invented',()=>{
 const d=timelineDraft(cp,fixture());d.add(take,'clip_a');d.add(take,'clip_b');assert.equal(d.selectedClip.repeat_reviewed,false);
 d.edit('transition_frames','');assert(d.invalid);assert.throws(()=>d.request('run_save'));d.edit('transition_frames','6');assert(!d.invalid);
 const clips=d.clips('Observed');assert.throws(()=>validateTimeline({performer:'Observed',mode:'timeline',clips:[clips[1]]}));
 d.select('Observed','clip_a');d.remove();assert.equal(d.clips('Observed')[0].transition,undefined);assert(!d.invalid);d.undo();assert.equal(d.clips('Observed')[1].transition.frames,6);
});
test('travel connector is explicit; reversal needs intermediate movement',()=>{
 const d=timelineDraft(cp,fixture());d.add(take,'clip_a');d.edit('travel',true);d.edit('pace','1');d.edit('direction','90');
 d.add(take,'clip_b');d.edit('travel',true);d.edit('direction','0');assert(!d.invalid);assert(d.connection.delta_m.every(v=>v>0));assert(d.arrow().origin_m[0]>0);
 d.edit('direction','-90');assert(d.invalid);assert.match(d.errors.map(e=>e.message).join(' '),/turn or stop/);assert.throws(()=>d.request('run_save'));
});
test('unsupported takes and old inspections do not silently acquire connections',()=>{
 for(const patch of [r=>delete r.inspection.performers[0].timeline.stitch_version,r=>delete r.inspection.performers[0].takes[0].stitch_channels,r=>r.inspection.performers[0].takes[0].stitch_blocker='Native root motion']){const r=fixture();patch(r);const d=timelineDraft(cp,r);d.add(take,'clip_a');d.add(take,'clip_b');assert.equal(d.selectedClip.start,26);assert.equal(d.selectedClip.transition,undefined);assert.equal(d.canConnect,false);}
});
test('dragging an earlier path ripples connected clips and undo restores every interval',()=>{
 const d=timelineDraft(cp,fixture());d.add(take,'clip_a');d.edit('travel',true);d.edit('pace','1');d.edit('repeat_reviewed',true);d.add(take,'clip_b');d.add(take,'clip_c');
 const before=d.clips('Observed');d.select('Observed','clip_a');d.moveEndpoint([0,2]);assert.deepEqual(d.clips('Observed').map(c=>c.start),[1,56,87]);assert(!d.invalid);
 d.finishEdit();d.undo();assert.deepEqual(d.clips('Observed'),before);
});
