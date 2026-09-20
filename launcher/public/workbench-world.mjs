/** Guided World presentation. Persisted scene evidence alone determines progress. */
import {taskBanner} from './workbench-task.mjs';
import {progressLabel} from './workbench-progress.mjs';
import {previewIsCurrent} from './workbench-lineage.mjs';

export function worldState({project,scene,locked=false,sourceUse,runs=[]}) {
  const checkpoint=scene.checkpoints.find(c=>c.id===(scene.candidate||scene.current));
  const objects=checkpoint?.audit?.objects||[];
  const pending=(project.workbench.catalogPins||[]).filter(a=>(scene.catalog||[]).includes(a.id)&&['model','pack'].includes(a.kind)&&(!checkpoint||Array.isArray(checkpoint.audit?.objects))&&!objects.some(o=>o.asset_id===a.id));
  const run=runs.find(r=>r.id===scene.run);
  const failed=runs.find(r=>r.sceneId===scene.id&&['FAILED','INTERRUPTED'].includes(r.state)&&!r.recovery);
  const kind=scene.task?'editing':scene.run?'working':locked?'locked':scene.candidate?'review':sourceUse&&!sourceUse.ready?'rights':pending.length?'add':checkpoint?'ready':scene.sources?.length?'package':'empty';
  return {kind,checkpoint,pending,run,failed};
}

export function worldView({project,scene,stages,locked,sourceUse,runs,taskStatus,cap,esc,b}) {
  const v=worldState({project,scene,locked,sourceUse,runs}),cp=v.checkpoint;
  const blocked=locked||!!scene.task||!!scene.run,unsupported=!cap?.task_workspace;
  const button=(label,action,data={},style='',disabled=false)=>b(label,action,data,style,disabled||blocked||unsupported);
  const guides={
    empty:['Find your first asset','Choose an environment, prop or character.','Find an asset','browse-assets'],
    package:['Prepare your source package','Original packages need reviewed catalog intake before import.','Inspect source package','source-detail',{id:scene.sources?.[0]}],
    add:['Add to your world',v.pending[0]?.title||'Review the selected source before adding it.','Add to world','catalog-detail',{id:v.pending[0]?.id}],
    rights:['Review source use','Confirm permission for the exact sources selected for this production.','Review source use','source-review'],
    review:['Review this change','Orbit the saved result. Keep it to continue building, or discard this change.','Keep this change','keep-building'],
    ready:['Ready for action?','Add more ingredients or arrange them in Blender. Continue when your World is ready.','Continue to Action','approve'],
    editing:['Arrange in Blender','Your saved scene stays here while you edit a separate working copy.'],
    working:[v.run?.action==='asset-contents'?'Inspecting source collections':'Building your scene',progressLabel(v.run)],
    locked:['Another operation is active','Wait for the project writer to finish. Your saved work is preserved.']
  };
  const [title,hint,label,action,data]=guides[v.kind];
  const status=scene.candidate?'New change · not kept':cp?'Saved scene':'No assets imported yet';
  const preview=cp&&previewIsCurrent(scene,cp.id),camera=cp?.audit?.objects?.some(o=>o.type==='CAMERA');
  return `<div class="world-top"><label>Scene<select id="scene-picker" aria-label="Selected scene">${project.workbench.scenes.map(x=>`<option value="${esc(x.id)}" ${x.id===scene.id?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label><div class="grow"></div><details class="world-more"><summary>More</summary><div class="world-menu">${b('Add scene','new-scene')}${b('Checkpoint history','history')}${button('Open Codex specialist','codex')}${button('Import saved working scene','import',{},'',!!scene.candidate)}${button('Start from an empty Blender scene','task',{},'',!!scene.candidate||!!cp)}${b('Selected ingredients','world-ingredients')}${b('Scene details','world-details')}</div></details></div>
    <nav class="steps world-steps" aria-label="Activities in this scene">${stages.map((st,i)=>{const unavailable=!!scene.task||!!scene.candidate||!!scene.run||stages.slice(0,i).some(x=>!scene.completed[x.id]);return `<span title="${unavailable?'Finish and review the current activity first':esc(st.label)}">${b((scene.completed[st.id]?'✓ ':String(i+1)+' ')+st.short,'stage',{stage:st.id},`${scene.stage===st.id?'active ':''}${scene.completed[st.id]?'done':''}`,unavailable).replace('<button','<button'+(scene.stage===st.id?' aria-current="step"':''))}</span>`;}).join('')}</nav>
    ${unsupported?'<div class="note warn" role="alert">'+esc(cap?.message||'This runtime cannot open Blender tasks. Check Studio before continuing.')+'</div>':''}
    ${v.failed&&!scene.run?`<div class="note warn world-failure" role="alert"><strong>An earlier attempt needs attention</strong><p>${esc(v.failed.error||v.failed.state)}. Failed evidence is retained.</p>${b('Inspect / recover attempt','recover',{run:v.failed.id})}</div>`:''}
    ${v.kind==='review'&&sourceUse&&!sourceUse.ready?'<div class="note warn" role="alert">Source-use review is still required. '+button('Review source use','source-review')+'</div>':''}
    <section class="world-canvas" aria-label="World scene"><header><h1>Build your world</h1><span class="world-status">${status}</span></header>
      ${cp?`<section class="viewer-3d" data-scene-viewer aria-label="Saved scene in 3D"><div class="viewer-message"><strong>Explore your saved scene</strong><p>${blocked?'Your current task is separate from this saved checkpoint.':'Loading saved geometry for inspection…'}</p>${b('View saved scene in 3D','scene-viewer',{},'ghost',blocked)}</div></section>`:`<div class="world-empty"><h2>${v.pending.length?'Your asset is chosen':'Every world starts with an ingredient'}</h2><p>${v.pending.length?'It is not in your scene yet. Add it below to create real scene objects.':'Find something to place in your scene, then make it your own.'}</p>${v.pending.length?b('Preview selected asset in 3D','catalog-preview-detail',{id:v.pending[0].id,preview:'true'},'ghost'):''}</div>`}
    </section>
    <section class="world-next" aria-label="Next step" data-world-state="${v.kind}"><div class="grow"><h2>${esc(title)}</h2><p>${esc(hint)}</p></div><div class="world-next-actions">${action?button(label,action,data||{},'primary'):''}${v.kind==='review'?button('Inspect in Blender','inspect-candidate')+button('Discard change','discard',{},'ghost'):v.kind==='ready'?button('Arrange in Blender','task')+button('Add another asset','browse-assets',{},'ghost'):['empty','add','rights','package'].includes(v.kind)?button(v.kind==='empty'?'Arrange in Blender':'Choose another asset',v.kind==='empty'?'task':'browse-assets',{},'ghost'):v.kind==='working'?b('Inspect operation','recover',{run:scene.run},'ghost'):v.kind==='locked'?b('Refresh status','refresh',{},'ghost'):''}</div></section>
    ${scene.task?taskBanner(scene,taskStatus,esc,b):''}
    ${cp?`<details class="world-inspection"><summary>Inspection tools</summary><div class="row">${b('Reload saved scene in 3D','scene-viewer',{},'',blocked)}${button('Inspect saved file in Blender','inspect-candidate')}</div><p>Saved geometry only; unsaved Blender edits are not shown. Preview lighting and materials may differ from Blender.</p><details class="rendered-evidence"><summary>Rendered still${preview?' · available':''}</summary>${preview?'<img data-media="preview" alt="Rendered still of the current saved checkpoint">':''}<p>${camera?'A camera-rendered still is separate from this interactive view.':'A saved camera is needed for a rendered still.'}</p>${button('Render preview still','preview',{},'',!cap?.render_frames||!camera)}</details></details>`:''}
    `;
}

/** Explicit add intent may pin first, but never grants rights or auto-approves. */
export async function addWorldAsset({selected,confirm,pin,reload,sourceReady,run}) {
  if(!confirm())return 'cancelled';
  if(!selected){await pin();sourceReady=(await reload()).sourceUse?.ready===true;}
  if(!sourceReady)return 'needs-rights';
  await run();return 'started';
}
