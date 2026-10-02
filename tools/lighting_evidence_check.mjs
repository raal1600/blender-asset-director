/** Four real CPU preview frames: two cameras before/after a shared look Save. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {randomUUID,createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2),uid=p=>p+randomUUID();
assert([out,generated,python,blender,playwright].every(x=>x&&path.isAbsolute(x))&&!await exists(out));
const fixture=await json(path.join(generated,'RESULTS.json'));assert.equal(fixture.status,'PASS');assert.equal(fixture.scope,'REAL_GENERATED_SCENE_LAYERS');
const member=fixture.outputs.at(-1),source=path.join(generated,member.path),original=await fileHash(source);assert.equal(original.sha256,member.sha256);await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),report={kind:'synthetic-rendered-lighting-browser',checks:[],errors:[],previews:[],previewFramesAuthorized:0,previewFrameBudget:4,human_review:'NOT_TESTED',native_desktop:'NOT_TESTED',scripted_decisions:['Generated World/Action/Shots baselines only; no Light approval']};
let app,browser,page;
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
 let p=await app.store.create('Synthetic rendered lighting','Two exact-camera still comparisons');await app.workbench.create(p.id,p.revision,'Shared light test');p=await app.store.get(p.id);
 const s=p.workbench.scenes[0],cpId=uid('cp_'),relative='Scenes/'+cpId+'.blend';await fs.copyFile(source,path.join(p.directory,relative),fs.constants.COPYFILE_EXCL);
 const prep=await app.runtime.harness(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await app.runtime.harness(['job-run',prep.id,'--blender',blender]));
 s.checkpoints.push({id:cpId,path:relative,...original,stage:'shots',parent:null,audit});s.current=cpId;s.stage='shots';s.completed={world:cpId,action:cpId};p=await app.store.save(p,p.revision);
 const state=async()=>{const r=await fetch(app.origin+'/api/workbench/state?'+new URLSearchParams({projectId:p.id,compact:true}),{headers});assert.equal(r.status,200);return r.json();};
 const post=async(route,body,status=200)=>{const r=await fetch(app.origin+'/api/workbench/'+route,{method:'POST',headers,body:JSON.stringify(body)}),v=await r.json();assert.equal(r.status,status,JSON.stringify(v));return v;};
 const wait=async id=>{const until=Date.now()+205000;while(Date.now()<until){const v=await state(),run=v.runs.find(r=>r.id===id);if(run&&['SUCCEEDED','FAILED','INTERRUPTED'].includes(run.state)&&!v.locked){assert.equal(run.state,'SUCCEEDED',JSON.stringify(run));return {v,run};}await new Promise(r=>setTimeout(r,200));}throw Error('Native operation timed out');};
 for(const [name,camera] of [['Wide','SyntheticWide'],['Close','SyntheticClose']]){const v=await state();await post('shot-save',{projectId:p.id,sceneId:s.id,revision:v.project.revision,shot:{name,camera,start:1,end:9}});}
 let v=await state();await post('approve',{projectId:p.id,sceneId:s.id,revision:v.project.revision,stage:'shots',checkpointId:cpId});v=await state();const shots=v.project.workbench.scenes[0].shots;
 const readyRun=await post('run',{projectId:p.id,sceneId:s.id,revision:v.project.revision,operation:'render-readiness'});const readiness=await wait(readyRun.run.id);assert.deepEqual(readiness.v.project.workbench.scenes[0].readiness.data.blockers,[]);
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});page=await browser.newPage({viewport:{width:1440,height:1000},serviceWorkers:'block'});page.setDefaultTimeout(30000);
 page.on('pageerror',e=>report.errors.push(e.message.replaceAll(app.token,'[REDACTED]')));page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text().replaceAll(app.token,'[REDACTED]'));});page.on('dialog',async dialog=>{await dialog.dismiss();report.errors.push('Unexpected human approval dialog');});
 const idle=()=>page.waitForFunction(()=>!document.body.classList.contains('working'));
 const ready=async()=>{await idle();await page.waitForFunction(()=>document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready'&&!document.querySelector('[data-action="layer-ready"]')?.disabled,null,{timeout:205000});await idle();};
 const click=async action=>{await page.locator('[data-action="'+action+'"]').click();await idle();};
 await page.goto(app.origin+'/workbench#'+app.token);await idle();await page.locator('[data-action="project"][data-id="'+p.id+'"]').click();await ready();
 const evidence=async shotId=>{const r=await fetch(app.origin+'/api/workbench/preview-evidence?'+new URLSearchParams({projectId:p.id,sceneId:s.id,shotId}),{headers});assert.equal(r.status,200);return r.json();};
 assert.equal((await fetch(app.origin+'/api/workbench/preview-evidence?'+new URLSearchParams({projectId:p.id,sceneId:s.id}))).status,401);
 async function preview(shot,phase){
  await page.locator('[data-action="select-shot"][data-id="'+shot.id+'"]').click();await ready();await click('preview');await page.locator('#preview-frame').fill('1');
  assert(report.previewFramesAuthorized<report.previewFrameBudget);report.previewFramesAuthorized++;await click('save-preview');
  await page.waitForFunction(()=>!document.body.classList.contains('working')&&!document.querySelector('[data-action="preview"]')?.disabled,null,{timeout:205000});
  const records=await evidence(shot.id),entry=records.items.find(x=>x.status==='VERIFIED'&&x.current);assert(entry,JSON.stringify(records));assert.equal(entry.frame,1);assert.equal(entry.camera,shot.camera);assert.equal(entry.dependencyStatus,'MATCH');assert.equal(entry.humanReview,'NOT_EVALUATED');
  const response=await fetch(app.origin+'/api/workbench/media?'+new URLSearchParams({projectId:p.id,sceneId:s.id,kind:'preview-evidence',runId:entry.runId}),{headers});assert.equal(response.status,200);const bytes=Buffer.from(await response.arrayBuffer());assert.equal(createHash('sha256').update(bytes).digest('hex'),entry.image.sha256);assert.equal(bytes.readUInt32BE(16),640);assert.equal(bytes.readUInt32BE(20),360);
  await fs.writeFile(path.join(out,phase+'-'+shot.name+'.png'),bytes,{flag:'wx'});report.previews.push({phase,...entry});return entry;
 }
 for(const shot of shots)await preview(shot,'before');
 v=await state();assert.equal(v.project.workbench.scenes[0].current,cpId);assert.equal(v.project.workbench.scenes[0].completed.light,undefined);report.checks.push('Two real explicitly authorized camera/frame stills from one unchanged scene, dependency/native/image identities verified');
 const details=page.locator('.layer-details').filter({hasText:'World brightness and exposure'});await details.locator('summary').click();await page.locator('[data-layer-kind="look"][data-layer-field="exposure"]').fill('1.5');await click('layer-save');await ready();
 v=await state();const changed=v.project.workbench.scenes[0],newCp=changed.checkpoints.find(c=>c.id===changed.current);assert.notEqual(newCp.id,cpId);assert.equal(changed.completed.light,undefined);assert.deepEqual(changed.shots,shots);
 for(const shot of shots){const old=await evidence(shot.id);assert.equal(old.items.filter(x=>x.current).length,0);assert.equal(old.items[0].checkpointId,cpId);await preview(shot,'after');}
 report.checks.push('Explicit shared exposure Save creates a separate unapproved checkpoint and makes both earlier camera stills historical');
 for(const shot of shots){
  const before=report.previews.find(x=>x.phase==='before'&&x.shot.id===shot.id),after=report.previews.find(x=>x.phase==='after'&&x.shot.id===shot.id);assert.notEqual(before.image.sha256,after.image.sha256);assert.equal(after.checkpointId,newCp.id);
  await page.getByRole('button',{name:'Compare rendered stills',exact:true}).click();await idle();await page.locator('#lighting-evidence-shot').selectOption(shot.id);await idle();await page.waitForFunction(()=>{const images=[...document.querySelectorAll('[data-lighting-run]')];return images.length===2&&images.every(n=>n.complete&&n.naturalWidth===640);},null,{timeout:30000});
  assert.match(await page.locator('#dialog').innerText(),/Same shot revision, camera, frame and preview settings/);assert.equal(await page.locator('[data-lighting-run="'+before.runId+'"]').count(),1);assert.equal(await page.locator('[data-lighting-run="'+after.runId+'"]').count(),1);
  const manifest=await fileHash(path.join(p.directory,'project.json'));await page.locator('#dialog').screenshot({path:path.join(out,'compare-'+shot.name+'.png')});assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),manifest);await page.getByRole('button',{name:'Back to Light',exact:true}).click();await idle();
 }
 report.checks.push('Actual before/after PNG pixels differ for both shots; browser loads the exact SHA-verified pairs and labels historical/current evidence without approval');
 await page.getByRole('button',{name:'Compare rendered stills',exact:true}).click();await idle();await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>[...document.querySelectorAll('[data-lighting-run]')].every(n=>n.complete&&n.naturalWidth===640));await page.locator('#dialog').screenshot({path:path.join(out,'comparison-mobile.png')});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.getByRole('button',{name:'Back to Light',exact:true}).click();await idle();
 const old=report.previews[0],oldResponse=await fetch(app.origin+'/api/workbench/media?'+new URLSearchParams({projectId:p.id,sceneId:s.id,kind:'preview-evidence',runId:old.runId}),{headers});assert.equal(oldResponse.status,200);assert.equal(createHash('sha256').update(Buffer.from(await oldResponse.arrayBuffer())).digest('hex'),old.image.sha256);
 assert.equal((await fetch(app.origin+'/api/workbench/media?'+new URLSearchParams({projectId:p.id,sceneId:uid('sc_'),kind:'preview-evidence',runId:old.runId}),{headers})).status,404);
 const foreign=await app.store.create('Other synthetic production','No access to previous receipt');await app.workbench.create(foreign.id,foreign.revision,'Other scene');const q=await app.store.get(foreign.id);assert.notEqual((await fetch(app.origin+'/api/workbench/media?'+new URLSearchParams({projectId:q.id,sceneId:q.workbench.scenes[0].id,kind:'preview-evidence',runId:old.runId}),{headers})).status,200);
 v=await state();await post('enter',{projectId:p.id,sceneId:s.id,revision:v.project.revision,stage:'shots'});v=await state();const first=shots[0];await post('shot-save',{projectId:p.id,sceneId:s.id,revision:v.project.revision,shot:{id:first.id,revision:first.revision,name:first.name,camera:first.camera,start:2,end:9}});
 assert.equal((await evidence(first.id)).items.some(x=>x.current),false);assert.equal((await evidence(shots[1].id)).items.some(x=>x.current),true);report.checks.push('Shot revision invalidates only its current-still status; old image access remains exact, cross-scene/production access refuses');
 assert.deepEqual(await fileHash(source),original);assert.deepEqual(await fileHash(path.join(p.directory,relative)),original);assert.deepEqual(await fileHash(path.join(p.directory,newCp.path)),{sha256:newCp.sha256,size:newCp.size});assert.equal((await state()).project.workbench.scenes[0].completed.light,undefined);assert.deepEqual(report.errors,[]);assert.equal(report.previewFramesAuthorized,4);
 report.checkpoints={before:cpId,after:newCp.id};report.checks.push('Four-frame CPU budget, original/checkpoint preservation, retained images, responsive comparison and no browser errors or Light approval');report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,previewFramesAuthorized:report.previewFramesAuthorized,error:report.error}));}
