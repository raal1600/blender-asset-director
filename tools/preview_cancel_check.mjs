/** Actual browser abandonment -> queued cancellation or safe native completion. Synthetic only. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,generated,python,blender,playwright].every(x=>x&&path.isAbsolute(x))&&!await exists(out));
assert.equal((await json(path.join(generated,'world_layers_report.json'))).status,'PASS');
const source=path.join(generated,'placed.blend'),original=await fileHash(source),repo=fileURLToPath(new URL('../',import.meta.url));
await fs.mkdir(out,{recursive:true});
const report={kind:'REAL_SYNTHETIC_PREVIEW_CANCELLATION',checks:[],native_conversions:0,human_review:'NOT_TESTED',native_gui:'NOT_TESTED',fixture_gate:'Holds the first actual successful conversion response, not its native process, to make queue ordering deterministic'};
let app,browser,page,first,releaseFirst,firstCompleted=false;
const errors=[],failed=new Set(),entries=[];
const until=async(predicate,label,milliseconds=30000)=>{const deadline=performance.now()+milliseconds;while(performance.now()<deadline){if(await predicate())return;await delay(25);}throw Error('Timed out: '+label);};
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
 const post=async(route,body)=>{const response=await fetch(app.origin+'/api/'+route,{method:'POST',headers,body:JSON.stringify(body)}),data=await response.json();assert.equal(response.status,200,JSON.stringify(data));return data;};
 const idle=async()=>!(await (await fetch(app.origin+'/api/lifecycle',{headers})).json()).busy;
 const native=app.runtime.harness.bind(app.runtime),gate=new Promise(resolve=>{releaseFirst=resolve;});
 app.runtime.harness=async(...args)=>{if(args[0][0]!=='workbench-preview')return native(...args);const number=++report.native_conversions,result=await native(...args);if(number===1){firstCompleted=true;await gate;}return result;};
 const auditJob=await native(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await native(['job-run',auditJob.id,'--blender',blender]));
 let p=await app.store.create('Synthetic preview cancellation');
 for(const name of ['Browser world','Queue owner']){
  const created=await app.workbench.create(p.id,p.revision,name);p=await app.store.get(p.id);const scene=p.workbench.scenes.find(s=>s.id===created.sceneId),id='cp_'+randomUUID(),relative='Scenes/'+id+'.blend';
  await fs.copyFile(source,path.join(p.directory,relative),fs.constants.COPYFILE_EXCL);scene.checkpoints.push({id,path:relative,...original,parent:null,stage:'world',audit});scene.current=id;p=await app.store.save(p,p.revision);entries.push({sceneId:scene.id,id,relative});
 }
 const manifest=await fileHash(path.join(p.directory,'project.json')),base=path.join(out,'Studio/SystemRuntime/UserData/ViewerPreviews');
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});
 page=await browser.newPage({viewport:{width:1440,height:1000},serviceWorkers:'block'});page.setDefaultTimeout(30000);
 page.on('pageerror',e=>errors.push(e.message.replaceAll(app.token,'[REDACTED]')));page.on('requestfailed',r=>failed.add(r));
 await page.route('**/*',route=>new URL(route.request().url()).origin===app.origin?route.continue():route.abort());
 await page.goto(app.origin+'/workbench#'+app.token);await page.waitForFunction(()=>!document.body.classList.contains('working'));
 const owner={projectId:p.id,sceneId:entries[1].sceneId,revision:p.revision,viewerId:'viewer_'+randomUUID(),request:{kind:'checkpoint',id:entries[1].id}};
 first=post('workbench/viewer-prepare',owner);first.catch(()=>{});await until(()=>firstCompleted,'first actual native conversion',205000);
 const posted=page.waitForRequest(r=>r.url().endsWith('/api/workbench/viewer-prepare'));
 await page.locator('[data-action=project][data-id='+p.id+']').click();const queued=await posted;
 await until(async()=>{const status=await(await fetch(app.origin+'/api/lifecycle',{headers})).json();return status.reasons.some(r=>r.startsWith('2 launcher operation'));},'both requests registered');
 await page.getByRole('button',{name:'Final film',exact:true}).click();
 await until(()=>failed.has(queued),'abandoned browser request abort',3000);
 releaseFirst();const firstRecord=await first;await until(idle,'cancelled queue drains');report.queued_phase_conversions=report.native_conversions;assert.equal(report.native_conversions,1,'Abandoned queued preview must not allocate another native conversion');
 await post('workbench/viewer-release',owner);
 const folders=(await fs.readdir(base)).filter(n=>n.startsWith('view_'));assert.deepEqual(folders,[firstRecord.previewId]);
 report.checks.push('Real browser navigation aborts queued preparation before a second conversion or derivative is allocated');
 const started=page.waitForRequest(r=>r.url().endsWith('/api/workbench/viewer-prepare'));
 await page.getByRole('button',{name:'Scenes',exact:true}).click();const running=await started;let runningJob,activeDirectory;
 await until(async()=>{
  for(const folder of (await fs.readdir(base)).filter(n=>n.startsWith('view_'))){
   const directory=path.join(base,folder),request=path.join(directory,'request.json'),jobs=path.join(directory,'library/jobs');
   if(!await exists(request)||(await json(request)).id!==entries[0].id||!await exists(jobs))continue;
   for(const job of await fs.readdir(jobs)){const filename=path.join(jobs,job,'job.json');if(await exists(filename)&&(await json(filename)).state==='RUNNING'){runningJob=filename;activeDirectory=directory;return true;}}
  }
  return false;
 },'actual second native writer starts');
 await page.getByRole('button',{name:'Final film',exact:true}).click();await until(()=>failed.has(running),'active preview browser request abort',3000);
 await until(idle,'abandoned active conversion safely completes',205000);assert.equal(report.native_conversions,2);
 assert.equal((await json(runningJob)).state,'SUCCEEDED');const active=await json(path.join(activeDirectory,'viewer.json'));
 assert.equal(active.version,original.sha256);const model=await fileHash(path.join(activeDirectory,'model.glb'));assert.equal(model.sha256,active.sha256);
 const plan=await post('viewer-cache/plan',{});assert(!plan.protected.some(c=>c.previewId===active.previewId),'An abandoned response cannot leak an active view');assert(plan.eligible.some(c=>c.previewId===active.previewId));
 report.checks.push('Abandoning an observed RUNNING native preview aborts display only; the bounded conversion completes with retained success evidence and no leaked active view');
 const prepared=page.waitForResponse(r=>r.url().endsWith('/api/workbench/viewer-prepare')&&r.ok());
 await page.getByRole('button',{name:'Scenes',exact:true}).click();const reused=await(await prepared).json();assert.equal(reused.cached,true);assert.equal(reused.previewId,active.previewId);
 await page.waitForFunction(()=>['ready','failed'].includes(document.querySelector('[data-scene-viewer]')?.dataset.viewerState),null,{timeout:30000});
 assert.equal(await page.locator('[data-scene-viewer]').getAttribute('data-viewer-state'),'ready',await page.locator('[data-scene-viewer]').innerText());assert.equal(await page.locator('[data-scene-viewer] canvas').count(),1);assert.equal(report.native_conversions,2);
 await page.screenshot({path:path.join(out,'returned-world.png'),fullPage:true});assert.deepEqual(errors,[]);
 assert.deepEqual(await fileHash(source),original);assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),manifest);
 for(const entry of entries)assert.deepEqual(await fileHash(path.join(p.directory,entry.relative)),original);
 report.checks.push('Returning reuses the exact verified native result without reconversion; original/checkpoint/manifest and approval state remain unchanged');
 report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error.stack||error).replaceAll(app?.token||'no-token','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}
finally{
 releaseFirst?.();await first?.catch(()=>{});await browser?.close();
 if(app){await until(async()=>!(await(await fetch(app.origin+'/api/lifecycle',{headers:{Authorization:'Bearer '+app.token}})).json()).busy,'owned test work drain',220000);app.server.closeAllConnections();await new Promise(r=>app.server.close(r));}
 report.errors=errors;await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify(report));
}
