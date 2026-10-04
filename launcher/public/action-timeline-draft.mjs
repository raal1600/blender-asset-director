/** Local clip edits; no jobs, approvals, native keys or source mutations. */
import {validateTimeline,timelineTiming,plannedFrames,clipEnd,connection,stitchVersion} from './action-timeline-contract.mjs';
const copy=v=>structuredClone(v);
const automaticTravel=(take,distance=take.gait.meters_per_cycle)=>{const g=take.gait,n=Math.hypot(...g.direction);return {delta_m:g.direction.map(v=>distance*v/n),meters_per_cycle:g.meters_per_cycle,gait_id:g.id};};
// Labels suggest an editable WORLD-axis arrow only; they do not prove facing,
// gait semantics, root ownership, travel speed, loop quality or approval.
export function suggestedPath(label){const words=String(label).toLowerCase().split(/[^a-z]+/);return words.some(w=>['back','backward','backwards'].includes(w))?[0,-1]:words.includes('right')?[1,0]:words.includes('left')?[-1,0]:[0,1];}
export function timelineDraft(checkpoint,run){
 const audit=run.inspection,baseline=new Map(audit.performers.map(p=>[p.name,copy(p.timeline?.clips||[])]));
 let tracks=copy(baseline),history=[],raw=new Map(),stationaryFrames=new Map(),gesture=null,selected=audit.performers.find(p=>p.takes.length)?.name||audit.performers[0]?.name||null,clipId=null;
 const performer=name=>{const p=audit.performers.find(p=>p.name===name);if(!p)throw Error('Choose an observed performer.');return p;};
 const editable=name=>{const p=performer(name);if(p.unsupported||p.timeline?.error)throw Error(p.unsupported||p.timeline.error);return p;};
 const remember=key=>{if(!key||gesture!==key){history.push({tracks:copy(tracks),raw:copy(raw),stationaryFrames:copy(stationaryFrames),selected,clipId});if(history.length>100)history.shift();}gesture=key;};
 const sorted=name=>[...tracks.get(name)].sort((a,b)=>a.start-b.start);
 const canConnect=(p,previous,take)=>{const prior=p.takes.find(t=>t.id===previous?.take_id);return p.timeline?.stitch_version===stitchVersion&&take?.stitch_blocker===null&&prior?.stitch_blocker===null&&/^[0-9a-f]{64}$/.test(take.stitch_channels||'')&&take.stitch_channels===prior.stitch_channels;};
 const reflow=order=>{for(let i=1;i<order.length;i++)if(order[i].transition)order[i].start=clipEnd(order[i-1])+1+order[i].transition.frames;};
 const join=(name,c)=>{const p=performer(name),order=sorted(name),previous=order[order.findIndex(x=>x.id===c.id)-1];if(!c.transition)return null;if(!canConnect(p,previous,p.takes.find(t=>t.id===c.take_id)))throw Error('These clips need a matching connection inspection or Blender review.');return connection(previous,c,p.takes.find(t=>t.id===previous.take_id),p.takes.find(t=>t.id===c.take_id));};
 const issue=(name,c)=>{try{const take=performer(name).takes.find(t=>t.id===c.take_id);if(!take)throw Error('Saved take changed; inspect in Blender.');if(c.travel&&!c.travel.gait_id&&(!Number.isFinite(c.travel.meters_per_cycle)||c.travel.meters_per_cycle<.001||c.travel.meters_per_cycle>1000))return {field:'pace',message:'Set metres per cycle to calibrate this path, or turn off path movement.'};timelineTiming(c,take);if(c.travel&&take.travel_blocker)throw Error(take.travel_blocker);join(name,c);return null;}catch(e){return {field:'clip',message:e.message};}};
 const changed=()=>[...tracks].filter(([name,clips])=>JSON.stringify(clips)!==JSON.stringify(baseline.get(name)));
 const errors=()=>{const list=[...raw.values()].filter(x=>x.message).map(copy);for(const [name,clips] of tracks){for(const c of clips){const problem=issue(name,c);if(problem&&!raw.has(c.id+':'+problem.field))list.push({performer:name,clip:c.id,...problem});}try{validateTimeline({performer:name,mode:'timeline',clips:sorted(name)});}catch(e){list.push({performer:name,field:'track',message:e.message});}}return list;};
 return {timeline:true,checkpointId:checkpoint.id,sha256:checkpoint.sha256,run,audit,
  get selected(){return selected;},get selectedClip(){return copy(tracks.get(selected)?.find(c=>c.id===clipId)||null);},
  get dirty(){return changed().length>0||raw.size>0;},get count(){return changed().length;},get canUndo(){return history.length>0;},get errors(){return errors();},get invalid(){return errors().length>0;},
  get changes(){return changed().map(([performer])=>({performer,mode:'timeline',clips:copy(sorted(performer))}));},
  get gait(){const c=this.selectedClip;return performer(selected).takes.find(t=>t.id===c?.take_id)?.gait;},
  get canConnect(){const c=this.selectedClip,order=sorted(selected),previous=order[order.findIndex(x=>x.id===c?.id)-1],p=performer(selected);return !!c&&canConnect(p,previous,p.takes.find(t=>t.id===c.take_id));},
  get connection(){try{return this.selectedClip?join(selected,this.selectedClip):null;}catch{return null;}},
  get playbackRange(){const range=[...audit.frame_range];for(const clips of tracks.values())for(const c of clips){range[0]=Math.min(range[0],c.start);range[1]=Math.max(range[1],clipEnd(c));}return range;},
  clips:name=>copy(sorted(name)),value:name=>({performer:name,mode:changed().some(([n])=>n===name)?'timeline':'keep'}),
  select(name,id=null){performer(name);selected=name;clipId=id;gesture=null;},
  nextFrame(name=selected){return Math.max(audit.frame_range[0],...tracks.get(name).map(c=>clipEnd(c)+1));},
  add(takeId,id='clip_'+crypto.randomUUID()){
   const p=editable(selected),take=p.takes.find(t=>t.id===takeId);if(!take)throw Error('Choose an observed native take.');
   if(tracks.get(selected).length>=64)throw Error('Use at most 64 clips per performer.');
   remember();clipId=id;const previous=sorted(selected).at(-1),transition=canConnect(p,previous,take)?{frames:Math.max(2,Math.min(120,Math.round(audit.fps*.25))),match_phase:true}:null;
   tracks.get(selected).push({id,take_id:takeId,start:this.nextFrame()+(transition?.frames||0),frames:Math.ceil(take.range[1]-take.range[0])+1,speed:1,repeat_reviewed:false,travel:null,...(transition?{transition}:{})});
  },
  remove(){editable(selected);if(!clipId)return;remember();tracks.set(selected,tracks.get(selected).filter(c=>c.id!==clipId));const order=sorted(selected);if(order[0])delete order[0].transition;reflow(order);for(const [k,v] of raw)if(v.clip===clipId)raw.delete(k);clipId=null;},
  input(field){const c=this.selectedClip;if(!c)return '';const error=raw.get(c.id+':'+field);if(error)return error.value;return field==='transition_frames'?c.transition?.frames||'':field==='distance'?c.travel?Math.hypot(...c.travel.delta_m):0:field==='pace'?c.travel?.meters_per_cycle||'':field==='direction'?c.travel?Math.atan2(c.travel.delta_m[1],c.travel.delta_m[0])*180/Math.PI:0:c[field];},
  edit(field,text){
   editable(selected);const c=tracks.get(selected).find(c=>c.id===clipId);if(!c)throw Error('Select a clip first.');
   const key=c.id+':'+field,order=sorted(selected);remember(key);
   if(field==='smooth'){
    if(text){if(!this.canConnect)throw Error('These clips need Blender review before connecting.');c.transition={frames:Math.max(2,Math.min(120,Math.round(audit.fps*.25))),match_phase:true};}
    else{const previous=order[order.findIndex(x=>x.id===c.id)-1];if(c.transition&&previous)c.start=clipEnd(previous)+1;delete c.transition;raw.delete(c.id+':transition_frames');}
   }else if(field==='match_phase'){if(!c.transition)throw Error('Enable a smooth connection first.');c.transition.match_phase=!!text;
   }else if(field==='travel'){
    if(text){const take=performer(selected).takes.find(t=>t.id===c.take_id);if(take.travel_blocker)throw Error(take.travel_blocker);if(!c.travel)stationaryFrames.set(c.id,c.frames);const calibrated=[...tracks.get(selected)].reverse().find(x=>x.id!==c.id&&x.take_id===c.take_id&&x.travel?.meters_per_cycle>0);c.travel=take.gait?.status==='estimated'?automaticTravel(take):{delta_m:suggestedPath(take.action),meters_per_cycle:calibrated?.travel.meters_per_cycle||0};}
    else{if(c.travel){const take=performer(selected).takes.find(t=>t.id===c.take_id);c.frames=stationaryFrames.get(c.id)??Math.ceil((take.range[1]-take.range[0])/c.speed)+1;}c.travel=null;for(const [k,v] of raw)if(v.clip===c.id&&['pace','direction','distance'].includes(v.field))raw.delete(k);}
   }else if(field==='automatic'){
    if(!c.travel)throw Error('Enable travel first.');
    if(text){const take=performer(selected).takes.find(t=>t.id===c.take_id);if(take.gait?.status!=='estimated')throw Error('No reliable automatic gait estimate is available.');c.travel=automaticTravel(take,Math.hypot(...c.travel.delta_m));for(const key of ['pace','direction'])raw.delete(c.id+':'+key);}
    else delete c.travel.gait_id;
    c.repeat_reviewed=false;
   }else if(field==='repeat_reviewed')c.repeat_reviewed=!!text;
   else{
    const n=typeof text==='string'&&text.trim()!==''?Number(text):NaN;
    const limits={start:[-100000,100000,true],frames:[2,3601,true],speed:[.1,4,false],distance:[.001,10000,false],pace:[.001,1000,false],direction:[-360,360,false],transition_frames:[2,120,true]},bound=limits[field];
    if(!bound)throw Error('Unknown motion control.');
    const message=!Number.isFinite(n)||n<bound[0]||n>bound[1]||bound[2]&&!Number.isInteger(n)?`${field}: enter ${bound[2]?'a whole number':'a number'} from ${bound[0]} to ${bound[1]}.`:'';
    if(message){raw.set(key,{performer:selected,clip:c.id,field,value:text,message});return;}
    raw.delete(key);
    if(['distance','direction','pace'].includes(field)){
     if(!c.travel)throw Error('Enable travel first.');
     if(c.travel.gait_id&&['pace','direction'].includes(field))throw Error('Automatic travel follows the measured gait. Switch to manual calibration to override it.');
     if(field==='pace')c.travel.meters_per_cycle=n;
     else{const d=field==='distance'?n:Math.hypot(...c.travel.delta_m),angle=field==='direction'?n*Math.PI/180:Math.atan2(c.travel.delta_m[1],c.travel.delta_m[0]);c.travel.delta_m=[d*Math.cos(angle),d*Math.sin(angle)];}
    }else if(field==='transition_frames'){if(!c.transition)throw Error('Enable a smooth connection first.');c.transition.frames=n;}
    else{if(field==='start'&&c.transition)throw Error('Disable the connection before setting an independent start frame.');c[field]=n;}
   }
   if(c.travel?.meters_per_cycle>0){const take=performer(selected).takes.find(t=>t.id===c.take_id);c.frames=plannedFrames(take,c.travel,c.speed);}
   reflow(order);
  },
  moveEndpoint(delta){if(!Array.isArray(delta)||delta.length!==2||!delta.every(Number.isFinite)||Math.hypot(...delta)<.001||Math.hypot(...delta)>10000)return;editable(selected);const c=tracks.get(selected).find(c=>c.id===clipId);if(!c?.travel)return;const order=sorted(selected);remember(c.id+':drag');const take=performer(selected).takes.find(t=>t.id===c.take_id);if(c.travel.gait_id){const g=take.gait,projection=Math.max(.001,delta.reduce((n,v,i)=>n+v*g.direction[i],0));c.travel=automaticTravel(take,projection);}else c.travel.delta_m=[...delta];for(const field of ['distance','direction'])raw.delete(c.id+':'+field);if(c.travel.meters_per_cycle>0)c.frames=plannedFrames(take,c.travel,c.speed);reflow(order);},
  shiftFollowing(){const c=this.selectedClip;if(!c)return;remember();let next=clipEnd(c)+1;for(const item of sorted(selected).filter(x=>x.id!==c.id&&x.start>=c.start)){item.start=next+(item.transition?.frames||0);next=clipEnd(item)+1;}},
  arrow(){
   const c=this.selectedClip,p=performer(selected);if(!c?.travel)return null;
   const origin=[...(p.timeline?.origin_m||[0,0,0])];let pendingConnection=false;
   // Geometry stays editable while timing or a connection needs correction.
   // Include known displacements, but never invent an unresolved bridge's travel.
   for(const old of sorted(selected)){
    try{const delta=join(selected,old)?.delta_m;if(delta){origin[0]+=delta[0];origin[1]+=delta[1];}}
    catch{pendingConnection=true;}
    if(old.id===c.id)break;
    if(old.travel){origin[0]+=old.travel.delta_m[0];origin[1]+=old.travel.delta_m[1];}
   }
   return {origin_m:origin,delta_m:c.travel.delta_m,meters_per_unit:p.timeline.meters_per_unit,pending_connection:pendingConnection,label:'Unsaved path · '+Math.hypot(...c.travel.delta_m).toFixed(2)+' m'+(c.travel.gait_id?' · drag along the observed gait direction':' · manual direction')};
  },
  finishEdit(){gesture=null;},
  undo(){gesture=null;if(history.length){const old=history.pop();({tracks,raw,stationaryFrames,selected,clipId}=old);}},
  discard(){tracks=copy(baseline);history=[];raw.clear();stationaryFrames.clear();gesture=null;clipId=null;},
  handoff(frame){if(this.dirty)throw Error('Save or discard Action changes before opening another editor.');performer(selected);frame=frame??audit.reference_frame;if(!Number.isInteger(frame)||frame<audit.frame_range[0]||frame>audit.frame_range[1])throw Error('Choose a frame in the saved scene.');return {version:'action-layer-v1',checkpointId:checkpoint.id,sha256:checkpoint.sha256,inspectionId:run.id,audit_sha256:audit.sha256,performer:selected,frame};},
  request(requestId){if(this.invalid)throw Error(this.errors[0].message);if(!this.changes.length)throw Error('No Action changes to save.');if(this.changes.length>32)throw Error('Save at most 32 performers at once.');const range=this.playbackRange;if(range[1]-range[0]>3600)throw Error('Timeline exceeds 3600 frame intervals.');return {version:'action-layer-v1',requestId,checkpointId:checkpoint.id,sha256:checkpoint.sha256,inspectionId:run.id,audit_sha256:audit.sha256,changes:this.changes,frame_range:range};}
 };
}
