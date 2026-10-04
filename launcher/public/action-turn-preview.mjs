/** Reversible unsaved heading target on exact exported performer ownership.
 * No guessed Three.js names, source writes, jobs or animation baking.
 */
const finite=n=>typeof n==='number'&&Number.isFinite(n);
const heading=c=>c.heading_deg??0;
const ease=value=>{const u=Math.max(0,Math.min(1,value));return u*u*u*(10+u*(-15+6*u));};
const fail=message=>{throw Error(message);};
const inside=(object,root)=>{for(let p=object;p;p=p.parent)if(p===root)return true;return false;};

/** Saved GLB is sampled on integer scene frames; never infer subframe yaw.
 * Heading is relative to the native saved basis, not an anatomical facing.
 */
export function savedHeadingAt(timeline,frame){
 if(!Number.isInteger(frame)||!timeline||timeline.error)return null;
 if(timeline.managed===false)return 0;
 if(timeline.managed!==true||!Array.isArray(timeline.clips)||!timeline.clips.length)return null;
 const clips=[...timeline.clips].sort((a,b)=>a.start-b.start);
 if(clips.some((c,i)=>!Number.isInteger(c.start)||!Number.isInteger(c.frames)||c.frames<2||!finite(heading(c))||Math.abs(heading(c))>180||(i&&c.start<=clips[i-1].start+clips[i-1].frames-1)))return null;
 // Legacy managed clips have no added heading; their native orientation is
 // still the zero basis. No transition metadata is needed for constant yaw.
 if(clips.every(c=>heading(c)===heading(clips[0])))return heading(clips[0]);
 if(frame<=clips[0].start)return heading(clips[0]);
 const connections=timeline.connections;
 if(!Array.isArray(connections))return null;
 for(let i=1;i<clips.length;i++){
  const current=clips[i],previous=clips[i-1];
  if(frame>=current.start)continue;
  if(current.transition){
   const matches=connections.filter(c=>c.clip_id===current.id);
   if(matches.length!==1)return null;
   const join=matches[0];
   if(![join.start,join.end,join.duration_frames,join.heading_in_deg,join.heading_out_deg,join.turn_delta_deg].every(finite)||join.duration_frames<=0||Math.abs(join.end-join.start-join.duration_frames)>1e-7||join.end!==current.start||Math.abs(join.heading_in_deg-heading(previous))>1e-7||Math.abs(join.heading_out_deg-heading(current))>1e-7||!['turn','blend'].includes(join.mode))return null;
   if(frame>=join.start){const u=(frame-join.start)/join.duration_frames;return join.heading_in_deg+join.turn_delta_deg*ease(join.mode==='turn'?(u-.25)*2:u);}
  }else if(Math.abs(((heading(current)-heading(previous)+540)%360)-180)>1e-7)return null;
  return heading(previous);
 }
 return heading(clips.at(-1));
}

/** Resolve exact native names only through GLTFLoader parser associations.
 * Caller must restore() BEFORE each mixer evaluation, seek, selection change,
 * playback or disposal. apply() restores its prior override itself, so repeated
 * target drags never accumulate. It returns false after ownership changes.
 */
export function createTurnPreview({THREE,gltf,performer,performers=[]}){
 let snapshots=[],binding=null;
 const disabled=reason=>({available:false,reason,roots:[],rig:null,apply:()=>false,restore:()=>{},pivot:()=>null});
 const restore=()=>{
  for(const saved of snapshots){const o=saved.object;o.position.copy(saved.position);o.quaternion.copy(saved.quaternion);o.scale.copy(saved.scale);o.matrix.copy(saved.matrix);o.matrixAutoUpdate=saved.matrixAutoUpdate;o.matrixWorldNeedsUpdate=true;}
  snapshots=[];gltf?.scene?.updateMatrixWorld(true);
 };
 try{
  if(!performer||typeof performer.name!=='string'||performer.type!=='ARMATURE')fail('Select an inspected rigged performer to preview its body turn.');
  if(performer.unsupported||performer.timeline?.error)fail(performer.unsupported||performer.timeline.error);
  if(!Array.isArray(performer.takes)||!performer.takes.length||performer.takes.some(t=>t.heading_blocker!==null))fail('This performer needs a matching supported heading inspection first.');
  const nodes=gltf?.parser?.json?.nodes,associations=gltf?.parser?.associations,model=gltf?.scene;
  if(!Array.isArray(nodes)||!associations?.get||!model?.isObject3D)fail('This older preview has no verified performer-node mapping. Reopen its saved 3D preview.');
  const objects=[];model.traverse(o=>objects.push(o));
  const indexes=nodes.flatMap((n,i)=>n?.name===performer.name?[i]:[]);
  if(indexes.length!==1)fail('The exported performer name is missing or ambiguous. Inspect this turn in Blender.');
  const candidates=objects.filter(o=>associations.get(o)?.nodes===indexes[0]);
  if(candidates.length!==1)fail('The exported performer binding is shared or ambiguous. Inspect this turn in Blender.');
  const rig=candidates[0];
  if(rig===model||rig.isBone||rig.isMesh)fail('The preview has no isolated native rig root. Inspect this turn in Blender.');
  const otherRoots=[];
  for(const other of performers){
   if(!other||other.name===performer.name)continue;
   // The audit also lists ordinary static meshes. A skin part with no native
   // bindings is not a second performer; its skeleton ownership decides below.
   if(other.type!=='ARMATURE'&&!other.takes?.length)continue;
   const ids=nodes.flatMap((n,i)=>n?.name===other.name?[i]:[]);
   for(const object of objects)if(ids.includes(associations.get(object)?.nodes))otherRoots.push(object);
  }
  if(otherRoots.some(o=>inside(o,rig)||inside(rig,o)))fail('A second performer shares this hierarchy. Inspect the turn in Blender.');
  const roots=[rig],ownedBones=new Set(objects.filter(o=>o.isBone&&inside(o,rig)));
  if(!ownedBones.size)fail('No observed skeleton belongs to the exported performer. Inspect this turn in Blender.');
  const skins=[];
  for(const mesh of objects.filter(o=>o.isSkinnedMesh)){
   const bones=mesh.skeleton?.bones||[],count=bones.filter(b=>ownedBones.has(b)).length;
   if(count&&count!==bones.length)fail('A skin mixes joints from different performers. Inspect the turn in Blender.');
   if(inside(mesh,rig)&&(!bones.length||count!==bones.length))fail('A different or incomplete skin shares this performer hierarchy. Inspect the turn in Blender.');
   if(!count)continue;
   if(mesh.bindMode!=='attached')fail('Detached skin binding needs Blender turn inspection.');
   if(!inside(mesh,rig)){
    if(mesh.children.length||otherRoots.some(o=>inside(o,mesh)||inside(mesh,o)))fail('An external skin has additional ownership. Inspect the turn in Blender.');
    roots.push(mesh);
   }
   skins.push({mesh,skeleton:mesh.skeleton,bones:[...bones]});
  }
  if(!skins.length)fail('The selected rig has no uniquely bound visible skin in this preview.');
  if(new Set(roots).size!==roots.length||roots.some((r,i)=>roots.some((s,j)=>i!==j&&inside(r,s))))fail('The exported turn roots overlap. Inspect the turn in Blender.');
  const parentRotation=root=>{
   const matrix=root.parent?.matrixWorld||new THREE.Matrix4(),e=matrix.elements;
   if(!e.every(finite)||matrix.determinant()<=1e-10)fail('This preview parent has an unsupported transform.');
   const columns=[new THREE.Vector3(e[0],e[1],e[2]),new THREE.Vector3(e[4],e[5],e[6]),new THREE.Vector3(e[8],e[9],e[10])],lengths=columns.map(c=>c.length()),max=Math.max(...lengths);
   if(Math.min(...lengths)<=1e-8||max-Math.min(...lengths)>1e-6*max||columns.some((c,i)=>columns.some((d,j)=>j<i&&Math.abs(c.dot(d))>1e-6*lengths[i]*lengths[j])))fail('Nonuniform or sheared parent space needs Blender turn inspection.');
   return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().extractRotation(matrix));
  };
  model.updateMatrixWorld(true);for(const root of roots)parentRotation(root);
  binding={parents:roots.map(r=>r.parent),skins};
  const valid=()=>roots.every((r,i)=>r.parent===binding.parents[i]&&inside(r,model))&&!otherRoots.some(o=>roots.some(r=>inside(o,r)||inside(r,o)))&&skins.every(s=>s.mesh.bindMode==='attached'&&s.mesh.skeleton===s.skeleton&&s.skeleton.bones.length===s.bones.length&&s.bones.every((b,i)=>s.skeleton.bones[i]===b&&inside(b,rig)));
  const pivot=()=>{if(!valid())return null;model.updateMatrixWorld(true);return rig.getWorldPosition(new THREE.Vector3());};
  const result={available:true,reason:null,rig,roots:[...roots],pivot,restore,
   apply(deltaDegrees){
    restore();
    try{
     if(!finite(deltaDegrees)||Math.abs(deltaDegrees)>360||!valid())fail('The performer preview changed; reopen it before turning.');
     model.updateMatrixWorld(true);const center=rig.getWorldPosition(new THREE.Vector3()),yaw=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),THREE.MathUtils.degToRad(deltaDegrees));
     const changes=roots.map(object=>{
      const parentQ=parentRotation(object),parentInverse=new THREE.Matrix4().copy(object.parent?.matrixWorld||new THREE.Matrix4()).invert();
      const position=object.getWorldPosition(new THREE.Vector3()).sub(center).applyQuaternion(yaw).add(center).applyMatrix4(parentInverse);
      const quaternion=parentQ.clone().invert().multiply(yaw).multiply(parentQ).multiply(object.quaternion);
      return {object,position,quaternion};
     });
     snapshots=roots.map(object=>({object,position:object.position.clone(),quaternion:object.quaternion.clone(),scale:object.scale.clone(),matrix:object.matrix.clone(),matrixAutoUpdate:object.matrixAutoUpdate}));
     for(const change of changes){change.object.position.copy(change.position);change.object.quaternion.copy(change.quaternion);change.object.updateMatrix();change.object.matrixWorldNeedsUpdate=true;}
     model.updateMatrixWorld(true);for(const {mesh} of skins)mesh.skeleton.update();return true;
    }catch(error){restore();result.reason=String(error?.message||error);return false;}
   }};
  return result;
 }catch(error){restore();return disabled(String(error?.message||error));}
}
