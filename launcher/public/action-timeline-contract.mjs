/** Shared wire validation; native Blender independently verifies every binding. */
export const timelineVersion='action-timeline-v1';
const fail=message=>{throw Error(message);};
const object=v=>v&&typeof v==='object'&&!Array.isArray(v);
const keys=(v,list)=>object(v)&&Object.keys(v).length===list.length&&Object.keys(v).every(k=>list.includes(k));
const number=(v,a,b)=>typeof v==='number'&&Number.isFinite(v)&&v>=a&&v<=b;
export const clipEnd=c=>c.start+c.frames-1;
export function validateTimeline(change){
 if(!keys(change,['performer','mode','clips'])||change.mode!=='timeline'||!Array.isArray(change.clips)||change.clips.length>64)fail('Use at most 64 clips per performer.');
 let end=-100001;const ids=new Set();
 for(const c of change.clips){
  if(!keys(c,['id','take_id','start','frames','speed','repeat_reviewed','travel'])||typeof c.id!=='string'||!/^clip_[a-zA-Z0-9_-]{1,64}$/.test(c.id)||ids.has(c.id)||typeof c.take_id!=='string'||!/^take_[a-f0-9]{64}$/.test(c.take_id))fail('Choose distinct clips and observed takes.');ids.add(c.id);
  if(!Number.isInteger(c.start)||!number(c.start,-100000,100000)||!Number.isInteger(c.frames)||!number(c.frames,2,3601)||!number(c.speed,.1,4)||typeof c.repeat_reviewed!=='boolean'||clipEnd(c)>100000)fail('Use integer frames and speed from 0.1 to 4.');
  if(c.start<=end)fail('Clips overlap on this character. Move or shorten the clip.');end=clipEnd(c);
  if(c.travel!==null){const t=c.travel;if(!keys(t,['delta_m','meters_per_cycle'])||!Array.isArray(t.delta_m)||t.delta_m.length!==2||!t.delta_m.every(v=>number(v,-10000,10000))||!number(Math.hypot(...t.delta_m),Number.MIN_VALUE,10000)||!number(t.meters_per_cycle,.001,1000))fail('Set travel distance and metres per animation cycle.');}
 }
 if(change.clips.length&&end-change.clips[0].start>3600)fail('Timeline exceeds 3600 frame intervals.');
 return change;
}
export function plannedFrames(take,travel,speed){return Math.ceil(Math.hypot(...travel.delta_m)/travel.meters_per_cycle*(take.range[1]-take.range[0])/speed-1e-9)+1;}
export function timelineTiming(c,take){
 const span=take.range[1]-take.range[0];if(!number(span,1e-6,100000))fail('Take has no usable duration.');
 let cycles=(c.frames-1)*c.speed/span;
 if(c.travel){cycles=Math.hypot(...c.travel.delta_m)/c.travel.meters_per_cycle;if(c.frames!==plannedFrames(take,c.travel,c.speed))fail('Distance, pace and occupied frames disagree.');}
 else if(cycles>1&&cycles<=1+c.speed/span+1e-9)cycles=1;
 if(!number(cycles,.001,100))fail('Keep each clip within 100 cycles.');
 if(cycles>1+1e-9&&!c.repeat_reviewed)fail('Check repeatable cycle before repeating this animation.');
 return {cycles,end:clipEnd(c),nativeEnd:c.start+cycles*span/c.speed};
}
