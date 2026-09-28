/** Explicit compatibility review. Rendering this UI never launches a job. */
export function preparationInspection(runs,scene,checkpoint){
 return runs.find(r=>r.sceneId===scene.id&&r.action==='world-prepare-audit'&&r.state==='SUCCEEDED'&&r.checkpointId===checkpoint?.id&&r.checkpointSha256===checkpoint?.sha256&&r.inspection?.version==='world-prepare-v1');
}
export function preparationHint({scene,checkpoint,runs,cap,blocked,esc,b}){
 if(!checkpoint||scene.candidate||cap?.world_prepare!=='world-prepare-v1')return '';
 const inspection=preparationInspection(runs,scene,checkpoint);
 const missing=inspection?inspection.inspection.groups.some(g=>g.status!=='ALREADY_PREPARED'):
  !Array.isArray(checkpoint.audit?.objects)||checkpoint.audit.objects.some(o=>o.asset_id&&o.import_job&&!o.placement_instance);
 if(!missing)return '';
 return `<div class="world-compatibility note"><span>Some saved assets need a placement check before you can move them here. Blender editing remains available.</span>${b(inspection?'Review placement check':'Check asset placement','world-prepare-inspect',{},'ghost',blocked)}</div>`;
}
export function preparationDialog({project,run,esc,b}){
 const groups=run.inspection.groups,labels=new Map((project.workbench.catalogPins||[]).map(a=>[a.id,a.title]));
 const available=groups.filter(g=>g.status==='PREPARABLE').length;
 const rows=groups.map((g,i)=>{
  const eligible=g.status==='PREPARABLE',title=labels.get(g.asset_id)||g.members[0]||g.asset_id;
  return `<section class="world-preparation-group"><label><input type="checkbox" name="world-prepare-group" value="${i}" ${eligible?'':'disabled'}> <span>${esc(title)}</span></label><p>${eligible?'Can enable whole-asset placement':g.status==='ALREADY_PREPARED'?'Placement already enabled':esc(g.reason||'Use Blender for this group; ownership could not be verified.')}</p><details><summary>Observed objects (${g.members.length})</summary><ul>${g.members.map(n=>`<li>${esc(n)}</li>`).join('')}</ul><p>Asset: ${esc(g.asset_id)}<br>Import: ${esc(g.import_job)}</p></details></section>`;
 }).join('');
 return {body:`<p>Choose assets to enable moving, rotating and scaling as whole objects. Director will verify a separate copy, preserving the saved arrangement and animation. It cannot recover an earlier unsaved placement.</p>${groups.length?rows:'<p>No owned import groups were observed. Arrange this scene in Blender; Director will not guess which objects belong together.</p>'}<p>Your current scene stays unchanged. Review the copy in 3D, then use <strong>Save changes</strong> to keep it or <strong>Undo</strong> to return. This does not mark World ready.</p>`,
  buttons:available?b('Prepare a separate copy','world-prepare-confirm',{run:run.id},'primary',true):''};
}
export function preparationSelection(run,indices){
 if(!Array.isArray(indices)||!indices.length||indices.length>64||new Set(indices.map(String)).size!==indices.length)throw Error('Choose one to 64 independently preparable assets.');
 return indices.map(value=>{const index=Number(value),g=Number.isInteger(index)&&index>=0?run.inspection.groups[index]:null;
  if(!g||g.status!=='PREPARABLE')throw Error('Choose only assets supported by this placement check.');
  return {asset_id:g.asset_id,import_job:g.import_job};
 });
}
