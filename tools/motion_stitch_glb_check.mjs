/** Compare actual saved-frame geometry; report subframe approximation separately. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import * as THREE from '../launcher/public/vendor/three/build/three.module.js';
import {GLTFLoader} from '../launcher/public/vendor/three/examples/jsm/loaders/GLTFLoader.js';
const [folder]=process.argv.slice(2);assert(path.isAbsolute(folder));
const report={scope:'GENERATED_CONNECTION_GLB_COMPARISON',checks:[],subframe_diagnostics:[],subframe_exact_agreement:'NOT_SUPPORTED_FRAME_SAMPLED_EXPORT',human_review:'NOT_TESTED'};
try{
 const native=JSON.parse(await fs.readFile(path.join(folder,'RESULTS.json'),'utf8'));assert.equal(native.status,'PASS');assert.equal(native.input_kind,'GENERATED');
 const raw=await fs.readFile(path.join(folder,'stitched.glb')),gltf=await new GLTFLoader().parseAsync(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength),'');
 assert.equal(gltf.animations.length,1);const mixer=new THREE.AnimationMixer(gltf.scene),clip=mixer.clipAction(gltf.animations[0]);clip.setLoop(THREE.LoopOnce,1);clip.clampWhenFinished=true;clip.play();
 for(const sample of native.samples){clip.paused=false;clip.time=(sample.frame-1)/24;mixer.update(0);gltf.scene.updateMatrixWorld(true);gltf.scene.traverse(o=>o.skeleton?.update());
  const mesh=gltf.scene.getObjectByName('VisibleSkin0');assert(mesh?.isMesh);const point=new THREE.Vector3(),v=new THREE.Vector3();
  for(let i=0;i<mesh.geometry.attributes.position.count;i++){mesh.getVertexPosition(i,v);point.add(v.applyMatrix4(mesh.matrixWorld));}point.divideScalar(mesh.geometry.attributes.position.count);
  const expected=new THREE.Vector3(sample.skin[0],sample.skin[2],-sample.skin[1]),error=point.distanceTo(expected);
  // The existing exporter explicitly samples whole scene frames, not the
  // quarter-frame native bridge keys. Verify its specified frames exactly;
  // preserve intervening differences rather than inventing a subframe guarantee.
  assert(Number.isFinite(error));
  if(Number.isInteger(sample.frame)){const tolerance=1e-4;assert(error<tolerance,'Native/GLB geometry differs at frame '+sample.frame+': '+error);report.checks.push({frame:sample.frame,error,tolerance});}
  else report.subframe_diagnostics.push({frame:sample.frame,error,units:'Blender scene units',acceptance:'DIAGNOSTIC_ONLY'});
 }
 assert(report.checks.some(c=>c.frame>native.join.start&&c.frame<native.join.end),'Missing saved-frame checks inside the connection');
 report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error);process.exitCode=1;}
await fs.writeFile(path.join(folder,'GLB-RESULTS.json'),JSON.stringify(report,null,2),{flag:'wx'});console.log(JSON.stringify(report));
