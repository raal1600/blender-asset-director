/** Production membership is not download state, permission or scene presence. */
const observed=(scene,id,key)=>{
  const checkpoint=scene.checkpoints?.find(c=>c.id===scene[key]);
  return checkpoint?.audit?.objects?.some(o=>o.asset_id===id)===true;
};
export function libraryUsage(project,scene,id,{source=false}={}) {
  const scenes=project.workbench?.scenes||[scene];
  if(!source&&observed(scene,id,'candidate'))return {label:'In pending change',action:'review',present:true};
  if(!source&&observed(scene,id,'current'))return {label:'In this scene',action:'locate',present:true};
  const chosen=source?(scene.sources||[]).includes(id):(scene.catalog||[]).includes(id);
  const other=scenes.filter(s=>s.id!==scene.id&&(!source&&observed(s,id,'current')));
  if(other.length)return {label:'Used in '+other.length+' other scene'+(other.length===1?'':'s'),action:'add',chosen};
  const cp=scene.checkpoints?.find(c=>c.id===(scene.candidate||scene.current));
  if(!source&&chosen&&cp&&!Array.isArray(cp.audit?.objects))return {label:'Chosen · scene presence unverified',action:'inspect',chosen};
  if(chosen)return {label:'Chosen · not imported',action:'add',chosen};
  const referenced=scenes.some(s=>(source?s.sources:s.catalog||[])?.includes(id));
  if(referenced)return {label:'Chosen in another scene · not imported',action:'add'};
  const historical=source?(project.assets||[]).some(a=>a.sourceId===id):(project.workbench?.catalogPins||[]).some(a=>a.id===id);
  return {label:historical?'Retained production reference':'Not in this production',action:'add'};
}

export function libraryAvailability(asset,{source=false}={}) {
  if(source)return asset.available?asset.prepared?'Local · prepared catalog version':'Local · needs preparation':'Files unavailable';
  if(asset.pinnedOnly)return 'Pinned version · check availability';
  if(!asset.policy?.eligible)return 'Local · rights review required';
  if(['model','pack'].includes(asset.kind))return asset.models?.length?'Local · ready for import checks':'Local · conversion required';
  return asset.kind==='animation'?'Local · motion review required':'Local · specialist setup required';
}
