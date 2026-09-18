/** Scene-local camera decisions; no simulated previews or duplicate scene workflows. */
export function shotPanel({scene,checkpoint,locked,esc,b}) {
  const editable=scene.stage==='shots'&&!locked&&!scene.candidate;
  return `<section class="library shot-library"><header><h3>Shots in this scene</h3><p>Different cameras into the same staged world.</p></header><div class="object-list">${b('Whole scene','scene-context',{},!scene.selectedShot?'active':'ghost',locked||!!scene.candidate)}${(scene.shots||[]).map(shot=>`<div class="shot-row">${b(shot.name,'select-shot',{id:shot.id},scene.selectedShot===shot.id?'active':'',locked||!!scene.candidate)}<small>${esc(shot.camera)} · ${shot.start}–${shot.end} · v${shot.revision}</small>${editable?b('Edit shot','edit-shot',{id:shot.id},'small ghost'):''}</div>`).join('')||'<p>No named shots yet. Save an observed camera and the moment it captures.</p>'}</div><footer>${scene.stage==='shots'?b('Save camera as shot','new-shot',{},'',!editable||!checkpoint):'<p>Keep this shot’s camera and timing through lighting and rendering. Lights remain shared scene state.</p>'}${checkpoint&&!checkpoint.audit?b('Inspect saved scene','readiness',{},'ghost',locked||!!scene.candidate):''}</footer></section>`;
}
export function shotEditor({scene,checkpoint,id,esc}) {
  const previous=(scene.shots||[]).find(s=>s.id===id),audit=checkpoint?.audit;
  const ready=scene.readiness?.checkpointId===checkpoint?.id?scene.readiness.data:null;
  const cameras=audit?.objects?.filter(o=>o.type==='CAMERA').map(o=>o.name)||ready?.cameras||[];
  const range=audit?.frame_range||ready?.frame_range;
  if(!cameras.length||!range)throw Error('Inspect the saved scene first. Create a camera in Blender when none exists.');
  const shot=previous||{name:cameras[0],camera:cameras[0],start:range[0],end:range[1]};
  return `<p>A shot references this scene’s camera and timing; it does not copy or rebuild the world. ${previous?'A revision makes previous renders historical.':''}</p><label>Shot name<input id="shot-name" maxlength="100" value="${esc(shot.name)}"></label><label>Observed camera<select id="shot-camera">${cameras.map(c=>`<option ${c===shot.camera?'selected':''}>${esc(c)}</option>`).join('')}</select></label><div class="fields"><label>First frame<input type="number" id="shot-start" value="${shot.start}" min="${range[0]}" max="${range[1]}"></label><label>Last frame<input type="number" id="shot-end" value="${shot.end}" min="${range[0]}" max="${range[1]}"></label></div><p>Observed scene: ${range[0]}–${range[1]}. Select at most 360 frames. No automatic trimming or retiming.</p>`;
}
