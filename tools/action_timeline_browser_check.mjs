/** Browser -> authenticated server -> real Blender -> persisted editable clips. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {randomUUID} from 'node:crypto';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,generated,python,blender,playwright].every(x=>x&&path.isAbsolute(x)));
assert(!await exists(out));assert.equal((await json(path.join(generated,'RESULTS.json'))).status,'PASS');
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),source=path.join(generated,'source.blend'),original=await fileHash(source);
const report={kind:'generated-action-timeline-browser',checks:[],errors:[],requests:[],not_tested:['Live installation','Licensed character gait/contact review','Native desktop UI','Human approval']};
let app,browser,page;
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const native=await app.runtime.harness(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await app.runtime.harness(['job-run',native.id,'--blender',blender]));
 let project=await app.store.create('Synthetic motion timeline','Generated fixtures only; no human acceptance');await app.workbench.create(project.id,project.revision,'Path and clips');project=await app.store.get(project.id);
 const scene=project.workbench.scenes[0],cpId='cp_'+randomUUID(),relative='Scenes/'+cpId+'.blend';await fs.copyFile(source,path.join(project.directory,relative),fs.constants.COPYFILE_EXCL);
 scene.checkpoints.push({id:cpId,path:relative,...original,parent:null,stage:'world',audit});scene.current=cpId;scene.stage='action';scene.completed={world:cpId};await app.store.save(project,project.revision);
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});page=await browser.newPage({viewport:{width:1440,height:1100},serviceWorkers:'block'});page.setDefaultTimeout(30000);
 const safe=value=>String(value).replaceAll(app.token,'[REDACTED]');page.on('pageerror',e=>report.errors.push(safe(e.message)));page.on('console',m=>{if(m.type()==='error')report.errors.push(safe(m.text()));});page.on('dialog',d=>d.dismiss());
 const models=[];page.on('request',r=>{if(r.url().startsWith(app.origin+'/'))report.requests.push({path:new URL(r.url()).pathname,method:r.method()});else if(/^https?:/.test(r.url()))report.errors.push('Unexpected external request');});
 page.on('response',r=>{if(new URL(r.url()).pathname==='/api/workbench/viewer-model'&&r.ok())void r.body().then(bytes=>models.push(bytes));});
 const idle=()=>page.waitForFunction(()=>!document.body.classList.contains('working'));
 const click=async selector=>{await page.locator('body').ariaSnapshot();await page.locator(selector).click();await idle();};
 const advanced=async()=>{const details=page.locator('details[data-motion-details]');if(!await details.evaluate(node=>node.open))await click('details[data-motion-details] > summary');};
 const ready=()=>page.waitForFunction(()=>!document.body.classList.contains('working')&&document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready'&&!document.querySelector('[data-action-field="performer"]')?.disabled,null,{timeout:205000});
 const inspect=async()=>{project=await app.store.get(project.id);const s=project.workbench.scenes[0],cp=s.checkpoints.find(c=>c.id===s.current);const run=(await app.store.runs(project.id)).find(r=>r.action==='action-audit'&&r.checkpointId===cp.id&&r.state==='SUCCEEDED');assert(run);return {s,cp,run};};
 await page.goto(app.origin+'/workbench#'+app.token);await idle();await click('[data-action="project"][data-id="'+project.id+'"]');await ready();
 assert.deepEqual(report.errors,[]);await page.screenshot({path:path.join(out,'01-loaded.png'),fullPage:true});report.checks.push('Authenticated app loads meaningful Action controls and real saved geometry without console errors');
 await click('[data-action="motion-enable"]');await page.getByLabel('Performer',{exact:true}).selectOption('TimelineRig0');await idle();
 const take=await page.locator('[data-motion-add] option').nth(1).getAttribute('value');await page.getByLabel('Add animation').selectOption(take);await page.locator('[data-motion-field="travel"]').check();
 const handle=page.getByRole('button',{name:'Move path endpoint',exact:true});await handle.waitFor({state:'visible'});await page.screenshot({path:path.join(out,'02-arrow.png'),fullPage:true});
 const distance=page.getByLabel('Distance (m)',{exact:true}),prior=await distance.inputValue();await handle.scrollIntoViewIfNeeded();const box=await handle.boundingBox();assert(box);await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2+36,box.y+box.height/2+12,{steps:8});await page.mouse.up();assert.notEqual(await distance.inputValue(),prior);
 await click('[data-action="action-undo"]');assert.equal(await distance.inputValue(),prior);await handle.focus();await handle.press('ArrowRight');assert.notEqual(await distance.inputValue(),prior);await click('[data-action="action-undo"]');
 report.checks.push('Red endpoint supports actual pointer drag and keyboard adjustment; each gesture undoes as one edit');
 await distance.fill('5');await page.getByLabel('Metres per cycle',{exact:true}).fill('2.5');assert.equal(await page.locator('[data-action="action-save"]').isDisabled(),true);
 await page.getByLabel('Direction (world degrees)',{exact:true}).fill('-90');await page.locator('[data-motion-field="repeat_reviewed"]').check();await idle();assert.equal(await page.locator('[data-action="action-save"]').isEnabled(),true);assert.match(await page.locator('[data-motion-duration]').innerText(),/Frames 1–49/);
 await page.getByLabel('Add animation').selectOption(take);await page.locator('body').ariaSnapshot();
 // Keep this journey's original hard-cut/ripple coverage. The separate
 // connection journey verifies the new default bridge and its saved geometry.
 await page.locator('[data-motion-field="smooth"]').uncheck();await page.locator('[data-motion-field="travel"]').uncheck();assert.match(await page.locator('[data-motion-duration]').innerText(),/Frames 50–74/);
 await page.getByLabel('Performer',{exact:true}).selectOption('TimelineRig1');const take2=await page.locator('[data-motion-add] option').nth(1).getAttribute('value');await page.getByLabel('Add animation').selectOption(take2);await page.locator('[data-motion-field="travel"]').uncheck();assert.match(await page.locator('[data-motion-duration]').innerText(),/Frames 1–25/);
 assert.equal(report.requests.filter(r=>r.path.endsWith('/action-save')).length,0);report.checks.push('Distance drives clip occupancy, next clip appends, other character keeps its independent track; no jobs while drafting');
 await page.screenshot({path:path.join(out,'03-timeline-draft.png'),fullPage:true});
 await page.locator('[data-action="action-save"]').click();await ready();const first=await inspect();assert.notEqual(first.cp.id,cpId);assert.deepEqual(first.s.completed,{world:cpId});
 const rig=first.run.inspection.performers.find(p=>p.name==='TimelineRig0');assert.equal(rig.timeline.clips.length,2);assert.deepEqual(rig.timeline.clips[0].travel.delta_m.map(v=>Math.round(v)),[0,-5]);assert.equal(rig.timeline.clips[1].start,50);assert.equal(report.requests.filter(r=>r.path.endsWith('/action-save')).length,1);report.checks.push('One pointer Save reaches real Blender, publishes an unapproved checkpoint and reopens the exact two-character timeline');
 assert.equal(await page.getByLabel('Performer',{exact:true}).inputValue(),'TimelineRig1');assert.match(await page.locator('.motion-next').innerText(),/frame 26/);assert.match(await page.locator('[data-view="clock"]').innerText(),/Frame 26 /);report.checks.push('Successful Save retains the selected character and advances to its next unoccupied frame');
 await page.reload();await ready();assert.equal(await page.locator('[data-motion-tracks]').count(),1);assert.equal(await page.locator('.motion-clip').count(),3);await page.screenshot({path:path.join(out,'04-saved.png'),fullPage:true});
 await page.locator('[data-view="play"]').click();await page.waitForFunction(()=>Number(document.querySelector('[data-view="time"]').value)>.3);await page.locator('[data-view="play"]').click();assert.equal(await page.locator('[data-view="play"]').innerText(),'Play');
 await page.getByLabel('Animation time',{exact:true}).press('End');assert.match(await page.locator('[data-view="clock"]').innerText(),/Frame 250 /);await page.screenshot({path:path.join(out,'04b-playback-end.png'),fullPage:true});await page.getByLabel('Animation time',{exact:true}).press('Home');assert.match(await page.locator('[data-view="clock"]').innerText(),/Frame 1 /);report.checks.push('Saved whole-scene playback advances in the browser and the full original frame range remains scrubbable');
 const originalMovie=await fileHash(path.join(project.directory,first.cp.path));
 await click('[data-action="motion-select"][data-performer="TimelineRig0"][data-clip="'+rig.timeline.clips[0].id+'"]');
 await page.getByLabel('Distance (m)',{exact:true}).fill('2.5');await advanced();await click('[data-action="motion-ripple"]');
 await click('[data-action="action-save"]');await ready();const second=await inspect();assert.notEqual(second.cp.id,first.cp.id);const changed=second.run.inspection.performers.find(p=>p.name==='TimelineRig0');assert.equal(changed.timeline.clips[0].frames,25);assert.equal(changed.timeline.clips[1].start,26);assert.deepEqual(await fileHash(path.join(project.directory,first.cp.path)),originalMovie);report.checks.push('Reload preserves editable clips; revision and explicit ripple create a separate checkpoint without overwriting the previous result');
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'05-mobile.png'),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(await fileHash(source),original);assert.deepEqual(await fileHash(path.join(project.directory,relative)),original);assert.deepEqual(report.errors,[]);assert(models.length>=3);report.checks.push('Actual saved GLBs refresh, narrow layout stays usable, original bytes preserved, no external requests or console errors');
 report.status='PASS';report.projectId=project.id;report.checkpoints=[cpId,first.cp.id,second.cp.id];
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;if(page)await page.screenshot({path:path.join(out,'FAILURE.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error}));}
