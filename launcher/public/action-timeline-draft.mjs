/** Local clip edits; no jobs, approvals, native keys or source mutations. */
import {validateTimeline,timelineTiming,plannedFrames,clipEnd,connection,stitchVersion,motionEditVersion,sourceRange,rotateDirection,turnAngle,generatedDurationPlan} from './action-timeline-contract.mjs';
const copy=v=>structuredClone(v);
const automaticTravel=(take,distance=take.gait.meters_per_cycle,heading=0)=>{const g=take.gait,direction=rotateDirection(g.direction,heading),n=Math.hypot(...direction);return {delta_m:direction.map(v=>distance*v/n),meters_per_cycle:g.meters_per_cycle,gait_id:g.id};};
const displayNumber=n=>Number.isFinite(n)?Number(n.toFixed(3)):n;
// Neutral editable world-axis default only. Labels never determine movement.
export function suggestedPath(){return [0,1];}
export function timelineDraft(checkpoint,run){
 const audit=run.inspection,baseline=new Map(audit.performers.map(p=>[p.name,copy(p.timeline?.clips||[])]));
 let tracks=copy(baseline),history=[],raw=new Map(),stationaryFrames=new Map(),gesture=null,samplingPlan=null,selected=audit.performers.find(p=>p.takes.length)?.name||audit.performers[0]?.name||null,clipId=null,selectedPart='clip';
 const performer=name=>{const p=audit.performers.find(p=>p.name===name);if(!p)throw Error('Choose an observed performer.');return p;};
 const editable=name=>{const p=performer(name);if(p.unsupported||p.timeline?.error)throw Error(p.unsupported||p.timeline.error);return p;};
 const remember=key=>{if(!key||gesture!==key){history.push({tracks:copy(tracks),raw:copy(raw),stationaryFrames:copy(stationaryFrames),samplingPlan:copy(samplingPlan),selected,clipId,selectedPart});if(history.length>100)history.shift();}gesture=key;};
 const extended=name=>{const p=editable(name);if(p.timeline?.edit_version!==motionEditVersion)throw Error('Inspect this saved performer with the matching motion-edit runtime first.');return p;};
 const sorted=name=>[...tracks.get(name)].sort((a,b)=>a.start-b.start);
 const canConnect=(p,previous,take)=>{const prior=p.takes.find(t=>t.id===previous?.take_id);return p.timeline?.stitch_version===stitchVersion&&take?.stitch_blocker===null&&prior?.stitch_blocker===null&&/^[0-9a-f]{64}$/.test(take.stitch_channels||'')&&take.stitch_channels===prior.stitch_channels;};
 const reflow=order=>{for(let i=1;i<order.length;i++)if(order[i].transition)order[i].start=clipEnd(order[i-1])+1+order[i].transition.frames;};
 const join=(name,c)=>{const p=performer(name),order=sorted(name),previous=order[order.findIndex(x=>x.id===c.id)-1];if(!c.transition)return null;if(!canConnect(p,previous,p.takes.find(t=>t.id===c.take_id)))throw Error('These clips need a matching connection inspection or Blender review.');return connection(previous,c,p.takes.find(t=>t.id===previous.take_id),p.takes.find(t=>t.id===c.take_id));};
 const issue=(name,c)=>{try{
  const p=performer(name),take=p.takes.find(t=>t.id===c.take_id);if(!take)throw Error('Saved take changed; inspect in Blender.');
  if(tracks.get(name).some(x=>x.heading_deg)&&take.heading_blocker!==null)throw Error(take.heading_blocker||'Inspect this performer again before changing body heading.');
  if(c.travel&&!c.travel.gait_id&&(!Number.isFinite(c.travel.meters_per_cycle)||c.travel.meters_per_cycle<.001||c.travel.meters_per_cycle>1000))return {field:'pace',message:'Set metres per cycle to calibrate this path, or turn off path movement.'};
  timelineTiming(c,take);if(c.travel&&take.travel_blocker)throw Error(take.travel_blocker);
  const order=sorted(name),previous=order[order.findIndex(x=>x.id===c.id)-1];
  if(previous&&Math.abs(turnAngle(previous.heading_deg||0,c.heading_deg||0))>1e-7&&!c.transition)throw Error('Choose Turn and connect to change body heading between clips.');
  if(c.transition&&previous){
   // A broken predecessor is reported on that predecessor, not again as a
   // spurious calibration error on every dependent connection. Save remains
   // blocked by the original issue and arrow placement stays pending.
   const priorTake=p.takes.find(t=>t.id===previous.take_id);if(!priorTake)return null;
   try{timelineTiming(previous,priorTake);}catch{return null;}
  }
  if(c.transition?.mode==='generated'){const provider=p.timeline?.motion_bricks;if(provider?.status!=='CONFIGURED'||provider.profile_sha256!==c.transition.profile_sha256)throw Error(provider?.blocker||'Generated rig mapping changed; inspect again.');if(c.heading_deg||previous?.heading_deg)throw Error('This generated adapter preserves the saved facing; use clips with their native heading.');const duration=c.start-timelineTiming(previous,p.takes.find(t=>t.id===previous.take_id)).nativeEnd;generatedDurationPlan(duration/audit.fps);}
  join(name,c);return null;
 }catch(e){return {field:'clip',message:e.message};}};
 const changed=()=>[...tracks].filter(([name,clips])=>JSON.stringify(clips)!==JSON.stringify(baseline.get(name))||samplingPlan&&clips.some(c=>c.transition?.mode==='generated'));
 const errors=()=>{const list=[...raw.values()].filter(x=>x.message).map(copy);for(const [name,clips] of tracks){for(const c of clips){const problem=issue(name,c);if(problem&&!raw.has(c.id+':'+problem.field))list.push({performer:name,clip:c.id,...problem});}try{validateTimeline({performer:name,mode:'timeline',clips:sorted(name)});}catch(e){list.push({performer:name,field:'track',message:e.message});}}return list;};
 return {timeline:true,checkpointId:checkpoint.id,sha256:checkpoint.sha256,run,audit,
  restoreRequest(request){if(request.checkpointId!==checkpoint.id||request.sha256!==checkpoint.sha256||request.audit_sha256!==audit.sha256)throw Error('Saved working request needs its original input inspection.');for(const change of request.changes){editable(change.performer);validateTimeline(change);tracks.set(change.performer,copy(change.clips));}samplingPlan=copy(request.sampling_plan||null);},
  setSamplingPlan(seeds){if(!Array.isArray(seeds)||!seeds.length||seeds.length>3)throw Error('Choose one to three candidate seeds.');remember();samplingPlan={mode:'gumbel-temperature-1',seeds:[...seeds]};for(const clips of tracks.values())for(const c of clips)if(c.transition?.mode==='generated'){c.transition.sampling=samplingPlan.mode;c.transition.seed=seeds[0];}},
  get selected(){return selected;},get selectedPart(){return selectedPart;},get selectedClip(){return copy(tracks.get(selected)?.find(c=>c.id===clipId)||null);},
  get supportsEditing(){return performer(selected).timeline?.edit_version===motionEditVersion;},
  get trimBlocker(){const c=this.selectedClip;if(!this.supportsEditing)return 'Inspect performers again to enable source editing.';if(c?.travel)return 'Travelling clips use distance to set their duration. Turn off added path movement before trimming or splitting native motion.';if(c?.repeat_reviewed)return 'Turn off reviewed repeats before trimming or splitting a single native pass.';return null;},
  get needsPaceRefresh(){const c=this.selectedClip,t=performer(selected).takes.find(t=>t.id===c?.take_id);return !!c?.travel?.gait_id&&c.travel.gait_id!==t?.gait?.id;},
  get dependencyKey(){return JSON.stringify({changes:this.changes,errors:this.errors,samplingPlan});},get dirty(){return changed().length>0||raw.size>0;},get count(){return changed().length;},get canUndo(){return history.length>0;},get errors(){return errors();},get invalid(){return errors().length>0;},
  get changes(){return changed().map(([performer])=>({performer,mode:'timeline',clips:copy(sorted(performer))}));},
  get hasGeneratedTransitions(){return [...tracks.values()].some(clips=>clips.some(c=>c.transition?.mode==='generated'));},
  get dependencyImpact(){return changed().map(([name])=>{
   const order=sorted(name),old=[...baseline.get(name)].sort((a,b)=>a.start-b.start),p=performer(name);
   let first=order.findIndex((c,i)=>JSON.stringify(c)!==JSON.stringify(old[i]));
   if(first<0)first=old.length!==order.length?order.length:order.findIndex(c=>c.transition?.mode==='generated');
   const label=c=>p.takes.find(t=>t.id===c?.take_id)?.action||'Changed animation';
   return {performer:name,changedClip:label(order[first]||old[first]),joins:order.slice(Math.max(1,first)).filter(c=>c.transition).map(c=>({clipId:c.id,label:label(c),targetFrame:c.start}))};
  });},
  get gait(){const c=this.selectedClip;return performer(selected).takes.find(t=>t.id===c?.take_id)?.gait;},
  get canConnect(){const c=this.selectedClip,order=sorted(selected),previous=order[order.findIndex(x=>x.id===c?.id)-1],p=performer(selected);return !!c&&canConnect(p,previous,p.takes.find(t=>t.id===c.take_id));},
  get connection(){try{const c=this.selectedClip;if(c?.transition?.mode==='generated'&&!this.dirty){const saved=performer(selected).timeline.connections?.find(j=>j.clip_id===c.id);if(saved)return saved;}return c?join(selected,c):null;}catch{return null;}},
  get playbackRange(){const range=[...audit.frame_range];for(const clips of tracks.values())for(const c of clips){range[0]=Math.min(range[0],c.start);range[1]=Math.max(range[1],clipEnd(c));}return range;},
  clips:name=>copy(sorted(name)),value:name=>({performer:name,mode:changed().some(([n])=>n===name)?'timeline':'keep'}),
  select(name,id=null,part='clip'){performer(name);if(id&&!tracks.get(name).some(c=>c.id===id))throw Error('Select an existing clip.');selected=name;clipId=id;selectedPart=part==='transition'&&this.selectedClip?.transition?'transition':'clip';gesture=null;},
  errorLabel(error){const c=tracks.get(error.performer)?.find(c=>c.id===error.clip),take=performer(error.performer).takes.find(t=>t.id===c?.take_id);return c?`${take?.action||'Changed take'} · frames ${c.start}–${clipEnd(c)}`:error.performer;},
  nextFrame(name=selected){return Math.max(audit.frame_range[0],...tracks.get(name).map(c=>clipEnd(c)+1));},
  add(takeId,id='clip_'+crypto.randomUUID()){
   const p=editable(selected),take=p.takes.find(t=>t.id===takeId);if(!take)throw Error('Choose an observed native take.');
   if(tracks.get(selected).length>=64)throw Error('Use at most 64 clips per performer.');
   remember();clipId=id;selectedPart='clip';const previous=sorted(selected).at(-1),transition=canConnect(p,previous,take)?{frames:Math.max(2,Math.min(120,Math.round(audit.fps*.25))),match_phase:true}:null;
   tracks.get(selected).push({id,take_id:takeId,start:this.nextFrame()+(transition?.frames||0),frames:Math.ceil(take.range[1]-take.range[0])+1,speed:1,repeat_reviewed:false,travel:null,...(previous?.heading_deg!==undefined?{heading_deg:previous.heading_deg}:{}),...(transition?{transition}:{})});
  },
  remove(){editable(selected);if(!clipId)return;if(selectedPart==='transition'){this.edit('smooth',false);selectedPart='clip';return;}remember();tracks.set(selected,tracks.get(selected).filter(c=>c.id!==clipId));const order=sorted(selected);if(order[0])delete order[0].transition;reflow(order);for(const [k,v] of raw)if(v.clip===clipId)raw.delete(k);clipId=null;},
  input(field){const c=this.selectedClip;if(!c)return '';if(field==='root_intent')return c.root_intent||'observed';if(field.startsWith('contact_')){const [,edge,property]=field.split('_');return raw.get(c.id+':'+field)?.value??c.transition?.contacts?.[edge]?.[property]??(property==='support'?'auto':.08);}const error=raw.get(c.id+':'+field);if(error)return error.value;const take=performer(selected).takes.find(t=>t.id===c.take_id);return displayNumber(field==='source_in'?sourceRange(c,take)[0]:field==='source_out'?sourceRange(c,take)[1]:field==='heading_deg'?c.heading_deg||0:field==='transition_mode'?c.transition?.mode||'blend':field==='transition_frames'?c.transition?.frames||'':field==='distance'?c.travel?Math.hypot(...c.travel.delta_m):0:field==='pace'?c.travel?.meters_per_cycle||'':field==='direction'?c.travel?Math.atan2(c.travel.delta_m[1],c.travel.delta_m[0])*180/Math.PI:0:c[field]);},
  refreshPace(){editable(selected);const c=tracks.get(selected).find(c=>c.id===clipId);if(!c?.travel)throw Error('Select a travelling clip first.');const take=performer(selected).takes.find(t=>t.id===c.take_id);if(take.gait?.status!=='estimated')throw Error('This take has no reliable new measurement. Use manual calibration or native motion instead.');remember();const end=clipEnd(c);c.travel=automaticTravel(take,Math.hypot(...c.travel.delta_m),c.heading_deg||0);c.frames=plannedFrames(take,c.travel,c.speed);c.repeat_reviewed=false;if(c.transition)c.transition.match_phase=false;for(const field of ['pace','direction'])raw.delete(c.id+':'+field);for(const next of sorted(selected).filter(x=>x.id!==c.id&&x.start>end))next.start+=clipEnd(c)-end;reflow(sorted(selected));gesture=null;},
  replace(takeId){const p=extended(selected),take=p.takes.find(t=>t.id===takeId),c=tracks.get(selected).find(c=>c.id===clipId);if(!take||!c)throw Error('Choose an observed native take for this clip.');if(takeId===c.take_id)return;remember();const end=clipEnd(c);c.take_id=takeId;c.travel=null;c.repeat_reviewed=false;delete c.source_range;delete c.root_intent;if(c.transition)delete c.transition.contacts;stationaryFrames.delete(c.id);c.frames=Math.ceil((take.range[1]-take.range[0])/c.speed)+1;if(c.transition)c.transition.match_phase=false;for(const [key,value] of raw)if(value.clip===c.id)raw.delete(key);for(const next of sorted(selected).filter(x=>x.id!==c.id&&x.start>end))next.start+=clipEnd(c)-end;reflow(sorted(selected));selectedPart='clip';},
  insertBefore(takeId,id='clip_'+crypto.randomUUID()){const p=extended(selected),take=p.takes.find(t=>t.id===takeId),c=tracks.get(selected).find(c=>c.id===clipId),order=sorted(selected),index=order.findIndex(x=>x.id===clipId);if(!take||!c||index<1)throw Error('Select a connection between two clips first.');if(order.length>=64)throw Error('Use at most 64 clips per performer.');remember();const previous=order[index-1],frames=Math.ceil(take.range[1]-take.range[0])+1,transition=canConnect(p,previous,take)?{frames:Math.max(2,Math.min(120,Math.round(audit.fps*.25))),match_phase:false}:null;const inserted={id,take_id:takeId,start:clipEnd(previous)+1+(transition?.frames||0),frames,speed:1,repeat_reviewed:false,travel:null,...(previous.heading_deg!==undefined?{heading_deg:previous.heading_deg}:{}),...(transition?{transition}:{})};const desired=clipEnd(inserted)+1+(c.transition?.frames||0),delta=desired-c.start;for(const next of order.slice(index))next.start+=delta;tracks.get(selected).push(inserted);if(c.transition)c.transition.match_phase=false;clipId=id;selectedPart='clip';},
  split(frame,id='clip_'+crypto.randomUUID()){extended(selected);if(this.trimBlocker)throw Error(this.trimBlocker);const c=tracks.get(selected).find(c=>c.id===clipId);if(!c)throw Error('Select a clip first.');if(!Number.isInteger(frame)||frame<c.start+2||frame>clipEnd(c)-1)throw Error('Move the playhead inside this clip, leaving at least two frames on each side.');if(tracks.get(selected).length>=64)throw Error('Use at most 64 clips per performer.');const take=performer(selected).takes.find(t=>t.id===c.take_id),range=sourceRange(c,take),left=frame-c.start,rightIn=range[0]+left*c.speed,rightOut=Math.min(range[1],range[0]+(c.frames-1)*c.speed);if(rightIn>=rightOut)throw Error('Move the playhead earlier within the native take.');remember();const right={...copy(c),id,start:frame,frames:c.frames-left,source_range:[rightIn,rightOut],repeat_reviewed:false};delete right.transition;c.frames=left;c.source_range=[range[0],range[0]+(left-1)*c.speed];if(c.transition)c.transition.match_phase=false;tracks.get(selected).push(right);clipId=id;selectedPart='clip';},
  move(direction){extended(selected);if(![-1,1].includes(direction))throw Error('Choose earlier or later.');const order=sorted(selected),index=order.findIndex(c=>c.id===clipId),target=index+direction;if(index<0||target<0||target>=order.length)return;remember();const start=order[0].start;[order[index],order[target]]=[order[target],order[index]];delete order[0].transition;let next=start;for(const c of order){c.start=next+(c.transition?.frames||0);next=clipEnd(c)+1;if(c.transition)c.transition.match_phase=false;}tracks.set(selected,order);},
  edit(field,text){
   editable(selected);const c=tracks.get(selected).find(c=>c.id===clipId);if(!c)throw Error('Select a clip first.');
   const key=c.id+':'+field,order=sorted(selected);remember(key);
   if(field==='root_intent'){
    if(!['observed','stationary-reviewed'].includes(text))throw Error('Choose observed motion or reviewed stationary intent.');
    if(text==='observed')delete c.root_intent;else c.root_intent=text;
   }else if(field.startsWith('contact_')){
    if(c.transition?.mode!=='generated')throw Error('Contact windows require generated mode.');
    const [,edge,property]=field.split('_');if(!['source','target'].includes(edge)||!['support','seconds'].includes(property))throw Error('Unknown contact control.');
    const value=property==='seconds'?Number(text):text;
    if(property==='seconds'&&(!Number.isFinite(value)||value<.04||value>.2)||property==='support'&&!['auto','left','right','both','none'].includes(value)){raw.set(key,{performer:selected,clip:c.id,field,value:text,message:'Choose a support foot and 0.04 to 0.20 seconds.'});return;}
    raw.delete(key);c.transition.contacts||={origin:'user-reviewed',source:{support:'auto',seconds:.08},target:{support:'auto',seconds:.08}};
    c.transition.contacts[edge][property]=value;
   }else if(field==='smooth'){
    if(text){if(!this.canConnect)throw Error('These clips need Blender review before connecting.');c.transition={frames:Math.max(2,Math.min(120,Math.round(audit.fps*.25))),match_phase:true};}
    else{const previous=order[order.findIndex(x=>x.id===c.id)-1];if(c.transition&&previous)c.start=clipEnd(previous)+1;delete c.transition;raw.delete(c.id+':transition_frames');}
   }else if(field==='transition_mode'){extended(selected);if(!c.transition)throw Error('Enable a connection first.');if(!['blend','turn','generated'].includes(text))throw Error('Choose a supported connection mode.');if(text==='generated'){const provider=performer(selected).timeline?.motion_bricks;if(provider?.status!=='CONFIGURED')throw Error(provider?.blocker||'Prepare a rig mapping and configure MotionBricks first.');c.transition.seed=1234;c.transition.profile_sha256=provider.profile_sha256;c.transition.frames=Math.max(2,Math.round(audit.fps*.5));}else{delete c.transition.seed;delete c.transition.profile_sha256;delete c.transition.sampling;delete c.transition.contacts;samplingPlan=null;}c.transition.mode=text;c.transition.match_phase=false;
   }else if(field==='match_phase'){if(c.transition?.mode==='generated'&&text)throw Error('Generated repositioning keeps the native opening pose.');if(!c.transition)throw Error('Enable a smooth connection first.');c.transition.match_phase=!!text;
   }else if(field==='travel'){
    if(text){const take=performer(selected).takes.find(t=>t.id===c.take_id);if(take.travel_blocker)throw Error(take.travel_blocker);if(c.source_range?.some((v,i)=>v!==take.range[i]))throw Error('Restore the full native take before adding a calibrated travel path.');if(!c.travel)stationaryFrames.set(c.id,c.frames);const calibrated=[...tracks.get(selected)].reverse().find(x=>x.id!==c.id&&x.take_id===c.take_id&&x.travel?.meters_per_cycle>0&&!x.travel.gait_id);c.travel=take.gait?.status==='estimated'?automaticTravel(take,undefined,c.heading_deg||0):{delta_m:suggestedPath(take.action),meters_per_cycle:calibrated?.travel.meters_per_cycle||0};}
    else{if(c.travel){const take=performer(selected).takes.find(t=>t.id===c.take_id);c.frames=stationaryFrames.get(c.id)??Math.ceil((take.range[1]-take.range[0])/c.speed)+1;}c.travel=null;for(const [k,v] of raw)if(v.clip===c.id&&['pace','direction','distance'].includes(v.field))raw.delete(k);}
   }else if(field==='automatic'){
    if(!c.travel)throw Error('Enable travel first.');
    if(text){const take=performer(selected).takes.find(t=>t.id===c.take_id);if(take.gait?.status!=='estimated')throw Error('No reliable automatic gait estimate is available.');c.travel=automaticTravel(take,Math.hypot(...c.travel.delta_m),c.heading_deg||0);for(const key of ['pace','direction'])raw.delete(c.id+':'+key);}
    else delete c.travel.gait_id;
    c.repeat_reviewed=false;if(c.transition)c.transition.match_phase=false;
   }else if(field==='repeat_reviewed')c.repeat_reviewed=!!text;
   else{
    const n=typeof text==='string'&&text.trim()!==''?Number(text):NaN;
    const take=performer(selected).takes.find(t=>t.id===c.take_id),limits={start:[-100000,100000,true],frames:[2,3601,true],speed:[.1,4,false],distance:[.001,10000,false],pace:[.001,1000,false],direction:[-360,360,false],transition_frames:[2,120,true],heading_deg:[-180,180,false],source_in:[take.range[0],take.range[1],false],source_out:[take.range[0],take.range[1],false]},bound=limits[field];
    if(!bound)throw Error('Unknown motion control.');
    const message=!Number.isFinite(n)||n<bound[0]||n>bound[1]||bound[2]&&!Number.isInteger(n)?`${field}: enter ${bound[2]?'a whole number':'a number'} from ${bound[0]} to ${bound[1]}.`:'';
    if(message){raw.set(key,{performer:selected,clip:c.id,field,value:text,message});return;}
    raw.delete(key);
    if(['distance','direction','pace'].includes(field)){
     if(!c.travel)throw Error('Enable travel first.');
     if(c.travel.gait_id&&['pace','direction'].includes(field))throw Error('Automatic travel follows the measured gait. Switch to manual calibration to override it.');
     if(field==='pace')c.travel.meters_per_cycle=n;
     else if(field==='distance'){const length=Math.hypot(...c.travel.delta_m);c.travel.delta_m=c.travel.delta_m.map(v=>v/length*n);}
     else{const d=Math.hypot(...c.travel.delta_m),angle=n*Math.PI/180;c.travel.delta_m=[d*Math.cos(angle),d*Math.sin(angle)];}
    }else if(field==='heading_deg'){extended(selected);const delta=n-(c.heading_deg||0);c.heading_deg=n;if(c.travel?.gait_id)c.travel.delta_m=rotateDirection(c.travel.delta_m,delta);}
    else if(['source_in','source_out'].includes(field)){extended(selected);if(this.trimBlocker)throw Error(this.trimBlocker);const range=[...sourceRange(c,take)];range[field==='source_in'?0:1]=n;if(range[1]<=range[0]){raw.set(key,{performer:selected,clip:c.id,field,value:text,message:'Source Out must be after Source In.'});return;}c.source_range=range;c.frames=Math.ceil((range[1]-range[0])/c.speed)+1;if(c.transition)c.transition.match_phase=false;}
    else if(field==='transition_frames'){if(!c.transition)throw Error('Enable a smooth connection first.');c.transition.frames=n;}
    else{if(field==='start'&&c.transition)throw Error('Disable the connection before setting an independent start frame.');c[field]=n;}
   }
   if(c.travel?.meters_per_cycle>0){const take=performer(selected).takes.find(t=>t.id===c.take_id);c.frames=plannedFrames(take,c.travel,c.speed);}
   reflow(order);
  },
  moveEndpoint(delta){if(!Array.isArray(delta)||delta.length!==2||!delta.every(Number.isFinite)||Math.hypot(...delta)<.001||Math.hypot(...delta)>10000)return;editable(selected);const c=tracks.get(selected).find(c=>c.id===clipId);if(!c?.travel)return;const order=sorted(selected);remember(c.id+':drag');const take=performer(selected).takes.find(t=>t.id===c.take_id);if(c.travel.gait_id){const length=Math.hypot(...c.travel.delta_m),direction=c.travel.delta_m.map(v=>v/length),projection=Math.max(.001,delta.reduce((n,v,i)=>n+v*direction[i],0));c.travel.delta_m=direction.map(v=>v*projection);}else c.travel.delta_m=[...delta];for(const field of ['distance','direction'])raw.delete(c.id+':'+field);if(c.travel.meters_per_cycle>0)c.frames=plannedFrames(take,c.travel,c.speed);reflow(order);},
  rotateHeading(degrees){
   const p=extended(selected),c=tracks.get(selected).find(c=>c.id===clipId);
   if(!c||!Number.isFinite(degrees))throw Error('Select an animation before rotating.');
   const order=sorted(selected),previous=order[order.findIndex(x=>x.id===c.id)-1];
   if(previous&&!c.transition)throw Error('Connect to previous clip before changing its orientation.');
   for(const clip of order){const take=p.takes.find(t=>t.id===clip.take_id);if(take?.heading_blocker!==null)throw Error(take?.heading_blocker||'Inspect this performer before rotating.');}
   const value=turnAngle(0,degrees),delta=turnAngle(c.heading_deg||0,value);
   if(Math.abs(delta)<1e-8)return;
   remember(c.id+':visual-turn');c.heading_deg=value;
   if(c.transition){c.transition.mode='turn';c.transition.match_phase=false;}
   if(c.travel?.gait_id)c.travel.delta_m=rotateDirection(c.travel.delta_m,delta);
   raw.delete(c.id+':heading_deg');
  },
  shiftFollowing(){const c=this.selectedClip;if(!c)return;remember();let next=clipEnd(c)+1;for(const item of sorted(selected).filter(x=>x.id!==c.id&&x.start>=c.start)){item.start=next+(item.transition?.frames||0);next=clipEnd(item)+1;}},
  arrow(){
   const c=this.selectedClip,p=performer(selected);if(!c?.travel)return null;
   const origin=[...(p.timeline?.origin_m||[0,0,0])];let pendingConnection=false;
   // Geometry stays editable while timing or a connection needs correction.
   // Include known displacements, but never invent an unresolved bridge's travel.
   for(const old of sorted(selected)){
    try{const connection=join(selected,old);if(connection?.placement_pending)pendingConnection=true;const saved=!this.dirty&&p.timeline.connections?.find(j=>j.clip_id===old.id);const delta=saved?.delta_m||connection?.delta_m;if(delta){origin[0]+=delta[0];origin[1]+=delta[1];}}
    catch{pendingConnection=true;}
    if(old.id===c.id)break;
    if(old.travel){origin[0]+=old.travel.delta_m[0];origin[1]+=old.travel.delta_m[1];}
   }
   return {origin_m:origin,delta_m:c.travel.delta_m,meters_per_unit:p.timeline.meters_per_unit,pending_connection:pendingConnection,label:'Unsaved path · '+Math.hypot(...c.travel.delta_m).toFixed(2)+' m'+(c.travel.gait_id?' · drag along the observed gait direction':' · manual direction')};
  },
  finishEdit(){gesture=null;},
  undo(){gesture=null;if(history.length){const old=history.pop();({tracks,raw,stationaryFrames,samplingPlan,selected,clipId,selectedPart}=old);}},
  discard(){tracks=copy(baseline);samplingPlan=null;history=[];raw.clear();stationaryFrames.clear();gesture=null;clipId=null;selectedPart='clip';},
  handoff(frame){if(this.dirty)throw Error('Save or discard Action changes before opening another editor.');performer(selected);frame=frame??audit.reference_frame;if(!Number.isInteger(frame)||frame<audit.frame_range[0]||frame>audit.frame_range[1])throw Error('Choose a frame in the saved scene.');return {version:'action-layer-v1',checkpointId:checkpoint.id,sha256:checkpoint.sha256,inspectionId:run.id,audit_sha256:audit.sha256,performer:selected,frame};},
  request(requestId){if(this.invalid)throw Error(this.errors[0].message);if(!this.changes.length)throw Error('No Action changes to save.');if(this.changes.length>32)throw Error('Save at most 32 performers at once.');const range=this.playbackRange;if(range[1]-range[0]>3600)throw Error('Timeline exceeds 3600 frame intervals.');return {version:'action-layer-v1',requestId,checkpointId:checkpoint.id,sha256:checkpoint.sha256,inspectionId:run.id,audit_sha256:audit.sha256,changes:this.changes,frame_range:range,...(samplingPlan?{sampling_plan:copy(samplingPlan)}:{})};}
 };
}
