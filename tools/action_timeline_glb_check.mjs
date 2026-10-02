/** Evaluate the actual native export independently of Blender and the DOM. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import * as THREE from '../launcher/public/vendor/three/build/three.module.js';
import {GLTFLoader} from '../launcher/public/vendor/three/examples/jsm/loaders/GLTFLoader.js';
const [folder]=process.argv.slice(2);assert(path.isAbsolute(folder));
const report={scope:'GENERATED_TIMELINE_GLB_COMPARISON',checks:[],human_review:'NOT_TESTED'};
try{
 const native=JSON.parse(await fs.readFile(path.join(folder,'RESULTS.json'),'utf8'));assert.equal(native.status,'PASS');
 const raw=await fs.readFile(path.join(folder,'timeline.glb')),gltf=await new GLTFLoader().parseAsync(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength),'');
 assert.equal(gltf.animations.length,1);const mixer=new THREE.AnimationMixer(gltf.scene),clip=mixer.clipAction(gltf.animations[0]);clip.setLoop(THREE.LoopOnce,1);clip.clampWhenFinished=true;clip.play();
 for(const sample of native.samples){clip.paused=false;clip.time=(sample.frame-1)/24;mixer.update(0);gltf.scene.updateMatrixWorld(true);gltf.scene.traverse(o=>o.skeleton?.update());
  const mesh=gltf.scene.getObjectByName('TimelineSkin0');assert(mesh?.isMesh);const point=new THREE.Vector3(),v=new THREE.Vector3();
  for(let i=0;i<mesh.geometry.attributes.position.count;i++){mesh.getVertexPosition(i,v);point.add(v.applyMatrix4(mesh.matrixWorld));}point.divideScalar(mesh.geometry.attributes.position.count);
  const expected=new THREE.Vector3(sample.skin[0],sample.skin[2],-sample.skin[1]),error=point.distanceTo(expected);assert(error<1e-4,'Native/GLB geometry differs at frame '+sample.frame+': '+error);report.checks.push({frame:sample.frame,error});
 }
 report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error);process.exitCode=1;}
await fs.writeFile(path.join(folder,'GLB-RESULTS.json'),JSON.stringify(report,null,2),{flag:'wx'});console.log(JSON.stringify(report));
