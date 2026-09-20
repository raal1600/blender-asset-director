/** Details, preselection preview, and guarded import are separate actions. */
import {subcategories,typeLabel,humanBytes,motionSummary,previewMember,previewHint,policyMessage} from './asset-presentation.mjs';
export function catalogDialog({asset,scene,locked,sourceReady,esc,b}) {
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
