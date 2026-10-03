/** Generated manual Action handoff -> actual Blender -> explicit Save reconciliation.
 * Background operator/data checks do not certify Windows dialogs or visual rig UI.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender]=process.argv.slice(2);
assert([out,generated,python,blender].every(v=>v&&path.isAbsolute(v))&&!await exists(out));
const fixture=await json(path.join(generated,'RESULTS.json'));
assert(fixture.status==='PASS'&&fixture.scope==='REAL_GENERATED_NATIVE_ACTION');
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),source=path.join(generated,'source.blend'),original=await fileHash(source),children=new Map();
const report={scope:'REAL_GENERATED_ACTION_TASK_SAVE_HTTP',checks:[],not_tested:['Native Windows controls/dialogs','Authenticated Codex execution','Human temporal review','Live/private inputs']};
let app,mode,activeProject;
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 app.runtime.launchWorkbenchTask=async(p,manifest)=>{
   const child=spawn(blender,['--background','--factory-startup','--disable-autoexec','--threads','2','--python-exit-code','12','--python',path.join(repo,'tools/action_task_native.py'),'--',manifest,mode],{windowsHide:true});
   const chunks=[];child.stdout.on('data',x=>chunks.push(x));child.stderr.on('data',x=>chunks.push(x));
   const done=new Promise((resolve,reject)=>{child.once('error',reject);child.once('close',async code=>{await fs.writeFile(path.join(p.directory,'Docs/action-task-native.log'),Buffer.concat(chunks));resolve(code);});});
   children.set(child.pid,{child,done});return child.pid;
 };
 app.runtime.inspectWorkbenchTask=async(_p,t)=>({state:children.get(t.processId)?.child.exitCode===null?'verified':'stopped'});
 const headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
 const post=async(route,body,status=200)=>{const r=await fetch(app.origin+'/api/workbench/'+route,{method:'POST',headers,body:JSON.stringify(body)}),v=await r.json();assert.equal(r.status,status,JSON.stringify(v));return v;};
 for(mode of ['no-save','save','saved-then-unsaved']){
   let p=await app.store.create('Synthetic Action handoff '+mode,'Generated separate scene, no creative approval');
   await app.workbench.create(p.id,p.revision,'Action task');p=await app.store.get(p.id);activeProject=p;
   const scene=p.workbench.scenes[0],cp={id:'cp_'+randomUUID(),path:'Scenes/original.blend',...original,parent:null,stage:'world'};
   await fs.copyFile(source,path.join(p.directory,cp.path),fs.constants.COPYFILE_EXCL);scene.checkpoints=[cp];scene.current=cp.id;scene.stage='action';scene.completed={world:cp.id};p=await app.store.save(p,p.revision);
   const request={version:'action-layer-v1',requestId:'run_'+randomUUID(),checkpointId:cp.id,sha256:cp.sha256};
   await post('action-inspect',{projectId:p.id,sceneId:scene.id,revision:p.revision,request});
   const deadline=Date.now()+205000;while(app.workbench.running.size){assert(Date.now()<deadline,'Inspection timeout');await new Promise(r=>setTimeout(r,100));}
   p=await app.store.get(p.id);const inspected=await json(path.join(p.directory,'Runs',request.requestId+'.json'));assert.equal(inspected.state,'SUCCEEDED');
   const actionContext={version:request.version,checkpointId:cp.id,sha256:cp.sha256,inspectionId:request.requestId,audit_sha256:inspected.inspection.sha256,performer:mode==='save'?'SyntheticRig1':'SyntheticRig0',frame:5};
   const body={projectId:p.id,sceneId:scene.id,revision:p.revision,context:{actionContext,rigControls:mode==='save'}};
   const prior=children.size;
   const legacyId='run_'+randomUUID(),legacyFile=path.join(p.directory,'Runs',legacyId+'.json');
   await writeJson(legacyFile,{...inspected,id:legacyId,implementation:undefined,fixture:'SIMULATED_LEGACY_RUNTIME_BINDING'});
   const legacyHash=await fileHash(legacyFile);
   const stale=await post('task-open',{...body,context:{...body.context,actionContext:{...actionContext,inspectionId:legacyId}}},409);
   assert.match(stale.error,/predates this runtime/);assert.deepEqual(await fileHash(legacyFile),legacyHash);
   await post('task-open',{...body,context:{...body.context,actionContext:{...actionContext,audit_sha256:'0'.repeat(64)}}},409);
   await post('task-open',{...body,context:{rigControls:true,actionContext:{...actionContext,performer:'StaticProp'}}},400);
   assert.equal(children.size,prior);assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),false);
   const opened=await post('task-open',body);assert.deepEqual(opened.task.targets,[actionContext.performer]);assert.equal(opened.task.frame,5);
   assert.equal(await children.get(opened.task.processId).done,0,'Actual Action task failed; inspect native log');
   const native=await json(path.join(p.directory,'Docs/action-task-native.json'));assert.equal(native.status,'PASS');
   p=await app.store.get(p.id);const returned=await post('task-sync',{projectId:p.id,sceneId:scene.id,revision:p.revision});
   p=await app.store.get(p.id);const after=p.workbench.scenes[0];assert.equal(after.task,null);assert.equal(after.stage,'action');assert.equal(after.completed.action,undefined);assert.equal(after.candidate,null);
   assert.equal(returned.outcome,mode==='no-save'?'no-save':'saved');
   if(mode==='no-save')assert.equal(after.current,cp.id);
   else{const saved=after.checkpoints.find(c=>c.id===after.current);assert.equal(saved.source,'blender-explicit-save');assert.equal(saved.parent,cp.id);assert.deepEqual(await fileHash(path.join(p.directory,saved.path)),{sha256:saved.sha256,size:saved.size});}
   assert.deepEqual(await fileHash(path.join(p.directory,cp.path)),original);
   report.checks.push({mode,status:'PASS',native,checkpoint:after.current,oldCheckpoint:cp.id});
 }
 assert.deepEqual(await fileHash(source),original);report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;}
finally{
 if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}
 if(report.status==='FAIL'&&activeProject)report.native=await fs.readFile(path.join(activeProject.directory,'Docs/action-task-native.log'),'utf8').catch(()=>null);
 await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error,native:report.native?.slice(-4000)}));
}
