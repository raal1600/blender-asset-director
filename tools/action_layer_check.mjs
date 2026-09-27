/** Real authenticated HTTP -> native Blender -> new checkpoint. Synthetic only. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender]=process.argv.slice(2);
assert([out,generated,python,blender].every(x=>x&&path.isAbsolute(x)),'Absolute generated fixture and installed tools required');
assert(!await exists(out),'Use new evidence storage');
assert.equal((await json(path.join(generated,'RESULTS.json'))).scope,'REAL_GENERATED_NATIVE_ACTION');
assert.equal((await json(path.join(generated,'RESULTS.json'))).status,'PASS');
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),source=path.join(generated,'source.blend'),before=await fileHash(source);
const report={kind:'synthetic-action-native-http',checks:[],not_tested:['Browser controls','Native GUI','Human temporal/creative approval','Private licensed inputs']};
let app;
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const native=await app.runtime.harness(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await app.runtime.harness(['job-run',native.id,'--blender',blender]));
 let p=await app.store.create('Synthetic Action protocol','Generated multi-performer native fixture; no human approval');
 await app.workbench.create(p.id,p.revision,'Motion controls');p=await app.store.get(p.id);
 const s=p.workbench.scenes[0],cpId='cp_'+randomUUID(),relative='Scenes/'+cpId+'.blend';
 await fs.copyFile(source,path.join(p.directory,relative),fs.constants.COPYFILE_EXCL);
 s.checkpoints.push({id:cpId,path:relative,...before,stage:'world',parent:null,source:'synthetic-action-fixture',audit});s.current=cpId;s.stage='action';s.completed={world:cpId};p=await app.store.save(p,p.revision);
 const headers={'Authorization':'Bearer '+app.token,'Content-Type':'application/json'};
 const state=async()=>{const r=await fetch(app.origin+'/api/workbench/state?'+new URLSearchParams({projectId:p.id,compact:true}),{headers});assert.equal(r.status,200);return r.json();};
 const post=async(route,body,status=200)=>{const r=await fetch(app.origin+'/api/workbench/'+route,{method:'POST',headers,body:JSON.stringify(body)}),v=await r.json();assert.equal(r.status,status,JSON.stringify(v));return v;};
 const wait=async runId=>{const deadline=Date.now()+205000;while(Date.now()<deadline){const v=await state(),run=v.runs.find(r=>r.id===runId);if(run&&['FAILED','INTERRUPTED','SUCCEEDED'].includes(run.state)&&!v.locked){assert.equal(run.state,'SUCCEEDED',JSON.stringify(run));return {snapshot:v,run};}await new Promise(r=>setTimeout(r,150));}throw Error('Native Action operation timed out');};
 const unauth=await fetch(app.origin+'/api/workbench/action-inspect',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});assert.equal(unauth.status,401);report.checks.push('Unauthorized caller cannot inspect or execute');
 const base={version:'action-layer-v1',requestId:'run_'+randomUUID(),checkpointId:cpId,sha256:before.sha256};
 await post('action-inspect',{projectId:p.id,sceneId:s.id,revision:p.revision,request:base});
 const inspected=await wait(base.requestId);assert.equal(inspected.snapshot.project.workbench.scenes[0].current,cpId);assert.equal(inspected.snapshot.project.workbench.scenes[0].checkpoints.length,1);
 const performers=inspected.run.inspection.performers;assert(performers.find(x=>x.name==='SyntheticRig0').takes.length===2);report.checks.push('Read-only native inspection returns real performer-owned take IDs');
 const request={...base,requestId:'run_'+randomUUID(),inspectionId:base.requestId,audit_sha256:inspected.run.inspection.sha256,frame_range:[1,12],changes:[{performer:'SyntheticRig0',mode:'clip',take_id:performers.find(x=>x.name==='SyntheticRig0').takes[0].id,start:3,speed:2}]};
 const body={projectId:p.id,sceneId:s.id,revision:inspected.snapshot.project.revision,request};
 await post('action-save',{...body,request:{...request,audit_sha256:'0'.repeat(64)}},409);
 await post('action-save',{...body,request:{...request,changes:[{...request.changes[0],performer:'SyntheticRig1'}]}},409);
 await post('action-save',{...body,revision:body.revision-1},409);report.checks.push('Stale revision/audit and foreign performer take refused before execution');
 await post('action-save',body);const replay=await post('action-save',body);assert.equal(replay.reused,true);
 const saved=await wait(request.requestId),savedScene=saved.snapshot.project.workbench.scenes[0],cp=savedScene.checkpoints.find(c=>c.id===savedScene.current);
 assert.equal(cp.id,saved.run.resultCheckpointId);assert.equal(cp.parent,cpId);assert.deepEqual(savedScene.completed,{world:cpId});assert.equal(savedScene.stage,'action');assert.deepEqual(await fileHash(path.join(p.directory,cp.path)),{sha256:cp.sha256,size:cp.size});
 report.checks.push('One idempotent native Save publishes a hashed unapproved checkpoint and preserves World review');
 await post('action-save',{...body,revision:saved.snapshot.project.revision,request:{...request,requestId:'run_'+randomUUID()}},409);report.checks.push('Previous inspection cannot save over the new checkpoint');
 const next={...base,requestId:'run_'+randomUUID(),checkpointId:cp.id,sha256:cp.sha256};
 await post('action-inspect',{projectId:p.id,sceneId:s.id,revision:saved.snapshot.project.revision,request:next});
 const second=await wait(next.requestId),observed=second.run.inspection.performers.find(x=>x.name==='SyntheticRig0');
 assert(!observed.active);const strip=observed.tracks.find(t=>!t.mute).strips[0];assert.equal(strip.start,3);assert.equal(strip.end,7);assert.equal(strip.scale,.5);report.checks.push('Independent native reinspection confirms saved timing, not just echoed parameters');
 const held={...next,requestId:'run_'+randomUUID(),inspectionId:next.requestId,audit_sha256:second.run.inspection.sha256,changes:[{performer:'SyntheticRig0',mode:'hold',frame:5}]};
 await post('action-save',{projectId:p.id,sceneId:s.id,revision:second.snapshot.project.revision,request:held});const holdResult=await wait(held.requestId);assert.notEqual(holdResult.run.resultCheckpointId,cp.id);report.checks.push('Static Action creates a separate verified checkpoint and retains prior motion result');
 assert.deepEqual(await fileHash(source),before);assert.deepEqual(await fileHash(path.join(p.directory,relative)),before);assert.deepEqual(await fileHash(path.join(p.directory,cp.path)),{sha256:cp.sha256,size:cp.size});report.checks.push('Original source, prior checkpoint and prior motion output preserved byte-for-byte');
 report.status='PASS';report.projectId=p.id;report.sceneId=s.id;report.initialCheckpoint=cpId;report.motionCheckpoint=cp.id;report.holdCheckpoint=holdResult.run.resultCheckpointId;report.movie='NOT_TESTED';
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;}
finally{
 try{if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}}
 catch(error){report.status='FAIL';report.cleanupError=String(error);process.exitCode=1;}
 await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error,cleanupError:report.cleanupError}));
}
