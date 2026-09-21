/** Details, preselection preview, and guarded import are separate actions. */
import {subcategories,typeLabel,humanBytes,motionSummary,previewMember,previewHint,policyMessage} from './asset-presentation.mjs';
import {ingredientStatus} from './workbench-browser.mjs';
export function catalogDialog({asset,scene,locked,sourceReady,fileChoice,esc,b}) {
  if(scene.stage==='world'&&['model','pack'].includes(asset.kind))return worldCatalogDialog({asset,scene,locked,sourceReady,fileChoice,esc,b});
  const selected=(scene.catalog||[]).includes(asset.id),observed=scene.assetContents?.[asset.id];
  const files=asset.files||[],models=asset.models||[];
  const file=models.length===1?models[0]:null;
  const contents=observed?.version===asset.version&&observed.file===(file||observed.file)?observed:null;
  const canWorld=scene.stage==='world'&&['model','pack'].includes(asset.kind);
  const previewFiles=files.filter(f=>previewMember(f.path));
  const members=[...new Set([...models,...previewFiles.map(f=>f.path)])];
  const motion=motionSummary(asset);
  const buttons=`${previewFiles.length?b('View in 3D','viewer-open',{kind:'catalog',id:asset.id,version:asset.version},'primary')+b('Preview in Blender','asset-preview-open',{kind:'catalog',id:asset.id,version:asset.version}):''}${b(selected?'Remove from selection':'Add to selection','catalog-detail-select',{id:asset.id},'',locked||!!scene.candidate)}${canWorld&&models.some(f=>f.toLowerCase().endsWith('.blend'))?b('Inspect collections','catalog-inspect',{id:asset.id},'',locked||!selected):''}${canWorld?b('Import into World','catalog-import',{id:asset.id},'',locked||!!scene.candidate||!selected||!models.length||!asset.policy?.eligible||!sourceReady):''}`;
  return {body:`<div class="asset-facts"><span class="asset-type" title="${esc(asset.subcategory?.basis)}">${esc(typeLabel(asset))}</span><span>${esc(asset.provider)}</span><span>${esc(asset.license_id)}</span></div>
    <p class="muted">${esc(asset.subcategory?.basis||'Specific subcategory has not been recorded. No type was guessed from the filename.')}</p>
    ${motion?'<p class="motion-facts">'+esc(motion)+'</p>':''}
    ${asset.bundled_clip_count!==null&&asset.bundled_clip_count!==undefined?'<p>'+asset.bundled_clip_count+' indexed bundled takes · native playback is separate from retargeting.</p>':''}
    <p>${files.length} recorded files · ${esc(humanBytes(files.reduce((n,f)=>n+f.size,0)))}</p>
    ${members.length?`<label>Source file<select id="catalog-file">${members.map(p=>`<option value="${esc(p)}" ${p===contents?.file?'selected':''}>${esc(p)} · ${esc(humanBytes(files.find(f=>f.path===p)?.size))}</option>`).join('')}</select></label>`:'<p>No supported 3D member. Use the reviewed material/HDRI specialist workflow.</p>'}
    ${previewFiles.length?previewHint():'<p class="note">Interactive preview supports blend, glTF, GLB, FBX and BVH members. This package needs a reviewed format adapter.</p>'}
    <section class="asset-use"><h3>Use in this scene</h3><p>${selected?'In your selection. ':'Not selected. '}${asset.kind==='animation'?'Selection does not apply motion. Use Action for native performer review and an exact reviewed transfer plan.':'Add keeps an ingredient reference. Import creates real objects in a new World candidate.'}</p>
    <p>${esc(policyMessage(asset.policy))}</p>
    <p id="catalog-operation-status" role="status" hidden></p>
    ${canWorld&&!sourceReady?'<p class="note warn">Production source use still needs your review before import. Preview does not grant permission.</p>':''}</section>
    ${contents?.collections?.length?`<fieldset><legend>Observed Blender collections</legend>${contents.collections.map(n=>`<label><input name="catalog-collection" type="checkbox" value="${esc(n)}"> ${esc(n)}</label>`).join('')}</fieldset>`:''}
    ${['model','pack'].includes(asset.kind)?`<details><summary>Edit subcategory</summary><p>A display label for this source version only. This does not change asset bytes, catalog identity or rights.</p><label>Subcategory<select id="asset-subcategory">${subcategories.filter(([id])=>['character','environment','prop','rigged-model','model','pack'].includes(id)).map(([id,label])=>`<option value="${id}" ${id===(asset.subcategory?.id||asset.kind)?'selected':''}>${esc(label)}</option>`).join('')}</select></label>${b('Save subcategory','catalog-label',{id:asset.id,version:asset.version})}</details>`:''}
    <details><summary>Version, source and rights evidence</summary><pre>${esc(JSON.stringify({id:asset.id,version:asset.version,source:asset.source_url,license:asset.license_url,author:asset.author,evidence:asset.evidence,metadata:asset.metadata},null,2))}</pre></details>`,buttons};
}

/** Preview first; exact member, collections and rights still gate every import. */
export function worldCatalogDialog({asset,scene,locked,sourceReady,fileChoice,esc,b}) {
  const models=asset.models||[],files=asset.files||[],selected=(scene.catalog||[]).includes(asset.id);
  const members=[...new Set([...models,...files.filter(f=>previewMember(f.path)).map(f=>f.path)])];
  const observed=scene.assetContents?.[asset.id];
  const file=members.includes(fileChoice)?fileChoice:members.includes(observed?.file)?observed.file:members[0];
  const blend=!!file?.toLowerCase().endsWith('.blend');
  const contents=observed?.version===asset.version&&observed.file===file?observed:null;
  const blocked=locked||!!scene.candidate||!!scene.task||!!scene.run;
  const status=ingredientStatus(scene,asset.id),present=['In checkpoint','In candidate'].includes(status);
  let main;
  if(!models.includes(file))main=b('Preview only · import preparation required','catalog-import',{id:asset.id},'primary',true);
  else if(!asset.policy?.eligible)main=b('Source policy blocks import','catalog-import',{id:asset.id},'primary',true);
  else if(selected&&!sourceReady)main=b('Review source use','source-review',{},'primary',blocked);
  else if(blend&&!contents)main=b('Inspect collections','catalog-inspect',{id:asset.id},'primary',blocked);
  else main=b(present?'Add another copy':'Add to world','catalog-import',{id:asset.id},'primary',blocked||!models.includes(file)||(blend&&!contents?.collections?.length));
  const preview=previewMember(file||''),viewButton=preview?b('View in 3D','viewer-open',{kind:'catalog',id:asset.id,version:asset.version},'ghost'):'';
  return {autoPreview:preview&&asset.policy?.eligible===true,body:`<div class="asset-facts"><span class="asset-type" title="${esc(asset.subcategory?.basis)}">${esc(typeLabel(asset))}</span><span>${present?status==='In candidate'?'In the pending scene change':'Already in the saved scene':status==='Presence not verified'?'Presence in saved scene not verified':'Preview · not in scene'}</span>${!asset.policy?.eligible?viewButton:''}</div>
    <p class="world-preview-scope">Single-asset preview. Add to world combines this asset with your existing saved scene; choosing it alone does not import it.</p>
    ${members.length?`<label class="world-member ${members.length===1?'single-member':''}">Source file<select id="catalog-file">${members.map(f=>`<option value="${esc(f)}" ${f===file?'selected':''}>${esc(f.split('/').at(-1))}</option>`).join('')}</select></label>`:'<p>No supported 3D member is recorded.</p>'}
    ${preview?previewHint():''}
    <p id="catalog-operation-status" role="status" hidden></p>
    ${blocked?'<p class="note warn" role="alert">Finish the current task or review the pending change before adding assets.</p>':''}
    ${!asset.policy?.eligible?'<p class="note warn" role="alert">'+esc(policyMessage(asset.policy))+'</p>':selected&&!sourceReady?'<p class="note warn">Review permission for this production before import. Previewing grants no rights.</p>':!selected?'<p class="muted">Add starts with your exact source choice. If rights review is needed, import waits for you.</p>':''}
    ${blend?contents?`<fieldset><legend>Choose collections to add</legend>${contents.collections.map(n=>`<label><input name="catalog-collection" type="checkbox" value="${esc(n)}"> ${esc(n)}</label>`).join('')||'<p>No appendable collections were observed. Prepare a named collection in a separate Blender copy.</p>'}</fieldset>`:'<p>Inspect this Blender file first, then choose its observed collections.</p>':''}
    <details class="asset-more"><summary>Details and more tools</summary><p>${esc(asset.subcategory?.basis||'Specific subcategory has not been recorded.')}</p><p>${files.length} files · ${esc(humanBytes(files.reduce((n,f)=>n+f.size,0)))} · ${esc(asset.license_id||'Rights not recorded')}</p><p>${esc(file||'')}</p><p>${esc(policyMessage(asset.policy))}</p><div class="row">${viewButton}${preview?b('Preview in Blender','asset-preview-open',{kind:'catalog',id:asset.id,version:asset.version}):''}${b(selected?'Remove from selection':'Choose without importing','catalog-detail-select',{id:asset.id},'',blocked)}${blend&&contents?b('Reinspect collections','catalog-inspect',{id:asset.id},'',blocked):''}</div>
    <label>Subcategory<select id="asset-subcategory">${subcategories.filter(([id])=>['character','environment','prop','rigged-model','model','pack'].includes(id)).map(([id,label])=>`<option value="${id}" ${id===(asset.subcategory?.id||asset.kind)?'selected':''}>${label}</option>`).join('')}</select></label>${b('Save subcategory','catalog-label',{id:asset.id,version:asset.version},'',blocked)}
    <details><summary>Version, source and rights evidence</summary><pre>${esc(JSON.stringify({id:asset.id,version:asset.version,source:asset.source_url,license:asset.license_url,author:asset.author,evidence:asset.evidence,metadata:asset.metadata},null,2))}</pre></details></details>`,buttons:main};
}
