/** Display verified stills, never infer artistic review or lighting-only changes. */
export function matchingLightingStill(a,b){
 return !!a&&!!b&&a.status==='VERIFIED'&&b.status==='VERIFIED'&&a.shot&&b.shot&&a.shot.id===b.shot.id&&a.shot.revision===b.shot.revision&&
 ['camera','frame','width','height','samples','engine'].every(k=>a[k]===b[k]);
}
export function lightingPair(items,shotId,beforeId){
 const rows=items.filter(x=>x.status==='VERIFIED'&&x.shot?.id===shotId),current=rows.find(x=>x.current)||null,older=rows.filter(x=>!x.current);
 const before=beforeId?older.find(x=>x.runId===beforeId)||null:older.find(x=>matchingLightingStill(current,x))||older[0]||null;
 return {current,before,older,matched:matchingLightingStill(current,before)};
}
export function lightingEvidenceView({data,scene,shotId,beforeId,esc,b}){
 const pair=lightingPair(data.items,shotId,beforeId),selected=scene.shots.find(x=>x.id===shotId);
 const label=x=>`${x.camera||'Unrecorded camera'} · frame ${x.frame} · ${x.shot?.name||'Scene still'} v${x.shot?.revision||'—'}`;
 const card=(entry,title)=>`<figure class="lighting-still"><figcaption><strong>${title}</strong>${entry?`<span>${esc(label(entry))}</span><small>${entry.width} × ${entry.height} · ${entry.samples} samples · CPU preview</small>`:''}</figcaption>${entry?`<img data-lighting-run="${esc(entry.runId)}" alt="${esc(title+' — '+label(entry))}">${entry.dependencyStatus==='MATCH'?'':`<p class="note warn">${entry.dependencyStatus==='CHANGED'?'An external source changed or is missing. This image remains historical.':'This older render did not record external dependency identities; it cannot establish current lighting.'}</p>`}<details><summary>Exact evidence</summary><pre>${esc(JSON.stringify(entry,null,2))}</pre></details>`:`<p>${title.startsWith('Current')?'No verified still for the current checkpoint on this page. Return to this shot and explicitly preview its saved lighting.':'No earlier still on this page. Previous files have not been removed.'}</p>`}</figure>`;
 return `<p>Actual Blender-rendered stills, separate from the 3D approximation. Review every affected shot; opening this comparison is not an approval.</p><label>Shot to review<select id="lighting-evidence-shot">${scene.shots.map(s=>`<option value="${esc(s.id)}" ${s.id===shotId?'selected':''}>${esc(s.name)} · ${esc(s.camera)}</option>`).join('')}</select></label><p>Evidence checked at production revision ${data.revision}. ${esc(selected?.name||'No shot')} · saved range ${selected?.start??'—'}–${selected?.end??'—'}.</p>
 ${pair.older.length?`<label>Earlier still<select id="lighting-evidence-before">${pair.older.map(x=>`<option value="${esc(x.runId)}" ${x.runId===pair.before?.runId?'selected':''}>${esc(label(x))} · ${esc(x.createdAt)}</option>`).join('')}</select></label>`:''}
 <div class="lighting-comparison">${card(pair.before,'Earlier checkpoint · historical')}${card(pair.current,'Current saved checkpoint')}</div>
 <p class="note ${pair.current&&pair.before&&!pair.matched?'warn':''}">${pair.matched?'Same shot revision, camera, frame and preview settings. Other scene changes may also differ; this comparison does not prove that only lighting changed.':pair.current&&pair.before?'These stills differ in shot revision, camera, frame or settings. Do not treat them as a controlled lighting comparison.':'Prepare the missing evidence before judging a before/after change.'}</p>
 ${data.items.filter(x=>x.status==='UNAVAILABLE').map(x=>`<p class="note warn">Retained still unavailable: ${esc(x.error)} · ${esc(x.runId)}</p>`).join('')}${data.issues.map(x=>`<p class="note warn">${esc(x.message)} ${esc(x.runId)}</p>`).join('')}
 <div class="lighting-history-nav">${b('Newer stills','lighting-evidence',{shot:shotId,page:Math.max(0,data.page-1)},'ghost',data.page===0)}<span>Page ${data.page+1} · ${data.total} retained successful receipt${data.total===1?'':'s'}</span>${b('Older stills','lighting-evidence',{shot:shotId,page:data.page+1},'ghost',!data.hasMore)}</div>`;
}
