import {clipEnd,sourceRange} from './action-timeline-contract.mjs';
export function timelinePicker(d,esc,disabled=false){
 const p=d.audit.performers.find(p=>p.name===d.selected);
 return `<div class="action-controls motion-controls"><label>Performer<select aria-label="Performer" data-action-field="performer" ${disabled?'disabled':''}>${d.audit.performers.map(x=>`<option value="${esc(x.name)}" ${x.name===d.selected?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label><label>Add animation<select data-motion-add aria-label="Add animation" ${disabled?'disabled':''}><option value="">Choose a native take…</option>${p.takes.map(t=>`<option value="${esc(t.id)}">${esc(t.action)}</option>`).join('')}</select></label><p class="motion-next">Next free frame <strong>${d.nextFrame()}</strong></p></div>`;
}
export function transitionProviderLabel(d){
 const c=d.selectedClip,p=d.audit.performers.find(p=>p.name===d.selected);
 if(!c?.transition)return null;
 if(c.transition.mode==='generated'){const saved=!d.dirty&&p?.timeline?.connections?.find(join=>join.clip_id===c.id);if(saved&&(saved.provider!=='motion-bricks.cpp'||saved.generation_mode!=='generated'))return 'Provider provenance mismatch: inspect this saved result again.';return 'MotionBricks: generated repositioning, predicted target placement';}
 const method=!d.dirty?p?.timeline?.connections?.find(join=>join.clip_id===c.id)?.method:p?.timeline?.stitch_version;
 if((method||p?.timeline?.stitch_version)!=='native-stitch-v1')return 'Provider unavailable: inspect this saved performer again.';
 return 'Blender native: deterministic '+(c.transition.mode==='turn'?'turn blend':'pose blend');
}
export function transitionContactLabel(d){
 const c=d.selectedClip,p=d.audit.performers.find(p=>p.name===d.selected);
 const saved=!d.dirty&&p?.timeline?.connections?.find(join=>join.clip_id===c?.id);
 if(saved?.contact_acceptance==='SAMPLED_AUTHORED_CLEANUP')return 'Authored planted contacts corrected and sampled. Review the saved playback; terrain adaptation is unavailable.';
 const take=p?.takes.find(t=>t.id===c?.take_id);
 if(take?.contacts?.status==='INVALID')return take.contacts.blocker||'Contact annotations are invalid. Correct them in Blender before saving.';
 if(take?.contacts?.status==='AUTHORED')return 'Authored contacts are available. Save to evaluate cleanup, then review the saved playback.';
 return 'Foot contacts are unannotated. Contact cleanup is unavailable; review the saved motion for sliding.';
}
export function timelineControls(d,esc,disabled=false){
 const p=d.audit.performers.find(p=>p.name===d.selected),c=d.selectedClip;
 const gait=d.gait,automatic=!!c?.travel?.gait_id;
 const field=(label,key,min,max,step='any')=>`<label>${label}<input type="number" data-motion-field="${key}" aria-label="${label}" aria-describedby="motion-${key}-error" min="${min}" max="${max}" step="${step}" value="${esc(d.input(key))}" ${disabled?'disabled':''}><small id="motion-${key}-error" data-motion-error="${key}" class="action-field-error" hidden></small></label>`;
 const options=p.takes.map(t=>`<option value="${esc(t.id)}" ${c?.take_id===t.id?'selected':''}>${esc(t.action)}</option>`).join('');
 const take=p.takes.find(t=>t.id===c?.take_id),editing=d.supportsEditing;
 const contact=transitionContactLabel(d);
 const provider=c?.transition?`<p data-motion-provider>Provider: ${esc(transitionProviderLabel(d))}</p>`:'';
 const button=(label,action,off=false)=>`<button type="button" data-action="${action}" ${disabled||off?'disabled':''}>${label}</button>`;
 const connect=c?.transition?`<label>Connection<select data-motion-field="transition_mode" aria-label="Connection" ${disabled?'disabled':''}><option value="blend" ${(c.transition.mode||'blend')==='blend'?'selected':''}>Smooth join · keep heading</option><option value="turn" ${c.transition.mode==='turn'?'selected':''}>Turn and connect</option><option value="generated" ${c.transition.mode==='generated'?'selected':''} ${p.timeline?.motion_bricks?.status==='CONFIGURED'?'':'disabled'}>MotionBricks repositioning</option></select></label>${field('Transition frames','transition_frames',2,120,'1')}${c.transition.mode==='turn'?field('Body turn (degrees)','heading_deg',-180,180)+'<p>Next clip’s rotation from the original saved orientation, not an extra turn from the previous clip. Backward and sideways takes keep their footwork.</p>':''}`:'';
 if(c&&d.selectedPart==='transition')return `<div class="motion-clip-controls motion-transition-inspector"><header class="motion-clip-heading"><span class="eyebrow">Selected transition</span><strong>Into ${esc(take?.action||'Changed take')}</strong><p data-motion-connection></p></header>${editing?connect:field('Transition frames','transition_frames',2,120,'1')}${provider}<p>${c.transition.mode==='generated'?'MotionBricks generates a separate repositioning interval, then the next native animation starts at its original opening. Both source clips stay intact.':c.transition.mode==='turn'?'Slows added travel, turns the body, then resumes travel into the next animation.':'Blends endpoint poses and movement; it does not turn the body.'} Save and play to review. Suitable motion is not chosen automatically.</p><p data-motion-contact>${esc(contact)}</p>${editing?`<details class="motion-insert"><summary>Use an existing turn or stop animation</summary><p>Choose a native take for this performer. It becomes a separate editable clip; no motion is identified by its name.</p><label>Insert animation before this clip<select data-motion-insert aria-label="Insert animation before this clip" ${disabled?'disabled':''}><option value="">Choose an observed take…</option>${p.takes.map(t=>`<option value="${esc(t.id)}">${esc(t.action)}</option>`).join('')}</select></label></details>`:''}<div class="motion-clip-actions">${button('Back to animation','motion-select-clip')}${button('Remove connection','motion-delete')}</div><p data-motion-errors role="alert" class="action-field-error" hidden></p></div>`;
 return `${c?`<div class="motion-clip-controls">
 <header class="motion-clip-heading"><span class="eyebrow">Selected clip</span><strong>${esc(p.takes.find(t=>t.id===c.take_id)?.action||'Changed take')}</strong><p data-motion-duration></p></header>
 ${editing?`<label>Animation<select data-motion-replace aria-label="Replace animation" ${disabled?'disabled':''}>${options}</select></label><p class="motion-replace-note">Replacing keeps the start and body turn; resets path, trim and review for the new motion.</p>`:''}
 <div class="motion-clip-actions motion-primary-actions">${editing?button('Split at playhead','motion-split',!!d.trimBlocker):''}${button('Delete clip','motion-delete')}</div><details class="motion-arrange"><summary>Move / close gaps</summary><div class="motion-clip-actions">${editing?button('Move earlier','motion-earlier')+button('Move later','motion-later'):''}${button('Close gap / shift following','motion-ripple')}</div></details>
 ${d.canConnect||c.transition?`<label class="motion-check"><input type="checkbox" data-motion-field="smooth" ${c.transition?'checked':''}> Connect to previous clip</label>`:''}
 ${c.transition?'<p data-motion-connection class="motion-connection-info"></p>'+provider+'<p data-motion-contact>'+esc(contact)+'</p>'+button('Edit connection','motion-select-transition'):''}
 <section class="motion-travel-controls"><label class="motion-check"><input type="checkbox" data-motion-field="travel" ${c.travel?'checked':''}> Move character along red path</label>
 ${c.travel?field('Distance (m)','distance',.001,10000):'<p>Use the take’s motion without an added travel path.</p>'}
 ${c.travel?`<p data-motion-pace>${automatic?'Estimated natural pace · distance sets cycles and time.':'Manual pace needed · this take could not be measured reliably.'}</p>`:''}
 ${d.needsPaceRefresh?`<div class="motion-refresh"><p>This saved clip uses an older pace measurement. Refresh it once to propose new timing; nothing is saved automatically.</p>${button('Refresh measured pace','motion-refresh-pace',gait?.status!=='estimated')}${gait?.status!=='estimated'?'<p>No reliable measurement is available. Turn off automatic pace in advanced options to calibrate manually, or turn off path movement.</p>':''}</div>`:''}
 ${c.travel&&!automatic?`<div class="motion-calibration" data-motion-calibration>${field('Metres per cycle','pace',.001,1000)}${field('Direction (world degrees)','direction',-360,360)}<details class="motion-pace-help"><summary>Why is a pace needed?</summary><p>${esc(gait?.reason||'Automatic pace is unavailable in this inspection.')}</p><p>The red path stays editable. Calibrate a cycle after inspecting the take, or switch off path movement to use its native motion. Direction changes the path, not the character’s facing.</p></details></div>`:''}</section>
 <label class="motion-check" data-motion-repeat><input type="checkbox" data-motion-field="repeat_reviewed" ${c.repeat_reviewed?'checked':''}> I reviewed the feet and loop join; allow repeats${c.transition?.match_phase?' and phase matching':''}</label>
 <p data-motion-errors role="alert" class="action-field-error" hidden></p>
 ${editing?`<details data-motion-trim><summary>Trim native motion</summary>${d.trimBlocker?`<p>${esc(d.trimBlocker)}</p>`:`<div class="motion-fields">${field('Source In','source_in',take.range[0],take.range[1])}${field('Source Out','source_out',take.range[0],take.range[1])}</div><p>Frames in the original take. Trimming keeps one native pass; the original animation stays intact.</p>`}</details>`:''}
 <details data-motion-details><summary>Timing and advanced options</summary><div class="motion-fields">
 ${field('Speed','speed',.1,4)}${c.transition?'':field('Start frame','start',-100000,100000,'1')}${editing?field('Body turn (degrees)','heading_deg',-180,180):''}
 ${!c.travel?field('Occupied frames','frames',2,3601,'1'):''}</div>
 ${c.travel&&gait?.status==='estimated'?`<label class="motion-check"><input type="checkbox" data-motion-field="automatic" ${automatic?'checked':''}> Use automatic pace and observed direction</label>`:''}
 ${c.transition&&c.transition.mode!=='generated'?`<label class="motion-check"><input type="checkbox" data-motion-field="match_phase" ${c.transition.match_phase?'checked':''}> Match the opening pose when this is a reviewed closed loop</label>`:''}
 <p>${automatic?'Estimated stride length is protected. More distance adds native cycles, not larger strides. Body turn rotates the measured path too.':'Manual calibration: wrong pace or direction can cause sliding. Path direction does not turn the character.'} Body turn is relative to the saved base orientation—not an inferred facing direction. A backward or sideways take keeps its footwork. ${esc(contact)}</p></details></div>`:'<div class="motion-empty"><strong>Shape an animation</strong><p>Add an animation above, or select a clip in the timeline. Select an amber connection to shape the turn between clips. Your saved performance stays untouched until you save.</p></div><p data-motion-errors role="alert" class="action-field-error" hidden></p>'}`;
}
export function timelineTracks(d,esc){
 const range=d.playbackRange,span=Math.max(1,range[1]-range[0]+1);
 const transition=(p,c)=>c.transition?`<button type="button" class="motion-transition ${d.selectedPart==='transition'&&d.selectedClip?.id===c.id?'selected':''}" data-action="motion-select" data-part="transition" data-performer="${esc(p.name)}" data-clip="${esc(c.id)}" data-left="${(c.start-c.transition.frames-range[0])/span*100}" data-width="${c.transition.frames/span*100}" title="${c.transition.mode==='generated'?'MotionBricks repositioning':c.transition.mode==='turn'?'Turn and connect':'Smooth join'} · ${c.transition.frames} added frames" aria-label="Connection ${c.start-c.transition.frames} to ${c.start-1}">↝</button>`:'';
 return `<header><strong>Action timeline</strong><span>Frames ${range[0]}–${range[1]} · ${d.audit.fps} fps</span></header>${d.audit.performers.filter(p=>p.takes.length||d.clips(p.name).length).map(p=>`<div class="motion-track"><span>${esc(p.name)}</span><div class="motion-lane" aria-label="${esc(p.name)} animation track">${d.clips(p.name).map(c=>transition(p,c)+`<button type="button" data-action="motion-select" data-performer="${esc(p.name)}" data-clip="${esc(c.id)}" class="motion-clip ${d.selectedPart!=='transition'&&d.selectedClip?.id===c.id?'selected':''}" data-left="${(c.start-range[0])/span*100}" data-width="${c.frames/span*100}" title="${esc(p.takes.find(t=>t.id===c.take_id)?.action)} · frames ${c.start}–${clipEnd(c)}" aria-label="${esc(p.takes.find(t=>t.id===c.take_id)?.action)} frames ${c.start} to ${clipEnd(c)}"><span>${esc(p.takes.find(t=>t.id===c.take_id)?.action||'Changed take')}</span><small>${c.start}–${clipEnd(c)}</small></button>`).join('')}</div></div>`).join('')}<p>Select an animation to edit it, or an amber connection to shape the join. Connected clips move together when timing changes.</p>`;
}
export function syncTimelineUI(d,esc,disabled){
 if(!d?.timeline)return;
 const next=document.querySelector('.motion-next strong');if(next)next.textContent=d.nextFrame();
 const tracks=document.querySelector('[data-motion-tracks]');if(tracks)tracks.innerHTML=timelineTracks(d,esc);
 for(const node of tracks?.querySelectorAll('[data-left]')||[]){node.style.left=node.dataset.left+'%';node.style.width=node.dataset.width+'%';}
 const c=d.selectedClip,errors=d.errors;
 const error=document.querySelector('[data-motion-errors]');if(error){const visible=errors.filter(e=>!(e.field==='track'&&e.message.startsWith('Manual travel needs a calibrated')&&errors.some(x=>x.performer===e.performer&&x.field==='pace'))).filter(e=>e.clip!==c?.id||!e.field||!document.querySelector(`[data-motion-error="${e.field}"]`));error.innerHTML=visible.map(e=>`<span>${e.clip!==c?.id?esc(d.errorLabel(e))+': ':''}${esc(e.message)}</span>${e.clip&&e.clip!==c?.id?`<button type="button" data-action="motion-select" data-performer="${esc(e.performer)}" data-clip="${esc(e.clip)}">Go to ${esc(d.errorLabel(e))}</button>`:''}`).join(' ');error.hidden=!visible.length;}
 const timingPending=!!c?.travel&&errors.some(e=>e.clip===c.id&&['pace','distance','speed','direction'].includes(e.field));
 const duration=document.querySelector('[data-motion-duration]');if(duration)duration.textContent=c?timingPending?'Timing pending · set a valid pace and path':`Frames ${c.start}–${clipEnd(c)} · ${c.frames} occupied frames · ${((c.frames-1)/d.audit.fps).toFixed(2)} s` :'';
 const connection=document.querySelector('[data-motion-connection]');if(connection&&c){const join=d.connection;connection.textContent=`${c.transition.frames} added frames${join?.placement_pending?' · target placement chosen during generation':join?' · '+Math.hypot(...join.delta_m).toFixed(2)+' m connecting movement':' · placement pending correction'}. ${d.dirty?'Preview after Save.':'Play to review.'}`;}
 const take=d.audit.performers.find(p=>p.name===d.selected)?.takes.find(t=>t.id===c?.take_id);
 const range=take&&c?sourceRange(c,take):null,span=range?range[1]-range[0]:0;
 let cycles=c&&span>0?c.travel?Math.hypot(...c.travel.delta_m)/c.travel.meters_per_cycle:(c.frames-1)*c.speed/span:0;
 if(c&&!c.travel&&cycles>1&&cycles<=1+c.speed/span+1e-9)cycles=1;
 const review=document.querySelector('[data-motion-repeat]');if(review)review.hidden=!((Number.isFinite(cycles)&&cycles>1+1e-7)||c?.repeat_reviewed||c?.transition?.match_phase);
 const seconds=c?cycles*span/c.speed/d.audit.fps:0;
 const pace=document.querySelector('[data-motion-pace]');if(pace&&c?.travel){if(c.travel.gait_id)pace.textContent=`Estimated natural pace · ${c.travel.meters_per_cycle.toFixed(2)} m/cycle · ${Number.isFinite(cycles)?cycles.toFixed(2):'—'} cycles · about ${seconds.toFixed(2)} s at ${c.speed===1?'normal speed':c.speed+'× speed'}.`;else pace.textContent=c.travel.meters_per_cycle>0&&!errors.some(e=>e.clip===c.id&&e.field==='pace')?'Manual pace · review the saved motion for foot sliding.':'Manual pace needed · this take could not be measured reliably.';}
 for(const node of document.querySelectorAll('[data-motion-field]')){
  node.disabled=disabled;
  if(node.type==='number'&&node!==document.activeElement)node.value=d.input(node.dataset.motionField);
  const message=errors.find(e=>e.clip===c?.id&&e.field===node.dataset.motionField)?.message||'';
  node.setCustomValidity(message);node.setAttribute('aria-invalid',String(!!message));
  const hint=document.querySelector(`[data-motion-error="${node.dataset.motionField}"]`);if(hint){hint.textContent=message;hint.hidden=!message;}
  if(message){const details=node.closest('[data-motion-details],[data-motion-trim]');if(details)details.open=true;}
 }
 for(const node of document.querySelectorAll('[data-motion-add],[data-motion-replace],[data-motion-insert],button[data-action^="motion-"]'))node.disabled=disabled||node.dataset.action==='motion-split'&&!!d.trimBlocker||node.dataset.action==='motion-refresh-pace'&&d.gait?.status!=='estimated';
}
