/** Generated-only user journey for timeline seeking and visual body-turn controls. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash,randomUUID} from 'node:crypto';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';

const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,generated,python,blender,playwright].every(v=>v&&path.isAbsolute(v)));
assert(!await exists(out),'Never overwrite earlier test evidence');
const fixture=await json(path.join(generated,'RESULTS.json'));
assert.equal(fixture.status,'PASS');assert.equal(fixture.input_kind,'GENERATED');
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),source=path.join(generated,'source.blend'),original=await fileHash(source);
assert.equal(original.sha256,fixture.source_sha256,'Use the exact generated two-performer source');
const report={kind:'generated-visual-motion-controls-browser',checks:[],errors:[],requests:[],instrumentation:[],
 not_tested:['Live runtime or user projects','Human motion/contact/creative approval','Foot IK or automatic choreography']};
const implementationFiles=['tools/motion_visual_controls_browser_check.mjs','launcher/server.mjs','launcher/public/viewer-3d.mjs',
 'launcher/public/action-rotation-editor.mjs','launcher/public/action-turn-preview.mjs','launcher/public/action-selection.mjs',
 'launcher/public/action-timeline-draft.mjs','launcher/public/action-timeline-view.mjs','launcher/public/workbench.mjs'];
let app,browser,page;
const digest=value=>createHash('sha256').update(value).digest('hex');
try{
 report.tested_files=Object.fromEntries(await Promise.all(implementationFiles.map(async relative=>[relative,await fileHash(path.join(repo,relative))])));
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const auditJob=await app.runtime.harness(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await app.runtime.harness(['job-run',auditJob.id,'--blender',blender]));
 let project=await app.store.create('Synthetic visual turn controls','Generated two-performer geometry and observed native takes only');
 await app.workbench.create(project.id,project.revision,'Visual controls');project=await app.store.get(project.id);
 const scene=project.workbench.scenes[0],cpId='cp_'+randomUUID(),relative='Scenes/'+cpId+'.blend';
 await fs.copyFile(source,path.join(project.directory,relative),fs.constants.COPYFILE_EXCL);
 scene.checkpoints.push({id:cpId,path:relative,...original,parent:null,stage:'world',audit});scene.current=cpId;scene.stage='action';scene.completed={world:cpId};await app.store.save(project,project.revision);
 const {chromium}=await import(pathToFileURL(playwright).href);
 browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});
 const context=await browser.newContext({viewport:{width:1440,height:1060},serviceWorkers:'block'});
 // Observation only: expose references already present in the exact local viewer.
 // No rendering, gesture, pose, timeline, API or persistence logic is replaced.
 await context.route('**/viewer-3d.mjs',async route=>{
  const response=await route.fetch(),body=await response.text(),needle='model=gltf.scene;';
  assert.equal(body.split(needle).length,2,'The read-only observer binds one actual model assignment');
  const observed=body.replace(needle,needle+'globalThis.__badVisualControlsObserver={model,gltf,THREE,GLTFLoader,bytes,get action(){return action;}};');
  report.instrumentation.push({module:'viewer-3d.mjs',original_sha256:digest(body),observed_sha256:digest(observed),
   scope:'One reference-only assignment; all tested behavior unchanged'});
  await route.fulfill({response,body:observed});
 });
 page=await context.newPage();page.setDefaultTimeout(30000);
 const safe=value=>String(value).replaceAll(app.token,'[REDACTED]');
 page.on('pageerror',e=>report.errors.push(safe(e.message)));
 page.on('console',m=>{if(m.type()==='error')report.errors.push(safe(m.text()));});
 page.on('dialog',d=>d.dismiss());
 page.on('request',r=>{if(r.url().startsWith(app.origin+'/'))report.requests.push({path:new URL(r.url()).pathname,method:r.method()});else if(/^https?:/.test(r.url()))report.errors.push('Unexpected external request');});
 page.on('response',r=>{if(r.status()>=400)report.errors.push('HTTP '+r.status()+' '+new URL(r.url()).pathname);});
 const snapshot=()=>page.locator('body').ariaSnapshot();
 const ready=()=>page.waitForFunction(()=>!document.body.classList.contains('working')&&document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready'&&!document.querySelector('[data-action-field="performer"]')?.disabled,null,{timeout:205000});
 const click=async selector=>{await snapshot();await page.locator(selector).click();await page.waitForFunction(()=>!document.body.classList.contains('working'));await snapshot();};
 const field=name=>page.locator(`[data-motion-field="${name}"]`),save=()=>page.locator('[data-action="action-save"]');
 const clips=()=>page.locator('.motion-clip'),joins=()=>page.locator('.motion-transition');
 const rotate=()=>page.getByRole('button',{name:'Rotate character',exact:true});
 const savedRequests=()=>report.requests.filter(r=>r.path.endsWith('/action-save')).length;
 const frame=async()=>Number((await page.locator('[data-view="clock"]').innerText()).match(/^Frame\s+(-?\d+)/)?.[1]);
 const assertFrame=async expected=>{
  await page.waitForFunction(value=>Number(document.querySelector('[data-view="clock"]')?.textContent.match(/^Frame\s+(-?\d+)/)?.[1])===value,expected);
  assert.equal(await frame(),expected);assert.equal(await page.locator('[data-view="play"]').innerText(),'Play','Selection pauses saved playback');
 };
 const saveAndRead=async()=>{
  assert(await save().isEnabled(),'Valid local controls must enable Save');
  const before=(await app.store.get(project.id)).workbench.scenes[0].current,known=new Set((await app.store.runs(project.id)).map(r=>r.id));
  await click('[data-action="action-save"]');await ready();project=await app.store.get(project.id);
  const s=project.workbench.scenes[0],cp=s.checkpoints.find(c=>c.id===s.current),runs=await app.store.runs(project.id);
  const edit=runs.find(r=>r.action==='action-edit'&&!known.has(r.id));assert.equal(edit?.state,'SUCCEEDED',edit?.error||'Real Blender Save did not finish');
  assert.notEqual(cp.id,before);const inspected=runs.find(r=>r.action==='action-audit'&&r.checkpointId===cp.id&&r.state==='SUCCEEDED');assert(inspected);
  assert.deepEqual(s.completed,{world:cpId});return {cp,range:inspected.inspection.frame_range,fps:inspected.inspection.fps,rig:inspected.inspection.performers.find(p=>p.name==='TestPerformer0'),other:inspected.inspection.performers.find(p=>p.name==='TestPerformer1')};
 };
 // Compare actual deformed world vertices with a separately decoded saved GLB.
 // This oracle never mutates the viewer's model or its AnimationMixer.
 const geometry=()=>page.evaluate(async()=>{
  const observed=globalThis.__badVisualControlsObserver;if(!observed)throw Error('Actual viewer model not observed');
  const {THREE}=observed;
  if(globalThis.__badVisualOracle?.observed!==observed){
   const gltf=await new observed.GLTFLoader().parseAsync(observed.bytes.slice(0),'');
   if(gltf.animations.length!==1)throw Error('Expected exact combined saved animation');
   const mixer=new THREE.AnimationMixer(gltf.scene),action=mixer.clipAction(gltf.animations[0]);
   action.setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;action.play();
   globalThis.__badVisualOracle={observed,gltf,mixer,action};
  }
  // Range inputs quantize to their step (0.001 s), whereas the saved mixer may
  // be at exact frame 38 / 24 fps. Compare the same exact source time, not UI rounding.
  const oracle=globalThis.__badVisualOracle,time=observed.action?.time;
  if(!Number.isFinite(time))throw Error('Actual saved mixer time not observed');
  oracle.action.paused=false;oracle.action.time=time;oracle.mixer.update(0);
  const points=gltf=>{
   gltf.scene.updateMatrixWorld(true);gltf.scene.traverse(o=>o.skeleton?.update());const result={};
   for(const name of ['VisibleSkin0','VisibleSkin1']){
    const index=gltf.parser.json.nodes.findIndex(n=>n.name===name);if(index<0)throw Error('Observed mesh is missing: '+name);
    let mesh;gltf.scene.traverse(o=>{if(o.isMesh&&gltf.parser.associations.get(o)?.nodes===index)mesh=o;});
    if(!mesh)throw Error('Actual skinned geometry not found: '+name);
    result[name]=Array.from({length:mesh.geometry.attributes.position.count},(_,i)=>mesh.getVertexPosition(i,new THREE.Vector3()).applyMatrix4(mesh.matrixWorld).toArray());
   }
   return result;
  };
  return {time,slider_time:Number(document.querySelector('[data-view="time"]').value),actual:points(observed.gltf),saved:points(oracle.gltf),status:document.querySelector('[data-motion-turn-status]')?.textContent||''};
 });
 const difference=(a,b)=>{assert.equal(a.length,b.length);return Math.max(...a.map((v,i)=>Math.hypot(...v.map((x,j)=>x-b[i][j]))));};
 const compare=s=>Object.fromEntries(Object.keys(s.actual).map(name=>[name,difference(s.actual[name],s.saved[name])]));
 const recordGeometry=async(name,{changed=false}={})=>{
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const value=await geometry(),error=compare(value);await writeJson(path.join(out,name+'.json'),value);
  assert(error.VisibleSkin1<1e-5,'Unselected performer must match saved geometry');
  assert(changed?error.VisibleSkin0>1e-3:error.VisibleSkin0<1e-5,`Selected geometry ${changed?'must visibly turn':'must match the saved scene'}: ${error.VisibleSkin0}`);
  report.checks.push({name,world_vertex_error:error,time:value.time,status:value.status});return value;
 };
 const assertHeading=async expected=>{
  assert(Math.abs(Number(await field('heading_deg').inputValue())-expected)<.001,'Inspector reflects visual heading');
  const value=await page.locator('[data-motion-heading]').innerText();assert(value.includes(String(Number(expected.toFixed(1)))),'Visible degree output reflects heading: '+value);
 };

 await page.goto(app.origin+'/workbench#'+app.token);await click(`[data-action="project"][data-id="${project.id}"]`);await ready();
 await click('[data-action="motion-enable"]');await page.getByLabel('Performer',{exact:true}).selectOption('TestPerformer0');
 await page.getByLabel('Add animation').selectOption({label:'Observed 0 0'});await field('travel').check();await field('pace').fill('1');await field('direction').fill('-90');
 await page.getByLabel('Add animation').selectOption({label:'Observed 0 1'});await field('travel').check();await field('pace').fill('1');await field('direction').fill('0');
 await joins().first().click();await field('transition_mode').selectOption('turn');await field('transition_frames').fill('12');await field('heading_deg').fill('90');
 const initial=await saveAndRead(),initialHash=await fileHash(path.join(project.directory,initial.cp.path));
 const first=initial.rig.timeline.clips[0],second=initial.rig.timeline.clips[1];assert.equal(second.heading_deg,90);assert(second.transition);
 await page.reload();await ready();
 await clips().first().click();await click('[data-motion-details] > summary');await field('start').fill('100');
 await clips().nth(1).click();await assertFrame(initial.range[1]);
 const clamp=page.locator('[data-view-seek-note]');assert(await clamp.isVisible());
 const clampText=await clamp.innerText();assert.match(clampText,/Draft starts at frame 137/);assert.match(clampText,/Save changes to preview the new timing/);
 assert.equal(await page.locator('.action-preview-scope').count(),1,'Generic playback scope has a separate unique node');
 await field('distance').fill('1.1');assert.equal(await clamp.innerText(),clampText,'Local inspector refresh cannot overwrite the explicit clamped-seek note');
 await click('[data-action="action-undo"]');await click('[data-action="action-undo"]');assert.equal(savedRequests(),1);
 report.checks.push('Draft selection outside saved range clamps with its own explicit note; generic scope refresh cannot overwrite it and Undo preserves the saved source');
 await page.locator('[data-view="play"]').click();await page.waitForFunction(()=>Number(document.querySelector('[data-view="time"]').value)>.1);
 await clips().first().click();await assertFrame(first.start);
 await clips().nth(1).click();await assertFrame(second.start);const incoming=await recordGeometry('01-saved-incoming');
 await joins().first().click();await assertFrame(second.start-second.transition.frames);
 assert.equal(savedRequests(),1);report.checks.push('Clicking a clip or amber transition seeks and pauses at that exact visible interval start');

 await rotate().scrollIntoViewIfNeeded();await rotate().focus();await rotate().press('ArrowRight');await assertFrame(second.start);await assertHeading(95);
 const keyboard=await recordGeometry('02-keyboard-heading',{changed:true});
 assert(difference(incoming.actual.VisibleSkin1,keyboard.actual.VisibleSkin1)<1e-5,'Ring changes only the selected performer at the same incoming frame');
 await rotate().press('Shift+ArrowRight');await assertHeading(110);await recordGeometry('03-shift-heading',{changed:true});
 assert.equal(savedRequests(),1);assert.match(await page.locator('[data-motion-turn-status]').innerText(),/orientation|heading|turn/i);
 await page.screenshot({path:path.join(out,'01-visual-heading-draft.png'),fullPage:true});
 await click('[data-action="action-undo"]');await assertHeading(95);const undoRemaining=await recordGeometry('03b-undo-retains-earlier-draft',{changed:true});
 assert(difference(undoRemaining.actual.VisibleSkin0,keyboard.actual.VisibleSkin0)<1e-5,'Undo restores the earlier unsaved five-degree pose, not the saved baseline');
 assert.equal(savedRequests(),1,'Undo never publishes a native Save');
 await click('[data-action="action-undo"]');await assertHeading(90);await recordGeometry('04-undo-restored');
 report.checks.push('Arrow and Shift+Arrow change heading by 5/15 degrees, seek incoming pose, synchronize degrees and preserve unselected geometry; two Undos restore saved pose');

 await rotate().scrollIntoViewIfNeeded();const handle=await rotate().boundingBox();assert(handle&&handle.width>0&&handle.height>0);
 await page.mouse.move(handle.x+handle.width/2,handle.y+handle.height/2);await page.mouse.down();
 await page.mouse.move(handle.x+handle.width/2+32,handle.y+handle.height/2-22,{steps:10});await page.mouse.up();
 const pointerHeading=Number(await field('heading_deg').inputValue());assert(Number.isFinite(pointerHeading)&&Math.abs(pointerHeading-90)>1,'Real pointer drag rotates the body');
 await assertHeading(pointerHeading);await assertFrame(second.start);await recordGeometry('05-pointer-heading',{changed:true});
 await page.screenshot({path:path.join(out,'02-pointer-heading.png'),fullPage:true});
 assert.equal(savedRequests(),1);await click('[data-action="action-undo"]');await assertHeading(90);await recordGeometry('06-pointer-undo');
 await rotate().focus();await rotate().press('ArrowRight');await assertHeading(95);await recordGeometry('07-final-unsaved-heading',{changed:true});
 await page.locator('[data-view="play"]').click();await page.waitForFunction(()=>document.querySelector('[data-view="play"]').textContent==='Pause');
 await recordGeometry('08-play-saved-no-overlay');await page.locator('[data-view="play"]').click();
 await assertHeading(95);assert(await save().isEnabled(),'Playback clears only the temporary pose, not the editable draft');
 report.checks.push('Real pointer rotation is undoable; Play removes only draft orientation overlay and plays the saved scene without discarding the draft');

 const saved=await saveAndRead();assert.equal(saved.rig.timeline.clips[1].heading_deg,95);
 assert.deepEqual(saved.rig.timeline.clips[0],initial.rig.timeline.clips[0]);assert.deepEqual(saved.other.timeline,initial.other.timeline);
 assert.deepEqual(await fileHash(path.join(project.directory,initial.cp.path)),initialHash);
 await page.reload();await ready();await clips().nth(1).click();await assertFrame(saved.rig.timeline.clips[1].start);
 await recordGeometry('09-reloaded-native-heading');await joins().first().click();await field('transition_mode').waitFor();await assertHeading(95);
 await page.screenshot({path:path.join(out,'03-reloaded-saved-heading.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await rotate().scrollIntoViewIfNeeded();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.screenshot({path:path.join(out,'04-mobile-visual-controls.png'),fullPage:true});
 assert.deepEqual(await fileHash(source),original);assert.deepEqual(await fileHash(path.join(project.directory,relative)),original);
 assert.equal(savedRequests(),2);assert.deepEqual(report.errors,[]);
 for(const [relative,identity] of Object.entries(report.tested_files))assert.deepEqual(await fileHash(path.join(repo,relative)),identity,'Implementation changed during test: '+relative);
 report.checks.push('Second real Blender Save/reload retains visual heading, earlier clip, other performer, original bytes and previous checkpoint; narrow UI has no page overflow');
 report.status='PASS';report.projectId=project.id;report.checkpoints=[initial.cp,saved.cp].map(({id,sha256})=>({id,sha256}));
}catch(error){report.status='FAIL';report.error=String(error?.stack||error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;if(page)await page.screenshot({path:path.join(out,'FAILURE.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error}));}
