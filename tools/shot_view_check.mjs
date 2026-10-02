/** Named shot -> authenticated conversion -> real GLB/camera -> browser controls. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {randomUUID,createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
import {sampledCamera} from '../launcher/public/shot-view.mjs';
const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,generated,python,blender,playwright].every(x=>x&&path.isAbsolute(x))&&!await exists(out));
const fixture=await json(path.join(generated,'RESULTS.json'));assert.equal(fixture.status,'PASS');assert.equal(fixture.scope,'REAL_GENERATED_SHOT_CAMERA');
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),report={kind:'synthetic-shot-camera-browser',checks:[],comparisons:[],previews:[],errors:[],human_review:'NOT_TESTED',native_desktop:'NOT_TESTED',scripted_decisions:['Synthetic World/Action baselines and Shots completion, not human approval']};
let app,browser,page;
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
 const post=async(route,body)=>{const r=await fetch(app.origin+'/api/workbench/'+route,{method:'POST',headers,body:JSON.stringify(body)});assert.equal(r.status,200,await r.clone().text());return r.json();};
 let p=await app.store.create('Synthetic shot viewing','Generated camera/motion tests only');const entries=[];let priorSource=null,currentScene;
 for(const item of fixture.cases){
  const source=path.join(generated,item.source),original=await fileHash(source);assert.equal(original.sha256,item.source_sha256);
  if(priorSource!==source){
   const prep=await app.runtime.harness(['job-prepare','scene-audit','--input',source]);const audit=await app.workbench.result(await app.runtime.harness(['job-run',prep.id,'--blender',blender]));
   const created=await app.workbench.create(p.id,p.revision,item.source);p=await app.store.get(p.id);currentScene=p.workbench.scenes.find(s=>s.id===created.sceneId);
   const cpId='cp_'+randomUUID(),relative='Scenes/'+cpId+'.blend';await fs.copyFile(source,path.join(p.directory,relative),fs.constants.COPYFILE_EXCL);
   currentScene.checkpoints.push({id:cpId,path:relative,...original,parent:null,stage:'action',audit});currentScene.current=cpId;currentScene.stage='shots';currentScene.completed={world:cpId,action:cpId};
   p=await app.store.save(p,p.revision);priorSource=source;
  }
  const {name,camera,start,end}=item.shotView.shot;await post('shot-save',{projectId:p.id,sceneId:currentScene.id,revision:p.revision,shot:{name,camera,start,end}});p=await app.store.get(p.id);currentScene=p.workbench.scenes.find(s=>s.id===currentScene.id);
  entries.push({item,source,original,sceneId:currentScene.id,cp:currentScene.checkpoints[0],shot:currentScene.shots.find(s=>s.name===name)});
 }
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});
 page=await browser.newPage({viewport:{width:1440,height:1000},serviceWorkers:'block'});page.setDefaultTimeout(30000);
 page.on('pageerror',e=>report.errors.push(e.message.replaceAll(app.token,'[REDACTED]')));
 page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text().replaceAll(app.token,'[REDACTED]'));});
 const requests=[];page.on('request',r=>{if(r.url().startsWith(app.origin+'/'))requests.push({method:r.method(),path:new URL(r.url()).pathname});else if(/^https?:/.test(r.url()))report.errors.push('Unexpected external request');});
 const idle=()=>page.waitForFunction(()=>!document.body.classList.contains('working'));
 const ready=async()=>{await page.waitForFunction(()=>['ready','failed'].includes(document.querySelector('[data-scene-viewer]')?.dataset.viewerState),null,{timeout:205000});assert.equal(await page.locator('[data-scene-viewer]').getAttribute('data-viewer-state'),'ready',await page.locator('[data-scene-viewer]').innerText());};
 await page.goto(app.origin+'/workbench#'+app.token);await idle();await page.locator('[data-action="project"][data-id="'+p.id+'"]').click();await idle();await ready();
 const THREE=await import(pathToFileURL(path.join(repo,'launcher/public/vendor/three/build/three.module.js')).href),{GLTFLoader}=await import(pathToFileURL(path.join(repo,'launcher/public/vendor/three/examples/jsm/loaders/GLTFLoader.js')).href);
 for(const entry of entries){
  await page.locator('#scene-picker').selectOption(entry.sceneId);await idle();await ready();
  await page.locator('[data-action="select-shot"][data-id="'+entry.shot.id+'"]').click();await idle();await ready();
  const host=page.locator('[data-scene-viewer]'),id=await host.getAttribute('data-preview-id'),record=await json(path.join(out,'Studio/SystemRuntime/UserData/ViewerPreviews',id,'viewer.json'));
  assert.equal(record.shotView.shot.id,entry.shot.id);assert.equal(record.shotView.shot.revision,entry.shot.revision);assert.equal(record.profile,'shot-framing-v1');
  report.previews.push({case:entry.item.label,id,modelSha256:record.sha256,sourceSha256:record.version,shot:record.shotView.shot});
  const response=await fetch(app.origin+'/api/workbench/viewer-model?'+new URLSearchParams({projectId:p.id,sceneId:entry.sceneId,previewId:id}),{headers});assert.equal(response.status,200);
  const bytes=Buffer.from(await response.arrayBuffer()),gltf=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.length),'');
  const mixer=new THREE.AnimationMixer(gltf.scene),clip=gltf.animations.length?mixer.clipAction(gltf.animations[0]):null,rig=sampledCamera(THREE,record.shotView);
  if(clip){clip.setLoop(THREE.LoopOnce,1);clip.clampWhenFinished=true;clip.play();}
  for(const sample of entry.item.samples){
   if(clip){clip.paused=false;clip.time=(sample.frame-record.playback.start)/record.playback.fps;mixer.update(0);}
   gltf.scene.updateMatrixWorld(true);const object=gltf.scene.getObjectByName('SyntheticShotSubject'),point=new THREE.Vector3(),v=new THREE.Vector3();assert(object?.isMesh);
   for(let i=0;i<object.geometry.attributes.position.count;i++){object.getVertexPosition(i,v);point.add(v.applyMatrix4(object.matrixWorld));}point.divideScalar(object.geometry.attributes.position.count);
   const positionError=point.distanceTo(new THREE.Vector3(...sample.position)),projected=point.clone().project(rig.frame(sample.frame)),projectionError=Math.max(Math.abs(projected.x-sample.ndc[0]),Math.abs(projected.y-sample.ndc[1]));
   assert.equal(rig.camera.isOrthographicCamera,record.shotView.samples[sample.frame-entry.shot.start].projection==='ORTHO');
   assert(positionError<1e-4&&projectionError<1e-4,JSON.stringify({positionError,projectionError,sample}));report.comparisons.push({case:entry.item.label,frame:sample.frame,positionError,projectionError});
  }
  assert.equal(await host.getAttribute('data-camera-mode'),'saved-shot');assert.match(await host.locator('.scene-playback-label').innerText(),new RegExp(entry.shot.camera));
  const manifest=path.join(p.directory,'project.json'),before=await fileHash(manifest),requestCount=requests.length;
  const canvas=host.locator('canvas');await canvas.scrollIntoViewIfNeeded();const imageHash=async()=>createHash('sha256').update(await canvas.screenshot()).digest('hex');
  const firstImage=await imageHash();await host.locator('[data-view="orbit"]').click();assert.equal(await host.getAttribute('data-camera-mode'),'orbit-inspection');assert.notEqual(await imageHash(),firstImage);
  await host.locator('[data-view="reset"]').click();assert.equal(await host.getAttribute('data-camera-mode'),'saved-shot');assert.equal(await imageHash(),firstImage);
  if(entry.shot.start!==entry.shot.end){
   await host.locator('[data-view="time"]').focus();await host.locator('[data-view="time"]').press('End');assert.equal(await host.getAttribute('data-shot-frame'),String(entry.shot.end));
   const endImage=await imageHash();assert.notEqual(endImage,firstImage,'Motion or camera changes actual pixels');
   await host.locator('[data-view="time"]').press('Home');assert.equal(await host.getAttribute('data-shot-frame'),String(entry.shot.start));
   await host.locator('[data-view="play"]').click();await page.waitForFunction(first=>Number(document.querySelector('[data-scene-viewer]').dataset.shotFrame)!==first,entry.shot.start);await host.locator('[data-view="play"]').click();
  }else assert.equal(await host.locator('[data-view="play"]').isDisabled(),true);
  assert.equal(requests.slice(requestCount).some(r=>r.method==='POST'),false,'Orbit/playback cannot start a job or edit cameras');assert.deepEqual(await fileHash(manifest),before);
  await page.screenshot({path:path.join(out,entry.item.label+'.png'),fullPage:true});
  assert.deepEqual(await fileHash(entry.source),entry.original);assert.deepEqual(await fileHash(path.join(p.directory,entry.cp.path)),entry.original);
  report.checks.push(entry.item.label+': actual GLB motion/projected framing matches Blender, bounded playback and orbit round-trip, no project or source writes');
 }
 const first=entries[0];await page.locator('#scene-picker').selectOption(first.sceneId);await idle();await ready();
 await page.locator('[data-action="select-shot"][data-id="'+first.shot.id+'"]').click();await idle();await ready();
 assert.equal(await page.locator('[data-scene-viewer]').getAttribute('data-preview-id'),report.previews[0].id,'Exact shot reuses verified preview');
 await page.locator('[data-action="edit-shot"][data-id="'+first.shot.id+'"]').click();await idle();await page.locator('#shot-start').fill(String(first.shot.start+1));await page.locator('[data-action="save-shot"]').click();await idle();await ready();
 const revisedId=await page.locator('[data-scene-viewer]').getAttribute('data-preview-id'),revised=await json(path.join(out,'Studio/SystemRuntime/UserData/ViewerPreviews',revisedId,'viewer.json'));
 assert.notEqual(revisedId,report.previews[0].id);assert.equal(revised.shotView.shot.revision,2);assert.equal(revised.shotView.shot.start,first.shot.start+1);assert.equal(revised.version,first.original.sha256);
 const oldBytes=await fetch(app.origin+'/api/workbench/viewer-model?'+new URLSearchParams({projectId:p.id,sceneId:first.sceneId,previewId:report.previews[0].id}),{headers});assert.equal(oldBytes.status,200);assert.equal(createHash('sha256').update(Buffer.from(await oldBytes.arrayBuffer())).digest('hex'),report.previews[0].modelSha256);
 report.checks.push('Changing shots refreshes camera/range; exact return is cached; a real shot revision creates a new preview and preserves old bytes');
 p=await app.store.get(p.id);await post('approve',{projectId:p.id,sceneId:first.sceneId,revision:p.revision,stage:'shots',checkpointId:first.cp.id});
 await page.locator('[data-action="refresh"]').click();await idle();await ready();
 const lightId=await page.locator('[data-scene-viewer]').getAttribute('data-preview-id'),light=await json(path.join(out,'Studio/SystemRuntime/UserData/ViewerPreviews',lightId,'viewer.json'));
 assert.equal(light.profile,'look-inspection-v1');assert.notEqual(lightId,revisedId);assert.deepEqual(light.shotView,revised.shotView);
 assert.match(await page.locator('.viewer-disclaimer').last().innerText(),/inspection approximations.*rendered previews/);
 const latest=await app.store.get(p.id),savedScene=latest.workbench.scenes.find(s=>s.id===first.sceneId);assert.equal(savedScene.completed.light,undefined);assert.equal(savedScene.current,first.cp.id);
 for(const request of [{kind:'checkpoint',id:first.cp.id,shot_view:{camera:'Foreign'}},{kind:'checkpoint',id:first.cp.id,preview_profile:'world-static-v1'}]){
   const r=await fetch(app.origin+'/api/workbench/viewer-prepare',{method:'POST',headers,body:JSON.stringify({projectId:p.id,sceneId:first.sceneId,revision:latest.revision,request})});assert.equal(r.status,400);
 }
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'light-mobile.png'),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 report.checks.push('Light retains exact selected shot framing under a separate approximation profile; no Light approval, camera override or source mutation');
 assert.deepEqual(report.errors,[]);report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error}));}
