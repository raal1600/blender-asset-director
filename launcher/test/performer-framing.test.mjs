import test from 'node:test';
import assert from 'node:assert/strict';
import {performerMeshes} from '../public/performer-framing.mjs';

test('camera focus follows exact exported rig ownership and excludes the floor and other actors',()=>{
 const rig={},bone={isBone:true,parent:rig},otherBone={isBone:true},skin={isSkinnedMesh:true,skeleton:{bones:[bone]}},otherSkin={isSkinnedMesh:true,skeleton:{bones:[otherBone]}},floor={isMesh:true};
 const objects=[rig,bone,skin,otherBone,otherSkin,floor];
 const gltf={scene:{traverse:fn=>objects.forEach(fn)},parser:{json:{nodes:[{name:'Reviewed rig'}]},associations:new Map([[rig,{nodes:0}]])}};
 assert.deepEqual(performerMeshes(gltf,'Reviewed rig'),[skin]);
 assert.deepEqual(performerMeshes(gltf,'Renamed or missing rig'),[]);
 gltf.parser.json.nodes.push({name:'Reviewed rig'});assert.deepEqual(performerMeshes(gltf,'Reviewed rig'),[]);
 gltf.parser.json.nodes.pop();skin.skeleton.bones.push(otherBone);assert.deepEqual(performerMeshes(gltf,'Reviewed rig'),[]);
});
