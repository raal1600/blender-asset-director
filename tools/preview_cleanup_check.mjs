/** Real synthetic native conversion, two browser viewers, reviewed cleanup and rebuild. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {spawn} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,walk,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,generated,python,blender,playwright].every(x=>x&&path.isAbsolute(x))&&!await exists(out));
assert.equal((await json(path.join(generated,'world_layers_report.json'))).status,'PASS');
const source=path.join(generated,'placed.blend'),before=await fileHash(source),repo=fileURLToPath(new URL('../',import.meta.url));
await fs.mkdir(out,{recursive:true});
const report={kind:'REAL_SYNTHETIC_PREVIEW_CLEANUP',checks:[],reviews:[],releases:[],native_conversions:0,human_review:'NOT_TESTED',decisions:'Scripted synthetic decline and confirmation only'};
let app,browser,page,other;
const errors=[],config={python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')};
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config});
 const original=app.runtime.harness.bind(app.runtime);
 app.runtime.harness=async(...args)=>{if(args[0][0]==='workbench-preview')report.native_conversions++;return original(...args);};
 let p=await app.store.create('Synthetic preview cleanup');await app.workbench.create(p.id,p.revision,'Static world');p=await app.store.get(p.id);
 const scene=p.workbench.scenes[0],cp='cp_'+randomUUID(),relative='Scenes/'+cp+'.blend';await fs.copyFile(source,path.join(p.directory,relative),fs.constants.COPYFILE_EXCL);
 const job=await app.runtime.harness(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await app.runtime.harness(['job-run',job.id,'--blender',blender]));
 scene.checkpoints.push({id:cp,path:relative,...before,stage:'world',parent:null,audit});scene.current=cp;p=await app.store.save(p,p.revision);
 const manifest=await fileHash(path.join(p.directory,'project.json'));
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});
 const ready=async target=>{
  await target.waitForFunction(()=>['ready','failed'].includes(document.querySelector('[data-scene-viewer]')?.dataset.viewerState),null,{timeout:205000});
  assert.equal(await target.locator('[data-scene-viewer]').getAttribute('data-viewer-state'),'ready',await target.locator('[data-scene-viewer]').innerText());
  assert.equal(await target.locator('[data-scene-viewer] canvas').count(),1);
  return target.locator('[data-scene-viewer]').getAttribute('data-preview-id');
 };
 const open=async()=>{
  const target=await browser.newPage({viewport:{width:1440,height:1000},serviceWorkers:'block'});target.setDefaultTimeout(30000);
  target.on('pageerror',error=>errors.push(error.message.replaceAll(app.token,'[REDACTED]')));
  await target.route('**/*',route=>new URL(route.request().url()).origin===app.origin?route.continue():route.abort());
  await target.goto(app.origin+'/workbench#'+app.token);await target.waitForFunction(()=>!document.body.classList.contains('working'));
  await target.locator('[data-action=project][data-id='+p.id+']').click();await ready(target);return target;
 };
 const plan=async()=>{
  await page.getByRole('button',{name:'Studio',exact:true}).click();
  const pending=page.waitForResponse(r=>r.url().endsWith('/api/viewer-cache/plan')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Preview storage',exact:true}).click();const response=await pending;assert.equal(response.status(),200);
  const result=await response.json();report.reviews.push(result);await page.locator('#dialog [data-action=preview-storage-apply]').waitFor();return result;
 };
 const leave=async target=>{
  const pending=target.waitForResponse(r=>r.url().endsWith('/api/workbench/viewer-release'));
  await target.getByRole('button',{name:'Final film',exact:true}).click();const response=await pending;assert.equal(response.status(),200);report.releases.push({status:response.status(),viewerId:response.request().postDataJSON().viewerId});
 };
 const keep=()=>page.getByRole('button',{name:'Keep everything',exact:true}).click();
 page=await open();const previewId=await ready(page);other=await open();assert.equal(await ready(other),previewId);assert.equal(report.native_conversions,1);
 let review=await plan();assert.equal(review.eligible.length,0);assert(review.protected.some(x=>x.previewId===previewId&&/Active/.test(x.reason)));
 assert(await page.locator('[data-action=preview-storage-apply]').isDisabled());await keep();
 await leave(page);review=await plan();assert.equal(review.eligible.length,0);await keep();
 report.checks.push('Two actual WebGL views share one Blender conversion; closing one does not allow cleanup of the other');
 await leave(other);review=await plan();assert.equal(review.eligible.length,1,JSON.stringify({protected:review.protected,releases:report.releases}));assert.equal(review.eligible[0].previewId,previewId);assert(review.eligible[0].files.includes('PREVIEW_COPY.blend'));
 await page.screenshot({path:path.join(out,'cleanup-review.png'),fullPage:true});
 const base=path.join(out,'Studio/SystemRuntime/UserData/ViewerPreviews'),directory=path.join(base,previewId),members=await walk(directory,10000);
 const identities=Object.fromEntries(await Promise.all(members.map(async name=>[name,await fileHash(path.join(directory,name))])));
 const unauthed=await fetch(app.origin+'/api/viewer-cache/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...review,confirmed:true,closedNativePreviews:true})});assert.equal(unauthed.status,401);
 let applyRequests=0;page.on('request',r=>{if(r.url().endsWith('/api/viewer-cache/apply'))applyRequests++;});
 page.once('dialog',d=>d.dismiss());await page.locator('[data-action=preview-storage-apply]').click();
 await page.waitForFunction(()=>!document.body.classList.contains('working'));assert.equal(applyRequests,0);
 for(const [name,identity] of Object.entries(identities))assert.deepEqual(await fileHash(path.join(directory,name)),identity);
 report.checks.push('Unauthenticated removal refuses; scripted decline sends no cleanup request and preserves every byte');
 // A known generated preview opened by a real, short-lived Blender process.
 const releaseFile=path.join(out,'native-probe-release');
 const probe=['import time','from pathlib import Path','release=Path('+JSON.stringify(releaseFile)+')','deadline=time.monotonic()+60',"print('CLEANUP_PROBE_READY', flush=True)",'while not release.exists() and time.monotonic()<deadline: time.sleep(.05)',"assert release.exists(), 'Owned preview guard test timed out'"].join(String.fromCharCode(10));
 const child=spawn(blender,['--background','--factory-startup','--disable-autoexec','--threads','2',path.join(directory,'PREVIEW_COPY.blend'),'--python-expr',probe],{windowsHide:true});
 const chunks=[];let mark;
 const started=new Promise((resolve,reject)=>{mark=resolve;child.once('error',reject);child.once('close',()=>reject(Error('Native preview probe closed before its marker')));});
 child.stdout.on('data',data=>{chunks.push(data);if(Buffer.concat(chunks).toString().includes('CLEANUP_PROBE_READY'))mark();});child.stderr.on('data',data=>chunks.push(data));
 const finished=new Promise((resolve,reject)=>{child.once('error',reject);child.once('close',code=>resolve(code));});
 await started;
 let refused;
 try{
  refused=await fetch(app.origin+'/api/viewer-cache/apply',{method:'POST',headers:{Authorization:'Bearer '+app.token,'Content-Type':'application/json'},body:JSON.stringify({id:review.id,digest:review.digest,confirmed:true,closedNativePreviews:true})});
  const refusal=await refused.json();report.native_refusal={status:refused.status,...refusal};
  assert.equal(refused.status,409,JSON.stringify(refusal));assert.match(refusal.error,/still open in Blender/);
 }finally{await fs.writeFile(releaseFile,'owned synthetic probe finished',{flag:'wx'});assert.equal(await finished,0);await fs.writeFile(path.join(out,'native-preview-probe.log'),Buffer.concat(chunks),{flag:'wx'});}
 for(const [name,identity] of Object.entries(identities))assert.deepEqual(await fileHash(path.join(directory,name)),identity);
 report.checks.push('Actual Blender process owning the generated preview prevents removal, despite scripted confirmation; it exits itself without any process kill');
 const pending=page.waitForResponse(r=>r.url().endsWith('/api/viewer-cache/apply'));
 page.once('dialog',d=>d.accept());await page.locator('[data-action=preview-storage-apply]').click();
 const response=await pending,result=await response.json();assert.equal(response.status(),200,JSON.stringify(result));assert.equal(result.state,'SUCCEEDED',JSON.stringify(result));assert.equal(applyRequests,1);
 assert.equal(result.removedBytes,review.removableBytes);const journal=await json(path.join(base,result.journal));assert.equal(journal.state,'SUCCEEDED');assert.equal(journal.pending,undefined);
 const targets=review.eligible[0].files;
 for(const [name,identity] of Object.entries(identities)){
  if(targets.includes(name))assert.equal(await exists(path.join(directory,name)),false,name);
  else assert.deepEqual(await fileHash(path.join(directory,name)),identity,name);
 }
 assert.equal(journal.removed.filter(x=>x.kind==='disposable-payload').length,targets.length);
 assert.equal(journal.removed.filter(x=>x.kind==='cache-index').length,1);
 const inventory=journal.review.eligible[0];assert.equal(await exists(path.join(base,inventory.index.path)),false);
 assert.equal(inventory.indexRecord.previewId,previewId);
 report.removed={previewId,bytes:result.removedBytes,files:targets,journal:result.journal};
 report.checks.push('Scripted confirmation removes only reviewed synthetic payloads and reuse pointer; all database, receipt, request, result and worker-log bytes remain intact');
 await page.getByRole('button',{name:'Done',exact:true}).click();
 await page.getByRole('button',{name:'Scenes',exact:true}).click();const rebuilt=await ready(page);assert.notEqual(rebuilt,previewId);assert.equal(report.native_conversions,2);
 const record=await json(path.join(base,rebuilt,'viewer.json'));assert.equal(record.sha256,identities['model.glb'].sha256);assert.equal(record.size,identities['model.glb'].size);
 const picker=page.locator('[data-world-pick]'),choice=await picker.locator('option').evaluateAll(rows=>rows.find(n=>n.textContent==='World placement - SyntheticRig0')?.value);assert(choice);
 await picker.selectOption(choice);await page.locator('.world-transform-details summary').click();assert.equal(Number(await page.getByLabel('Placement X',{exact:true}).inputValue()),2);
 await page.screenshot({path:path.join(out,'rebuilt-world.png'),fullPage:true});
 assert.deepEqual(await fileHash(source),before);assert.deepEqual(await fileHash(path.join(p.directory,relative)),before);assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),manifest);
 report.checks.push('Reopening the World rebuilds exact geometry through real Blender; source, checkpoint, manifest, placement and approval state remain unchanged');
 assert.deepEqual(errors,[]);report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error.stack||error).replaceAll(app?.token||'no-token','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(r=>app.server.close(r));}report.errors=errors;await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify(report));}
