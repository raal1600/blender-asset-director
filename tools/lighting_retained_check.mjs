/** Continue comparison checks on retained synthetic renders; never rerender them. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash,randomUUID} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,retained,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,retained,python,blender,playwright].every(x=>x&&path.isAbsolute(x))&&!await exists(out));
const previousPath=path.join(retained,'RESULTS.json'),previous=await json(previousPath),previousHash=await fileHash(previousPath);
assert.equal(previous.kind,'synthetic-rendered-lighting-browser');assert.equal(previous.previewFramesAuthorized,4);assert.equal(previous.previews.length,4);
assert.equal(previous.status,'FAIL');assert.match(previous.error,/strict mode violation/);assert.deepEqual(previous.errors,[]);
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),root=path.join(retained,'Studio');
const report={kind:'retained-synthetic-lighting-comparison',retainedReport:previousHash,checks:[],errors:[],newPreviewFrames:0,human_review:'NOT_TESTED',native_desktop:'NOT_TESTED'};
let app,browser,page;
try{
 app=await createApp({root,port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(root,'Database/AssetDirector')}});
 const inventory=await app.store.list();assert.deepEqual(inventory.errors,[]);
 const matches=inventory.projects.filter(p=>p.name==='Synthetic rendered lighting'&&p.brief==='Two exact-camera still comparisons');assert.equal(matches.length,1);
 const p=matches[0],s=p.workbench.scenes[0];assert.equal(p.workbench.scenes.length,1);assert.equal(s.stage,'light');assert.equal(s.shots.length,2);assert.equal(s.completed.light,undefined);
 const headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
 const get=async(route,query)=>{const response=await fetch(app.origin+'/api/workbench/'+route+'?'+new URLSearchParams({projectId:p.id,sceneId:s.id,...query}),{headers});assert.equal(response.status,200);return response.json();};
 const nativeFiles=s.checkpoints.map(cp=>({path:path.join(p.directory,cp.path),sha256:cp.sha256,size:cp.size}));
 for(const cp of nativeFiles)assert.deepEqual(await fileHash(cp.path),{sha256:cp.sha256,size:cp.size});
 for(const old of previous.previews){
  const records=await get('preview-evidence',{shotId:old.shot.id}),entry=records.items.find(x=>x.runId===old.runId);
  assert.equal(entry.status,'VERIFIED');assert.equal(entry.current,old.phase==='after');assert.equal(entry.dependencyStatus,'MATCH');assert.deepEqual(entry.image,old.image);
 }
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});
 page=await browser.newPage({viewport:{width:1440,height:1000},serviceWorkers:'block'});page.setDefaultTimeout(30000);
 page.on('pageerror',e=>report.errors.push(e.message.replaceAll(app.token,'[REDACTED]')));page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text().replaceAll(app.token,'[REDACTED]'));});
 page.on('dialog',async dialog=>{await dialog.dismiss();report.errors.push('Unexpected approval dialog');});
 const idle=()=>page.waitForFunction(()=>!document.body.classList.contains('working'));
 await page.goto(app.origin+'/workbench#'+app.token);await idle();await page.locator('[data-action="project"][data-id="'+p.id+'"]').click();await idle();
 await page.waitForFunction(()=>!document.querySelector('[data-action="layer-ready"]')?.disabled,null,{timeout:205000});
 const unchanged=await fileHash(path.join(p.directory,'project.json'));
 const imagesReady=()=>page.waitForFunction(()=>{const nodes=[...document.querySelectorAll('[data-lighting-run]')];return nodes.length===2&&nodes.every(n=>n.complete&&n.naturalWidth===640);});
 for(const shot of s.shots){
  const before=previous.previews.find(x=>x.phase==='before'&&x.shot.id===shot.id),after=previous.previews.find(x=>x.phase==='after'&&x.shot.id===shot.id);assert.notEqual(before.image.sha256,after.image.sha256);
  await page.getByRole('button',{name:'Compare rendered stills',exact:true}).click();await idle();await page.locator('#lighting-evidence-shot').selectOption(shot.id);await idle();await imagesReady();
  assert.match(await page.locator('#dialog').innerText(),/Same shot revision, camera, frame and preview settings/);
  for(const entry of [before,after])assert.equal(await page.locator('[data-lighting-run="'+entry.runId+'"]').count(),1);
  await page.locator('#dialog').screenshot({path:path.join(out,'compare-'+shot.name+'.png')});
  assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),unchanged);
  await page.getByRole('button',{name:'Back to Light',exact:true}).click();await idle();
 }
 report.checks.push('Both retained before/after camera pairs display decoded exact-hash PNGs; different pixels and matching recipes, no data mutation or approval');
 await page.getByRole('button',{name:'Compare rendered stills',exact:true}).click();await idle();await page.setViewportSize({width:390,height:844});await imagesReady();
 await page.locator('#dialog').screenshot({path:path.join(out,'comparison-mobile.png')});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.getByRole('button',{name:'Back to Light',exact:true}).click();await idle();
 const old=previous.previews[0],media=query=>fetch(app.origin+'/api/workbench/media?'+new URLSearchParams({projectId:p.id,sceneId:s.id,kind:'preview-evidence',runId:old.runId,...query}),{headers});
 const oldResponse=await media({});assert.equal(oldResponse.status,200);assert.equal(createHash('sha256').update(Buffer.from(await oldResponse.arrayBuffer())).digest('hex'),old.image.sha256);
 assert.equal((await media({sceneId:'sc_'+randomUUID()})).status,404);
 const peer=await app.store.create('Other synthetic comparison','No access to retained production');await app.workbench.create(peer.id,peer.revision,'Other scene');const q=await app.store.get(peer.id);
 assert.notEqual((await media({projectId:q.id,sceneId:q.workbench.scenes[0].id})).status,200);
 report.checks.push('Narrow mobile layout and historical media access verified; foreign scene and production refused');
 const post=async(route,body)=>{const response=await fetch(app.origin+'/api/workbench/'+route,{method:'POST',headers,body:JSON.stringify({projectId:p.id,sceneId:s.id,...body})});assert.equal(response.status,200,await response.text());};
 let state=await get('state',{compact:true});await post('enter',{revision:state.project.revision,stage:'shots'});state=await get('state',{compact:true});
 const first=s.shots[0];await post('shot-save',{revision:state.project.revision,shot:{id:first.id,revision:first.revision,name:first.name,camera:first.camera,start:2,end:9}});
 assert.equal((await get('preview-evidence',{shotId:first.id})).items.some(x=>x.current),false);assert.equal((await get('preview-evidence',{shotId:s.shots[1].id})).items.some(x=>x.current),true);
 const final=await get('state',{compact:true});assert.equal(final.project.workbench.scenes[0].completed.light,undefined);assert.deepEqual(final.project.jobs,p.jobs);
 for(const cp of nativeFiles)assert.deepEqual(await fileHash(cp.path),{sha256:cp.sha256,size:cp.size});
 assert.deepEqual(await fileHash(previousPath),previousHash);assert.deepEqual(report.errors,[]);
 report.checks.push('Named-shot revision makes only its still historical; all native files/jobs and previous failed evidence remain intact, no new renders or Light approval');report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify(report));}
