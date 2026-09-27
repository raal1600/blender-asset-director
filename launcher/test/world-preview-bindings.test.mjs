import test from 'node:test';
import assert from 'node:assert/strict';
import {bindWorldPreview} from '../lib/world-preview-bindings.mjs';
const instance='instance_00000000-0000-4000-8000-000000000001';
const metadata=()=>({placement:{version:'world-transform-v1',instances:[{instance,control:'Whole subject',members:['Native mesh'],matrix:[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]}]},static_objects:[{instance,source:'Native mesh',node:'World preview - Native mesh'}]});
function glb(nodes){let bytes=Buffer.from(JSON.stringify({asset:{version:'2.0'},nodes}));bytes=Buffer.concat([bytes,Buffer.alloc((4-bytes.length%4)%4,32)]);const header=Buffer.alloc(20);header.writeUInt32LE(0x46546c67,0);header.writeUInt32LE(2,4);header.writeUInt32LE(20+bytes.length,8);header.writeUInt32LE(bytes.length,12);header.writeUInt32LE(0x4e4f534a,16);return Buffer.concat([header,bytes]);}
test('World selection uses exact exported node indices tied to observed native members',()=>{
 const record=bindWorldPreview(glb([{name:'World preview - Native mesh',mesh:0},{name:'Unrelated',mesh:1}]),metadata());assert.deepEqual(record.instances[0].nodes,[0]);assert.equal(record.instances[0].instance,instance);assert.equal(bindWorldPreview(glb([]),{}),null);
});
test('ambiguous, absent and cross-instance meshes cannot become editable',()=>{
 const mesh={name:'World preview - Native mesh',mesh:0};for(const nodes of [[],[mesh,mesh],[{name:mesh.name}]])assert.throws(()=>bindWorldPreview(glb(nodes),metadata()),/ambiguous/);
 const changed=metadata();changed.static_objects[0].source='Another instance';assert.throws(()=>bindWorldPreview(glb([mesh]),changed),/different instance/);
 changed.static_objects[0].source='Native mesh';changed.placement.instances.push(changed.placement.instances[0]);assert.throws(()=>bindWorldPreview(glb([mesh]),changed),/identity/);
});
