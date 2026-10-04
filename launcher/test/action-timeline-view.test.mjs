import test from 'node:test';
import assert from 'node:assert/strict';
import {timelineDraft} from '../public/action-timeline-draft.mjs';
import {timelineControls,timelinePicker} from '../public/action-timeline-view.mjs';
import {actionView} from '../public/workbench-action.mjs';

const cp={id:'cp_saved',sha256:'a'.repeat(64)},take='take_'+'b'.repeat(64);
function fixture(){
 const run={id:'run_inspected',implementation:'e'.repeat(64),inspection:{version:'action-layer-v1',sha256:'c'.repeat(64),frame_range:[1,250],fps:24,reference_frame:1,unassigned:[],performers:[{name:'Observed',takes:[{id:take,action:'Native take',range:[1,25],travel_blocker:null,stitch_blocker:null,stitch_channels:'d'.repeat(64),gait:{status:'unavailable',reason:'Synthetic measurement is inconclusive.'}}],timeline:{version:'action-timeline-v1',stitch_version:'native-stitch-v1',clips:[],origin_m:[0,0,0],meters_per_unit:1}}]}};
 return timelineDraft(cp,run);
}
test('manual calibration stays visible without expanding advanced timing',()=>{
 const d=fixture();d.add(take,'clip_a');d.edit('travel',true);
 const html=timelineControls(d,String),advanced=html.indexOf('<details data-motion-details>');
 assert(advanced>0);assert.doesNotMatch(html,/<details[^>]*\bopen(?:[\s=>]|$)/);
 for(const key of ['pace','direction','distance'])assert(html.indexOf(`data-motion-field="${key}"`)<advanced);
 assert(html.indexOf('data-motion-field="speed"')>advanced);
 assert.match(html,/aria-describedby="motion-pace-error"/);
 assert.match(html,/data-motion-error="pace"/);
 assert.match(html,/Why is a pace needed/);assert.match(html,/Synthetic measurement is inconclusive/);
 assert(d.invalid);assert.throws(()=>d.request('run_save'),/calibrate/);
 assert(d.arrow(),'Presentation must not remove the correction path');
});
test('timeline picker is separate from clip settings and respects read-only state',()=>{
 const d=fixture();d.add(take,'clip_a');
 const picker=timelinePicker(d,String,true),controls=timelineControls(d,String,true);
 assert.match(picker,/aria-label="Performer"[^>]*disabled/);
 assert.match(picker,/aria-label="Add animation"[^>]*disabled/);
 assert.doesNotMatch(controls,/data-motion-add|data-action-field="performer"/);
 assert.match(controls,/Selected clip/);
});
test('timeline presentation puts viewer and tracks before the compact inspector',()=>{
 const d=fixture();d.add(take,'clip_a');d.edit('travel',true);
 const scene={id:'scene',name:'Generated',stage:'action',completed:{world:cp.id},checkpoints:[cp]};
 const html=actionView({project:{workbench:{scenes:[scene]}},scene,stages:[{id:'world',short:'World'},{id:'action',short:'Action'}],checkpoint:cp,runs:[],locked:false,cap:{implementation:d.run.implementation,action_layer:'action-layer-v1',action_timeline:'action-timeline-v1'},draft:d,esc:v=>String(v??''),b:(label,action)=>`<button data-action="${action}">${label}</button>`});
 assert(html.indexOf('data-motion-add')<html.indexOf('data-scene-viewer'));
 assert(html.indexOf('data-scene-viewer')<html.indexOf('data-motion-tracks'));
 assert(html.indexOf('data-motion-tracks')<html.indexOf('data-motion-inspector'));
 assert.equal((html.match(/data-scene-viewer/g)||[]).length,1);
 assert.match(html,/Playback shows the saved scene/);
 assert.match(html,/Set metres per cycle to calibrate this path/);
 assert.match(html,/Saving and playback are not approval/);
});
