import test from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {validateSceneLayerRequest} from '../lib/scene-layer.mjs';
const uid=p=>p+randomUUID();
const base=()=>({version:'scene-layer-v1',layer:'shots',requestId:uid('run_'),checkpointId:uid('cp_'),sha256:'a'.repeat(64)});
const request=()=>({...base(),inspectionId:uid('run_'),audit_sha256:'b'.repeat(64),operations:[{operation:'camera-fit',name:'Wide',options:{subjects:['Observed mesh'],frames:[1],direction:[1,-1,1],lens_mm:50}}]});
test('camera/light transport separates inspection, layer operations and exact identities',()=>{
 validateSceneLayerRequest(base(),true);validateSceneLayerRequest(request());
 for(const patch of [{version:'other'},{layer:'world'},{layer:['shots']},{script:'no'},{inspectionId:'guessed'},{sha256:'bad'}])assert.throws(()=>validateSceneLayerRequest({...request(),...patch}));
 assert.throws(()=>validateSceneLayerRequest(request(),true));
});
test('camera/light endpoint is bounded, not a generic operation executor',()=>{
 for(const operations of [[],request().operations.concat(request().operations),[{operation:'import',options:{}}],[{operation:'camera-fit',name:'Wide',options:{},script:'no'}]])assert.throws(()=>validateSceneLayerRequest({...request(),operations}));
 assert.throws(()=>validateSceneLayerRequest({...request(),layer:'light'}));
 validateSceneLayerRequest({...request(),layer:'light',operations:[{operation:'light-adjust',options:{lights:[{name:'Key',energy:200}]}}]});
});
test('camera plan endpoint preserves Action timing and retained camera motion',()=>{
 for(const options of [{fps:60},{frame_range:[1,48]},{existing_animation:'clear'}])assert.throws(()=>validateSceneLayerRequest({...request(),operations:[{operation:'camera-plan',options}]}));
});
