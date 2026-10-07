/** Read-only camera bounds from exact exported ownership, never guessed names. */
export function performerMeshes(gltf,name){
 const nodes=gltf?.parser?.json?.nodes,associations=gltf?.parser?.associations;
 if(!name||!Array.isArray(nodes)||!associations?.get)return [];
 const ids=nodes.flatMap((node,i)=>node.name===name?[i]:[]);if(ids.length!==1)return [];
 const objects=[];gltf.scene.traverse(o=>objects.push(o));
 const roots=objects.filter(o=>associations.get(o)?.nodes===ids[0]);if(roots.length!==1)return [];
 const inside=o=>{for(let p=o;p;p=p.parent)if(p===roots[0])return true;return false;};
 const bones=new Set(objects.filter(o=>o.isBone&&inside(o)));if(!bones.size)return [];
 const meshes=objects.filter(o=>o.isSkinnedMesh&&o.skeleton?.bones?.some(b=>bones.has(b)));
 if(meshes.some(o=>!o.skeleton.bones.every(b=>bones.has(b))))return [];
 return meshes;
}
