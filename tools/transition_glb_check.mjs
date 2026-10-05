/** Compare real exported animation with fresh Blender evaluated poses. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import * as THREE from '../launcher/public/vendor/three/build/three.module.js';
import {GLTFLoader} from '../launcher/public/vendor/three/examples/jsm/loaders/GLTFLoader.js';
const [folder]=process.argv.slice(2);assert(path.isAbsolute(folder));
const result={status:'FAIL',checks:[],frame_parity:'NOT_VERIFIED',subframe_parity:'NOT_VERIFIED'};
try{
 const native=JSON.parse(await fs.readFile(path.join(folder,'RESULTS.json'),'utf8'));
 assert.equal(native.status,'PASS');
 const raw=await fs.readFile(path.join(folder,'accepted.glb'));
 const gltf=await new GLTFLoader().parseAsync(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength),'');
 assert.equal(gltf.animations.length,1);
 const mixer=new THREE.AnimationMixer(gltf.scene),action=mixer.clipAction(gltf.animations[0]);
 action.setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;action.play();
 const bones=new Map();gltf.scene.traverse(node=>{
  if(node.isBone){const name=node.userData.name??node.name;assert(!bones.has(name),`Ambiguous exported bone ${name}`);bones.set(name,node);}
 });
 const sourceToGltf=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),-Math.PI/2);
 const rows=[];
 for(const sample of native.samples){
  action.paused=false;action.time=(sample.frame-native.frame_range[0])/native.fps;
  mixer.update(0);gltf.scene.updateMatrixWorld(true);gltf.scene.traverse(o=>o.skeleton?.update());
  const compare=(name,pose,offset=null)=>{
   const node=bones.get(name);assert(node?.isBone,`Export lost bone ${name}`);
   const point=offset?offset.clone().applyMatrix4(node.matrixWorld):node.getWorldPosition(new THREE.Vector3());
   const expected=new THREE.Vector3(pose.p[0],pose.p[2],-pose.p[1]);
   const actualQ=node.getWorldQuaternion(new THREE.Quaternion());
   const blenderQ=new THREE.Quaternion(pose.q[1],pose.q[2],pose.q[3],pose.q[0]);
   const expectedQ=sourceToGltf.clone().multiply(blenderQ);
   const position=point.distanceTo(expected),orientation=THREE.MathUtils.radToDeg(actualQ.angleTo(expectedQ));
   assert(Number.isFinite(position)&&Number.isFinite(orientation));
   rows.push({frame:sample.frame,joint:name,position_m:position,orientation_deg:orientation});
   assert(position<=.001*native.height_m,`GLB ${name} position parity at ${sample.frame}: ${position}`);
   assert(orientation<=1,`GLB ${name} orientation parity at ${sample.frame}: ${orientation}`);
  };
  if(sample.joints){for(const [name,pose] of Object.entries(sample.joints)) compare(name,pose);}
  if(sample.p)compare('Upper',sample,new THREE.Vector3(0,.7,0));
 }
 assert(rows.some(r=>Number.isInteger(r.frame)),'Integer-frame coverage is required');
 assert(rows.some(r=>!Number.isInteger(r.frame)),'Subframe coverage is required');
 assert(rows.length>=native.samples.length,'Every Blender sample must contain compared joint transforms');
 result.status='PASS';result.frame_parity='PASS';result.subframe_parity='PASS';result.samples=rows;
 result.source_sha256=native.source_sha256;
 result.checks.push('Same accepted .blend and application GLB agree at integer frames and boundary subframes within .001 height / 1 degree');
}catch(error){result.error=String(error);process.exitCode=1;}
await fs.writeFile(path.join(folder,'GLB-RESULTS.json'),JSON.stringify(result,null,2),{flag:'wx'});
console.log(JSON.stringify(result));
