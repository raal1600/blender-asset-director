/** Match exporter-observed mesh nodes to observed instance controls, never guessed names. */
import {assert} from './storage.mjs';
import {validId} from './workbench-model.mjs';
import {unpackGLB} from './viewer-gltf.mjs';
import {placementMatrix} from '../public/world-draft.mjs';

export function bindWorldPreview(bytes,exported){
  if(!exported.placement)return null; // Older matching inspection-only runtimes remain viewable.
  const placement=exported.placement;
  assert(placement.version==='world-transform-v1'&&Array.isArray(placement.instances)&&placement.instances.length<=10000&&
    Array.isArray(exported.static_objects)&&exported.static_objects.length<=10000,'Invalid observed World placement metadata.');
  const {document}=unpackGLB(bytes),used=new Set(),identities=new Set(),instances=[];
  assert(Array.isArray(document.nodes),'World preview has no observed nodes.');
  const nodeMap=new Map(),membersByInstance=new Map();
  document.nodes.forEach((node,index)=>{if(node.mesh!==undefined){const matches=nodeMap.get(node.name)||[];matches.push(index);nodeMap.set(node.name,matches);}});
  for(const member of exported.static_objects){const members=membersByInstance.get(member.instance)||[];members.push(member);membersByInstance.set(member.instance,members);}
  for(const item of placement.instances){
    assert(validId(item.instance,'instance_')&&!identities.has(item.instance)&&typeof item.control==='string'&&
      Array.isArray(item.members)&&item.members.length<=10000,'Invalid World instance identity.');identities.add(item.instance);
    placementMatrix(item.matrix);
    const nodes=[],owned=new Set(item.members);
    for(const member of membersByInstance.get(item.instance)||[]){
      assert(owned.has(member.source),'Preview geometry belongs to a different instance.');
      const matches=nodeMap.get(member.node)||[];
      assert(matches.length===1&&!used.has(matches[0]),'Preview node mapping is ambiguous.');
      used.add(matches[0]);nodes.push(matches[0]);
    }
    if(nodes.length)instances.push({instance:item.instance,control:item.control,assetId:item.asset_id,importJob:item.import_job,
      matrix:item.matrix,nodes,rigged:item.rigged,members:item.members});
  }
  return {version:placement.version,instances,unsupported:placement.unsupported||[],unprepared:placement.unprepared||[]};
}
