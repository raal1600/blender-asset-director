/** Synthetic browser -> authenticated API -> native Blender -> saved playback. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {randomUUID} from 'node:crypto';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,generated,python,blender,playwright].every(x=>x&&path.isAbsolute(x)));
assert(!await exists(out));const native=await json(path.join(generated,'RESULTS.json'));assert.equal(native.status,'PASS');assert.equal(native.input_kind,'GENERATED');
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),source=path.join(generated,'source.blend'),original=await fileHash(source);
const report={kind:'generated-motion-stitch-browser',checks:[],errors:[],requests:[],not_tested:['Live runtime','Human performance/contact approval','Foot locking or terrain adaptation']};
let app,browser,page;
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const job=await app.runtime.harness(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await app.runtime.harness(['job-run',job.id,'--blender',blender]));
 let project=await app.store.create('Synthetic clip connections','Generated non-human joint motion only');await app.workbench.create(project.id,project.revision,'Connected movement');project=await app.store.get(project.id);
 const scene=project.workbench.scenes[0],cpId='cp_'+randomUUID(),relative='Scenes/'+cpId+'.blend';await fs.copyFile(source,path.join(project.directory,relative),fs.constants.COPYFILE_EXCL);
 scene.checkpoints.push({id:cpId,path:relative,...original,parent:null,stage:'world',audit});scene.current=cpId;scene.stage='action';scene.completed={world:cpId};await app.store.save(project,project.revision);
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});page=await browser.newPage({viewport:{width:1440,height:1100},serviceWorkers:'block'});page.setDefaultTimeout(30000);
 const safe=v=>String(v).replaceAll(app.token,'[REDACTED]');page.on('pageerror',e=>report.errors.push(safe(e.message)));page.on('console',m=>{if(m.type()==='error')report.errors.push(safe(m.text()));});page.on('dialog',d=>d.dismiss());
 page.on('request',r=>{if(r.url().startsWith(app.origin+'/'))report.requests.push({path:new URL(r.url()).pathname,method:r.method()});else if(/^https?:/.test(r.url()))report.errors.push('Unexpected external request');});
 const ready=()=>page.waitForFunction(()=>!document.body.classList.contains('working')&&document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready'&&!document.querySelector('[data-action-field="performer"]')?.disabled,null,{timeout:205000});
 const snapshot=()=>page.locator('body').ariaSnapshot();
 const click=async selector=>{await snapshot();await page.locator(selector).click();await page.waitForFunction(()=>!document.body.classList.contains('working'));};
 const field=name=>page.locator('[data-motion-field="'+name+'"]');
 const advanced=async()=>{const details=page.locator('details[data-motion-details]');if(!await details.evaluate(node=>node.open))await click('details[data-motion-details] > summary');};
 const checkLayout=async(width,height,name)=>{
  await page.setViewportSize({width,height});await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));await snapshot();
  const viewer=await page.locator('[data-scene-viewer]').boundingBox(),inspector=await page.locator('[data-motion-inspector]').boundingBox(),timeline=await page.locator('[data-motion-tracks]').boundingBox();assert(viewer&&inspector&&timeline);
  const canvas=await page.locator('[data-scene-viewer] .viewer-canvas').boundingBox(),endpoint=await page.getByRole('button',{name:'Move path endpoint',exact:true}).boundingBox();assert(canvas&&endpoint,'Pending path has an accessible endpoint after resizing');
  const center={x:endpoint.x+endpoint.width/2-canvas.x,y:endpoint.y+endpoint.height/2-canvas.y};assert(center.x>0&&center.x<canvas.width&&center.y>0&&center.y<canvas.height,'Endpoint is inside the resized canvas');
  const projection={x:(center.x-canvas.width/2)/canvas.height,y:(center.y-canvas.height/2)/canvas.height};
  // With unchanged perspective camera/orbit, pixel offsets scale with canvas
  // height. This catches stale DOM handles after the WebGL projection resizes.
  const previous=report.layouts?.[0]?.projection;if(previous){assert(Math.abs(projection.x-previous.x)<.006,'Endpoint X tracks the resized camera projection');assert(Math.abs(projection.y-previous.y)<.006,'Endpoint Y tracks the resized camera projection');}
  const order=await page.evaluate(()=>!!(document.querySelector('[data-scene-viewer]').compareDocumentPosition(document.querySelector('[data-motion-inspector]'))&Node.DOCUMENT_POSITION_FOLLOWING));assert.equal(order,true,'Viewer must precede the inspector in reading order');
  if(width>=1000){assert(inspector.x>=viewer.x+viewer.width-2,'Desktop inspector belongs beside the viewer');assert(Math.abs(inspector.y-viewer.y)<8,'Desktop viewer and inspector share a top edge');assert(viewer.width>inspector.width,'Viewer remains the primary desktop surface');assert(Math.abs(timeline.x-viewer.x)<8,'Timeline aligns under the desktop viewer');}
  else assert(inspector.y>=viewer.y+viewer.height-2,'Narrow layout puts the viewer before clip settings');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'No page-level horizontal overflow');
  assert.equal(await page.locator('details[data-motion-details]').evaluate(node=>node.open),false,'Advanced timing is collapsed by default');
  await page.locator('[data-scene-viewer]').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,name),fullPage:true});
  (report.layouts??=[]).push({width,height,viewer,inspector,timeline,canvas,endpoint,projection});
 };
 await page.goto(app.origin+'/workbench#'+app.token);await click('[data-action="project"][data-id="'+project.id+'"]');await ready();await click('[data-action="motion-enable"]');
 await snapshot();await page.getByLabel('Performer',{exact:true}).selectOption('TestPerformer0');
 await snapshot();await page.getByLabel('Add animation').selectOption({label:'Observed 0 0'});await field('travel').check();await snapshot();await page.getByLabel('Metres per cycle',{exact:true}).fill('1');await page.getByLabel('Direction (world degrees)',{exact:true}).fill('-90');
 await snapshot();await page.getByLabel('Add animation').selectOption({label:'Observed 0 1'});
 assert.equal(await field('smooth').isChecked(),true);assert.equal(await field('repeat_reviewed').isChecked(),false);assert.equal(await field('repeat_reviewed').isVisible(),true);
 assert.equal(await page.getByRole('button',{name:'Connection 26 to 31',exact:true}).count(),1);assert.match(await page.locator('[data-motion-duration]').innerText(),/Frames 32–56/);
 report.checks.push('Compatible native clips append with a visible six-frame connection and no invented loop approval');
 await field('travel').check();
 // Reproduce an uncalibrated connected clip: geometric editing must not depend
 // on a bridge that cannot yet be validated or executed.
 const pace=page.getByLabel('Metres per cycle',{exact:true}),distance=page.getByLabel('Distance (m)',{exact:true}),handle=page.getByRole('button',{name:'Move path endpoint',exact:true});
 assert.equal(await pace.inputValue(),'');assert.equal(await pace.isVisible(),true);assert.equal(await pace.getAttribute('aria-invalid'),'true');assert.equal(await page.locator('[data-action="action-save"]').isDisabled(),true);
 assert.match(await page.locator('[data-motion-error="pace"]').innerText(),/Set metres per cycle to calibrate this path, or turn off path movement\./);assert.match(await page.locator('.action-savebar [role="status"]').innerText(),/metres per cycle/i);assert(await pace.getAttribute('aria-describedby'));await handle.waitFor({state:'visible'});assert.match(await page.locator('[data-motion-path]').innerText(),/connection placement pending/i);
 const pendingPosts=report.requests.filter(r=>r.method==='POST').length,pendingRuns=(await app.store.runs(project.id)).length,priorDistance=await distance.inputValue();
 await handle.scrollIntoViewIfNeeded();await handle.focus();await handle.press('ArrowRight');assert.notEqual(await distance.inputValue(),priorDistance);assert.equal(await page.locator('[data-action="action-save"]').isDisabled(),true);await click('[data-action="action-undo"]');assert.equal(await distance.inputValue(),priorDistance);
 await handle.scrollIntoViewIfNeeded();const endpoint=await handle.boundingBox();assert(endpoint);await page.mouse.move(endpoint.x+endpoint.width/2,endpoint.y+endpoint.height/2);await page.mouse.down();await page.mouse.move(endpoint.x+endpoint.width/2+30,endpoint.y+endpoint.height/2+12,{steps:8});await page.mouse.up();assert.notEqual(await distance.inputValue(),priorDistance);await click('[data-action="action-undo"]');assert.equal(await distance.inputValue(),priorDistance);
 assert.equal(report.requests.filter(r=>r.method==='POST').length,pendingPosts);assert.equal((await app.store.runs(project.id)).length,pendingRuns);assert.equal(await page.locator('[data-action="action-save"]').isDisabled(),true);
 await checkLayout(1440,1100,'00-pending-connection-desktop.png');await checkLayout(1440,900,'00-pending-connection-short-desktop.png');await checkLayout(390,844,'00-pending-connection-narrow.png');await page.setViewportSize({width:1440,height:1100});
 report.checks.push('Missing connected-clip calibration keeps a visible provisional red path editable by pointer and keyboard; pace errors block Save without mutation jobs');
 report.checks.push('Viewer-first desktop and mobile layouts retain a compact inspector, collapsed advanced timing and no page overflow');
 await pace.fill('1');await page.getByLabel('Direction (world degrees)',{exact:true}).fill('0');assert.match(await page.locator('[data-motion-pace]').innerText(),/^Manual pace ·/);assert.doesNotMatch(await page.locator('[data-motion-pace]').innerText(),/needed/i);
 assert.equal(await page.locator('[data-action="action-save"]').isEnabled(),true);assert.match(await page.locator('[data-motion-connection]').innerText(),/0\.21 m/);
 await page.getByLabel('Direction (world degrees)',{exact:true}).fill('90');assert.equal(await page.locator('[data-action="action-save"]').isDisabled(),true);assert.match(await page.locator('[data-motion-errors]').innerText(),/turn or stop/);
 await page.getByLabel('Direction (world degrees)',{exact:true}).fill('0');assert.equal(await page.locator('[data-action="action-save"]').isEnabled(),true);
 report.checks.push('Measured path velocities expose added distance; a sharp reversal refuses before any job executes');
 await advanced();await page.getByLabel('Transition frames',{exact:true}).fill('');assert.equal(await page.locator('[data-action="action-save"]').isDisabled(),true);assert.equal(await field('transition_frames').getAttribute('aria-invalid'),'true');
 await page.getByLabel('Transition frames',{exact:true}).fill('10');await page.getByLabel('Speed',{exact:true}).focus();assert.match(await page.locator('[data-motion-duration]').innerText(),/Frames 36–60/);
 await click('[data-action="action-undo"]');assert.match(await page.locator('[data-motion-duration]').innerText(),/Frames 32–56/);
 await advanced();await field('smooth').uncheck();assert.equal(await page.locator('.motion-transition').count(),0);assert.match(await page.locator('[data-motion-duration]').innerText(),/Frames 26–50/);assert.equal(await page.locator('details[data-motion-details]').evaluate(node=>node.open),true);await field('smooth').check();assert.equal(await page.locator('details[data-motion-details]').evaluate(node=>node.open),true);
 report.checks.push('Transition duration is editable, raw errors stay visible, Undo restores timing and a hard cut remains available');
 await page.getByRole('button',{name:'Observed 0 0 frames 1 to 25',exact:true}).click();await snapshot();await page.getByLabel('Distance (m)',{exact:true}).fill('2');
 assert.equal(await page.getByRole('button',{name:'Connection 50 to 55',exact:true}).count(),1);assert.equal(await page.locator('[data-action="action-save"]').isDisabled(),true);
 // Generated mathematical loop only; never an answer to a human review request.
 await field('repeat_reviewed').check();assert.equal(await page.locator('[data-action="action-save"]').isEnabled(),true);await page.getByLabel('Distance (m)',{exact:true}).fill('1');
 await page.getByRole('button',{name:'Observed 0 1 frames 32 to 56',exact:true}).click();await snapshot();await field('repeat_reviewed').check();
 assert.equal(report.requests.filter(r=>r.path.endsWith('/action-save')).length,0);await page.screenshot({path:path.join(out,'01-connected-draft.png'),fullPage:true});
 report.checks.push('Changing an earlier distance ripples connected clips; repeated cycles need explicit synthetic review; drafts stay local');
 await click('[data-action="action-save"]');await ready();project=await app.store.get(project.id);
 const saved=project.workbench.scenes[0],cp=saved.checkpoints.find(c=>c.id===saved.current);assert.notEqual(cp.id,cpId);assert.deepEqual(saved.completed,{world:cpId});
 const run=(await app.store.runs(project.id)).find(r=>r.action==='action-audit'&&r.checkpointId===cp.id&&r.state==='SUCCEEDED');assert(run);const rig=run.inspection.performers.find(p=>p.name==='TestPerformer0');
 assert.equal(rig.timeline.clips.length,2);const join=rig.timeline.connections[0];assert(join.matched_phase>.65&&join.matched_phase<.85);assert(Math.abs(join.phase-(join.matched_phase+join.duration_frames/24)%1)<1e-6);assert(join.match_cost_after<join.match_cost_before*.1);assert.equal(join.contact_acceptance,'NOT_EVALUATED');
 assert.equal(report.requests.filter(r=>r.path.endsWith('/action-save')).length,1);report.checks.push('One Save executes real Blender, verifies the measured phase bridge and creates an unapproved separate checkpoint');
 await page.reload();await ready();assert.equal(await page.locator('.motion-clip').count(),2);assert.equal(await page.locator('.motion-transition').count(),1);
 await page.locator('[data-view="play"]').click();await page.waitForFunction(()=>Number(document.querySelector('[data-view="time"]').value)>1.3);await page.locator('[data-view="play"]').click();
 await page.screenshot({path:path.join(out,'02-saved-playback.png'),fullPage:true});report.checks.push('Reload retains connection occupancy and plays the actual saved scene through the join');
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Observed 0 1 frames 32 to 56',exact:true}).click();await snapshot();await page.screenshot({path:path.join(out,'03-narrow.png'),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(await fileHash(source),original);assert.deepEqual(await fileHash(path.join(project.directory,relative)),original);assert.deepEqual(report.errors,[]);
 report.checks.push('Source bytes and previous checkpoint remain intact; no narrow overflow, external requests or browser errors');report.status='PASS';report.projectId=project.id;report.checkpoint={id:cp.id,sha256:cp.sha256};report.join=join;
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;if(page)await page.screenshot({path:path.join(out,'FAILURE.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error}));}
