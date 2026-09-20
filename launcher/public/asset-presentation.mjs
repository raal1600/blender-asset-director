/** Factual display helpers; no inference from an asset's marketing name. */
export const subcategories=[['character','Character'],['environment','Environment'],['prop','Prop'],['rigged-model','Rigged model'],['model','Model · unclassified'],['pack','Asset pack'],['motion','Motion take'],['material','Material'],['hdri','HDRI']];
export const previewMember=file=>/\.(blend|gltf|glb|fbx|bvh)$/i.test(file);
export const referenceImage=file=>/\.(png|jpe?g)$/i.test(file)&&/(^|[ _.-])(preview|thumbnail|thumb|screenshot|reference)([ _.-]|$)/i.test(file.split('/').pop().replace(/\.[^.]+$/,''));
export function sourceCategory(source) {
  if(source.kind==='Characters')return {id:'character',basis:'Registered Characters collection'};
  if(source.kind==='Animations')return {id:'motion',basis:'Registered Animations collection'};
  const category=source.relative?.split('/')[1]?.toLowerCase();
  if(['terrain','environments','landscapes','buildings'].includes(category))return {id:'environment',basis:'Registered '+category+' collection'};
  if(['props','objects','furniture'].includes(category))return {id:'prop',basis:'Registered '+category+' collection'};
  return {id:'model',basis:'Specific model subcategory has not been recorded'};
}
export function typeLabel(asset) {
  const id=asset.subcategory?.id||({animation:'motion',Animations:'motion',Characters:'character',Meshes:'model'}[asset.kind]||asset.kind);
  return subcategories.find(([key])=>key===id)?.[1]||'Unclassified asset';
}
export function humanBytes(value) {
  if(!Number.isFinite(value)||value<0)return 'Size unknown';
  return value>=1024*1024?(value/(1024*1024)).toFixed(1)+' MiB':value>=1024?(value/1024).toFixed(1)+' KiB':value+' bytes';
}
export function motionSummary(asset) {
  const m=asset.motion||asset.metadata||{},fps=Number(m.fps);
  const start=m.frame_start??m.frame_range?.[0],end=m.frame_end??m.frame_range?.[1];
  const seconds=Number.isFinite(start)&&Number.isFinite(end)&&fps>0?(end-start)/fps:null;
  return [seconds!==null?seconds.toFixed(2)+' s':null,Number.isFinite(fps)&&fps>0?fps+' fps':null,m.source_object?'Performer: '+m.source_object:null].filter(Boolean).join(' · ');
}
export function previewHint() {
  return '<p class="preview-explanation">Orbit the real asset in a separate Blender <strong>preview copy</strong>. Play observed native takes with the Asset preview panel. Your current Blender scene stays untouched.</p><p class="muted">Inspection only: no selection, import, retargeting or rights approval. Copies at most 512 MiB / 4096 files; no render or download. Close the preview with X when finished.</p><p id="asset-preview-status" role="status" aria-live="polite"></p>';
}
export function policyMessage(policy) {
  if(policy?.eligible)return 'Recorded source policy permits use; production source review and technical compatibility are separate.';
  const labels={PRICE_UNVERIFIED:'Free-use or price evidence has not been verified',FORMAT_UNSUPPORTED:'Production-import format has not been recorded as supported',LICENSE_EVIDENCE_MISSING:'Retained license evidence is missing',LICENSE_UNSUPPORTED:'The recorded license needs review'};
  return policy?.reasons?.map(reason=>labels[reason]||String(reason).replaceAll('_',' ').toLowerCase()).join('. ')||'Source-use evidence is required before production use.';
}
