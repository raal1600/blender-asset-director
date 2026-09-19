/** Utilities retained in the new workbench; no alternate role-page application. */
export function productionRow({project,esc,b}) {
  return `<article class="production-row" data-production-id="${esc(project.id)}" aria-label="${esc(project.name)}"><div class="production-copy"><h2>${esc(project.name)}</h2><p>${esc(project.brief||'No production intent yet.')}</p><small>${project.workbench?.scenes.length||0} workbench scenes · original project preserved</small></div><div class="production-actions row">${b('Open production','project',{id:project.id})}${b('Archive production','archive-production',{id:project.id},'ghost')}</div></article>`;
}
export function archiveTarget({projects,current,id}) {
  const target=id===undefined?current:projects.find(p=>p.id===id);
  if(!target)throw new Error('Production is no longer listed. Refresh and try again.');
  return target;
}
export function archiveConfirmation(project) {
  return `Archive "${project.name}"?\n\nThis removes it from Productions and keeps its scenes, renders and history in recoverable Archive/Trash. Shared library assets stay in place. Restore it from Archived productions. This is not permanent deletion.`;
}
export function diagnosticsView({detail,esc,b,locked}) {
  return {body:`<p>Inspect project-owned saved files and linked job records. This does not create a workbench checkpoint or approve an output.</p><label>Saved file<select id="diagnostic-scene">${detail.scenes.map(f=>`<option value="${esc(f)}">${esc(f)}</option>`).join('')}</select></label><div class="row">${b('Audit selected saved file','audit-saved',{},'',locked||!detail.scenes.length)}${b('Verify source files','verify-sources',{},'',locked)}</div><div id="source-verification" role="status"></div><h3>Linked harness jobs</h3><div id="diagnostic-jobs">${detail.jobs.map(j=>`<details><summary>${esc(j.operation||j.id)} · ${esc(j.state)}</summary><pre>${esc(JSON.stringify(j,null,2))}</pre></details>`).join('')||'<p>No linked jobs yet.</p>'}</div><p>Job records are historical evidence, not permission to rerun. Use the normal reviewed specialist workflow to execute jobs.</p>`};
}
export function trashView({trash,esc,b}) {
  return {body:`<p>Recoverable productions in Archive/Trash. Restoration never overwrites an occupied project folder.</p>${trash.errors.map(e=>`<p class="warn">${esc(e.message)}</p>`).join('')}${trash.projects.map(p=>`<div class="production-row"><div><h3>${esc(p.name)}</h3><p>${esc(p.trashedAt)}</p></div>${b('Restore production','restore-production',{id:p.id},'',!!trash.errors.length)}</div>`).join('')||'<p>No archived productions.</p>'}`};
}
