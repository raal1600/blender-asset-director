/** Actual authenticated camera/shared-light saves and shot lineage. Synthetic only. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender]=process.argv.slice(2),uid=p=>p+randomUUID();
assert([out,generated,python,blender].every(x=>x&&path.isAbsolute(x))&&!await exists(out));
const fixture=await json(path.join(generated,'RESULTS.json'));assert.equal(fixture.scope,'REAL_GENERATED_SCENE_LAYERS');assert.equal(fixture.status,'PASS');
const member=fixture.outputs.at(-1),source=path.join(generated,member.path),before=await fileHash(source);assert.equal(before.sha256,member.sha256);
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),report={kind:'synthetic-scene-layer-native-http',checks:[],human_review:'NOT_TESTED',browser_controls:'NOT_TESTED',native_desktop:'NOT_TESTED',scripted_decisions:['Synthetic Shots completion only; not human approval']};
let app;
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const prepared=await app.runtime.harness(['job-prepare','scene-audit','--input',source]);const audit=await app.workbench.result(await app.runtime.harness(['job-run',prepared.id,'--blender',blender]));
 let p=await app.store.create('Synthetic Shots and Light','Generated camera/light acceptance only');await app.workbench.create(p.id,p.revision,'One world, two cameras');p=await app.store.get(p.id);
 const s=p.workbench.scenes[0],cpId=uid('cp_'),relative='Scenes/'+cpId+'.blend';await fs.copyFile(source,path.join(p.directory,relative),fs.constants.COPYFILE_EXCL);
 s.checkpoints.push({id:cpId,path:relative,...before,stage:'action',parent:null,audit});s.current=cpId;s.stage='shots';s.completed={world:cpId,action:cpId};p=await app.store.save(p,p.revision);
 const headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
 const state=async()=>{const r=await fetch(app.origin+'/api/workbench/state?'+new URLSearchParams({projectId:p.id,compact:true}),{headers});assert.equal(r.status,200);return r.json();};
 const post=async(route,body,status=200)=>{const r=await fetch(app.origin+'/api/workbench/'+route,{method:'POST',headers,body:JSON.stringify(body)}),v=await r.json();assert.equal(r.status,status,JSON.stringify(v));return v;};
 const wait=async id=>{const until=Date.now()+205000;while(Date.now()<until){const v=await state(),run=v.runs.find(r=>r.id===id);if(run&&['FAILED','INTERRUPTED','SUCCEEDED'].includes(run.state)&&!v.locked){assert.equal(run.state,'SUCCEEDED',JSON.stringify(run));return {state:v,run};}await new Promise(r=>setTimeout(r,150));}throw Error('Layer job timed out');};
 const inspect=async layer=>{const v=await state(),scene=v.project.workbench.scenes[0],cp=scene.checkpoints.find(c=>c.id===scene.current),request={version:'scene-layer-v1',layer,requestId:uid('run_'),checkpointId:cp.id,sha256:cp.sha256};await post('scene-layer-inspect',{projectId:p.id,sceneId:s.id,revision:v.project.revision,request});return {...await wait(request.requestId),request};};
 const saveBody=(inspection,operations)=>({projectId:p.id,sceneId:s.id,revision:inspection.state.project.revision,request:{...inspection.request,requestId:uid('run_'),inspectionId:inspection.request.requestId,audit_sha256:inspection.run.inspection.sha256,operations}});
 for(const route of ['scene-layer-inspect','scene-layer-save'])assert.equal((await fetch(app.origin+'/api/workbench/'+route,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).status,401);
 report.checks.push('Authentication required for camera/light inspection and Save');
 for(const [name,camera] of [['Wide','SyntheticWide'],['Close','SyntheticClose']]){const v=await state();await post('shot-save',{projectId:p.id,sceneId:s.id,revision:v.project.revision,shot:{name,camera,start:1,end:9}});}
 const shots=(await state()).project.workbench.scenes[0].shots;assert.equal(shots.length,2);report.checks.push('Two actual named shot definitions reference observed cameras in the same world');
 const inspection=await inspect('shots');assert.equal(inspection.state.project.workbench.scenes[0].current,cpId);
 const body=saveBody(inspection,[{operation:'camera-plan',options:{mode:'adapt',camera:'SyntheticClose',subjects:['SyntheticSkin0'],lens_mm:70,keyframes:[{frame:1,aim:{subject:'SyntheticSkin0'},direction:[1,-2,1],fit:{margin:.1}}]}}]);
 await post('scene-layer-save',{...body,revision:body.revision-1},409);
 await post('scene-layer-save',{...body,request:{...body.request,audit_sha256:'0'.repeat(64)}},409);
 await post('scene-layer-save',{...body,request:{...body.request,operations:[{operation:'camera-plan',options:{...body.request.operations[0].options,camera:'Foreign camera'}}]}},409);
 await post('scene-layer-save',{...body,request:{...body.request,operations:[{operation:'import',options:{}}]}},400);
 report.checks.push('Stale revision/audit, foreign camera and cross-layer operation refuse before native Save');
 await post('scene-layer-save',body);assert.equal((await post('scene-layer-save',body)).reused,true);
 const saved=await wait(body.request.requestId),scene=saved.state.project.workbench.scenes[0],cameraCp=scene.checkpoints.find(c=>c.id===scene.current);
 assert.notEqual(cameraCp.id,cpId);assert.deepEqual(scene.completed,{world:cpId,action:cpId});assert.deepEqual(scene.shots,shots);assert.equal(scene.stage,'shots');
 assert.deepEqual(saved.run.context.affectedShots,shots.map(({id,revision,name,camera,start,end})=>({id,revision,name,camera,start,end})));
 const again=await inspect('shots');assert.equal(again.run.inspection.cameras.find(c=>c.name==='SyntheticClose').lens_mm,70);report.checks.push('One idempotent native camera Save, independent lens inspection, unchanged shot definitions and unapproved new checkpoint');
 await post('approve',{projectId:p.id,sceneId:s.id,revision:again.state.project.revision,stage:'shots',checkpointId:cameraCp.id});
 const lighting=await inspect('light');const lightBody=saveBody(lighting,[{operation:'light-adjust',options:{lights:[{name:'SyntheticLayerKey',energy:300}]}}]);
 await post('scene-layer-save',lightBody);const lit=await wait(lightBody.request.requestId),litScene=lit.state.project.workbench.scenes[0],lightCp=litScene.checkpoints.find(c=>c.id===litScene.current);
 assert.equal(litScene.completed.light,undefined);assert.equal(litScene.completed.shots,cameraCp.id);assert.equal(litScene.selectedShot,scene.selectedShot);
 assert.deepEqual(lit.run.context.affectedShots.map(s=>s.id),shots.map(s=>s.id));assert.equal(lit.run.context.sharedScene,true);
 const lightingAgain=await inspect('light');assert.equal(lightingAgain.run.inspection.look.state.lights.find(l=>l.name==='SyntheticLayerKey').energy,300);
 assert.deepEqual(lightingAgain.run.inspection.cameras,again.run.inspection.cameras);report.checks.push('Shared lighting Save lists both affected shots, keeps cameras/selected shot and requires new Light review');
 const current=lightingAgain.state;await post('scene-layer-save',{...lightBody,revision:current.project.revision,request:{...lightBody.request,requestId:uid('run_')}},409);
 for(const cp of [cameraCp,lightCp])assert.deepEqual(await fileHash(path.join(p.directory,cp.path)),{sha256:cp.sha256,size:cp.size});
 assert.deepEqual(await fileHash(source),before);assert.deepEqual(await fileHash(path.join(p.directory,relative)),before);
 report.checks.push('Earlier source/checkpoint bytes preserved and stale lighting draft cannot overwrite the new scene');
 report.checkpoints={source:cpId,camera:cameraCp.id,light:lightCp.id};report.shots=shots;report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;}
finally{if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error}));}
