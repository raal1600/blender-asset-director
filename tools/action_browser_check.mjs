/** Generated Action user journey: browser -> API -> native save -> combined GLB. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {randomUUID,createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,previewFixture,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,generated,previewFixture,python,blender,playwright].every(x=>x&&path.isAbsolute(x)));
assert(!await exists(out),'New private evidence folder required');
assert.equal((await json(path.join(generated,'RESULTS.json'))).scope,'REAL_GENERATED_NATIVE_ACTION');
const expected=await json(path.join(previewFixture,'RESULTS.json'));assert.equal(expected.scope,'GENERATED_COMBINED_ACTION_PREVIEW');assert.equal(expected.status,'PASS');
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),source=path.join(generated,'source.blend'),original=await fileHash(source);
const report={kind:'synthetic-action-browser',checks:[],errors:[],requests:[],not_tested:['Native window/rig controls','Human temporal approval','Private asset compatibility','Live installation']};
let app,browser,page;
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const inspect=await app.runtime.harness(['job-prepare','scene-audit','--input',source]);const audit=await app.workbench.result(await app.runtime.harness(['job-run',inspect.id,'--blender',blender]));
 let project=await app.store.create('Synthetic Action browser','Generated multi-performer scene; no human creative acceptance');
 await app.workbench.create(project.id,project.revision,'Combined performance');project=await app.store.get(project.id);
 const scene=project.workbench.scenes[0],cpId='cp_'+randomUUID(),relative='Scenes/'+cpId+'.blend';await fs.copyFile(source,path.join(project.directory,relative),fs.constants.COPYFILE_EXCL);
 scene.checkpoints.push({id:cpId,path:relative,...original,parent:null,stage:'world',audit});scene.current=cpId;scene.stage='action';scene.completed={world:cpId};await app.store.save(project,project.revision);
 // Upgrade regression: a generated legacy receipt has the same checkpoint but
 // predates implementation-bound inspections and timeline audit fields.
 const oldJob=await app.runtime.harness(['job-prepare','action-audit','--input',source]);
 const oldAudit=structuredClone(await app.workbench.result(await app.runtime.harness(['job-run',oldJob.id,'--blender',blender])));
 for(const performer of oldAudit.performers){delete performer.timeline;for(const take of performer.takes)delete take.travel_blocker;}
 const oldFile=path.join(project.directory,'Runs/run_'+randomUUID()+'.json');
 await writeJson(oldFile,{schema:1,id:path.basename(oldFile,'.json'),projectId:project.id,sceneId:scene.id,checkpointId:cpId,checkpointSha256:original.sha256,
   action:'action-audit',state:'SUCCEEDED',startedAt:'2000-01-01T00:00:00Z',inspection:oldAudit,fixture:'SIMULATED_LEGACY_AUDIT_SCHEMA_NOT_A_HISTORICAL_RECEIPT'});
 const oldHash=await fileHash(oldFile);
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});
 page=await browser.newPage({viewport:{width:1440,height:1000},serviceWorkers:'block'});page.setDefaultTimeout(30000);
 const safe=value=>String(value).replaceAll(app.token,'[REDACTED]');
 page.on('pageerror',e=>report.errors.push(safe(e.message)));page.on('console',m=>{if(m.type()==='error')report.errors.push(safe(m.text()));});page.on('dialog',d=>d.dismiss());
 const records=[],models=[],pending=[];
 page.on('request',r=>{if(r.url().startsWith(app.origin+'/'))report.requests.push({path:new URL(r.url()).pathname,method:r.method()});else if(/^https?:/.test(r.url()))report.errors.push('Unexpected external request');});
 page.on('response',r=>{const url=new URL(r.url());if(url.pathname==='/api/workbench/viewer-prepare'&&r.ok())pending.push(r.json().then(v=>records.push(v)));if(url.pathname==='/api/workbench/viewer-model'&&r.ok())pending.push(r.body().then(b=>models.push(b)));});
 const idle=()=>page.waitForFunction(()=>!document.body.classList.contains('working'));
 const click=async selector=>{await page.locator('body').ariaSnapshot();await page.locator(selector).click();await idle();};
 const ready=async()=>{await page.waitForFunction(()=>!document.body.classList.contains('working')&&document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready'&&!!document.querySelector('[data-action-field="performer"]')&&!document.querySelector('[data-action-field="performer"]').disabled,null,{timeout:205000});};
 await page.goto(app.origin+'/workbench#'+app.token);await idle();
 const inspectionStarted=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/workbench/action-inspect'&&r.ok());
 await click('[data-action="project"][data-id="'+project.id+'"]');await inspectionStarted;await page.reload();await ready();await Promise.all(pending);
 assert.equal(await page.locator('#notice').isVisible(),false);
 assert.equal(report.requests.filter(r=>r.path.endsWith('/action-inspect')).length,1,'Reload must reuse the running inspection, not start another');
 const refreshed=(await app.store.runs(project.id)).filter(r=>r.action==='action-audit'&&r.state==='SUCCEEDED'&&r.implementation);
 assert.equal(refreshed.length,1);assert.equal(refreshed[0].implementation,(await app.workbench.available()).implementation);
 assert(refreshed[0].inspection.performers.every(p=>p.timeline?.version==='action-timeline-v1'));
 assert.deepEqual(await fileHash(oldFile),oldHash);assert.equal((await app.store.get(project.id)).workbench.scenes[0].current,cpId);
 await page.getByRole('button',{name:'Build a motion timeline',exact:true}).click();
 await page.getByRole('region',{name:'Character action timelines',exact:true}).waitFor();
 await page.screenshot({path:path.join(out,'00-upgrade-timeline.png'),fullPage:true});
 await page.reload();await ready();await Promise.all(pending);
 assert.equal(report.requests.filter(r=>r.path.endsWith('/action-inspect')).length,1);
 report.checks.push('Legacy same-checkpoint receipt is preserved; browser automatically obtains one current native inspection and timeline opens without manual reinspection');
 assert.equal(await page.locator('.action-workspace').count(),1);assert.equal(await page.getByLabel('Animation take').isVisible(),false);assert.match(await page.locator('.scene-playback-label').innerText(),/Whole scene.*24 fps/);
 await page.screenshot({path:path.join(out,'01-action-ready.png'),fullPage:true});await fs.writeFile(path.join(out,'01-action-ready.txt'),safe(await page.locator('body').ariaSnapshot()),{flag:'wx'});
 assert.deepEqual(report.errors,[]);report.checks.push('Action opens with automatic real performer inspection and whole-scene playback, no arbitrary global take selector');
 // Independent evaluation of the actual app GLB, not a hidden UI test shortcut.
 const THREE=await import(pathToFileURL(path.join(repo,'launcher/public/vendor/three/build/three.module.js')).href);
 const {GLTFLoader}=await import(pathToFileURL(path.join(repo,'launcher/public/vendor/three/examples/jsm/loaders/GLTFLoader.js')).href);
 const raw=models[0],gltf=await new GLTFLoader().parseAsync(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength),'');assert.equal(gltf.animations.length,1);
 const mixer=new THREE.AnimationMixer(gltf.scene),clip=mixer.clipAction(gltf.animations[0]);clip.setLoop(THREE.LoopOnce,1);clip.clampWhenFinished=true;clip.play();
 const distances=[];
 for(const sample of expected.samples){clip.time=(sample.frame-expected.playback.start)/expected.playback.fps;mixer.update(0);gltf.scene.updateMatrixWorld(true);gltf.scene.traverse(o=>o.skeleton?.update());
  for(const [name,point] of Object.entries(sample.positions)){const object=gltf.scene.getObjectByName(name);assert(object?.isMesh,'Observed skin/prop exists');const centroid=new THREE.Vector3(),v=new THREE.Vector3();for(let i=0;i<object.geometry.attributes.position.count;i++){object.getVertexPosition(i,v);centroid.add(v.applyMatrix4(object.matrixWorld));}centroid.divideScalar(object.geometry.attributes.position.count);const error=centroid.distanceTo(new THREE.Vector3(...point));assert(error<1e-4,name+' GLB differs from native frame '+sample.frame+': '+error);distances.push({name,frame:sample.frame,error});}
 }
 report.evaluatedComparisons=distances;report.checks.push('Both skinned performers and moving prop agree with actual Blender samples at start/middle/end');
 const canvas=page.locator('[data-scene-viewer] canvas'),first=await canvas.screenshot();await page.locator('[data-view="play"]').click();await page.waitForTimeout(150);await page.locator('[data-view="play"]').click();
 await page.locator('[data-view="time"]').fill((4/24).toFixed(3));await page.locator('[data-view="time"]').dispatchEvent('input');await page.waitForTimeout(100);assert.notEqual(createHash('sha256').update(await canvas.screenshot()).digest('hex'),createHash('sha256').update(first).digest('hex'));assert.match(await page.locator('[data-view="clock"]').innerText(),/Frame 5/);report.checks.push('Actual scene playback and frame-labelled scrubbing change rendered geometry');
 await page.getByRole('combobox',{name:'Performer',exact:true}).selectOption('SyntheticRig0');
 const nativeChoice=await page.locator('[data-action-field="mode"] option').filter({hasText:'Synthetic Alternate'}).getAttribute('value');await page.getByRole('combobox',{name:'Performance',exact:true}).selectOption(nativeChoice);
 const startField=page.getByLabel('Start frame',{exact:true}),speedField=page.getByLabel('Speed',{exact:true}),saveButton=page.locator('[data-action="action-save"]');
 const stableStart=await startField.elementHandle(),stableSave=await saveButton.elementHandle(),stableViewer=await page.locator('[data-scene-viewer]').elementHandle();
 await startField.fill('0.1');assert.equal(await saveButton.isDisabled(),true);assert.match(await page.locator('#action-start-error').innerText(),/whole number/);
 await page.screenshot({path:path.join(out,'02a-invalid-start.png'),fullPage:true});
 await startField.press('Tab');assert.equal(await stableStart.evaluate(n=>n.isConnected),true);assert.equal(await stableSave.evaluate(n=>n.isConnected),true);
 await page.getByRole('combobox',{name:'Performer',exact:true}).selectOption('SyntheticRig1');assert.equal(await saveButton.isDisabled(),true);await page.getByRole('combobox',{name:'Performer',exact:true}).selectOption('SyntheticRig0');assert.equal(await startField.inputValue(),'0.1');
 await startField.fill('1');await startField.press('Tab');
 for(const invalid of ['', '0', '4.1']){await speedField.fill(invalid);assert.equal(await saveButton.isDisabled(),true);assert.match(await page.locator('#action-speed-error').innerText(),/Speed/);assert.doesNotMatch(await page.locator('.action-preview-scope').innerText(),/Infinity|NaN/);}
 await page.screenshot({path:path.join(out,'02b-invalid-speed.png'),fullPage:true});
 await speedField.fill('1.25');await speedField.press('Tab');assert.equal(await saveButton.isEnabled(),true);assert.equal(await stableViewer.evaluate(n=>n.isConnected),true);
 await click('[data-action="action-undo"]');assert.equal(await speedField.inputValue(),'1');assert.equal(await saveButton.isEnabled(),true);
 assert.equal(report.requests.filter(r=>r.path.endsWith('/action-save')).length,0);report.checks.push('Action timing validates per field, preserves invalid text across performer selection, coalesces Undo and never rebuilds focused controls or the viewer');
 await page.getByLabel('Start frame',{exact:true}).fill('20');await page.getByLabel('Start frame',{exact:true}).press('Tab');await page.getByLabel('Speed',{exact:true}).fill('2');await page.getByLabel('Speed',{exact:true}).press('Tab');
 await click('[data-action="action-undo"]');assert.equal(await page.getByLabel('Speed',{exact:true}).inputValue(),'1');await page.getByLabel('Speed',{exact:true}).fill('2');await page.getByLabel('Speed',{exact:true}).press('Tab');
 await page.getByRole('combobox',{name:'Performer',exact:true}).selectOption('StaticProp');await page.getByRole('combobox',{name:'Performance',exact:true}).selectOption('hold');
 for(const invalid of ['','1.5','25']){await page.getByLabel('Hold frame',{exact:true}).fill(invalid);assert.equal(await saveButton.isDisabled(),true);assert.match(await page.locator('#action-frame-error').innerText(),/Hold frame/);}
 await page.getByLabel('Hold frame',{exact:true}).fill('5');await page.getByLabel('Hold frame',{exact:true}).press('Tab');
 assert.match(await page.locator('.action-savebar').innerText(),/2 performers/);assert.equal(report.requests.filter(r=>r.path.endsWith('/action-save')).length,0);assert.equal((await app.store.get(project.id)).workbench.scenes[0].current,cpId);
 await click('[data-action="tab"][data-tab="film"]');assert.match(await page.locator('#dialog').innerText(),/Keep your Action changes/);await click('#dialog [data-action="close"]');report.checks.push('Two-performer local draft, Undo and unsaved-navigation guard with no job per field change');
 await page.screenshot({path:path.join(out,'02-action-draft.png'),fullPage:true});
 // A real pointer click straight from an edited input must submit exactly once;
 // do not Tab/blur first, which used to conceal the disappearing Save button.
 await page.getByLabel('Hold frame',{exact:true}).fill('4');await page.getByLabel('Hold frame',{exact:true}).press('Tab');await page.getByLabel('Hold frame',{exact:true}).fill('5');
 const saveBox=await saveButton.boundingBox();assert(saveBox);await page.mouse.click(saveBox.x+saveBox.width/2,saveBox.y+saveBox.height/2);
 await page.waitForFunction(()=>document.body.classList.contains('working')||document.querySelector('#notice')?.textContent.includes('Performance saved'),null,{timeout:10000});await ready();
 project=await app.store.get(project.id);const saved=project.workbench.scenes[0],cp=saved.checkpoints.find(c=>c.id===saved.current);assert.notEqual(cp.id,cpId);assert.deepEqual(saved.completed,{world:cpId});assert.equal(saved.stage,'action');assert.equal(report.requests.filter(r=>r.path.endsWith('/action-save')).length,1);
 const nativeState=(await app.store.runs(project.id)).find(r=>r.action==='action-audit'&&r.checkpointId===cp.id&&r.state==='SUCCEEDED').inspection;
 const rig=nativeState.performers.find(p=>p.name==='SyntheticRig0'),prop=nativeState.performers.find(p=>p.name==='StaticProp');assert.equal(rig.tracks.find(t=>!t.mute).strips[0].scale,.5);assert.equal(rig.tracks.find(t=>!t.mute).strips[0].start,20);assert(prop.tracks.every(t=>t.mute));assert.deepEqual(nativeState.frame_range,[1,24]);
 report.checks.push('One UI Save reaches real Blender; refreshed independent inspection proves exact timing and hold without approving Action');
 await page.screenshot({path:path.join(out,'03-action-saved.png'),fullPage:true});
 await page.getByRole('combobox',{name:'Performer',exact:true}).selectOption('SyntheticRig1');await page.getByRole('combobox',{name:'Performance',exact:true}).selectOption('hold');await click('[data-action="action-discard"]');await ready();assert.equal((await app.store.get(project.id)).workbench.scenes[0].current,cp.id);report.checks.push('Discard removes only the local Action draft');
 await click('[data-action="stage"][data-stage="world"]');await page.waitForFunction(()=>document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready',null,{timeout:205000});assert.equal(await page.locator('.viewer-animation').isVisible(),false);assert.match(await page.locator('.viewer-disclaimer:not(.viewer-texture-note)').innerText(),/Static World/);report.checks.push('Returning to World freezes saved Action at its recorded frame without changing native motion');
 await click('[data-action="stage"][data-stage="action"]');await ready();await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'04-action-mobile.png'),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(await fileHash(source),original);assert.deepEqual(await fileHash(path.join(project.directory,relative)),original);assert.deepEqual(report.errors,[]);report.checks.push('Originals preserved, responsive 390px view, no browser errors or external requests');
 // Real browser request and owned native task, but not a native desktop-window claim.
 let child,finished,handed;
 app.runtime.launchWorkbenchTask=async(p,manifest)=>{
  handed=await json(manifest);const chunks=[];
  child=spawn(blender,['--background','--factory-startup','--disable-autoexec','--threads','2','--python-exit-code','12','--python',path.join(repo,'tools/action_task_native.py'),'--',manifest,'no-save'],{windowsHide:true});
  child.stdout.on('data',x=>chunks.push(x));child.stderr.on('data',x=>chunks.push(x));
  finished=new Promise((resolve,reject)=>{child.once('error',reject);child.once('close',async code=>{await fs.writeFile(path.join(out,'manual-handoff.log'),Buffer.concat(chunks));resolve(code);});});return child.pid;
 };
 app.runtime.inspectWorkbenchTask=async()=>({state:child?.exitCode===null?'verified':'stopped'});
 await page.getByRole('combobox',{name:'Performer',exact:true}).selectOption('SyntheticRig1');
 await page.locator('[data-view="time"]').fill((4/24).toFixed(3));await page.locator('[data-view="time"]').dispatchEvent('input');assert.match(await page.locator('[data-view="clock"]').innerText(),/Frame 5/);
 await page.locator('.action-details summary').click();await page.screenshot({path:path.join(out,'05-explicit-rig-access.png'),fullPage:true});
 await click('[data-action="action-rig"]');assert(handed);assert.equal(handed.rigControls,true);assert.equal(handed.actionContext.performer,'SyntheticRig1');assert.equal(handed.frame,5);
 assert.equal(await finished,0,'Native manual-handoff fixture failed');
 await page.waitForFunction(()=>!document.querySelector('[data-action="focus-task"]'),null,{timeout:30000});await ready();
 const returned=(await app.store.get(project.id)).workbench.scenes[0];assert.equal(returned.task,null);assert.equal(returned.current,cp.id);assert.equal(returned.lastEdit.outcome,'no-save');assert.equal(returned.completed.action,undefined);
 report.nativeHandoff=await json(path.join(project.directory,'Docs/action-task-native.json'));assert.deepEqual(report.errors,[]);
 report.checks.push('Explicit rig button carries selected saved performer/frame through API to real background Blender and returns without saving or approving');report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;if(page){await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(path.join(out,'failure.txt'),await page.locator('body').innerText()).catch(()=>{});}}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error}));}
