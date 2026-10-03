/** Generated-only browser -> authenticated API -> real Blender -> saved GLB. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {randomUUID} from 'node:crypto';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,generated,python,blender,playwright].every(x=>x&&path.isAbsolute(x)));
assert(!await exists(out));const nativeReport=await json(path.join(generated,'RESULTS.json'));assert.equal(nativeReport.status,'PASS');assert.equal(nativeReport.input_kind,'GENERATED');
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),source=path.join(generated,'source.blend'),original=await fileHash(source);
const report={kind:'generated-gait-browser',checks:[],errors:[],requests:[],not_tested:['Live runtime','Human loop/contact approval','Terrain or foot locking']};
let app,browser,page;
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const native=await app.runtime.harness(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await app.runtime.harness(['job-run',native.id,'--blender',blender]));
 let project=await app.store.create('Synthetic gait acceptance','Generated feet only, no human review');await app.workbench.create(project.id,project.revision,'Automatic travel');project=await app.store.get(project.id);
 const scene=project.workbench.scenes[0],cpId='cp_'+randomUUID(),relative='Scenes/'+cpId+'.blend';await fs.copyFile(source,path.join(project.directory,relative),fs.constants.COPYFILE_EXCL);
 scene.checkpoints.push({id:cpId,path:relative,...original,parent:null,stage:'world',audit});scene.current=cpId;scene.stage='action';scene.completed={world:cpId};await app.store.save(project,project.revision);
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});page=await browser.newPage({viewport:{width:1440,height:1100},serviceWorkers:'block'});page.setDefaultTimeout(30000);
 const safe=v=>String(v).replaceAll(app.token,'[REDACTED]');page.on('pageerror',e=>report.errors.push(safe(e.message)));page.on('console',m=>{if(m.type()==='error')report.errors.push(safe(m.text()));});page.on('dialog',d=>d.dismiss());
 page.on('request',r=>{if(r.url().startsWith(app.origin+'/'))report.requests.push({path:new URL(r.url()).pathname,method:r.method()});else if(/^https?:/.test(r.url()))report.errors.push('Unexpected external request');});
 const ready=()=>page.waitForFunction(()=>!document.body.classList.contains('working')&&document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready'&&!document.querySelector('[data-action-field="performer"]')?.disabled,null,{timeout:205000});
 const snapshot=()=>page.locator('body').ariaSnapshot();
 const click=async selector=>{await snapshot();await page.locator(selector).click();await page.waitForFunction(()=>!document.body.classList.contains('working'));};
 await page.goto(app.origin+'/workbench#'+app.token);await click('[data-action="project"][data-id="'+project.id+'"]');await ready();
 await click('[data-action="motion-enable"]');await snapshot();await page.getByLabel('Performer',{exact:true}).selectOption('SyntheticWalker');
 const take=await page.locator('[data-motion-add] option').nth(1).getAttribute('value');await snapshot();await page.getByLabel('Add animation').selectOption(take);
 assert.equal(await page.locator('[data-motion-field="travel"]').isChecked(),true);assert.equal(await page.locator('[data-motion-field="pace"]').count(),0);
 assert.equal(await page.locator('[data-action="action-save"]').isEnabled(),true);assert.match(await page.locator('[data-motion-pace]').innerText(),/Estimated natural pace/);
 report.checks.push('Observed gait automatically creates a valid natural-cycle path without asking for stride length');
 const distance=page.getByLabel('Distance (m)',{exact:true});await distance.fill('5');assert.equal(await page.locator('[data-action="action-save"]').isDisabled(),true);
 assert.match(await page.locator('.action-savebar [role="status"]').innerText(),/loop join/);assert.equal(await page.locator('[data-motion-repeat]').isVisible(),true);
 assert.match(await page.locator('[data-motion-duration]').innerText(),new RegExp('Frames 1–'+nativeReport.frames));
 assert.match(await page.locator('.motion-next').innerText(),new RegExp('frame '+(nativeReport.frames+1)));
 await page.screenshot({path:path.join(out,'01-calculated.png'),fullPage:true});report.checks.push('Five metres calculates repeated-cycle duration and exposes the exact remaining review beside Save');
 const handle=page.getByRole('button',{name:'Move path endpoint',exact:true});
 // Numeric distance works even when the endpoint is outside the current view.
 await distance.fill('1');await handle.scrollIntoViewIfNeeded();await handle.focus();await handle.press('ArrowRight');assert(Math.abs(Number(await distance.inputValue())-1.1)<1e-5);
 await click('[data-action="action-undo"]');assert(Math.abs(Number(await distance.inputValue())-1)<1e-5);
 const box=await handle.boundingBox();assert(box);await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2+25,box.y+box.height/2-20,{steps:8});await page.mouse.up();assert.notEqual(Number(await distance.inputValue()),1);
 await click('[data-action="action-undo"]');assert(Math.abs(Number(await distance.inputValue())-1)<1e-5);report.checks.push('Pointer and keyboard distance edits remain constrained to the observed heading and undo as one gesture');
 await distance.fill('');assert.equal(await page.locator('[data-action="action-save"]').isDisabled(),true);assert.equal(await distance.getAttribute('aria-invalid'),'true');await distance.fill('5');
 await page.locator('.motion-clip-controls summary').click();await snapshot();await page.locator('[data-motion-field="automatic"]').uncheck();assert.equal(await page.getByLabel('Metres per cycle',{exact:true}).isVisible(),true);
 await page.getByLabel('Metres per cycle',{exact:true}).fill('5');await page.locator('[data-motion-field="automatic"]').check();assert.equal(await page.locator('[data-motion-field="pace"]').count(),0);assert.match(await page.locator('[data-motion-duration]').innerText(),new RegExp('Frames 1–'+nativeReport.frames));
 assert.equal(report.requests.filter(r=>r.path.endsWith('/action-save')).length,0);report.checks.push('Manual override is explicit and reversible; invalid values explain themselves; drafts dispatch no mutation jobs');
 // This checkbox is exercised only with generated mathematical test feet.
 await page.locator('[data-motion-field="repeat_reviewed"]').check();assert.equal(await page.locator('[data-action="action-save"]').isEnabled(),true);await click('[data-action="action-save"]');await ready();
 project=await app.store.get(project.id);const saved=project.workbench.scenes[0],cp=saved.checkpoints.find(c=>c.id===saved.current);assert.notEqual(cp.id,cpId);assert.deepEqual(saved.completed,{world:cpId});
 const run=(await app.store.runs(project.id)).find(r=>r.action==='action-audit'&&r.checkpointId===cp.id&&r.state==='SUCCEEDED');assert(run);const rig=run.inspection.performers.find(p=>p.name==='SyntheticWalker'),clip=rig.timeline.clips[0];
 assert.equal(clip.frames,nativeReport.frames);assert.equal(clip.travel.gait_id,rig.takes.find(t=>t.id===clip.take_id).gait.id);assert(Math.abs(Math.hypot(...clip.travel.delta_m)-5)<1e-5);
 assert.equal(report.requests.filter(r=>r.path.endsWith('/action-save')).length,1);report.checks.push('One Save runs real Blender, stores exact gait calibration and creates a separate unapproved checkpoint');
 await page.reload();await ready();assert.match(await page.locator('.motion-next').innerText(),new RegExp('frame '+(clip.frames+1)));assert.equal(await page.locator('.motion-clip').count(),1);
 await page.locator('[data-view="play"]').click();await page.waitForFunction(()=>Number(document.querySelector('[data-view="time"]').value)>.3);await page.locator('[data-view="play"]').click();await page.screenshot({path:path.join(out,'02-saved-playback.png'),fullPage:true});
 report.checks.push('Reload retains the clip, advances append position after occupied frames and plays actual saved GLB');
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'03-narrow.png'),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(await fileHash(source),original);assert.deepEqual(await fileHash(path.join(project.directory,relative)),original);assert.deepEqual(report.errors,[]);report.checks.push('Original bytes unchanged; narrow view has no horizontal overflow, no external requests or console errors');
 report.status='PASS';report.projectId=project.id;report.checkpoint=cp.id;
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;if(page)await page.screenshot({path:path.join(out,'FAILURE.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error}));}
