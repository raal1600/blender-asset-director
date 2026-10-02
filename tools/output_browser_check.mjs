/** Real synthetic browser -> Blender -> MP4 -> revision. Not human/GUI acceptance. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome,ffmpeg,ffprobe]=process.argv.slice(2),uid=p=>p+randomUUID();
assert([out,generated,python,blender,playwright,ffmpeg,ffprobe].every(x=>x&&path.isAbsolute(x))&&!await exists(out));
const fixture=await json(path.join(generated,'RESULTS.json'));assert.equal(fixture.status,'PASS');assert.equal(fixture.scope,'REAL_GENERATED_SCENE_LAYERS');
const member=fixture.outputs.at(-1),source=path.join(generated,member.path),original=await fileHash(source);assert.equal(original.sha256,member.sha256);
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),report={kind:'synthetic-progressive-output',checks:[],errors:[],decisions:[],renders:[],cuts:[],framesAuthorized:0,frameBudget:19,human_review:'NOT_TESTED',native_desktop:'NOT_TESTED',codex:'NOT_TESTED',scope:'Generated three-scene technical fixture; scripted baseline/output decisions, no production approval'};
let app,browser,page,consent=null;
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,ffmpeg,ffprobe,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};let p=await app.store.create('Synthetic progressive film','Three generated scenes; scoped output and historical-cut tests only');
 const prep=await app.runtime.harness(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await app.runtime.harness(['job-run',prep.id,'--blender',blender]));
 const scenes=[];
 const state=async()=>{const response=await fetch(app.origin+'/api/workbench/state?'+new URLSearchParams({projectId:p.id,compact:true}),{headers});assert.equal(response.status,200);return response.json();};
 const post=async(route,body,expected=200)=>{const response=await fetch(app.origin+'/api/workbench/'+route,{method:'POST',headers,body:JSON.stringify({projectId:p.id,...body})}),v=await response.json();assert.equal(response.status,expected,JSON.stringify(v));return v;};
 for(let i=0;i<3;i++){
  p=await app.store.get(p.id);const made=await app.workbench.create(p.id,p.revision,'Scene '+(i+1));p=await app.store.get(p.id);const scene=p.workbench.scenes.find(s=>s.id===made.sceneId),cp={id:uid('cp_'),path:'Scenes/'+uid('synthetic_')+'.blend',...original,stage:'light',parent:null,audit};
  await fs.copyFile(source,path.join(p.directory,cp.path),fs.constants.COPYFILE_EXCL);scene.checkpoints.push(cp);scene.current=cp.id;scene.stage='shots';scene.completed={world:cp.id,action:cp.id};p=await app.store.save(p,p.revision);
  for(const [name,camera] of (i===0?[['Wide','SyntheticWide'],['Close','SyntheticClose']]:[['Wide','SyntheticWide']])){
   const v=await state();await post('shot-save',{sceneId:scene.id,revision:v.project.revision,shot:{name,camera,start:1,end:4}});
  }
  p=await app.store.get(p.id);for(const stage of ['shots','light'])p=await app.workbench.approve(p.id,scene.id,p.revision,stage,cp.id);
  scenes.push({id:scene.id,cp,shots:p.workbench.scenes.find(s=>s.id===scene.id).shots});
 }
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});page=await browser.newPage({viewport:{width:1440,height:1000},serviceWorkers:'block'});page.setDefaultTimeout(30000);
 page.on('pageerror',e=>report.errors.push(e.message.replaceAll(app.token,'[REDACTED]')));page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text().replaceAll(app.token,'[REDACTED]'));});
 page.on('dialog',async dialog=>{const choice=consent;consent=null;if(!choice||!choice.pattern.test(dialog.message())){report.errors.push('Unexpected decision: '+dialog.message());await dialog.dismiss();return;}report.decisions.push({prompt:dialog.message(),scripted:true,answer:choice.accept?'ACCEPT':'DECLINE'});await (choice.accept?dialog.accept():dialog.dismiss());});
 const idle=()=>page.waitForFunction(()=>!document.body.classList.contains('working'));
 const click=async selector=>{await page.locator(selector).click();await idle();assert.equal(await page.locator('#notice[data-kind="error"]').isVisible(),false);};
 const choose=async(pattern,accept,action)=>{assert.equal(consent,null);consent={pattern,accept};await action();assert.equal(consent,null,'Expected explicit decision was not requested');};
 const settle=async()=>{const until=Date.now()+300000;while(Date.now()<until){const v=await state();if(!v.locked){assert(!v.runs.some(r=>['FAILED','INTERRUPTED'].includes(r.state)),JSON.stringify(v.runs));await click('.projectbar [data-action="refresh"]');return v;}await new Promise(r=>setTimeout(r,200));}throw Error('Bounded native output task timed out; do not restart automatically');};
 async function play(selector){await page.waitForFunction(selector=>{const v=document.querySelector(selector);return v&&v.readyState>=2&&!v.error;},selector);await page.locator(selector).evaluate(v=>{v.muted=true;v.currentTime=0;return v.play();});await page.waitForFunction(selector=>document.querySelector(selector)?.ended===true,selector);}
 await page.goto(app.origin+'/workbench#'+app.token);await idle();await click('[data-action="project"][data-id="'+p.id+'"]');
 async function renderShot(scene,shot,declineFirst=false){
  await page.locator('#scene-picker').selectOption(scene.id);await idle();await click('[data-action="select-shot"][data-id="'+shot.id+'"]');
  if(!await page.locator('[data-action="render"]').count()){await click('[data-action="readiness"]');await settle();}
  for(const [field,value] of [['width','64'],['height','64'],['samples','1']])await page.locator('#render-'+field).fill(value);
  assert.equal(await page.locator('#render-camera').inputValue(),shot.camera);assert.equal(await page.locator('#render-start').inputValue(),String(shot.start));assert.equal(await page.locator('#render-end').inputValue(),String(shot.end));
  assert.equal(await page.locator('#render-device').inputValue(),'0');
  if(declineFirst){const before=await state();await choose(/^Authorize CPU render/,false,()=>click('[data-action="render"]'));assert.deepEqual((await state()).project.jobs,before.project.jobs);}
  const count=shot.end-shot.start+1;assert(report.framesAuthorized+count<=report.frameBudget);report.framesAuthorized+=count;
  await choose(/^Authorize CPU render/,true,()=>click('[data-action="render"]'));const v=await settle(),current=v.project.workbench.scenes.find(x=>x.id===scene.id),movie=current.renders.at(-1);
  assert.equal(movie.shotId,shot.id);assert.equal(movie.shotRevision,shot.revision);assert.equal(movie.video.frames,count);assert.equal(movie.video.state,'SUCCEEDED');assert.equal(movie.video.human_acceptance,'PENDING');assert.equal(movie.approved,false);assert.equal(movie.data.render_device.backend,'CPU');
  const file=path.join(p.directory,'Deliverables',movie.video.plan.id,'film.mp4');assert.deepEqual(await fileHash(file),{sha256:movie.video.sha256,size:movie.video.size});
  const selector='video[aria-label="Rendered shot movie"]';assert.equal(await page.locator(selector).getAttribute('data-id'),movie.id);await play(selector);
  if(declineFirst){
   const handle=await page.$(selector);await handle.evaluate(v=>{v.pause();return new Promise(resolve=>{v.addEventListener('seeked',resolve,{once:true});v.currentTime=v.duration/3;});});const position=await handle.evaluate(v=>v.currentTime);
   await click('.projectbar [data-action="refresh"]');assert.equal(await handle.evaluate(v=>v.isConnected&&v===document.querySelector('video[aria-label="Rendered shot movie"]')),true);assert(Math.abs(await handle.evaluate(v=>v.currentTime)-position)<.01);
   await choose(/watched the real movie/,false,()=>click('[data-action="approve-render"][data-id="'+movie.id+'"]'));assert.equal((await state()).project.workbench.scenes.find(s=>s.id===scene.id).renders.at(-1).approved,false);
  }
  await choose(/watched the real movie/,true,()=>click('[data-action="approve-render"][data-id="'+movie.id+'"]'));report.renders.push({sceneId:scene.id,id:movie.id,shotId:shot.id,shotRevision:shot.revision,jobId:movie.jobId,checkpointId:movie.checkpointId,file,...await fileHash(file),video:movie.video});
  return movie;
 }
 for(const scene of scenes)for(const shot of scene.shots)await renderShot(scene,shot,report.renders.length===0);
 assert.equal(report.framesAuthorized,16);report.checks.push('Four explicit real CPU shot renders across three synthetic scenes, two cameras in one world, inline full playback, declined render/review no dependent work, refresh keeps exact video');
 const firstRender=report.renders[0],job=await app.runtime.job(firstRender.jobId),frames=job.outputs.filter(x=>/frame_\d+\.png$/.test(x.path));assert.equal(frames.length,4);assert(new Set(frames.map(x=>x.sha256)).size>1,'Animated source must change actual rendered pixels');
 await click('.projectbar [data-action="tab"][data-tab="film"]');
 for(const r of report.renders)await click('[data-action="add-clip"][data-id="'+r.id+'"]');
 async function buildCut(expectedFrames){
  await choose(/Encode this exact ordered list/,true,()=>click('[data-action="build-film"]'));const v=await settle(),cut=v.project.workbench.film.cuts.at(-1);
  assert.equal(cut.result.frames,expectedFrames);assert.equal(cut.result.state,'SUCCEEDED');assert.equal(cut.approved,false);assert.equal(cut.result.human_acceptance,'PENDING');
  const directory=path.join(p.directory,'Deliverables',cut.id),file=path.join(directory,'film.mp4');assert.deepEqual(await fileHash(file),{sha256:cut.result.sha256,size:cut.result.size});
  assert.equal(await page.locator('video[aria-label="Final film"]').getAttribute('data-id'),cut.id);await play('video[aria-label="Final film"]');
  report.cuts.push({id:cut.id,file,...await fileHash(file),manifest:await fileHash(path.join(directory,'manifest.json')),result:cut.result});return cut;
 }
 const firstCut=await buildCut(16);await choose(/watched the complete cut/,true,()=>click('[data-action="approve-cut"]'));await page.screenshot({path:path.join(out,'first-film.png'),fullPage:true});
 const filmPosition=.1;await page.locator('video[aria-label="Final film"]').evaluate((v,t)=>{v.pause();v.currentTime=t;},filmPosition);
 const firstScene=scenes[0],firstShot=firstScene.shots[0],sourceButton='.film-strip [data-action="edit-source"][data-id="'+firstScene.id+'"][data-shot="'+firstShot.id+'"]';
 await click(sourceButton);assert.equal((await state()).project.workbench.scenes[0].selectedShot,firstShot.id);assert.equal(await page.locator('#scene-picker').inputValue(),firstScene.id);
 await click('[data-action="return-film"]');assert.equal(await page.locator('#film-cut').inputValue(),firstCut.id);await page.waitForFunction(t=>Math.abs(document.querySelector('video[aria-label="Final film"]')?.currentTime-t)<.03,filmPosition);
 report.checks.push('Actual four-shot film encoded, FFprobe validated/full FFmpeg decoded by native adapter and fully browser-played; source roundtrip retains shot, arrangement, cut and time');
 await click(sourceButton);await click('[data-action="render-shots"]');
 const layerReady=async()=>{await page.waitForFunction(()=>document.querySelector('[data-action="layer-ready"]')?.disabled===false,null,{timeout:205000});await idle();};
 await layerReady();await click('[data-action="edit-shot"][data-id="'+firstShot.id+'"]');await page.locator('#shot-end').fill('3');await click('[data-action="save-shot"]');
 let v=await state(),revised=v.project.workbench.scenes.find(s=>s.id===firstScene.id).shots.find(s=>s.id===firstShot.id);
 assert.equal(revised.revision,firstShot.revision+1);assert.equal(revised.end,3);assert.equal(v.project.workbench.scenes[0].current,firstScene.cp.id);
 await click('[data-action="return-film"]');assert.equal(await page.locator('[data-action="build-film"]').isDisabled(),true);assert.equal(await page.locator('[data-action="approve-cut"]').isDisabled(),true);
 const priorJobs=v.project.jobs,priorCuts=v.project.workbench.film.cuts;
 await post('approve-cut',{revision:v.project.revision,cutId:firstCut.id},409);
 await post('assemble',{revision:v.project.revision,confirmed:true},409);
 v=await state();assert.deepEqual(v.project.jobs,priorJobs);assert.deepEqual(v.project.workbench.film.cuts,priorCuts);
 report.checks.push('Shot revision preserves checkpoint and old movie; UI disables stale approval/build and backend refuses both without scheduling a job');
 await click(sourceButton);await layerReady();await choose(/reviewed every named shot/,true,()=>click('[data-action="layer-ready"]'));
 await layerReady();await choose(/reviewed real lighting for every affected shot/,true,()=>click('[data-action="layer-ready"]'));
 const replacement=await renderShot(firstScene,revised);assert.equal(report.framesAuthorized,19);
 await click('.projectbar [data-action="tab"][data-tab="film"]');await click('[data-action="remove-clip"][data-index="0"]');await click('[data-action="add-clip"][data-id="'+replacement.id+'"]');
 for(let index=3;index>0;index--)await click('[data-action="reorder"][data-index="'+index+'"][data-delta="-1"]');
 v=await state();assert.deepEqual(v.project.workbench.film.clips.map(x=>x.renderId),[replacement.id,...report.renders.slice(1,4).map(x=>x.id)]);
 const secondCut=await buildCut(15);assert.notEqual(secondCut.id,firstCut.id);assert.notEqual(secondCut.result.sha256,firstCut.result.sha256);
 report.checks.push('Explicit replacement render and new 15-frame cut; unchanged three shots reused, old 16-frame film never overwritten');
 const arrangement=(await state()).project.workbench.film.clips;
 await page.locator('#film-cut').selectOption(firstCut.id);await idle();assert.equal(await page.locator('video[aria-label="Final film"]').getAttribute('data-id'),firstCut.id);await play('video[aria-label="Final film"]');
 assert.deepEqual((await state()).project.workbench.film.clips,arrangement);
 await page.locator('video[aria-label="Final film"]').evaluate((node,t)=>{node.pause();node.currentTime=t;},filmPosition);
 await click(sourceButton);await click('[data-action="return-film"]');assert.equal(await page.locator('#film-cut').inputValue(),firstCut.id);
 await page.waitForFunction(t=>Math.abs(document.querySelector('video[aria-label="Final film"]')?.currentTime-t)<.03,filmPosition);
 assert.deepEqual((await state()).project.workbench.film.clips,arrangement);
 await page.screenshot({path:path.join(out,'historical-film.png'),fullPage:true});
 await page.locator('#film-cut').selectOption(secondCut.id);await idle();await play('video[aria-label="Final film"]');
 await page.screenshot({path:path.join(out,'replacement-film.png'),fullPage:true});await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'replacement-film-mobile.png'),fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await click(sourceButton);assert.equal(await page.locator('video[aria-label="Rendered shot movie"]').getAttribute('data-id'),replacement.id);await play('video[aria-label="Rendered shot movie"]');
 await page.screenshot({path:path.join(out,'render-mobile.png'),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 for(const scene of scenes)assert.deepEqual(await fileHash(path.join(p.directory,scene.cp.path)),original);
 for(const r of report.renders)assert.deepEqual(await fileHash(r.file),{sha256:r.sha256,size:r.size});
 for(const c of report.cuts){assert.deepEqual(await fileHash(c.file),{sha256:c.sha256,size:c.size});assert.deepEqual(await fileHash(path.join(path.dirname(c.file),'manifest.json')),c.manifest);}
 assert.deepEqual(await fileHash(source),original);assert.deepEqual(report.errors,[]);
 report.tools={ffmpeg:{path:ffmpeg,...await fileHash(ffmpeg)},ffprobe:{path:ffprobe,...await fileHash(ffprobe)}};
 report.checks.push('Historical cut playback/source roundtrip retains exact cut/time without restoring old arrangement; desktop/mobile videos play; source, all checkpoints, prior movies and cut manifests remain byte-identical');
 report.status='PASS';

}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,framesAuthorized:report.framesAuthorized,error:report.error}));}
