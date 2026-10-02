import test from 'node:test';
import assert from 'node:assert/strict';
import {selectedShotPreview,validateShotCamera} from '../lib/shot-preview.mjs';
import {previewProfile,validateActionPlayback} from '../lib/embedded-preview.mjs';
import {shotFrame,shotViewport} from '../public/shot-view.mjs';
import {viewerTaskFrame} from '../public/workbench-shots.mjs';
const shot={id:'shot_test',revision:1,name:'Wide',camera:'ObservedCamera',start:3,end:5};
const scene={stage:'shots',shots:[shot],selectedShot:shot.id},cp={id:'cp_test',audit:{objects:[{name:shot.camera,type:'CAMERA'}],frame_range:[1,9]}};
test('profile and saved shot identity are derived from scene state, never an asset request',()=>{
 const expected={version:'shot-view-v1',...shot};assert.deepEqual(selectedShotPreview(scene,cp),expected);
 assert.equal(selectedShotPreview({...scene,stage:'world'},cp),null);
 assert.equal(selectedShotPreview({...scene,selectedShot:null},cp),null);
 assert.throws(()=>selectedShotPreview({...scene,selectedShot:'foreign'},cp));
 assert.throws(()=>selectedShotPreview(scene,{...cp,audit:{...cp.audit,frame_range:[1,4]}}));
 assert.equal(previewProfile('shots','checkpoint',expected),'shot-framing-v1');
 assert.equal(previewProfile('light','checkpoint',expected),'look-inspection-v1');
 assert.equal(previewProfile('light','catalog',expected),'inspection-v1');
});
test('camera samples bind camera, exact shot revision, actual timebase and ordered frames',()=>{
 const expected={version:'shot-view-v1',...shot},playback={fps:24,start:1,end:9};
 const view={version:'shot-camera-samples-v1',shot:expected,fps:24,aspect:16/9,sampling:'INTEGER_FRAMES',lighting:'INSPECTION_APPROXIMATION',depth_of_field:'NOT_SIMULATED',human_acceptance:'NOT_EVALUATED',samples:[3,4,5].map(frame=>({frame,projection:'PERSP',matrix_world:Array(16).fill(0),projection_matrix:Array(16).fill(0)}))};
 validateShotCamera(view,expected,playback);
 for(const patch of [{shot:{...expected,revision:2}},{fps:30},{aspect:NaN},{samples:view.samples.slice(1)},{human_acceptance:'APPROVED'}])assert.throws(()=>validateShotCamera({...view,...patch},expected,playback));
 assert.throws(()=>validateShotCamera({...view,samples:view.samples.map(v=>({...v,projection:'PANO'}))},expected,playback));
 const still={version:'scene-playback-v1',scope:'SAVED_SCENE',start:1,end:9,duration:8/24,fps:24,static:true,clip:null,static_evidence:'NO_EVALUATED_GEOMETRY_MOTION_SOURCES'};
 validateActionPlayback(still,{animations:[]},true);assert.throws(()=>validateActionPlayback(still,{animations:[]}));
});
test('shot scrub stays in range and viewport preserves saved pixel aspect',()=>{
 const view={shot,fps:24};assert.equal(shotFrame(view,-1),3);assert.equal(shotFrame(view,1/24),4);assert.equal(shotFrame(view,100),5);
 for(const [w,h] of [[800,600],[390,400],[1920,1080]]){const v=shotViewport(w,h,16/9);assert(Math.abs(v.width/v.height-16/9)<1e-9);assert(v.width<=w&&v.height<=h&&v.x>=0&&v.y>=0);}
});
test('manual camera/light handoff uses the exact inspected frame without leaking World playback',()=>{
 for(const stage of ['shots','light','render'])assert.deepEqual(viewerTaskFrame({...scene,stage},4),{frame:4});
 assert.deepEqual(viewerTaskFrame({...scene,stage:'action'},2),{frame:2});
 assert.deepEqual(viewerTaskFrame({...scene,stage:'world'},4),{});
 assert.deepEqual(viewerTaskFrame({...scene,selectedShot:null},4),{});
 assert.deepEqual(viewerTaskFrame(scene,null),{});assert.throws(()=>viewerTaskFrame(scene,6));
});
