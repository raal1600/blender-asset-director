/** Performer-first presentation and local-only timing draft. No implicit approval. */
import {taskBanner} from './workbench-task.mjs';
import {progressLabel} from './workbench-progress.mjs';

// Automatic read-only inspection can race a reload/second tab. Refresh once,
// reuse its exact native receipt, and never retry a mutation or failed job.
export async function ensureActionInspection({read,create,sceneId,checkpointId,sha256}){
  for(let attempt=0;attempt<2;attempt++){
    const state=await read(),scene=state.project.workbench.scenes.find(s=>s.id===sceneId);
    const cp=scene?.checkpoints.find(c=>c.id===(scene.candidate||scene.current));
    if(scene?.stage!=='action'||cp?.id!==checkpointId||cp.sha256!==sha256||state.locked)return;
    if(state.runs.some(r=>r.action==='action-audit'&&r.sceneId===sceneId&&r.checkpointId===checkpointId&&r.checkpointSha256===sha256))return;
    try{await create(state.project.revision);return;}catch(error){if(error.status!==409||attempt===1)throw error;}
  }
}

export function actionInspection(runs,scene,checkpoint){
  return runs.find(r=>r.action==='action-audit'&&r.sceneId===scene.id&&r.checkpointId===checkpoint?.id&&r.checkpointSha256===checkpoint?.sha256&&r.state==='SUCCEEDED')||null;
}
export function actionDraft(checkpoint,run){
  const audit=run.inspection,changes=new Map(),errors=new Map(),history=[];
  let editKey=null;
  let selected=audit.performers.find(p=>p.takes.length)?.name||audit.performers[0]?.name||null;
  const copy=map=>[...map].map(([k,v])=>[k,{...v}]);
  const remember=()=>{history.push({changes:copy(changes),errors:copy(errors)});if(history.length>100)history.shift();};
  const key=(name,field)=>JSON.stringify([name,field]);
  const clearErrors=name=>{for(const [k,e] of errors)if(e.performer===name)errors.delete(k);};
  const performer=name=>{const p=audit.performers.find(p=>p.name===name);if(!p)throw Error('Choose an observed performer.');return p;};
  const timingError=(field,value)=>{
    if(field==='start')return Number.isInteger(value)&&value>=-100000&&value<=100000?'':'Start frame must be a whole number from -100000 to 100000.';
    if(field==='speed')return typeof value==='number'&&Number.isFinite(value)&&value>=.1&&value<=4?'':'Speed must be a number from 0.1 to 4 (1 is normal speed).';
    if(field==='frame')return Number.isInteger(value)&&value>=audit.frame_range[0]&&value<=audit.frame_range[1]?'':`Hold frame must be a whole number from ${audit.frame_range[0]} to ${audit.frame_range[1]}.`;
    throw Error('Unknown timing field.');
  };
  const validate=value=>{for(const field of value.mode==='clip'?['start','speed']:value.mode==='hold'?['frame']:[]){const error=timingError(field,value[field]);if(error)throw Error(error);}};
  return {checkpointId:checkpoint.id,sha256:checkpoint.sha256,run,audit,
    get selected(){return selected;},select:name=>{performer(name);selected=name;editKey=null;},
    get dirty(){return changes.size>0||errors.size>0;},get canUndo(){return history.length>0;},get count(){return new Set([...changes.keys(),...[...errors.values()].map(e=>e.performer)]).size;},
    get invalid(){return errors.size>0;},get errors(){return [...errors.values()].map(e=>({...e}));},
    input(name,field){return errors.get(key(name,field))?.raw??this.value(name)[field];},
    get changes(){return [...changes.values()].map(v=>({...v}));},
    handoff(frame){if(this.dirty)throw Error('Save or discard Action changes before opening another editor.');performer(selected);frame=frame??audit.reference_frame;if(!Number.isInteger(frame)||frame<audit.frame_range[0]||frame>audit.frame_range[1])throw Error('Choose a frame in the saved scene.');return {version:'action-layer-v1',checkpointId:checkpoint.id,sha256:checkpoint.sha256,inspectionId:run.id,audit_sha256:audit.sha256,performer:selected,frame};},
    get playbackRange(){const range=[...audit.frame_range];for(const c of changes.values())if(c.mode==='clip'){const take=performer(c.performer).takes.find(t=>t.id===c.take_id);range[0]=Math.min(range[0],c.start);range[1]=Math.max(range[1],Math.ceil(c.start+(take.range[1]-take.range[0])/c.speed));}return range;},
    value:name=>({...changes.get(name)||{performer:name,mode:'keep'}}),
    change(name,value){const p=performer(name);if(p.unsupported)throw Error(p.unsupported);
      if(value.mode==='clip'&&!p.takes.some(t=>t.id===value.take_id))throw Error('This take does not belong to this performer.');
      if(!['keep','clip','hold'].includes(value.mode))throw Error('Unknown performance choice.');
      if(!changes.has(name)&&value.mode!=='keep'&&changes.size>=32)throw Error('Save at most 32 performer changes at once.');
      validate(value);remember();editKey=null;clearErrors(name);if(value.mode==='keep')changes.delete(name);else changes.set(name,{...value,performer:name});
    },
    editTiming(name,field,raw){
      const p=performer(name),value=this.value(name);if(p.unsupported)throw Error(p.unsupported);
      if(!(value.mode==='clip'?['start','speed']:value.mode==='hold'?['frame']:[]).includes(field))throw Error('Choose a performance before editing its timing.');
      if(typeof raw!=='string')throw Error('Timing input must be text.');
      const k=key(name,field),number=raw.trim()===''?NaN:Number(raw),message=timingError(field,number);
      if(message?errors.get(k)?.raw===raw:!errors.has(k)&&value[field]===number)return;
      if(editKey!==k){remember();editKey=k;}
      if(message)errors.set(k,{performer:name,field,raw,message});
      else{errors.delete(k);changes.set(name,{...value,[field]:number});}
    },
    finishEdit(){editKey=null;},
    holdAll(frame){if(audit.performers.length>32||audit.performers.some(p=>p.unsupported))throw Error('This scene needs Blender to hold every performer together.');validate({mode:'hold',frame});remember();editKey=null;errors.clear();for(const p of audit.performers)changes.set(p.name,{performer:p.name,mode:'hold',frame});},
    undo(){editKey=null;if(history.length){const old=history.pop();changes.clear();errors.clear();for(const [k,v] of old.changes)changes.set(k,v);for(const [k,v] of old.errors)errors.set(k,v);}},
    discard(){changes.clear();errors.clear();history.length=0;editKey=null;},
    request(requestId){if(this.invalid)throw Error(this.errors[0].message);if(!changes.size)throw Error('No Action changes to save.');for(const value of changes.values())validate(value);const range=this.playbackRange;if(range[1]-range[0]>3600)throw Error('Full motion exceeds the 3600-frame playback bound. Adjust timing or use Blender.');return {version:'action-layer-v1',requestId,checkpointId:checkpoint.id,sha256:checkpoint.sha256,inspectionId:run.id,audit_sha256:audit.sha256,changes:this.changes,...(range.some((f,i)=>f!==audit.frame_range[i])?{frame_range:range}:{})};}
  };
}

export function actionDraftStatus(draft){return draft?.invalid?'Check timing for '+[...new Set(draft.errors.map(e=>e.performer))].join(', '):draft?.dirty?'Unsaved Action changes · '+draft.count+' performer'+(draft.count===1?'':'s'):'Saved performance';}
export function actionPreviewScope(draft,stale=false){return stale?'Older saved checkpoint · local draft retained':draft?.invalid?'Playback shows the saved scene. Correct the highlighted timing fields before saving.':draft?.dirty?'Playback shows the saved scene. Save changes to preview the new motion. Planned playback: frames '+draft.playbackRange.join('–')+'; expanded if needed to include each full take.':'Play the whole saved scene together. Inspection lighting is approximate; playback does not approve motion.';}

export function actionView({project,scene,stages,checkpoint,runs,locked,taskStatus,cap,draft,saving,esc,b}){
  const active=locked||!!scene.task||!!scene.run||!!saving,stale=!!draft&&(draft.checkpointId!==checkpoint?.id||draft.sha256!==checkpoint?.sha256);
  const run=runs.find(r=>r.id===scene.run),attempt=runs.find(r=>r.action==='action-audit'&&r.sceneId===scene.id&&r.checkpointId===checkpoint?.id);
  const p=draft?.audit.performers.find(p=>p.name===draft.selected),value=p?draft.value(p.name):null;
  const disabled=active||stale||!draft||!!p?.unsupported;
  const button=(label,action,cls='',off=false)=>b(label,action,{},cls,active||off);
  const status=saving?'Saving performance in Blender':stale?'Preview out of date — discard the local draft to reload':scene.run?progressLabel(run):actionDraftStatus(draft);
  const timing=(label,field,min,max,step='1')=>{
    const error=draft.errors.find(e=>e.performer===p.name&&e.field===field)?.message||'';
    return `<label>${label}<input type="number" aria-label="${label}" data-action-field="${field}" required min="${min}" max="${max}" step="${step}" value="${esc(draft.input(p.name,field))}" aria-invalid="${!!error}" aria-describedby="action-${field}-error" ${disabled?'disabled':''}><small id="action-${field}-error" class="action-field-error" ${error?'':'hidden'}>${esc(error)}</small></label>`;
  };
  const controls=draft?`<div class="action-controls"><label>Performer<select data-action-field="performer" ${active?'disabled':''}>${draft.audit.performers.map(x=>`<option ${x.name===draft.selected?'selected':''} value="${esc(x.name)}">${esc(x.name)}${draft.value(x.name).mode!=='keep'?' · edited':''}</option>`).join('')}</select></label>${p?`<label>Performance<select data-action-field="mode" ${disabled?'disabled':''}><option value="keep" ${value.mode==='keep'?'selected':''}>Keep saved performance</option><option value="hold" ${value.mode==='hold'?'selected':''}>Hold a pose · static</option>${p.takes.map(t=>`<option value="${esc(t.id)}" ${value.take_id===t.id?'selected':''}>${esc(t.action)} · ${esc(t.range.join('–'))}</option>`).join('')}</select></label>${value.mode==='clip'?timing('Start frame','start',-100000,100000)+timing('Speed','speed',.1,4,'any'):value.mode==='hold'?timing('Hold frame','frame',draft.audit.frame_range[0],draft.audit.frame_range[1]):''}`:''}</div>`: '';
  return `<div class="world-top"><label>Scene<select id="scene-picker" aria-label="Selected scene">${project.workbench.scenes.map(x=>`<option value="${esc(x.id)}" ${x.id===scene.id?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label><span class="grow"></span><details class="world-more"><summary>More</summary><div class="world-menu">${b('Add scene','new-scene')}${b('Checkpoint history','history')}${button('Find motion in library','browse-assets')}${button('Reviewed motion specialist','codex')}${button('Import saved working scene','import','',!!scene.candidate)}</div></details></div>
  <nav class="steps world-steps" aria-label="Activities in this scene">${stages.map((st,i)=>b((scene.completed[st.id]?'✓ ':i+1+' ')+st.short,'stage',{stage:st.id},scene.stage===st.id?'active':'',active||!!scene.candidate||stages.slice(0,i).some(x=>!scene.completed[x.id]))).join('')}</nav>
  <section class="action-workspace" aria-label="Action layer"><header class="action-heading"><div><h1>Bring your world to life</h1><p>Choose a performer. Keep its motion, choose a native take, or hold a pose.</p></div>${button('Edit performance in Blender','task','ghost',!cap?.task_workspace||!!scene.candidate)}</header>
  <div class="action-savebar"><span role="status">${esc(status)}</span><div>${button('Discard changes','action-discard','ghost',!draft?.dirty||!!saving)}${button('Undo','action-undo','ghost',!draft?.canUndo||stale)}${button('Save changes','action-save',draft?.dirty?'primary':'ghost',!draft?.dirty||draft?.invalid||stale)}</div></div>
  ${scene.task?taskBanner(scene,taskStatus,esc,b):''}${run?`<div class="note" role="status">${esc(progressLabel(run))} ${b('Inspect operation','recover',{run:run.id},'ghost')}</div>`:''}
  ${!cap?.action_layer?'<p class="note warn">Install the matching Action runtime before using native motion controls.</p>':''}
  ${controls}
  ${checkpoint?'<section class="viewer-3d" data-scene-viewer aria-label="Saved scene in 3D"></section>':'<p>No saved World yet. Return to World to add your scene.</p>'}
  <p class="action-preview-scope">${esc(actionPreviewScope(draft,stale))}</p>
  ${draft?`${p?.unsupported?`<p class="note warn">${esc(p.unsupported)}. Use Blender or the reviewed specialist.</p>`:''}<details class="action-details"><summary>Timing and motion details</summary><p>${esc(draft.audit.fps)} fps · scene frames ${esc(draft.audit.frame_range.join('–'))}. Native source keys and World placement stay intact. Timing changes use the complete take; no loop, retarget or inferred mapping.</p>${button('Hold whole scene at current frame','action-hold-all','ghost',disabled)}${p?.type==='ARMATURE'?button('Edit rig controls in Blender','action-rig','ghost',!cap?.action_task||!!draft.dirty):''}${button('Inspect performers again','action-inspect','ghost',!!draft.dirty)}${draft.audit.unassigned.length?`<p>${draft.audit.unassigned.length} unbound action slot(s) need reviewed binding in Blender; they are not assigned by name.</p>`:''}</details>`:checkpoint?`<p role="status">${attempt?.state==='FAILED'?esc(attempt.error):'Inspecting saved performers and their native motion…'}</p>${!active?button(attempt?'Retry performer inspection':'Inspect performers','action-inspect'):''}`:''}
  <section class="world-next"><div class="grow"><h2>Review the motion, then continue</h2><p>Check timing, deformation and contacts. A still scene is valid too. Saving and playback are not approval.</p></div>${button('Action ready · continue to Shots','action-ready','primary',!checkpoint||!!draft?.dirty||stale||!draft)}</section></section>`;
}
