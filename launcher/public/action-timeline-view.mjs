import {clipEnd} from './action-timeline-contract.mjs';
export function timelineControls(d,esc,disabled=false){
 const p=d.audit.performers.find(p=>p.name===d.selected),c=d.selectedClip;
 const field=(label,key,min,max,step='any')=>`<label>${label}<input type="number" data-motion-field="${key}" aria-label="${label}" min="${min}" max="${max}" step="${step}" value="${esc(d.input(key))}" ${disabled?'disabled':''}></label>`;
 return `<div class="action-controls motion-controls"><label>Performer<select aria-label="Performer" data-action-field="performer">${d.audit.performers.map(x=>`<option value="${esc(x.name)}" ${x.name===d.selected?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label><label>Add animation<select data-motion-add aria-label="Add animation" ${disabled?'disabled':''}><option value="">Choose a native take…</option>${p.takes.map(t=>`<option value="${esc(t.id)}">${esc(t.action)}</option>`).join('')}</select></label><p class="motion-next">Next action starts at frame <strong>${d.nextFrame()}</strong></p></div>
 ${c?`<div class="motion-clip-controls"><strong>${esc(p.takes.find(t=>t.id===c.take_id)?.action||'Changed take')}</strong><label class="motion-check"><input type="checkbox" data-motion-field="travel" ${c.travel?'checked':''}> Move character along red path</label>${c.travel?field('Distance (m)','distance',.001,10000)+field('Metres per cycle','pace',.001,1000):''}${field('Speed','speed',.1,4)}<details><summary>Timing and path</summary><div class="motion-fields">${field('Start frame','start',-100000,100000,'1')}${!c.travel?field('Occupied frames','frames',2,3601,'1'):field('Direction (world degrees)','direction',-360,360)}</div><label class="motion-check"><input type="checkbox" data-motion-field="repeat_reviewed" ${c.repeat_reviewed?'checked':''}> I checked that this take can repeat</label><p>In-place motion has no measured travel speed. Set metres travelled per native cycle; inspect feet and joins. Direction does not turn the character. No automatic foot locking or transition blending.</p><button type="button" data-action="motion-ripple">Shift following clips after this one</button><button type="button" data-action="motion-delete">Delete this clip</button></details><p data-motion-duration></p></div>`:'<p class="muted">Choose an animation to append a clip, or select an existing clip to edit it. Existing saved performance stays untouched until you save.</p>'}
 <p data-motion-errors role="alert" class="action-field-error"></p>`;
}
export function timelineTracks(d,esc){
 const range=d.playbackRange,span=Math.max(1,range[1]-range[0]+1);
 return `<header><strong>Action timeline</strong><span>Frames ${range[0]}–${range[1]} · ${d.audit.fps} fps</span></header>${d.audit.performers.filter(p=>p.takes.length||d.clips(p.name).length).map(p=>`<div class="motion-track"><span>${esc(p.name)}</span><div class="motion-lane" aria-label="${esc(p.name)} animation track">${d.clips(p.name).map(c=>`<button type="button" data-action="motion-select" data-performer="${esc(p.name)}" data-clip="${esc(c.id)}" class="motion-clip ${d.selectedClip?.id===c.id?'selected':''}" data-left="${(c.start-range[0])/span*100}" data-width="${c.frames/span*100}" title="${esc(p.takes.find(t=>t.id===c.take_id)?.action)} · frames ${c.start}–${clipEnd(c)}" aria-label="${esc(p.takes.find(t=>t.id===c.take_id)?.action)} frames ${c.start} to ${clipEnd(c)}"><span>${esc(p.takes.find(t=>t.id===c.take_id)?.action||'Changed take')}</span><small>${c.start}–${clipEnd(c)}</small></button>`).join('')}</div></div>`).join('')}<p>Clips occupy their character’s track only. Earlier clips stay editable; blank space remains available.</p>`;
}
export function syncTimelineUI(d,esc,disabled){
 if(!d?.timeline)return;
 const tracks=document.querySelector('[data-motion-tracks]');if(tracks)tracks.innerHTML=timelineTracks(d,esc);
 for(const node of tracks?.querySelectorAll('[data-left]')||[]){node.style.left=node.dataset.left+'%';node.style.width=node.dataset.width+'%';}
 const error=document.querySelector('[data-motion-errors]');if(error)error.textContent=[...new Set(d.errors.map(e=>e.message))].join(' ');
 const c=d.selectedClip,duration=document.querySelector('[data-motion-duration]');if(duration)duration.textContent=c?`Frames ${c.start}–${clipEnd(c)} · ${c.frames} occupied frames · ${((c.frames-1)/d.audit.fps).toFixed(2)} s` :'';
 for(const node of document.querySelectorAll('[data-motion-field]')){
  node.disabled=disabled;
  if(node.type==='number'&&node!==document.activeElement)node.value=d.input(node.dataset.motionField);
  const message=d.errors.find(e=>e.clip===c?.id&&e.field===node.dataset.motionField)?.message||'';
  node.setCustomValidity(message);node.setAttribute('aria-invalid',String(!!message));
 }
 for(const node of document.querySelectorAll('[data-motion-add],button[data-action^="motion-"]'))node.disabled=disabled;
}
