/** Display metadata only: preserve originals, catalog versions and review history. */
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {assert,exists,json,now,safe,writeJson} from './storage.mjs';

export async function labelArguments(work) {
  const file=await safe(work.store.root,'SystemRuntime/UserData/Launcher/asset-labels.json');
  return await exists(file)?['--labels',file]:[];
}
export async function displayLabels(work,state) {
  const args=await labelArguments(work);if(!args.length)return state;
  const store=await json(args[1]);assert(store.schema===1&&store.labels,'Invalid display label store.');
  for(const pin of state.project.workbench.catalogPins||[]) {
    const label=store.labels[pin.id];
    if(label?.version===pin.version)pin.subcategory={id:label.subcategory,basis:'User catalog label for this exact source version'};
  }
  return state;
}
export async function setCatalogLabel(work,id,sceneId,revision,request) {
  assert(request&&Object.keys(request).every(k=>['assetId','version','subcategory'].includes(k)),'Unknown label request.');
  assert(['character','environment','prop','rigged-model','model','pack'].includes(request.subcategory),'Choose a supported subcategory.');
  const p=await work.project(id,revision);work.scene(p,sceneId);
  const asset=await work.catalogDetail(id,request.assetId);
  assert(asset.version===request.version&&['model','pack'].includes(asset.kind),'The displayed asset changed or has a fixed type. Reopen Details.',409);
  const file=await safe(work.store.root,'SystemRuntime/UserData/Launcher/asset-labels.json');
  const store=await exists(file)?await json(file):{schema:1,labels:{}};
  assert(store.schema===1&&store.labels&&Object.keys(store.labels).length<10000,'Display label store is invalid or full.');
  const previous=store.labels[asset.id]||null,next={version:asset.version,subcategory:request.subcategory};
  await writeJson(path.join(path.dirname(file),'AssetLabelHistory',randomUUID()+'.json'),{assetId:asset.id,previous,next,at:now(),kind:'DISPLAY_LABEL_ONLY'});
  store.labels[asset.id]=next;await writeJson(file,store);
  return {saved:true,assetId:asset.id,version:asset.version,subcategory:request.subcategory,sourceChanged:false,rightsApproved:false};
}
