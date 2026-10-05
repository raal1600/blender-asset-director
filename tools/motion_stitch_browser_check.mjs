/** Synthetic browser -> authenticated API -> native Blender -> saved playback. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {randomUUID} from 'node:crypto';
import {spawn} from 'node:child_process';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome,installedRoot]=process.argv.slice(2);
assert(!installedRoot||path.isAbsolute(installedRoot));
assert([out,generated,python,blender,playwright].every(x=>x&&path.isAbsolute(x)));
assert(!await exists(out));const native=await json(path.join(generated,'RESULTS.json'));assert.equal(native.status,'PASS');assert.equal(native.input_kind,'GENERATED');
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),source=path.join(generated,'source.blend'),original=await fileHash(source);
const report={kind:'generated-motion-stitch-browser',runtime:installedRoot?'installed-normal-entrypoint':'source-application-instance',checks:[],errors:[],requests:[],failed_requests:[],boundary_frames:[],not_tested:['Live Blender desktop session','Human performance/contact approval','Foot locking or terrain adaptation']};
let app,browser,context,page,serverProcess,serverLog,serverCount=0,decision=null;
const studio=installedRoot||path.join(out,'Studio');
const config=installedRoot?await json(path.join(studio,'SystemRuntime/UserData/Launcher/config.json')):{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(studio,'Database/AssetDirector')};
const factory=installedRoot?(await import(pathToFileURL(path.join(studio,'SystemRuntime/Launcher/server.mjs')).href)).createApp:createApp;
const startApp=async()=>{app=await factory({root:studio,port:0,config});};
const stopApp=async()=>{
 if(serverProcess){const proc=serverProcess;serverProcess=null;if(proc.exitCode===null){const stopped=new Promise(resolve=>proc.once('exit',resolve));proc.kill();await Promise.race([stopped,new Promise((_,reject)=>setTimeout(()=>reject(Error('Owned launcher did not stop')),5000))]);}await serverLog?.close();serverLog=null;}
 if(app?.server.listening){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}
};
const startInstalled=async()=>{
 serverLog=await fs.open(path.join(out,'installed-server-'+(++serverCount)+'.log'),'wx');
 serverProcess=spawn(process.execPath,[path.join(studio,'SystemRuntime/Launcher/server.mjs'),studio],{windowsHide:true,stdio:['ignore',serverLog.fd,serverLog.fd]});
 const deadline=Date.now()+60000;let session;
 while(Date.now()<deadline){assert.equal(serverProcess.exitCode,null,'Installed launcher exited during startup');try{session=await json(path.join(studio,'SystemRuntime/UserData/Launcher/session.json'));if(session.pid===serverProcess.pid)break;}catch{}await new Promise(resolve=>setTimeout(resolve,100));}
 assert.equal(session?.pid,serverProcess.pid,'Installed launcher did not publish its normal session');app.origin=session.origin;app.token=session.token;
};
try{
 await startApp();
 if(installedRoot)assert.equal((await app.store.list()).projects.length,0,'Installed acceptance requires a clean isolated studio');
 const job=await app.runtime.harness(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await app.runtime.harness(['job-run',job.id,'--blender',blender]));
 let project=await app.store.create('Synthetic clip connections','Generated non-human joint motion only');await app.workbench.create(project.id,project.revision,'Connected movement');project=await app.store.get(project.id);
 const scene=project.workbench.scenes[0],cpId='cp_'+randomUUID(),relative='Scenes/'+cpId+'.blend';await fs.copyFile(source,path.join(project.directory,relative),fs.constants.COPYFILE_EXCL);
 scene.checkpoints.push({id:cpId,path:relative,...original,parent:null,stage:'world',audit});scene.current=cpId;scene.stage='action';scene.completed={world:cpId};await app.store.save(project,project.revision);
 if(installedRoot){await stopApp();await startInstalled();}
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});context=await browser.newContext({viewport:{width:1440,height:1100},serviceWorkers:'block',recordVideo:{dir:path.join(out,'video'),size:{width:1440,height:1100}}});page=await context.newPage();page.setDefaultTimeout(30000);
 const safe=v=>String(v).replaceAll(app.token,'[REDACTED]');page.on('pageerror',e=>report.errors.push(safe(e.message)));page.on('console',m=>{if(m.type()==='error')report.errors.push(safe(m.text()));});page.on('dialog',async d=>{const expected=decision;decision=null;if(!expected||!expected.test(d.message())){report.errors.push('Unexpected decision: '+d.message());await d.dismiss();return;}(report.decisions??=[]).push({prompt:d.message(),scripted:true,scope:'GENERATED_FIXTURE_ONLY'});await d.accept();});
 page.on('request',r=>{if(r.url().startsWith(app.origin+'/'))report.requests.push({path:new URL(r.url()).pathname,method:r.method()});else if(/^https?:/.test(r.url()))report.errors.push('Unexpected external request');});
 page.on('response',r=>{if(r.status()>=400)report.failed_requests.push({path:new URL(r.url()).pathname,status:r.status()});});
 page.on('requestfailed',r=>{if(!r.failure()?.errorText?.includes('ERR_ABORTED'))report.failed_requests.push({path:new URL(r.url()).pathname,error:safe(r.failure()?.errorText)});});
 const ready=()=>page.waitForFunction(()=>!document.body.classList.contains('working')&&document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready'&&!document.querySelector('[data-action-field="performer"]')?.disabled,null,{timeout:205000});
 const snapshot=()=>page.locator('body').ariaSnapshot();
 const click=async selector=>{await snapshot();await page.locator(selector).click();await page.waitForFunction(()=>!document.body.classList.contains('working'));};
 const choose=async(pattern,selector)=>{assert.equal(decision,null);decision=pattern;await click(selector);assert.equal(decision,null,'Expected the visible scoped confirmation');};
 const settle=async()=>{const deadline=Date.now()+300000;while(Date.now()<deadline){const p=await app.store.get(project.id);if(!p.workbench.scenes.some(s=>s.run)){const runs=await app.store.runs(project.id);const failures=runs.filter(r=>['FAILED','INTERRUPTED'].includes(r.state)).map(({id,action,state,error})=>({id,action,state,error}));assert.deepEqual(failures,[]);await click('.projectbar [data-action="refresh"]');return p;}await new Promise(resolve=>setTimeout(resolve,200));}throw Error('Bounded native output did not settle');};
 const field=name=>page.locator('[data-motion-field="'+name+'"]');
 const seek=async frame=>{
  // Native range inputs do not support Playwright fill. Dispatch their normal
  // input event; the production viewer handles seeking and renders the frame.
  await page.locator('[data-view="time"]').evaluate((node,time)=>{node.value=String(time);node.dispatchEvent(new Event('input',{bubbles:true}));},(frame-1)/24);
  await page.waitForFunction(frame=>document.querySelector('[data-view="clock"]').textContent.includes('Frame '+frame+' '),frame);
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 };
 const boundaries=async(join,label)=>{
  await page.locator('[data-scene-viewer]').scrollIntoViewIfNeeded();
  for(const frame of [...new Set([join.start-2,join.start-1,join.start,join.start+1,join.end-1,join.end,join.end+1,join.end+2])]){
   await seek(frame);const filename=label+'-frame-'+String(frame).padStart(4,'0')+'.png';await page.locator('[data-scene-viewer]').screenshot({path:path.join(out,filename)});report.boundary_frames.push({label,frame,file:filename});
  }
  await seek(join.start-2);await page.locator('[data-view="play"]').click();
  await page.waitForFunction(time=>Number(document.querySelector('[data-view="time"]').value)>time,(join.end+2-1)/24);
  await page.locator('[data-view="play"]').click();
 };

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
 assert.match(await page.locator('[data-motion-provider]').innerText(),/Blender native: deterministic pose blend/);
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
 await click('[data-action="motion-select-transition"]');await page.getByLabel('Transition frames',{exact:true}).fill('');assert.equal(await page.locator('[data-action="action-save"]').isDisabled(),true);assert.equal(await field('transition_frames').getAttribute('aria-invalid'),'true');
 await page.getByLabel('Transition frames',{exact:true}).fill('10');await click('[data-action="motion-select-clip"]');assert.match(await page.locator('[data-motion-duration]').innerText(),/Frames 36–60/);
 await click('[data-action="action-undo"]');await click('[data-action="motion-select-clip"]');assert.match(await page.locator('[data-motion-duration]').innerText(),/Frames 32–56/);
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
 const savedPreview=await page.locator('[data-scene-viewer]').getAttribute('data-preview-id');assert(savedPreview);
 await boundaries(join,'01-saved-boundary');
 await page.reload();await ready();assert.equal(await page.locator('.motion-clip').count(),2);assert.equal(await page.locator('.motion-transition').count(),1);
 await page.locator('[data-view="play"]').click();await page.waitForFunction(()=>Number(document.querySelector('[data-view="time"]').value)>1.3);await page.locator('[data-view="play"]').click();
 await page.screenshot({path:path.join(out,'02-saved-playback.png'),fullPage:true});report.checks.push('Reload retains connection occupancy and plays the actual saved scene through the join');
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Observed 0 1 frames 32 to 56',exact:true}).click();await snapshot();await page.screenshot({path:path.join(out,'03-narrow.png'),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.setViewportSize({width:1440,height:1100});
 const oldToken=app.token;await page.goto('about:blank');await stopApp();if(installedRoot)await startInstalled();else await startApp();assert.notEqual(app.token,oldToken);
 await page.goto(app.origin+'/workbench#'+app.token);await click('[data-action="project"][data-id="'+project.id+'"]');await ready();
 assert.equal(await page.locator('.motion-clip').count(),2);assert.equal(await page.locator('.motion-transition').count(),1);
 assert.equal(await page.locator('[data-scene-viewer]').getAttribute('data-preview-id'),savedPreview,'Unchanged saved source reuses its verified preview across restart');
 await boundaries(join,'02-reopened-boundary');report.checks.push('Application restart reopens saved clips, reuses the exact verified artifact and replays both stitch boundaries');
 await page.getByRole('button',{name:'Connection 26 to 31',exact:true}).click();await page.getByLabel('Transition frames',{exact:true}).fill('10');
 assert.match(await page.locator('[data-motion-provider]').innerText(),/Blender native: deterministic pose blend/);
 await click('[data-action="action-save"]');await ready();project=await app.store.get(project.id);
 const revisedScene=project.workbench.scenes[0],revised=revisedScene.checkpoints.find(c=>c.id===revisedScene.current),revisedRun=(await app.store.runs(project.id)).find(r=>r.action==='action-audit'&&r.checkpointId===revised.id&&r.state==='SUCCEEDED');
 assert.notEqual(revised.id,cp.id);assert.notEqual(revised.sha256,cp.sha256);assert(revisedRun);
 const revisedJoin=revisedRun.inspection.performers.find(p=>p.name==='TestPerformer0').timeline.connections[0];assert.equal(revisedJoin.end,36);
 const revisedPreview=await page.locator('[data-scene-viewer]').getAttribute('data-preview-id');assert.notEqual(revisedPreview,savedPreview,'Changed transition cannot reuse the earlier preview');
 await boundaries(revisedJoin,'03-revised-boundary');
 assert.equal((await fileHash(path.join(project.directory,cp.path))).sha256,cp.sha256,'Earlier saved transition remains immutable');
 report.checks.push('Changing duration creates a new immutable Blender checkpoint and preview; revised result plays across both boundaries');
 report.output_blend=path.join(project.directory,revised.path);report.previous_output_blend=path.join(project.directory,cp.path);report.revised_checkpoint={id:revised.id,sha256:revised.sha256};report.revised_join=revisedJoin;report.preview_ids={saved:savedPreview,revised:revisedPreview};report.studio=studio;
 if(installedRoot&&config.ffmpeg&&config.ffprobe){
  assert(audit.objects.some(o=>o.type==='CAMERA'&&o.name==='Synthetic transition camera'),'Render acceptance requires the generated transition camera fixture');
  await choose(/reviewed this exact saved performance/, '[data-action="action-ready"]');
  await click('[data-action="new-shot"]');await page.locator('#shot-name').fill('Synthetic transition boundaries');await page.locator('#shot-camera').selectOption('Synthetic transition camera');await page.locator('#shot-start').fill(String(revisedJoin.start-3));await page.locator('#shot-end').fill(String(revisedJoin.end+3));await click('[data-action="save-shot"]');
  await page.waitForFunction(()=>document.querySelector('[data-action="layer-ready"]')?.disabled===false,null,{timeout:205000});await choose(/every named shot/, '[data-action="layer-ready"]');
  await page.locator('[data-action="preview"]').waitFor();await click('[data-action="preview"]');await page.locator('#preview-frame').fill(String(revisedJoin.start));await click('[data-action="save-preview"]');await settle();
  await page.waitForFunction(()=>document.querySelector('[data-action="layer-ready"]')?.disabled===false,null,{timeout:205000});await choose(/reviewed real lighting/, '[data-action="layer-ready"]');
  await click('[data-action="readiness"]');await settle();
  for(const [name,value] of [['width','320'],['height','240'],['samples','1']])await page.locator('#render-'+name).fill(value);
  assert.equal(await page.locator('#render-device').inputValue(),'0');await choose(/^Authorize CPU render/, '[data-action="render"]');project=await settle();
  const movie=project.workbench.scenes[0].renders.at(-1),count=revisedJoin.end-revisedJoin.start+7;
  assert.equal(movie.checkpointId,revised.id);assert.equal(movie.video.frames,count);assert.equal(movie.video.state,'SUCCEEDED');assert.equal(movie.data.render_device.backend,'CPU');
  const selector='video[aria-label="Rendered shot movie"]';assert.equal(await page.locator(selector).getAttribute('data-id'),movie.id);
  await page.waitForFunction(selector=>{const v=document.querySelector(selector);return v&&v.readyState>=2&&!v.error;},selector);await page.locator(selector).evaluate(v=>{v.muted=true;v.currentTime=0;return v.play();});await page.waitForFunction(selector=>document.querySelector(selector)?.ended===true,selector);
  const movieFile=path.join(project.directory,'Deliverables',movie.video.plan.id,'film.mp4');assert.equal((await fileHash(movieFile)).sha256,movie.video.sha256);
  const job=await app.runtime.job(movie.jobId),frames=job.outputs.filter(x=>/frame_\d+\.png$/.test(x.path));assert.equal(frames.length,count);assert(new Set(frames.map(x=>x.sha256)).size>1,'Rendered transition must change actual pixels');
  report.render={id:movie.id,checkpointId:movie.checkpointId,jobId:movie.jobId,file:movieFile,sha256:movie.video.sha256,frames:count,start:revisedJoin.start-3,end:revisedJoin.end+3,device:movie.data.render_device,frame_evidence:frames,browser_playback:'PASS',human_acceptance:'NOT_TESTED'};
  await page.screenshot({path:path.join(out,'04-rendered-boundaries.png'),fullPage:true});report.checks.push('Visible shot, lighting preview and explicit CPU render controls produce and browser-play the exact saved transition across both boundaries');
 }else report.not_tested.push('Rendered transition: provide a clean installed studio with configured FFmpeg/FFprobe and the generated camera fixture');
 assert.deepEqual(await fileHash(source),original);assert.deepEqual(await fileHash(path.join(project.directory,relative)),original);assert.deepEqual(report.errors,[]);assert.deepEqual(report.failed_requests,[]);
 report.checks.push('Source bytes and previous checkpoint remain intact; no narrow overflow, external requests or browser errors');report.status='PASS';report.projectId=project.id;report.checkpoint={id:cp.id,sha256:cp.sha256};report.join=join;
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;if(page)await page.screenshot({path:path.join(out,'FAILURE.png'),fullPage:true}).catch(()=>{});}
finally{if(page?.video())report.video=path.relative(out,await page.video().path());await context?.close();await browser?.close();await stopApp();await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error}));}
