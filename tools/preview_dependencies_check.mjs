/** Real authenticated checkpoint conversion with unrelated pins; synthetic only. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,generated,python,blender].every(p=>p&&path.isAbsolute(p))&&!await exists(out));
const fixture=await json(path.join(generated,'RESULTS.json'));assert.equal(fixture.status,'PASS');
await fs.mkdir(out,{recursive:true});
const report={kind:'REAL_SYNTHETIC_DEPENDENCY_COPY',checks:[],measurements:[],human_review:'NOT_TESTED',native_gui:'NOT_TESTED'};
let app,browser,page;
try{
 const library=path.join(generated,'Catalog'),repo=fileURLToPath(new URL('../',import.meta.url));
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library}});
 let p=await app.store.create('Synthetic dependency copy');await app.workbench.create(p.id,p.revision,'Textured world');p=await app.store.get(p.id);
 p=await app.workbench.selectCatalog(p.id,p.workbench.scenes[0].id,p.revision,fixture.asset_id,true);
 const scene=p.workbench.scenes[0],cp='cp_'+randomUUID(),relative='Scenes/'+cp+'.blend';
 await fs.copyFile(fixture.source.path,path.join(p.directory,relative),fs.constants.COPYFILE_EXCL);
 scene.checkpoints.push({id:cp,path:relative,sha256:fixture.source.sha256,size:fixture.source.size,stage:'world',parent:null,audit:await json(path.join(generated,'audit.json'))});scene.current=cp;p=await app.store.save(p,p.revision);
 const manifest=await fileHash(path.join(p.directory,'project.json')),headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'},body={projectId:p.id,sceneId:scene.id,revision:p.revision,request:{kind:'checkpoint',id:cp}};
 const prepare=async label=>{const started=performance.now(),r=await fetch(app.origin+'/api/workbench/viewer-prepare',{method:'POST',headers,body:JSON.stringify(body)}),record=await r.json();assert.equal(r.status,200,JSON.stringify(record));report.measurements.push({label,elapsed_ms:performance.now()-started,cached:record.cached});return record;};
 const first=await prepare('cold'),directory=path.join(out,'Studio/SystemRuntime/UserData/ViewerPreviews',first.previewId),request=await json(path.join(directory,'request.json'));
 report.copied_files=request.files.length;report.copied_source_bytes=request.files.reduce((n,f)=>n+f.size,0);report.all_pinned_copy_bytes=fixture.source.size+fixture.files.reduce((n,f)=>n+f.size,0);
 assert.equal(request.files.length,2,'Only the checkpoint and its actual texture should be copied, not unrelated pins');
 assert(request.files.some(f=>f.sha256===fixture.files[0].sha256));assert(!request.files.some(f=>f.sha256===fixture.files[1].sha256));
 const receipt=await json(path.join(directory,'receipt.json'));assert.equal(receipt.state,'READY');assert.equal(receipt.source_version,fixture.source.sha256);
 const job=await json(path.join(directory,'library/jobs',receipt.job_id,'job.json'));assert.equal(job.state,'SUCCEEDED');
 const copies=await fs.readdir(path.join(directory,'library/incoming/package'));assert.equal(copies.length,2);assert(copies.some(n=>n.endsWith('.png')));
 report.checks.push('Actual Blender conversion copies the exact checkpoint and required texture; unrelated pinned bytes are absent');
 const warm=await prepare('warm');assert.equal(warm.cached,true);assert.equal(warm.previewId,first.previewId);
 report.checks.push('Warm preparation reuses the verified derivative without another package copy');
 if(playwright){
  const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});
  page=await browser.newPage({viewport:{width:1440,height:1000},serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message.replaceAll(app.token,'[REDACTED]')));
  await page.route('**/*',route=>new URL(route.request().url()).origin===app.origin?route.continue():route.abort());
  await page.goto(app.origin+'/workbench#'+app.token);await page.locator('[data-action=project][data-id='+p.id+']').click();
  await page.waitForFunction(()=>['ready','failed'].includes(document.querySelector('[data-scene-viewer]')?.dataset.viewerState),null,{timeout:205000});
  assert.equal(await page.locator('[data-scene-viewer]').getAttribute('data-viewer-state'),'ready',await page.locator('[data-scene-viewer]').innerText());
  assert.equal(await page.locator('[data-scene-viewer]').getAttribute('data-preview-id'),first.previewId);assert.equal(await page.locator('[data-scene-viewer] canvas').count(),1);assert.deepEqual(errors,[]);
  await page.screenshot({path:path.join(out,'textured-world.png'),fullPage:true});report.checks.push('Actual authenticated World canvas displays the same verified textured derivative with no browser errors');
 }
 assert.equal((await fileHash(fixture.source.path)).sha256,fixture.source.sha256);assert.equal((await fileHash(path.join(p.directory,relative))).sha256,fixture.source.sha256);assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),manifest);
 for(const f of fixture.files)assert.deepEqual(await fileHash(path.join(library,f.path)),{sha256:f.sha256,size:f.size});
 report.checks.push('All source files, checkpoint, pinned rights metadata and project/approval state unchanged');report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error.stack||error).replaceAll(app?.token||'no-token','[REDACTED]');process.exitCode=1;}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify(report));}
