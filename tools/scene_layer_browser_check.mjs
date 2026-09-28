/** Real UI -> authenticated API -> native Blender -> immutable saved scene. Synthetic only. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2),uid=p=>p+randomUUID();
assert([out,generated,python,blender,playwright].every(x=>x&&path.isAbsolute(x))&&!await exists(out));
const fixture=await json(path.join(generated,'RESULTS.json'));assert.equal(fixture.status,'PASS');assert.equal(fixture.scope,'REAL_GENERATED_SCENE_LAYERS');
const member=fixture.outputs.at(-1),source=path.join(generated,member.path),original=await fileHash(source);assert.equal(original.sha256,member.sha256);
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),report={kind:'synthetic-progressive-layers-browser',checks:[],errors:[],saved:[],human_review:'NOT_TESTED',native_desktop:'NOT_TESTED',scripted_decisions:['Generated World/Action baseline and Shots ready only; not human acceptance']};
let app,browser,page;
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
 let p=await app.store.create('Synthetic progressive camera and light','Generated controls and preservation tests only');await app.workbench.create(p.id,p.revision,'One world');p=await app.store.get(p.id);
 const s=p.workbench.scenes[0],cpId=uid('cp_'),relative='Scenes/'+cpId+'.blend';await fs.copyFile(source,path.join(p.directory,relative),fs.constants.COPYFILE_EXCL);
 const prepared=await app.runtime.harness(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await app.runtime.harness(['job-run',prepared.id,'--blender',blender]));
 s.checkpoints.push({id:cpId,path:relative,...original,stage:'action',parent:null,audit});s.current=cpId;s.stage='shots';s.completed={world:cpId,action:cpId};p=await app.store.save(p,p.revision);
 const state=async()=>{const r=await fetch(app.origin+'/api/workbench/state?'+new URLSearchParams({projectId:p.id,compact:true}),{headers});assert.equal(r.status,200);return r.json();};
 const post=async(route,body)=>{const r=await fetch(app.origin+'/api/workbench/'+route,{method:'POST',headers,body:JSON.stringify(body)}),v=await r.json();assert.equal(r.status,200,JSON.stringify(v));return v;};

 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});page=await browser.newPage({viewport:{width:1440,height:1000},serviceWorkers:'block'});page.setDefaultTimeout(30000);
 page.on('pageerror',e=>report.errors.push(e.message.replaceAll(app.token,'[REDACTED]')));page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text().replaceAll(app.token,'[REDACTED]'));});
 page.on('dialog',async dialog=>{assert.match(dialog.message(),/reviewed every named shot/);await dialog.accept();});
 const idle=()=>page.waitForFunction(()=>!document.body.classList.contains('working'));
 const ready=async()=>{await idle();await page.waitForFunction(()=>document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready',null,{timeout:205000});await page.waitForFunction(()=>!document.querySelector('[data-action="layer-ready"]')?.disabled,null,{timeout:205000});await idle();};
 const click=async action=>{await page.locator('[data-action="'+action+'"]').click();await idle();};
 const input=async(selector,value)=>{await page.locator(selector).fill(String(value));await page.locator(selector).press('Tab');};
 await page.goto(app.origin+'/workbench#'+app.token);await idle();await page.locator('[data-action="project"][data-id="'+p.id+'"]').click();await idle();await page.waitForFunction(()=>document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready',null,{timeout:205000});
 assert.equal(await page.locator('#notice').isVisible(),false);assert.equal(await page.locator('[data-action="layer-ready"]').isDisabled(),true);assert.equal(Object.hasOwn((await state()).project.workbench.scenes[0],'shots'),false);report.checks.push('Older scene with no optional shots metadata opens without a crash, migration or fabricated completion');
 for(const [name,camera] of [['Wide','SyntheticWide'],['Close','SyntheticClose']]){const v=await state();await post('shot-save',{projectId:p.id,sceneId:s.id,revision:v.project.revision,shot:{name,camera,start:1,end:9}});}
 await click('refresh');await ready();
 assert.equal(await page.locator('.layered-scene').count(),1);assert.equal(await page.locator('.scene-layout').count(),0);await page.screenshot({path:path.join(out,'shots-before.png'),fullPage:true});
 const base=await fileHash(path.join(p.directory,'project.json'));
 await click('layer-camera');await page.locator('[name="layer-subject"][value="SyntheticSkin0"]').check();await page.locator('#layer-camera-name').fill('SyntheticBrowserCamera');await page.locator('#layer-lens').fill('55');assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),base);
 await click('layer-camera-save');await ready();let v=await state(),scene=v.project.workbench.scenes[0],cameraCP=scene.checkpoints.find(c=>c.id===scene.current);
 assert.notEqual(cameraCP.id,cpId);assert.equal(scene.completed.shots,undefined);const cameraRun=v.runs.find(r=>r.action==='scene-layer-audit'&&r.state==='SUCCEEDED'&&r.checkpointId===cameraCP.id);
 assert.equal(cameraRun.inspection.cameras.find(c=>c.name==='SyntheticBrowserCamera').lens_mm,55);assert.equal(cameraRun.inspection.cameras.length,3);report.saved.push(cameraCP);
 report.checks.push('Observed subject selection -> explicit new camera Save -> real independently audited camera; old cameras and unapproved state retained');
 await click('new-shot');await page.locator('#shot-name').fill('Detail');await page.locator('#shot-camera').selectOption('SyntheticBrowserCamera');await click('save-shot');await ready();
 assert.equal(await page.locator('[data-scene-viewer]').getAttribute('data-camera-mode'),'saved-shot');v=await state();scene=v.project.workbench.scenes[0];assert.equal(scene.shots.length,3);
 const previewId=await page.locator('[data-scene-viewer]').getAttribute('data-preview-id'),preview=await json(path.join(out,'Studio/SystemRuntime/UserData/ViewerPreviews',previewId,'viewer.json'));assert.equal(preview.shotView.shot.camera,'SyntheticBrowserCamera');assert.deepEqual(preview.shotView.shot.start,1);
 report.checks.push('Name the real new camera as a shot, select it and view its exact saved framing and range');
 await click('layer-ready');await ready();assert.match(await page.locator('h1').innerText(),/Light your scene/);
 await page.locator('[data-layer-field="selected"]').selectOption('SyntheticLayerKey');await input('[data-layer-field="energy"]',350);
 v=await state();assert.equal(v.project.workbench.scenes[0].current,cameraCP.id);assert.match(await page.locator('.layer-scope').last().innerText(),/still the saved scene/);
 await click('layer-undo');assert.equal(Number(await page.locator('[data-layer-field="energy"]').inputValue()),200);
 await input('[data-layer-field="energy"]',350);await page.locator('[data-action="stage"][data-stage="shots"]').click();await idle();assert.match(await page.locator('#dialog').innerText(),/Keep your camera/);await page.getByRole('button',{name:'Stay here',exact:true}).click();await idle();
 assert.match(await page.locator('h1').innerText(),/Light your scene/);assert.equal(Number(await page.locator('[data-layer-field="energy"]').inputValue()),350);
 await page.locator('[data-layer-field="energy"]').fill('-1');assert.equal(await page.locator('[data-action="layer-save"]').isDisabled(),true);assert.equal(await page.locator('[data-layer-field="energy"]').evaluate(n=>n.checkValidity()),false);
 await page.locator('[data-layer-field="energy"]').fill('350');await click('layer-save');await ready();assert.equal(await page.locator('[data-layer-field="selected"]').inputValue(),'SyntheticLayerKey');v=await state();scene=v.project.workbench.scenes[0];const lightCP=scene.checkpoints.find(c=>c.id===scene.current),lightRun=v.runs.find(r=>r.action==='scene-layer-audit'&&r.state==='SUCCEEDED'&&r.checkpointId===lightCP.id),save=v.runs.find(r=>r.resultCheckpointId===lightCP.id);
 assert.equal(lightRun.inspection.look.state.lights.find(l=>l.name==='SyntheticLayerKey').energy,350);assert.equal(lightRun.inspection.look.state.lights.find(l=>l.name==='SyntheticLayerFill').energy,25);assert.equal(scene.completed.light,undefined);assert.deepEqual(save.context.affectedShots.map(x=>x.id),scene.shots.map(x=>x.id));assert.deepEqual(lightRun.inspection.cameras,cameraRun.inspection.cameras);report.saved.push(lightCP);
 report.checks.push('Light local draft does not write; Undo and navigation Stay preserve intent; one explicit Save changes only named light and lists every affected shot');
 await page.locator('[data-layer-field="selected"]').selectOption('SyntheticLayerKey');await input('[data-layer-field="energy"]',450);
 const request={version:'scene-layer-v1',layer:'light',requestId:uid('run_'),checkpointId:lightCP.id,sha256:lightCP.sha256,inspectionId:lightRun.id,audit_sha256:lightRun.inspection.sha256,operations:[{operation:'light-adjust',options:{lights:[{name:'SyntheticLayerKey',energy:375}]}}]};
 await post('scene-layer-save',{projectId:p.id,sceneId:s.id,revision:v.project.revision,request});const until=Date.now()+205000;
 while(Date.now()<until){v=await state();const r=v.runs.find(r=>r.id===request.requestId);if(r&&['FAILED','INTERRUPTED','SUCCEEDED'].includes(r.state)&&!v.locked){assert.equal(r.state,'SUCCEEDED',JSON.stringify(r));break;}await new Promise(r=>setTimeout(r,200));}
 assert.equal(v.runs.find(r=>r.id===request.requestId)?.state,'SUCCEEDED');await click('refresh');assert.match(await page.locator('.action-savebar').innerText(),/changed elsewhere/);assert.equal(await page.locator('[data-action="layer-save"]').isDisabled(),true);assert.equal(Number(await page.locator('[data-layer-field="energy"]').inputValue()),450);
 await click('layer-discard');await ready();await page.locator('[data-layer-field="selected"]').selectOption('SyntheticLayerKey');assert.equal(Number(await page.locator('[data-layer-field="energy"]').inputValue()),375);
 report.checks.push('A second genuine native Save makes the local draft stale; Save refuses, stale draft stays visible, explicit Discard reloads current native values');
 await page.screenshot({path:path.join(out,'light-after.png'),fullPage:true});await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'light-mobile.png'),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 for(const cp of [cameraCP,lightCP])assert.deepEqual(await fileHash(path.join(p.directory,cp.path)),{sha256:cp.sha256,size:cp.size});assert.deepEqual(await fileHash(source),original);assert.deepEqual(await fileHash(path.join(p.directory,relative)),original);assert.deepEqual(report.errors,[]);
 report.checks.push('Desktop/mobile layout, no browser errors, original and previous checkpoints preserved byte-for-byte');report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error}));}
