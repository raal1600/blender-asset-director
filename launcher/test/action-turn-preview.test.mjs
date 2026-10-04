import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../public/vendor/three/build/three.module.js';
import {createTurnPreview,savedHeadingAt} from '../public/action-turn-preview.mjs';

const close=(actual,expected,tolerance=1e-6)=>assert(actual.distanceTo(expected)<tolerance,`${actual.toArray()} != ${expected.toArray()}`);
const performer=name=>({name,type:'ARMATURE',takes:[{heading_blocker:null}],unsupported:null,timeline:{error:null}});
function fixture({external=false}={}){
 const scene=new THREE.Group(),parent=new THREE.Group(),rig=new THREE.Group(),bone=new THREE.Bone(),other=new THREE.Group(),otherBone=new THREE.Bone();
 scene.add(parent,other);parent.add(rig);rig.add(bone);other.add(otherBone);parent.position.set(2,3,4);parent.rotation.set(.3,.4,.2);parent.scale.setScalar(2);rig.position.set(1,.5,-1);rig.rotation.set(.2,.6,-.4);other.position.set(8,0,1);
 const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute([1,0,0,0,1,0,0,0,1],3));geometry.setAttribute('skinIndex',new THREE.Uint16BufferAttribute([0,0,0,0,0,0,0,0,0,0,0,0],4));geometry.setAttribute('skinWeight',new THREE.Float32BufferAttribute([1,0,0,0,1,0,0,0,1,0,0,0],4));
 const skin=new THREE.SkinnedMesh(geometry,new THREE.MeshBasicMaterial());(external?scene:rig).add(skin);scene.updateMatrixWorld(true);skin.bind(new THREE.Skeleton([bone]));
 const floor=new THREE.Mesh(new THREE.BoxGeometry(),new THREE.MeshBasicMaterial());floor.position.set(-4,0,7);scene.add(floor);
 const json={nodes:[{name:'Native Rig.001'},{name:'Native Joint'},{name:'Other Rig'},{name:'Other Joint'},{name:'Body'},{name:'Ground'}]};
 const associations=new Map([[rig,{nodes:0}],[bone,{nodes:1}],[other,{nodes:2}],[otherBone,{nodes:3}],[skin,{nodes:4}],[floor,{nodes:5}]]);
 rig.name='Native_Rig001';other.name='Other_Rig';
 const gltf={scene,parser:{json,associations}},selected=performer('Native Rig.001'),performers=[selected,performer('Other Rig')];
 const view=createTurnPreview({THREE,gltf,performer:selected,performers});
 return {scene,parent,rig,bone,other,otherBone,skin,floor,gltf,selected,performers,view};
}
function vertices(f){f.scene.updateMatrixWorld(true);f.skin.skeleton.update();return [0,1,2].map(i=>f.skin.getVertexPosition(i,new THREE.Vector3()).applyMatrix4(f.skin.matrixWorld));}

test('exact glTF associations locate sanitized native name; only selected character rotates',()=>{
 const f=fixture(),v=f.view;assert(v.available,v.reason);assert.equal(v.rig,f.rig);assert.equal(v.roots.length,1);
 const before=vertices(f),pivot=v.pivot(),other=f.other.matrixWorld.clone(),floor=f.floor.matrixWorld.clone(),local=f.rig.matrix.clone();
 assert(v.apply(90));const q=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),Math.PI/2);
 vertices(f).forEach((p,i)=>close(p,before[i].clone().sub(pivot).applyQuaternion(q).add(pivot)));
 assert.deepEqual(f.other.matrixWorld.elements,other.elements);assert.deepEqual(f.floor.matrixWorld.elements,floor.elements);
 v.restore();assert.deepEqual(f.rig.matrix.elements,local.elements);vertices(f).forEach((p,i)=>close(p,before[i]));
});
test('external skin whose bones belong entirely to rig receives one world rotation',()=>{
 const f=fixture({external:true});assert(f.view.available,f.view.reason);assert.equal(f.view.roots.length,2);
 const before=vertices(f),pivot=f.view.pivot(),q=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),-.7);
 assert(f.view.apply(-.7*180/Math.PI));vertices(f).forEach((p,i)=>close(p,before[i].clone().sub(pivot).applyQuaternion(q).add(pivot)));
 f.view.restore();vertices(f).forEach((p,i)=>close(p,before[i]));
});
test('static skin-part audit entries do not falsely become independent performers',()=>{
 const f=fixture({external:true});f.performers.push({name:'Body',type:'MESH',takes:[]});
 const view=createTurnPreview({THREE,gltf:f.gltf,performer:f.selected,performers:f.performers});assert(view.available,view.reason);assert.equal(view.roots.length,2);
});
test('repeated target changes are non-accumulating and restore before mixer update',()=>{
 const f=fixture(),before=vertices(f),pivot=f.view.pivot(),q=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),Math.PI/4);
 assert(f.view.apply(80));assert(f.view.apply(45));vertices(f).forEach((p,i)=>close(p,before[i].clone().sub(pivot).applyQuaternion(q).add(pivot)));
 f.view.restore();const animation=new THREE.AnimationClip('move',1,[new THREE.VectorKeyframeTrack(f.rig.uuid+'.position',[0,1],[1,.5,-1,3,.5,-1])]),mixer=new THREE.AnimationMixer(f.scene),action=mixer.clipAction(animation);action.play();mixer.setTime(.5);
 assert.equal(f.rig.position.x,2);const saved=f.rig.position.clone();assert(f.view.apply(20));f.view.restore();assert.deepEqual(f.rig.position.toArray(),saved.toArray());
});
test('duplicate raw names or shared node associations are refused without transforms',()=>{
 for(const change of [f=>f.gltf.parser.json.nodes.push({name:f.selected.name}),f=>f.gltf.parser.associations.set(f.floor,{nodes:0})]){
  const f=fixture(),before=f.rig.matrix.clone();change(f);const v=createTurnPreview({THREE,gltf:f.gltf,performer:f.selected,performers:f.performers});assert(!v.available);assert.deepEqual(f.rig.matrix.elements,before.elements);
 }
});
test('mixed performer skin, detached skin and nested other performer are refused',()=>{
 for(const change of [f=>f.skin.skeleton=new THREE.Skeleton([f.bone,f.otherBone]),f=>f.skin.bindMode='detached',f=>f.rig.add(f.other),f=>f.other.add(f.rig),f=>f.other.add(f.skin)]){
  const f=fixture();change(f);const v=createTurnPreview({THREE,gltf:f.gltf,performer:f.selected,performers:f.performers});assert(!v.available,v.reason);
 }
});
test('missing legacy mapping, unknown heading and nonuniform parents fail closed',()=>{
 for(const change of [f=>delete f.gltf.parser,f=>f.selected.takes[0].heading_blocker='Review native rotation',f=>f.parent.scale.set(1,2,3),f=>f.parent.scale.set(-1,-1,-1)]){
  const f=fixture();change(f);const v=createTurnPreview({THREE,gltf:f.gltf,performer:f.selected,performers:f.performers});assert(!v.available);
 }
});
test('changed skin ownership refuses apply and restores the previous target',()=>{
 const f=fixture(),original=f.rig.quaternion.clone();assert(f.view.apply(60));f.skin.skeleton.bones[0]=f.otherBone;assert.equal(f.view.apply(80),false);assert.deepEqual(f.rig.quaternion.toArray(),original.toArray());
});
test('bone or second-performer reparenting invalidates isolated ownership',()=>{
 for(const change of [f=>f.other.add(f.bone),f=>f.rig.add(f.other)]){
  const f=fixture();change(f);assert.equal(f.view.apply(20),false);
 }
});
const timeline={managed:true,clips:[{id:'a',start:1,frames:25,heading_deg:20},{id:'b',start:38,frames:25,heading_deg:110,transition:{mode:'turn'}}],connections:[{clip_id:'b',start:25,end:38,duration_frames:13,heading_in_deg:20,heading_out_deg:110,turn_delta_deg:90,mode:'turn'}]};
test('saved heading reads native zero, constant clip headings and held endpoints',()=>{
 assert.equal(savedHeadingAt({managed:false,clips:[]},1),0);assert.equal(savedHeadingAt(timeline,-3),20);assert.equal(savedHeadingAt(timeline,20),20);assert.equal(savedHeadingAt(timeline,38),110);assert.equal(savedHeadingAt(timeline,400),110);
 const legacy={managed:true,clips:[{start:1,frames:25},{start:38,frames:25,transition:{frames:12}}]};assert.equal(savedHeadingAt(legacy,30),0);
});
test('saved turn matches brake/turn/accelerate easing at integer native samples',()=>{
 assert.equal(savedHeadingAt(timeline,28),20);assert.equal(savedHeadingAt(timeline,35),110);
 const u=((31-25)/13-.25)*2,e=u*u*u*(10+u*(-15+6*u));assert(Math.abs(savedHeadingAt(timeline,31)-(20+90*e))<1e-10);
});
test('unknown saved basis, ambiguous joins and subframes do not guess a baseline',()=>{
 assert.equal(savedHeadingAt({managed:true,clips:[]},1),null);assert.equal(savedHeadingAt(timeline,31.5),null);
 assert.equal(savedHeadingAt({...timeline,connections:[]},30),null);assert.equal(savedHeadingAt({...timeline,connections:[...timeline.connections,...timeline.connections]},30),null);
 assert.equal(savedHeadingAt({...timeline,error:'stale'},1),null);
});
