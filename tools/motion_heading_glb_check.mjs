/** Independent whole-frame preview geometry, including the explicit body turn. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import * as THREE from '../launcher/public/vendor/three/build/three.module.js';
import {GLTFLoader} from '../launcher/public/vendor/three/examples/jsm/loaders/GLTFLoader.js';
const [folder]=process.argv.slice(2);assert(path.isAbsolute(folder));
const report={scope:'GENERATED_HEADING_GLB_COMPARISON',checks:[],human_review:'NOT_TESTED',subframe_agreement:'NOT_TESTED'};
try{
 const native=JSON.parse(await fs.readFile(path.join(folder,'RESULTS.json'),'utf8'));assert.equal(native.status,'PASS');assert.equal(native.input_kind,'GENERATED');
 const raw=await fs.readFile(path.join(folder,'heading.glb')),gltf=await new GLTFLoader().parseAsync(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength),'');
 assert.equal(gltf.animations.length,1);const mixer=new THREE.AnimationMixer(gltf.scene),action=mixer.clipAction(gltf.animations[0]);action.setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;action.play();
 const nodeIndex=gltf.parser.json.nodes.findIndex(n=>n.name===native.mesh);assert(nodeIndex>=0,'Observed native mesh node was exported');
 let mesh;gltf.scene.traverse(o=>{if(o.isMesh&&gltf.parser.associations.get(o)?.nodes===nodeIndex)mesh=o;});assert(mesh?.isMesh);
 for(const sample of native.samples){
  action.paused=false;action.time=(sample.frame-1)/native.fps;mixer.update(0);gltf.scene.updateMatrixWorld(true);gltf.scene.traverse(o=>o.skeleton?.update());
  const points=[];
  for(let i=0;i<mesh.geometry.attributes.position.count;i++){const point=new THREE.Vector3();mesh.getVertexPosition(i,point);points.push(point.applyMatrix4(mesh.matrixWorld));}
  const expected=sample.points.map(p=>new THREE.Vector3(p[0],p[2],-p[1]));
  // Export splits vertices at face-normal boundaries. Compare both directions
  // without assuming identical vertex ordering/counts or just a centroid.
  const directed=(a,b)=>Math.max(...a.map(p=>Math.min(...b.map(q=>p.distanceTo(q)))));
  const error=Math.max(directed(points,expected),directed(expected,points));assert(Number.isFinite(error)&&error<1e-4,`Saved turn/GLB differs at frame ${sample.frame}: ${error}`);
  report.checks.push({frame:sample.frame,error,tolerance:1e-4});
 }
 assert(report.checks.some(c=>c.frame>25&&c.frame<38));report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error);process.exitCode=1;}
await fs.writeFile(path.join(folder,'GLB-RESULTS.json'),JSON.stringify(report,null,2),{flag:'wx'});console.log(JSON.stringify(report));
