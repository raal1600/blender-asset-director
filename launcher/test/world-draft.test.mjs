import test from 'node:test';
import assert from 'node:assert/strict';
import {worldDraft,worldActionNeedsSave,placementMatrix,instanceObjects} from '../public/world-draft.mjs';
const identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
const id=n=>'instance_00000000-0000-4000-8000-'+String(n).padStart(12,'0');
const matrix=x=>identity.map((v,i)=>i===3?x:v);
const make=(n=2)=>worldDraft({checkpointId:'cp_00000000-0000-4000-8000-000000000001',sha256:'a'.repeat(64),instances:Array.from({length:n},(_,i)=>({instance:id(i),matrix:identity}))});
test('GLTF default materials without source associations are not editable nodes',()=>{
 const object={isObject3D:true},associations=new Map([[{},undefined],[object,{nodes:4}]]);
 assert.deepEqual(instanceObjects(associations,4),[object]);assert.throws(()=>instanceObjects(associations,8),/unambiguously/);
 associations.set({isObject3D:true},{nodes:4});assert.throws(()=>instanceObjects(associations,4),/unambiguously/);
});
test('placement draft is local, coalesces drag into one undo, and binds the original hash/matrices',()=>{
 const d=make();d.begin();d.preview([{instance:id(0),matrix:matrix(1)}]);d.preview([{instance:id(0),matrix:matrix(2)}]);
 assert.throws(()=>d.request('run_test'),/gesture/);d.commit();assert.equal(d.state().count,1);
 const request=d.request('run_test');assert.equal(request.sha256,'a'.repeat(64));assert.deepEqual(request.transforms[0].expected_matrix,identity);assert.deepEqual(request.transforms[0].matrix,matrix(2));
 request.transforms[0].matrix[3]=999;assert.equal(d.get(id(0))[3],2);d.undo();assert.equal(d.state().dirty,false);assert.equal(d.state().canUndo,false);
});
test('multi-instance edits validate the entire batch and cancel/discard preserve baseline',()=>{
 const d=make();d.apply([{instance:id(0),matrix:matrix(2)},{instance:id(1),matrix:matrix(5)}]);assert.equal(d.state().count,2);
 assert.throws(()=>d.apply([{instance:id(0),matrix:matrix(20)},{instance:id(99),matrix:matrix(2)}]),/Unknown/);assert.equal(d.get(id(0))[3],2);
 d.begin();d.preview([{instance:id(1),matrix:matrix(9)}]);d.cancel();assert.equal(d.get(id(1))[3],5);d.discard();assert.equal(d.state().dirty,false);assert.equal(d.state().canUndo,false);assert.throws(()=>d.request('run_test'),/No placement/);
});
test('draft refuses unsupported transforms and limits a save to 64 instances',()=>{
 for(const edit of [m=>m[0]=-1,m=>m[0]=2,m=>m[1]=.2,m=>m[3]=Infinity,m=>m[3]=1e7,m=>m[15]=0]){const m=identity.slice();edit(m);assert.throws(()=>placementMatrix(m));}
 const d=make(65);d.apply(Array.from({length:64},(_,i)=>({instance:id(i),matrix:matrix(1)})));assert.throws(()=>d.apply([{instance:id(64),matrix:matrix(1)}]),/64/);assert.equal(d.state().count,64);
});
test('navigation and unknown mutations require resolving a dirty draft, inspections do not',()=>{
 for(const name of ['task','approve','library-add','stage','scene','picker','tab','scene-viewer','save-production','save-scene','unknown-future-mutation'])assert.equal(worldActionNeedsSave(name),true,name);
 for(const name of ['save-world','world-undo','refresh','catalog-detail','viewer-open','history','close','retry','resolve'])assert.equal(worldActionNeedsSave(name),false,name);
});
