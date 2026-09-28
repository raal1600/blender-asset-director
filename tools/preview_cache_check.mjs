/** Actual native preview reuse across an authenticated launcher restart. Synthetic only. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {randomUUID,createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,generated,python,blender].every(x=>x&&path.isAbsolute(x))&&!await exists(out));
assert.equal((await json(path.join(generated,'world_layers_report.json'))).status,'PASS');
const source=path.join(generated,'placed.blend'),before=await fileHash(source),repo=fileURLToPath(new URL('../',import.meta.url));
await fs.mkdir(out,{recursive:true});
const report={kind:'REAL_SYNTHETIC_PREVIEW_CACHE',checks:[],measurements:[],native_conversions:0,
 human_review:'NOT_TESTED',browser_webgl:'NOT_TESTED',memory_scope:'Launcher process RSS only; Blender/browser peaks not measured'};
let app,browser,page,peak=process.memoryUsage().rss;
const sample=setInterval(()=>{peak=Math.max(peak,process.memoryUsage().rss);},50);
const config={python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')};
const open=async()=>{
 app=await createApp({root:path.join(out,'Studio'),port:0,config});
 const original=app.runtime.harness.bind(app.runtime);
 app.runtime.harness=async(...args)=>{if(args[0][0]==='workbench-preview')report.native_conversions++;return original(...args);};
};
const close=async()=>{app.server.closeAllConnections();await new Promise(r=>app.server.close(r));};
try{
 await open();let p=await app.store.create('Synthetic cache acceptance');await app.workbench.create(p.id,p.revision,'Static world');p=await app.store.get(p.id);
 const scene=p.workbench.scenes[0],cp='cp_'+randomUUID(),relative='Scenes/'+cp+'.blend';await fs.copyFile(source,path.join(p.directory,relative),fs.constants.COPYFILE_EXCL);
 const job=await app.runtime.harness(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await app.runtime.harness(['job-run',job.id,'--blender',blender]));
 scene.checkpoints.push({id:cp,path:relative,...before,stage:'world',parent:null,audit});scene.current=cp;p=await app.store.save(p,p.revision);
 const manifest=await fileHash(path.join(p.directory,'project.json')),body={projectId:p.id,sceneId:scene.id,revision:p.revision,request:{kind:'checkpoint',id:cp}};
 const view=async(label,preview)=>{
  if(!playwright)return;
  if(!browser){const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});}
  page=await browser.newPage({viewport:{width:1440,height:1000},serviceWorkers:'block'});page.setDefaultTimeout(30000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message.replaceAll(app.token,'[REDACTED]')));
  await page.goto(app.origin+'/workbench#'+app.token);await page.waitForFunction(()=>!document.body.classList.contains('working'));
  const started=performance.now();await page.locator('[data-action="project"][data-id="'+p.id+'"]').click();
  await page.waitForFunction(()=>['ready','failed'].includes(document.querySelector('[data-scene-viewer]')?.dataset.viewerState),null,{timeout:205000});
  assert.equal(await page.locator('[data-scene-viewer]').getAttribute('data-viewer-state'),'ready',await page.locator('[data-scene-viewer]').innerText());
  assert.equal(await page.locator('[data-scene-viewer]').getAttribute('data-preview-id'),preview.previewId);
  assert.equal(await page.locator('[data-scene-viewer] canvas').count(),1);
  report.measurements.push({label,project_to_webgl_ready_ms:performance.now()-started});
  const picker=page.locator('[data-world-pick]'),choice=await picker.locator('option').evaluateAll(rows=>rows.find(n=>n.textContent==='World placement - SyntheticRig0')?.value);assert(choice);
  await picker.selectOption(choice);await page.locator('.world-transform-details summary').click();
  assert.equal(Number(await page.getByLabel('Placement X',{exact:true}).inputValue()),2);
  await page.screenshot({path:path.join(out,label+'.png'),fullPage:true});assert.deepEqual(errors,[]);await page.close();page=null;
 };
 const prepare=async label=>{
  const start=performance.now(),headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
  const response=await fetch(app.origin+'/api/workbench/viewer-prepare',{method:'POST',headers,body:JSON.stringify(body)}),record=await response.json();assert.equal(response.status,200,JSON.stringify(record));
  const prepared_ms=performance.now()-start;
  const model=await fetch(app.origin+'/api/workbench/viewer-model?'+new URLSearchParams({projectId:p.id,sceneId:scene.id,previewId:record.previewId}),{headers});assert.equal(model.status,200);
  const bytes=Buffer.from(await model.arrayBuffer());assert.equal(bytes.length,record.size);assert.equal(createHash('sha256').update(bytes).digest('hex'),record.sha256);
  report.measurements.push({label,prepared_ms,total_ms:performance.now()-start,bytes:bytes.length,cached:record.cached,previewId:record.previewId,native_conversions:report.native_conversions});
  return record;
 };
 const cold=await prepare('cold'),warm=await prepare('warm');assert.equal(warm.previewId,cold.previewId);assert.equal(warm.cached,true);assert.equal(report.native_conversions,1);
 report.checks.push('Cold conversion is actual Blender; warm same-session request reuses exact preview identity and bytes');
 await view('warm-browser',cold);
 const oldToken=app.token;await close();await open();assert.notEqual(app.token,oldToken);
 assert.equal((await fetch(app.origin+'/api/session',{headers:{Authorization:'Bearer '+oldToken}})).status,401);
 const restarted=await prepare('fresh authenticated session');
 assert.equal(restarted.previewId,cold.previewId,'Restart must reuse verified immutable geometry, not allocate another Blender copy');assert.equal(restarted.cached,true);assert.equal(report.native_conversions,1);
 report.checks.push('Fresh authenticated session re-verifies and reuses the same derivative without native reconversion');
 await view('fresh-session-browser',cold);assert.equal(report.native_conversions,1);
 if(playwright){report.browser_webgl='PASS';report.checks.push('Actual workbench canvas and whole-instance selection agree before/after restart with no reconversion or browser errors');}
 assert.deepEqual(await fileHash(source),before);assert.deepEqual(await fileHash(path.join(p.directory,relative)),before);assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),manifest);
 report.checks.push('Original, saved checkpoint, manifest and approval state unchanged');report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error.stack||error).replaceAll(app?.token||'no-token','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}
finally{clearInterval(sample);await browser?.close();if(app)await close();report.launcher_peak_rss_bytes=peak;await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify(report));}
