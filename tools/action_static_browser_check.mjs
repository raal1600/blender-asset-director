/** Synthetic still Action: UI -> authenticated API -> Blender -> GLB -> pixels. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,generated,python,blender,playwright].every(x=>x&&path.isAbsolute(x)));
assert(!await exists(out),'Fresh evidence directory required');
const expected=await json(path.join(generated,'RESULTS.json'));
assert.equal(expected.scope,'GENERATED_STATIC_ACTION_PREVIEW');assert.equal(expected.status,'PASS');
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url));
const report={kind:'synthetic-static-action-browser',checks:[],errors:[],comparisons:[],human_review:'NOT_TESTED'};
let app,browser,page;
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const scenes=[];let project=await app.store.create('Synthetic static Action','Generated still scenes only; no human creative approval');
 for(const item of expected.cases){
  const source=path.join(generated,item.name+'.blend'),original=await fileHash(source);
  const job=await app.runtime.harness(['job-prepare','scene-audit','--input',source]);
  const audit=await app.workbench.result(await app.runtime.harness(['job-run',job.id,'--blender',blender]));
  const created=await app.workbench.create(project.id,project.revision,item.name);project=await app.store.get(project.id);
  const scene=project.workbench.scenes.find(s=>s.id===created.sceneId),cpId='cp_'+randomUUID(),relative='Scenes/'+cpId+'.blend';
  await fs.copyFile(source,path.join(project.directory,relative),fs.constants.COPYFILE_EXCL);
  scene.checkpoints.push({id:cpId,path:relative,...original,parent:null,stage:'world',audit});
  scene.current=cpId;scene.stage='action';scene.completed={world:cpId};
  await app.store.save(project,project.revision);project=await app.store.get(project.id);
  scenes.push({id:scene.id,cpId,source,original,relative,item});
 }
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});
 page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});page.setDefaultTimeout(30000);
 page.on('pageerror',e=>report.errors.push(e.message.replaceAll(app.token,'[REDACTED]')));
 page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text().replaceAll(app.token,'[REDACTED]'));});
 page.on('request',r=>{if(/^https?:/.test(r.url())&&!r.url().startsWith(app.origin+'/'))report.errors.push('Unexpected external request');});
 const THREE=await import(pathToFileURL(path.join(repo,'launcher/public/vendor/three/build/three.module.js')).href);
 const {GLTFLoader}=await import(pathToFileURL(path.join(repo,'launcher/public/vendor/three/examples/jsm/loaders/GLTFLoader.js')).href);
 const idle=()=>page.waitForFunction(()=>!document.body.classList.contains('working'));
 await page.goto(app.origin+'/workbench#'+app.token);await idle();
 await page.locator('[data-action="project"][data-id="'+project.id+'"]').click();await idle();
 for(const entry of scenes){
  await page.locator('body').ariaSnapshot();await page.locator('#scene-picker').selectOption(entry.id);await idle();
  await page.waitForFunction(()=>document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready'&&!document.querySelector('[data-action="action-ready"]').disabled,null,{timeout:205000});
  assert.equal(await page.locator('#notice').isVisible(),false);
  const previewId=await page.locator('[data-scene-viewer]').getAttribute('data-preview-id');
  const url=new URL('/api/workbench/viewer-model',app.origin);url.search=new URLSearchParams({projectId:project.id,sceneId:entry.id,previewId});
  const response=await fetch(url,{headers:{Authorization:'Bearer '+app.token}});assert.equal(response.status,200);
  const bytes=Buffer.from(await response.arrayBuffer());
  const gltf=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
  const mixer=new THREE.AnimationMixer(gltf.scene),clip=gltf.animations.length?mixer.clipAction(gltf.animations[0]):null;
  if(clip){clip.setLoop(THREE.LoopOnce,1);clip.clampWhenFinished=true;clip.play();}
  for(const sample of entry.item.samples){
   if(clip){clip.time=(sample.frame-entry.item.playback.start)/entry.item.playback.fps;mixer.update(0);}
   gltf.scene.updateMatrixWorld(true);gltf.scene.traverse(o=>o.skeleton?.update());
   for(const [name,point] of Object.entries(sample.positions)){
    const object=gltf.scene.getObjectByName(name);assert(object?.isMesh);const center=new THREE.Vector3(),v=new THREE.Vector3();
    for(let i=0;i<object.geometry.attributes.position.count;i++){object.getVertexPosition(i,v);center.add(v.applyMatrix4(object.matrixWorld));}
    center.divideScalar(object.geometry.attributes.position.count);const error=center.distanceTo(new THREE.Vector3(...point));assert(error<1e-4);
    report.comparisons.push({case:entry.item.name,name,frame:sample.frame,error});
   }
  }
  if(entry.item.playback.static){
   assert.equal(gltf.animations.length,0);assert.match(await page.locator('.scene-playback-label').innerText(),/Static scene/);
   assert.equal(await page.locator('[data-view="play"]').isDisabled(),true);assert.equal(await page.locator('[data-view="time"]').isDisabled(),true);
  }else assert.equal(gltf.animations.length,1);
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,entry.item.name+'.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.setViewportSize({width:1280,height:850});
  const current=(await app.store.get(project.id)).workbench.scenes.find(s=>s.id===entry.id);
  assert.equal(current.current,entry.cpId);assert.equal(current.completed.action,undefined);
  assert.deepEqual(await fileHash(entry.source),entry.original);assert.deepEqual(await fileHash(path.join(project.directory,entry.relative)),entry.original);
  report.checks.push(entry.item.name+': actual saved-scene geometry, static controls, ready without approval, original hashes intact');
 }
 assert.deepEqual(report.errors,[]);report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error}));}
