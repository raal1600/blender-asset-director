/** Shared wire validation; native Blender independently verifies every binding. */
export const timelineVersion='action-timeline-v1';
export const stitchVersion='native-stitch-v1';
export const motionEditVersion='native-motion-edit-v1';
export function generatedDurationPlan(seconds){
 const choices=Array.from({length:11},(_,i)=>24+4*i).map(n=>({model_frames:n,native_duration_seconds:(n-7)/30}));
 const valid=choices.filter(x=>Number.isFinite(seconds)&&seconds>0&&seconds/x.native_duration_seconds>=.85-1e-12&&seconds/x.native_duration_seconds<=1.15+1e-12);
 if(!valid.length)throw Error('Generated duration must fit 24,28,…,64 model frames at 30 FPS with bridge-only retiming 0.85–1.15 (0.481667–2.185 seconds).');
 valid.sort((a,b)=>Math.abs(a.native_duration_seconds-seconds)-Math.abs(b.native_duration_seconds-seconds)||a.model_frames-b.model_frames);
 return {...valid[0],requested_duration_seconds:seconds,generated_retime_ratio:seconds/valid[0].native_duration_seconds};
}
const fail=message=>{throw Error(message);};
const object=v=>v&&typeof v==='object'&&!Array.isArray(v);
const keys=(v,list)=>object(v)&&Object.keys(v).length===list.length&&Object.keys(v).every(k=>list.includes(k));
const number=(v,a,b)=>typeof v==='number'&&Number.isFinite(v)&&v>=a&&v<=b;
export const clipEnd=c=>c.start+c.frames-1;
export const sourceRange=(c,take)=>c.source_range||take.range;
export const rotateDirection=(direction,degrees=0)=>{const a=degrees*Math.PI/180,co=Math.cos(a),si=Math.sin(a);return [direction[0]*co-direction[1]*si,direction[0]*si+direction[1]*co];};
export const turnAngle=(from=0,to=0)=>((to-from+540)%360)-180;
export function validateTimeline(change){
 if(!keys(change,['performer','mode','clips'])||change.mode!=='timeline'||!Array.isArray(change.clips)||change.clips.length>64)fail('Use at most 64 clips per performer.');
 let end=-100001;const ids=new Set();
 for(const [index,c] of change.clips.entries()){
  if(!keys(c,['id','take_id','start','frames','speed','repeat_reviewed','travel',...['transition','source_range','heading_deg'].filter(k=>c?.[k]!==undefined)])||typeof c.id!=='string'||!/^clip_[a-zA-Z0-9_-]{1,64}$/.test(c.id)||ids.has(c.id)||typeof c.take_id!=='string'||!/^take_[a-f0-9]{64}$/.test(c.take_id))fail('Choose distinct clips and observed takes.');ids.add(c.id);
  if(c.heading_deg!==undefined&&!number(c.heading_deg,-180,180))fail('Body turn must be between -180 and 180 degrees.');
  if(c.source_range!==undefined&&(!Array.isArray(c.source_range)||c.source_range.length!==2||!c.source_range.every(v=>number(v,-100000,100000))||c.source_range[1]<=c.source_range[0]))fail('Choose increasing source In and Out frames.');
  if(!Number.isInteger(c.start)||!number(c.start,-100000,100000)||!Number.isInteger(c.frames)||!number(c.frames,2,3601)||!number(c.speed,.1,4)||typeof c.repeat_reviewed!=='boolean'||clipEnd(c)>100000)fail('Use integer frames and speed from 0.1 to 4.');
  if(c.start<=end)fail('Clips overlap on this character. Move or shorten the clip.');
  if(index&&Math.abs(turnAngle(change.clips[index-1].heading_deg||0,c.heading_deg||0))>1e-7&&c.transition?.mode!=='turn')fail('Choose Turn and connect to change body heading between clips.');
  if(c.transition!==undefined&&c.transition!==null){const t=c.transition;if(index===0||!keys(t,['frames','match_phase',...(t.mode!==undefined?['mode']:[]),...(t.mode==='generated'?['seed','profile_sha256',...(t.sampling!==undefined?['sampling']:[])]:[])])||t.mode!==undefined&&!['blend','turn','generated'].includes(t.mode)||!Number.isInteger(t.frames)||!number(t.frames,2,120)||typeof t.match_phase!=='boolean')fail('A connection needs a previous clip and 2 to 120 added frames.');if(t.mode==='generated'&&(t.match_phase||!Number.isInteger(t.seed)||t.seed<0||t.seed>=2**32||!/^([a-f0-9]{64})$/.test(t.profile_sha256)||t.sampling!==undefined&&!['argmax','gumbel-temperature-1'].includes(t.sampling)))fail('Generated repositioning needs a verified rig profile, supported sampling and seed, with phase matching off.');if(c.start!==end+1+t.frames)fail('Connected clips must follow their visible transition; move following clips together.');}
  end=clipEnd(c);
  if(c.travel!==null){const t=c.travel,fields=['delta_m','meters_per_cycle',...(t?.gait_id!==undefined?['gait_id']:[])];if(!keys(t,fields)||t.gait_id!==undefined&&!/^[a-f0-9]{64}$/.test(t.gait_id)||!Array.isArray(t.delta_m)||t.delta_m.length!==2||!t.delta_m.every(v=>number(v,-10000,10000))||!number(Math.hypot(...t.delta_m),Number.MIN_VALUE,10000)||!number(t.meters_per_cycle,.001,1000))fail('Manual travel needs a calibrated metres-per-cycle value. Use automatic pace when available.');}
 }
 if(change.clips.length&&end-change.clips[0].start>3600)fail('Timeline exceeds 3600 frame intervals.');
 return change;
}
export function plannedFrames(take,travel,speed){return Math.ceil(Math.hypot(...travel.delta_m)/travel.meters_per_cycle*(take.range[1]-take.range[0])/speed-1e-9)+1;}
export function timelineTiming(c,take){
 const range=sourceRange(c,take),span=range[1]-range[0];if(!number(span,1e-6,100000)||range[0]<take.range[0]||range[1]>take.range[1])fail('Trim must stay inside the inspected native take.');
 const trimmed=range.some((v,i)=>v!==take.range[i]);
 if(trimmed&&(c.travel||c.repeat_reviewed||c.transition?.match_phase))fail('Trimmed motion supports one native pass without added travel or phase matching. Use distance to edit a travelling clip.');
 let cycles=(c.frames-1)*c.speed/span;
 if(c.travel){
  const t=c.travel,g=take.gait,distance=Math.hypot(...t.delta_m);
  if(t.gait_id){if(g?.status!=='estimated'||g.id!==t.gait_id)fail('Automatic pace changed; inspect the saved performer again.');const direction=rotateDirection(g.direction,c.heading_deg||0);if(Math.abs(t.meters_per_cycle-g.meters_per_cycle)>=1e-7||Math.hypot(...t.delta_m.map((v,i)=>v/distance-direction[i]))>=1e-6)fail('Automatic travel must use the inspected pace and direction.');}
  cycles=distance/t.meters_per_cycle;if(c.frames!==plannedFrames(take,t,c.speed))fail('Distance, pace and occupied frames disagree.');
 }
 else if(cycles>1&&cycles<=1+c.speed/span+1e-9)cycles=1;
 if(trimmed&&cycles>1+1e-9)fail('A trimmed clip cannot repeat. Shorten it to one native pass.');
 if(!number(cycles,.001,100))fail('Keep each clip within 100 cycles.');
 if(cycles>1+1e-9&&!c.repeat_reviewed)fail('Review feet and the loop join, then check repeatable cycle below to allow repeats.');
 return {cycles,end:clipEnd(c),nativeEnd:c.start+cycles*span/c.speed};
}
export function connection(previous,c,previousTake,take){
 if(!c.transition)return null;
 const a=timelineTiming(previous,previousTake),b=timelineTiming(c,take),duration=c.start-a.nativeEnd;
 if(!number(duration,Number.MIN_VALUE,122))fail('Invalid connection interval.');
 const velocity=(clip,t)=>clip.travel?clip.travel.delta_m.map(v=>v/(t.nativeEnd-clip.start)):[0,0];
 const va=velocity(previous,a),vb=velocity(c,b),na=Math.hypot(...va),nb=Math.hypot(...vb);
 const mode=c.transition.mode||'blend',heading_in_deg=previous.heading_deg||0,heading_out_deg=c.heading_deg||0,turn_delta_deg=turnAngle(heading_in_deg,heading_out_deg);
 if(mode==='blend'&&Math.abs(turn_delta_deg)>1e-7)fail('Choose Turn and connect to change body heading between clips.');
 if(mode==='turn'&&Math.abs(turn_delta_deg)>135)fail('This body turn exceeds 135 degrees. Insert an observed turn clip or edit the transition in Blender.');
 if(mode==='blend'&&na>1e-9&&nb>1e-9&&va.reduce((n,v,i)=>n+v*vb[i],0)/(na*nb)<Math.cos(135*Math.PI/180))fail('This sharp reversal needs a turn or stop clip, or a reviewed Blender edit.');
 return {start:a.nativeEnd,end:c.start,duration_frames:duration,velocity_in:va,velocity_out:vb,delta_m:mode==='generated'?[0,0]:va.map((v,i)=>(v+vb[i])*duration*(mode==='turn'?.125:.5)),placement_pending:mode==='generated',mode,heading_in_deg,heading_out_deg,turn_delta_deg};
}
