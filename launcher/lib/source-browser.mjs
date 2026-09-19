/** Read-only projections of the original registry; never scan or rewrite it. */
import {assert} from './storage.mjs';
import {scopeKinds} from '../public/workbench-scope.mjs';

export const SOURCE_PAGE_SIZE=24;
export function sourceSummary({id,name,kind,version,available,review,bytes,fileCount}) {
  return {id,name,kind,version,available,review,bytes,fileCount};
}
export function sourcePage(inventory,{query='',kind='',offset=0,selectedIds=null,activity='all'}={}) {
  assert(typeof query==='string'&&query.length<=2000,'Invalid source search.');
  assert(kind===''||['Meshes','Characters','Animations'].includes(kind),'Invalid source type.');
  assert(Number.isSafeInteger(offset)&&offset>=0,'Invalid source page.');
  let kinds;try{kinds=scopeKinds(activity,true);}catch{assert(false,'Invalid workflow activity.');}
  const words=query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  const selected=selectedIds===null?null:new Set(selectedIds);
  const matches=inventory.sources.filter(a=>kinds.includes(a.kind)&&(!kind||a.kind===kind)&&
    (!selected||selected.has(a.id))&&words.every(w=>a.name.toLocaleLowerCase().includes(w)))
    .sort((a,b)=>a.name.localeCompare(b.name)||a.id.localeCompare(b.id));
  // A refreshed registry can shrink. Return its last valid page, not a dead end.
  const start=matches.length?Math.min(offset,Math.floor((matches.length-1)/SOURCE_PAGE_SIZE)*SOURCE_PAGE_SIZE):0;
  return {items:matches.slice(start,start+SOURCE_PAGE_SIZE).map(sourceSummary),total:matches.length,
    offset:start,next_offset:start+SOURCE_PAGE_SIZE<matches.length?start+SOURCE_PAGE_SIZE:null};
}
export function selectedSourceSummary(inventory,project) {
  const ids=new Set(project.workbench.scenes.flatMap(s=>s.sources));
  return {schema:inventory.schema,scannedAt:inventory.scannedAt,total:inventory.sources.length,
    sources:inventory.sources.filter(a=>ids.has(a.id)).map(sourceSummary)};
}
