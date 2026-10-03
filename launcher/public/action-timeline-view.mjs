import {clipEnd} from './action-timeline-contract.mjs';
export function timelineControls(d,esc,disabled=false){
 const p=d.audit.performers.find(p=>p.name===d.selected),c=d.selectedClip;
 const gait=d.gait,automatic=!!c?.travel?.gait_id;
 const field=(label,key,min,max,step='any')=>`<label>${label}<input type="number" data-motion-field="${key}" aria-label="${label}" min="${min}" max="${max}" step="${step}" value="${esc(d.input(key))}" ${disabled?'disabled':''}></label>`;
 return `<div class="action-controls motion-controls"><label>Performer<select aria-label="Performer" data-action-field="performer">${d.audit.performers.map(x=>`<option value="${esc(x.name)}" ${x.name===d.selected?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label><label>Add animation<select data-motion-add aria-label="Add animation" ${disabled?'disabled':''}><option value="">Choose a native take…</option>${p.takes.map(t=>`<option value="${esc(t.id)}">${esc(t.action)}</option>`).join('')}</select></label><p class="motion-next">Next free frame <strong>${d.nextFrame()}</strong></p></div>
 ${c?`<div class="motion-clip-controls">
 <strong>${esc(p.takes.find(t=>t.id===c.take_id)?.action||'Changed take')}</strong>
 ${d.canConnect||c.transition?`<label class="motion-check"><input type="checkbox" data-motion-field="smooth" ${c.transition?'checked':''}> Smooth connection</label>`:''}
 ${c.transition?'<p data-motion-connection class="motion-connection-info"></p>':''}
 <label class="motion-check"><input type="checkbox" data-motion-field="travel" ${c.travel?'checked':''}> Move character along red path</label>
 ${c.travel?field('Distance (m)','distance',.001,10000):''}
 <p data-motion-pace>${automatic?'Automatic pace · estimated from this character’s support motion. Change the distance; Director calculates cycles and time.':esc(gait?.reason||'Automatic pace is unavailable in this inspection. Keep the native take, inspect again, or use manual calibration.')}</p>
 <p data-motion-duration></p>
 <label class="motion-check" data-motion-repeat><input type="checkbox" data-motion-field="repeat_reviewed" ${c.repeat_reviewed?'checked':''}> I checked this take’s feet and loop join; allow repeats${c.transition?.match_phase?' and phase matching':''}</label>
 <details ${c.travel&&!automatic?'open':''}><summary>Timing and path</summary><div class="motion-fields">
 ${field('Speed','speed',.1,4)}${c.transition?field('Transition frames','transition_frames',2,120,'1'):field('Start frame','start',-100000,100000,'1')}
 ${!c.travel?field('Occupied frames','frames',2,3601,'1'):!automatic?field('Metres per cycle','pace',.001,1000)+field('Direction (world degrees)','direction',-360,360):''}</div>
 ${c.travel&&gait?.status==='estimated'?`<label class="motion-check"><input type="checkbox" data-motion-field="automatic" ${automatic?'checked':''}> Use automatic pace and observed direction</label>`:''}
 ${c.transition?`<label class="motion-check"><input type="checkbox" data-motion-field="match_phase" ${c.transition.match_phase?'checked':''}> Match the opening pose when this is a reviewed closed loop</label>`:''}
 <p>${automatic?'Estimated stride length and heading are protected. More distance adds native cycles, not larger strides.':'Manual calibration: wrong pace or direction can cause sliding. Direction does not turn the character.'} Connections blend measured poses and path velocities, not foot locking or terrain adaptation. A partial final cycle can stop mid-step; review the saved result before continuing.</p>
 <button type="button" data-action="motion-ripple">Shift following clips after this one</button><button type="button" data-action="motion-delete">Delete this clip</button></details></div>`:'<p class="muted">Choose an animation to append a clip, or select an existing clip to edit it. Existing saved performance stays untouched until you save.</p>'}
 <p data-motion-errors role="alert" class="action-field-error"></p>`;
}
export function timelineTracks(d,esc){
 const range=d.playbackRange,span=Math.max(1,range[1]-range[0]+1);
 const transition=(p,c)=>c.transition?`<button type="button" class="motion-transition" data-action="motion-select" data-performer="${esc(p.name)}" data-clip="${esc(c.id)}" data-left="${(c.start-c.transition.frames-range[0])/span*100}" data-width="${c.transition.frames/span*100}" title="Connection · ${c.transition.frames} added frames" aria-label="Connection ${c.start-c.transition.frames} to ${c.start-1}">↝</button>`:'';
 return `<header><strong>Action timeline</strong><span>Frames ${range[0]}–${range[1]} · ${d.audit.fps} fps</span></header>${d.audit.performers.filter(p=>p.takes.length||d.clips(p.name).length).map(p=>`<div class="motion-track"><span>${esc(p.name)}</span><div class="motion-lane" aria-label="${esc(p.name)} animation track">${d.clips(p.name).map(c=>transition(p,c)+`<button type="button" data-action="motion-select" data-performer="${esc(p.name)}" data-clip="${esc(c.id)}" class="motion-clip ${d.selectedClip?.id===c.id?'selected':''}" data-left="${(c.start-range[0])/span*100}" data-width="${c.frames/span*100}" title="${esc(p.takes.find(t=>t.id===c.take_id)?.action)} · frames ${c.start}–${clipEnd(c)}" aria-label="${esc(p.takes.find(t=>t.id===c.take_id)?.action)} frames ${c.start} to ${clipEnd(c)}"><span>${esc(p.takes.find(t=>t.id===c.take_id)?.action||'Changed take')}</span><small>${c.start}–${clipEnd(c)}</small></button>`).join('')}</div></div>`).join('')}<p>Connected clips move together when timing changes. Connections add visible time and may carry movement between paths. Earlier clips remain editable.</p>`;
}
export function syncTimelineUI(d,esc,disabled){
 if(!d?.timeline)return;
 const next=document.querySelector('.motion-next strong');if(next)next.textContent=d.nextFrame();
 const tracks=document.querySelector('[data-motion-tracks]');if(tracks)tracks.innerHTML=timelineTracks(d,esc);
 for(const node of tracks?.querySelectorAll('[data-left]')||[]){node.style.left=node.dataset.left+'%';node.style.width=node.dataset.width+'%';}
 const error=document.querySelector('[data-motion-errors]');if(error)error.textContent=[...new Set(d.errors.map(e=>e.message))].join(' ');
 const c=d.selectedClip,duration=document.querySelector('[data-motion-duration]');if(duration)duration.textContent=c?`Frames ${c.start}–${clipEnd(c)} · ${c.frames} occupied frames · ${((c.frames-1)/d.audit.fps).toFixed(2)} s` :'';
 const connection=document.querySelector('[data-motion-connection]');if(connection&&c){const join=d.connection;connection.textContent=`Connection · ${c.transition.frames} added frames before this clip${join?' · carries '+Math.hypot(...join.delta_m).toFixed(2)+' m of movement':''}. ${d.dirty?'Preview after Save':'Play to review the saved connection'}; original clips stay intact.`;}
 const take=d.audit.performers.find(p=>p.name===d.selected)?.takes.find(t=>t.id===c?.take_id);
 const span=take?take.range[1]-take.range[0]:0;
 let cycles=c&&span>0?c.travel?Math.hypot(...c.travel.delta_m)/c.travel.meters_per_cycle:(c.frames-1)*c.speed/span:0;
 if(c&&!c.travel&&cycles>1&&cycles<=1+c.speed/span+1e-9)cycles=1;
 const review=document.querySelector('[data-motion-repeat]');if(review)review.hidden=!(cycles>1+1e-7||c?.repeat_reviewed||c?.transition?.match_phase);
 const seconds=c?cycles*span/c.speed/d.audit.fps:0;
 const pace=document.querySelector('[data-motion-pace]');if(pace&&c?.travel?.gait_id)pace.textContent=`Estimated natural pace · ${c.travel.meters_per_cycle.toFixed(2)} m/cycle · ${Number.isFinite(cycles)?cycles.toFixed(2):'—'} cycles · about ${seconds.toFixed(2)} s at ${c.speed===1?'normal speed':c.speed+'× speed'}.`;
 for(const node of document.querySelectorAll('[data-motion-field]')){
  node.disabled=disabled;
  if(node.type==='number'&&node!==document.activeElement)node.value=d.input(node.dataset.motionField);
  const message=d.errors.find(e=>e.clip===c?.id&&e.field===node.dataset.motionField)?.message||'';
  node.setCustomValidity(message);node.setAttribute('aria-invalid',String(!!message));
 }
 for(const node of document.querySelectorAll('[data-motion-add],button[data-action^="motion-"]'))node.disabled=disabled;
}
