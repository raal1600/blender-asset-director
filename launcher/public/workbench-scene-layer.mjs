/** Progressive camera/shared-light editing. Draft values never masquerade as renders. */
import {taskBanner} from './workbench-task.mjs';
import {progressLabel} from './workbench-progress.mjs';
import {shotFor} from './workbench-lineage.mjs';
const copy=value=>structuredClone(value),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const geometry=audit=>audit.scene.objects.filter(o=>['MESH','CURVE','SURFACE','FONT','META'].includes(o.type));
export function layerInspection(runs,scene,checkpoint){
 return runs.find(r=>r.action==='scene-layer-audit'&&r.sceneId===scene.id&&r.checkpointId===checkpoint?.id&&r.checkpointSha256===checkpoint?.sha256&&r.inspection?.layer===scene.stage&&r.state==='SUCCEEDED')||null;
}
export async function ensureLayerInspection({read,create,sceneId,checkpointId,sha256,layer}){
 for(let attempt=0;attempt<2;attempt++){
  const state=await read(),scene=state.project.workbench.scenes.find(s=>s.id===sceneId),cp=scene?.checkpoints.find(c=>c.id===(scene.candidate||scene.current));
  if(scene?.stage!==layer||cp?.id!==checkpointId||cp.sha256!==sha256||state.locked)return;
  if(state.runs.some(r=>r.action==='scene-layer-audit'&&r.sceneId===sceneId&&r.checkpointId===checkpointId&&r.checkpointSha256===sha256&&r.options?.layer===layer))return;
  try{await create(state.project.revision);return;}catch(error){if(error.status!==409||attempt===1)throw error;}
 }
}
const number=(value,min=-1e9,max=1e9)=>{
 if(typeof value==='string'&&!value.trim())throw Error('Enter a number; an empty field is not zero.');
 const n=Number(value);if(!Number.isFinite(n)||n<min||n>max)throw Error(`Enter a number between ${min} and ${max}.`);return n;
};
export function sceneLayerDraft(checkpoint,run){
 const audit=run.inspection,layer=audit.layer,history=[];let editKey=null,operations=[],selected=audit.look.state.lights[0]?.name||null;
 const remember=key=>{if(!key||key!==editKey){history.push(copy(operations));if(history.length>100)history.shift();}editKey=key;};
 const light=name=>{const found=audit.look.state.lights.find(l=>l.name===name);if(!found)throw Error('Choose an observed scene light.');return found;};
 const group=op=>operations.find(o=>o.operation===op)?.options||{};
 const update=(operation,options)=>{operations=operations.filter(o=>o.operation!==operation);if(Object.keys(options).length)operations.push({operation,options:copy(options)});};
 return {checkpointId:checkpoint.id,sha256:checkpoint.sha256,audit,run,layer,
  get selected(){return selected;},select(name){light(name);selected=name;editKey=null;},finishEdit(){editKey=null;},
  get dirty(){return operations.length>0;},get canUndo(){return history.length>0;},get operations(){return copy(operations);},
  value(name){return {...copy(light(name)),...copy(group('light-adjust').lights?.find(l=>l.name===name)||{})};},
  setting(kind,key){return group(kind+'-adjust')[key]??(kind==='world'?audit.look.state.world[key==='strength'?'background_strength':key]:audit.look.state.color_management[key]);},
  changeLight(name,key,value){
   if(layer!=='light')throw Error('Light edits belong in Light.');const original=light(name);if(original.unsupported)throw Error(original.unsupported);
   const ranges={energy:[0,1e6],size:[0,1e5],shadow_soft_size:[0,1e5],angle_deg:[0,180],spot_size_deg:[.1,180]};
   const vector=key==='color'||key==='location';
   if(!Object.hasOwn(original,key)||!(vector||Object.hasOwn(ranges,key)))throw Error('Use Blender for this light property.');
   const allowed={size:['AREA'],shadow_soft_size:['POINT','SPOT'],angle_deg:['SUN'],spot_size_deg:['SPOT']};
   if(allowed[key]&&!allowed[key].includes(original.type))throw Error('This property is not supported by this light type.');
   if(vector){if(!Array.isArray(value)||value.length!==3)throw Error('Enter three components.');value=value.map(v=>number(v,...(key==='color'?[0,1]:[-1e9,1e9])));}else value=number(value,...ranges[key]);
   const lights=copy(group('light-adjust').lights||[]),found=lights.find(l=>l.name===name)||{name};
   if(!lights.includes(found))lights.push(found);
   if(same(value,original[key]))delete found[key];else found[key]=value;
   const kept=lights.filter(l=>Object.keys(l).length>1);if(kept.length>32)throw Error('Save up to 32 changed lights at a time.');
   remember('light:'+name+':'+key);update('light-adjust',kept.length?{lights:kept}:{});
  },
  changeSetting(kind,key,value){
   if(layer!=='light'||!['world','look'].includes(kind)||!(kind==='world'?key==='strength':key==='exposure'))throw Error('Unsupported lighting control.');
   if(!(kind==='world'?audit.look.editable.world:audit.look.editable.color_management).includes(key))throw Error('This setting needs detailed Blender editing.');
   value=number(value,...(kind==='world'?[0,1e6]:[-100,100]));const options=copy(group(kind+'-adjust'));
   const original=kind==='world'?audit.look.state.world.background_strength:audit.look.state.color_management[key];
   if(value===original)delete options[key];else options[key]=value;remember(kind+':'+key);update(kind+'-adjust',options);
  },
  fitCamera({name,subjects,direction,lens,frame,margin=.1,projection='PERSP'}){
   if(layer!=='shots')throw Error('Camera creation belongs in Shots.');
   if(typeof name!=='string'||!name.trim()||new TextEncoder().encode(name).length>63||/[\r\n\0]/.test(name)||audit.scene.objects.some(o=>o.name===name))throw Error('Choose a new camera name (up to 63 UTF-8 bytes).');
   if(!Array.isArray(subjects)||!subjects.length||subjects.length>128||new Set(subjects).size!==subjects.length||subjects.some(n=>!geometry(audit).some(o=>o.name===n)))throw Error('Choose observed scene geometry to frame.');
   if(!Array.isArray(direction)||direction.length!==3)throw Error('Enter a camera direction.');direction=direction.map(v=>number(v));if(Math.hypot(...direction)<1e-9)throw Error('Camera direction cannot be zero.');
   frame=number(frame,...audit.scene.frame_range);if(!Number.isInteger(frame))throw Error('Choose an integer frame.');
   if(!['PERSP','ORTHO'].includes(projection))throw Error('Choose perspective or orthographic.');
   const options={subjects:[...subjects],frames:[frame],direction,lens_mm:number(lens,1,1000),margin:number(margin,0,.449999),projection};
   remember();operations=[{operation:'camera-fit',name,options}];
  },
  undo(){editKey=null;if(history.length)operations=history.pop();},discard(){operations=[];history.length=0;editKey=null;},
  request(requestId){if(!operations.length)throw Error('No camera or lighting changes to save.');return {version:'scene-layer-v1',layer,requestId,checkpointId:checkpoint.id,sha256:checkpoint.sha256,inspectionId:run.id,audit_sha256:audit.sha256,operations:copy(operations)};}
 };
}

export function cameraForm(draft,esc){
 const {audit}=draft,range=audit.scene.frame_range;let name='Camera';for(let i=2;audit.scene.objects.some(o=>o.name===name);i++)name='Camera '+i;
 return `<p>Create a separate camera around the geometry you choose. This fits visible bounds at one frame; it is a technical starting view, not reviewed composition. Existing cameras and motion stay intact.</p><label>Camera name<input id="layer-camera-name" maxlength="63" value="${esc(name)}"></label><fieldset class="layer-subjects"><legend>What should this camera frame?</legend>${geometry(audit).map(o=>`<label><input type="checkbox" name="layer-subject" value="${esc(o.name)}">${esc(o.name)}</label>`).join('')}</fieldset><div class="fields"><label>Lens (mm)<input id="layer-lens" type="number" value="50" min="1" max="1000"></label><label>Fit at frame<input id="layer-frame" type="number" value="${range[0]}" min="${range[0]}" max="${range[1]}"></label></div><fieldset class="layer-vector"><legend>View direction · from subject toward camera</legend>${['X','Y','Z'].map((axis,i)=>`<label>${axis}<input id="layer-direction-${i}" type="number" step="any" value="${[1,-1,1][i]}"></label>`).join('')}</fieldset><p>50 mm and direction (1, −1, 1) are editable starting values. The saved scene's aspect and Action timing are preserved. Name the shot after saving this camera.</p>`;
}

export function sceneLayerView({project,scene,stages,checkpoint,runs,locked,taskStatus,cap,draft,saving,esc,b}){
 const shots=scene.shots||[],layer=scene.stage,isLight=layer==='light',shot=shotFor(scene),active=locked||!!scene.task||!!scene.run||!!saving;
 const stale=!!draft&&(draft.checkpointId!==checkpoint?.id||draft.sha256!==checkpoint?.sha256),run=runs.find(r=>r.id===scene.run);
 const attempt=runs.find(r=>r.action==='scene-layer-audit'&&r.sceneId===scene.id&&r.checkpointId===checkpoint?.id&&r.options?.layer===layer);
 const editDisabled=active||stale||!draft||cap?.scene_layer!=='scene-layer-v1';
 const button=(label,action,cls='',off=false,data={})=>b(label,action,data,cls,active||off);
 const status=saving?'Saving in Blender · previous scene preserved':stale?'Saved scene changed elsewhere · local draft retained':draft?.dirty?'Unsaved '+(isLight?'lighting':'camera')+' changes':run?progressLabel(run):'All changes saved';
 const selected=draft?.selected?draft.value(draft.selected):null;
 const field=(label,key,value,{kind='light',min, max,step='any',index,off=false}={})=>`<label>${esc(label)}<input type="number" data-layer-field="${key}" data-layer-kind="${kind}" ${index===undefined?'':`data-layer-index="${index}"`} value="${esc(value)}" step="${step}" ${min===undefined?'':`min="${min}"`} ${max===undefined?'':`max="${max}"`} ${editDisabled||off?'disabled':''}></label>`;
 const lightControls=selected?`<div class="layer-controls"><label>Scene light<select data-layer-field="selected" ${editDisabled?'disabled':''}>${draft.audit.look.state.lights.map(l=>`<option value="${esc(l.name)}" ${l.name===selected.name?'selected':''}>${esc(l.name)} · ${esc(l.type)}</option>`).join('')}</select></label>${field(selected.type==='SUN'?'Strength (W/m²)':selected.normalize===false?'Energy (Blender units)':'Power (W)','energy',selected.energy,{min:0,max:1e6,off:!!selected.unsupported})}${selected.type==='AREA'?field('Size','size',selected.size,{min:0,max:1e5,off:!!selected.unsupported}):['POINT','SPOT'].includes(selected.type)?field('Soft radius','shadow_soft_size',selected.shadow_soft_size,{min:0,max:1e5,off:!!selected.unsupported}):field('Sun angle (°)','angle_deg',selected.angle_deg,{min:0,max:180,off:!!selected.unsupported})}</div>${selected.unsupported?`<p class="note warn">${esc(selected.unsupported)}. Open Blender for this light.</p>`:`<details class="layer-details"><summary>Light color and placement</summary><fieldset class="layer-vector"><legend>Linear RGB · not a screen color</legend>${['R','G','B'].map((axis,i)=>field(axis,'color',selected.color[i],{min:0,max:1,index:i})).join('')}</fieldset><fieldset class="layer-vector"><legend>World position · scene units</legend>${['X','Y','Z'].map((axis,i)=>field(axis,'location',selected.location[i],{index:i})).join('')}</fieldset></details>`}`:draft?'<p>No scene lights were observed. Open Blender to add the light you need; existing world and materials stay intact.</p>':'';
 const shotControls=`<div class="layer-shotbar" aria-label="Shots in this scene">${button('Whole scene','scene-context',!shot?'active':'ghost',!!scene.candidate)}${shots.map(x=>button(x.name,'select-shot',x.id===shot?.id?'active':'ghost',!!scene.candidate,{id:x.id})).join('')}${!isLight?button('+ Name a shot','new-shot','ghost',!checkpoint||!!scene.candidate):''}</div>${shot?`<p class="layer-scope">${esc(shot.camera)} · frames ${shot.start}–${shot.end} · shot v${shot.revision} ${!isLight?button('Edit name / range','edit-shot','small ghost',!!scene.candidate,{id:shot.id}):''}</p>`:'<p class="layer-scope">Choose a named shot for its exact saved camera and range. Orbiting does not change a camera.</p>'}`;
 return `<div class="world-top"><label>Scene<select id="scene-picker" aria-label="Selected scene">${project.workbench.scenes.map(x=>`<option value="${esc(x.id)}" ${x.id===scene.id?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label><span class="grow"></span><details class="world-more"><summary>More</summary><div class="world-menu">${b('Add scene','new-scene')}${b('Checkpoint history','history')}${button('Reviewed specialist','codex')}${button('Import saved working scene','import','',!!scene.candidate)}${button('Inspect layer again','layer-inspect','',!!draft?.dirty)}</div></details></div>
 <nav class="steps world-steps" aria-label="Activities in this scene">${stages.map((st,i)=>b((scene.completed[st.id]?'✓ ':i+1+' ')+st.short,'stage',{stage:st.id},scene.stage===st.id?'active':'',active||!!scene.candidate||stages.slice(0,i).some(x=>!scene.completed[x.id]))).join('')}</nav>
 <section class="layer-workspace" aria-label="${isLight?'Light':'Shots'} layer"><header class="action-heading"><div><h1>${isLight?'Light your scene':'Frame your story'}</h1><p>${isLight?'Choose a shot, adjust a scene light, then preview the saved lighting.':'Make different shots into the same world. Start with a camera, then choose its moment.'}</p></div>${button(isLight?'Refine lighting in Blender':'Refine cameras in Blender','task','ghost',!cap?.task_workspace||!!scene.candidate)}</header>
 <div class="action-savebar"><span role="status">${esc(status)}</span><div>${button('Discard changes','layer-discard','ghost',!draft?.dirty||!!saving)}${button('Undo','layer-undo','ghost',!draft?.canUndo||stale)}${button('Save changes','layer-save',draft?.dirty?'primary':'ghost',!draft?.dirty||stale||editDisabled)}</div></div>
 ${scene.candidate?`<section class="note"><strong>Imported candidate · review before using</strong><p>This separate file has not replaced the current working scene. Keeping it here does not mark ${isLight?'Light':'Shots'} ready.</p>${button('Inspect candidate in Blender','inspect-candidate')}${button('Use as working scene','keep-building')}${button('Reject candidate','discard','ghost')}</section>`:''}
 ${scene.task?taskBanner(scene,taskStatus,esc,b):''}${run?`<div class="note" role="status">${esc(progressLabel(run))} ${b('Inspect operation','recover',{run:run.id},'ghost')}</div>`:''}
 ${shotControls}
 ${isLight?lightControls:''}
 ${checkpoint?'<section class="viewer-3d" data-scene-viewer aria-label="Saved scene in 3D"></section>':'<p>No saved scene yet. Return to World to build it.</p>'}
 <p class="layer-scope layer-view-scope">${draft?.dirty?'This is still the saved scene. Save changes to update its preview.':'Saved geometry and camera · approximate materials and inspection lighting.'} ${isLight?'Use a Blender-rendered still to judge actual lighting.':''}</p>
 ${cap?.scene_layer!=='scene-layer-v1'?'<p class="note warn">Install the matching camera/light runtime to use these controls.</p>':''}
 ${isLight?'':`<div class="layer-tools">${button('Create camera','layer-camera','',editDisabled||!!draft?.dirty)}<p>Fit chosen objects in a new camera. For detailed framing or camera motion, open Blender.</p></div>`}
 ${isLight&&draft?`<details class="layer-details"><summary>World brightness and exposure</summary><div class="layer-controls">${draft.audit.look.editable.world.includes('strength')?field('World strength','strength',draft.setting('world','strength'),{kind:'world',min:0,max:1e6}):'<p>This world graph needs Blender editing; it will not be simplified.</p>'}${field('Exposure (stops)','exposure',draft.setting('look','exposure'),{kind:'look',min:-100,max:100,off:!draft.audit.look.editable.color_management.includes('exposure')})}</div><p>Materials and HDRI node graphs remain in the detailed Blender / reviewed specialist workflow.</p></details>`:''}
 ${!draft&&checkpoint?`<p role="status">${attempt?.state==='FAILED'?esc(attempt.error):'Inspecting the saved cameras and lights…'}</p>${button(attempt?'Retry layer inspection':'Inspect saved layer','layer-inspect')}`:''}
 ${isLight?`<section class="layer-preview"><h2>Check the real lighting</h2><p>Lights are shared by ${shots.length} named shot${shots.length===1?'':'s'}. Review each affected shot: ${esc(shots.map(x=>x.name).join(', ')||'name a shot in Shots')}.</p>${button('Preview lighting','preview','',!cap?.render_frames||!checkpoint||!shot||!!draft?.dirty||stale)}${button('Compare rendered stills','lighting-evidence','ghost',!shots.length)}<p>Compare rendered stills to verify their checkpoint, shot and external-source identities before judging the saved lighting.</p></section>`:''}
 <section class="world-next"><div class="grow"><h2>${isLight?'Review all affected shots':'Review your framing'}</h2><p>${isLight?'Changes affect the whole scene, not just the selected shot.':'Check cameras and timing in every named shot.'} Saving is separate from marking this layer ready.</p></div>${button(isLight?'Light ready · continue to Render':'Shots ready · continue to Light','layer-ready','primary',!checkpoint||!draft||!!draft.dirty||stale||!shots.length)}</section></section>`;
}
