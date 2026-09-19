/** Read-only workflow classification. Never edits catalog identities or source folders. */
export const catalogKinds=[['model','Models'],['pack','Packs'],['animation','Motion'],['material','Materials'],['hdri','HDRIs']];
export const sourceKinds=[['Meshes','Meshes'],['Characters','Characters'],['Animations','Animations']];
export const workflowScopes={
  world:{label:'World assets',description:'Environments, props and characters to place in the scene.',catalog:['model','pack'],sources:['Meshes','Characters']},
  action:{label:'Animation & movement',description:'Motion takes for the performers already in this scene. Inspect rigs before transfer.',catalog:['animation'],sources:['Animations']},
  light:{label:'Materials & lighting',description:'Materials and HDRIs for the shared scene look. Assignment uses reviewed specialist tools.',catalog:['material','hdri'],sources:[]},
  shots:{label:'Scene cameras',description:'Use cameras observed in this scene checkpoint.',catalog:[],sources:[]},
  render:{label:'Shot outputs',description:'Use the saved shots and their rendered movies.',catalog:[],sources:[]}
};
export function scopeKinds(activity,source=false) {
  if(activity==='all')return (source?sourceKinds:catalogKinds).map(([kind])=>kind);
  const scope=workflowScopes[activity];
  if(!scope)throw new Error('Invalid workflow activity.');
  return scope[source?'sources':'catalog'];
}
export function inScope(asset,activity,source=false){return scopeKinds(activity,source).includes(asset.kind);}
