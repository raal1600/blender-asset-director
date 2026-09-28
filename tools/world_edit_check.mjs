/** Synthetic browser -> authenticated API -> actual Blender -> saved file.
 * Explicit disposable root, generated inputs and installed browser only.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {randomUUID,createHash} from 'node:crypto';
import {createApp} from '../launcher/server.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,generated,python,blender,playwright].every(v=>v&&path.isAbsolute(v))&&(!chrome||path.isAbsolute(chrome)),'Explicit absolute fixture/tool paths required');
assert(!await exists(out),'Use a new evidence folder');
assert.equal((await json(path.join(generated,'world_layers_report.json'))).status,'PASS','Generated two-rig fixture required');
await fs.mkdir(out,{recursive:true});
const repo=fileURLToPath(new URL('../',import.meta.url)),source=path.join(generated,'placed.blend'),sourceBefore=await fileHash(source);
const report={kind:'synthetic-world-direct-edit',checks:[],errors:[],requests:[],not_tested:['Native GUI controls','Human creative approval','Licensed production assets']};
let app,browser,page;
try{
 app=await createApp({root:path.join(out,'Studio'),port:0,config:{python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')}});
 const prepared=await app.runtime.harness(['job-prepare','scene-audit','--input',source]);
 const result=await app.runtime.harness(['job-run',prepared.id,'--blender',blender]);
 const audit=await app.workbench.result(result);
 let project=await app.store.create('Synthetic World direct editing','Generated rigs and props; no human creative acceptance.');
 await app.workbench.create(project.id,project.revision,'Two performers and props');project=await app.store.get(project.id);
 const scene=project.workbench.scenes[0],cpId='cp_'+randomUUID(),relative='Scenes/'+cpId+'.blend';
 await fs.copyFile(source,path.join(project.directory,relative),fs.constants.COPYFILE_EXCL);
 scene.checkpoints.push({id:cpId,path:relative,...sourceBefore,parent:null,stage:'world',createdAt:new Date().toISOString(),source:'synthetic-native-world-fixture',audit});scene.current=cpId;
 project=await app.store.save(project,project.revision);
 const before=await fileHash(path.join(project.directory,'project.json'));
 const {chromium}=await import(pathToFileURL(playwright).href);
 browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});
 const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});page=await context.newPage();page.setDefaultTimeout(25000);
 page.on('pageerror',e=>report.errors.push(String(e).replaceAll(app.token,'[REDACTED]')));
 page.on('request',r=>{if(r.url().startsWith(app.origin+'/'))report.requests.push({path:new URL(r.url()).pathname,method:r.method()});else if(!r.url().startsWith('blob:'))report.errors.push('Unexpected external request');});
 page.on('response',r=>{if(r.status()>=400)report.errors.push(r.status()+' '+new URL(r.url()).pathname);});
 let approveSyntheticWorld=false;page.on('dialog',d=>approveSyntheticWorld?d.accept():d.dismiss());
 const idle=()=>page.waitForFunction(()=>!document.body.classList.contains('working'));
 const click=async selector=>{await page.locator(selector).click();await idle();};
 const ready=async()=>{await page.waitForFunction(()=>['ready','failed'].includes(document.querySelector('[data-scene-viewer]')?.dataset.viewerState),null,{timeout:205000});assert.equal(await page.locator('[data-scene-viewer]').getAttribute('data-viewer-state'),'ready',await page.locator('[data-scene-viewer]').innerText());};
 await page.goto(app.origin+'/workbench#'+app.token);await idle();await click('[data-action="project"][data-id="'+project.id+'"]');await ready();
 const host=page.locator('[data-scene-viewer]'),picker=host.locator('[data-world-pick]');
 assert.equal(await picker.locator('option').count(),4,'Two rigs and multi-root prop are separately selectable');
 assert.equal(await host.locator('.viewer-animation').isVisible(),false);
 await page.screenshot({path:path.join(out,'01-ready.png'),fullPage:true});
 report.checks.push('Real static GLB + three native instance bindings + usable editor');
 const observedInstances=await picker.locator('option').evaluateAll(rows=>rows.map(x=>({id:x.value,label:x.textContent})).filter(x=>x.id));
 // Instance UUID order is deliberately unstable. The multi-root prop has a
 // genuine empty gap at its bounds centre, so bind the pointer target to the
 // observed generated skin rather than assuming option 2 is a character.
 const ids=['SyntheticRig0','SyntheticRig1','StaticProp'].map(name=>{
   const row=observedInstances.find(x=>x.label==='World placement - '+name);assert(row,'Observed generated instance '+name);return row.id;
 });
 // Real ray picking and handle drag. Focusing a known visible instance gives a
 // stable user-visible target without exposing an internal editor test channel.
 await picker.selectOption(ids[1]);await host.locator('[data-world-focus]').click();await picker.selectOption('');
 const pickCanvas=host.locator('canvas');await pickCanvas.scrollIntoViewIfNeeded();let bounds=await pickCanvas.boundingBox();
 await page.mouse.click(bounds.x+bounds.width/2,bounds.y+bounds.height/2);assert.equal(await picker.inputValue(),ids[1]);
 let handlePoint=null;
 for(let dx=12;dx<=110&&!handlePoint;dx+=8)for(let dy=-38;dy<=38&&!handlePoint;dy+=8){
   const point={x:bounds.x+bounds.width/2+dx,y:bounds.y+bounds.height/2+dy};await page.mouse.move(point.x,point.y);
   if((await host.locator('[data-world-handle]').innerText())==='translate · X')handlePoint=point;
 }
 assert(handlePoint,'Observed Move X handle must be reachable');
 await page.mouse.down();await page.mouse.move(handlePoint.x+55,handlePoint.y,{steps:12});await page.mouse.up();
 assert.match(await page.locator('.world-savebar').innerText(),/Unsaved placement/);await click('[data-action="world-undo"]');
 assert.match(await page.locator('.world-savebar').innerText(),/All changes saved/);
 await host.getByRole('button',{name:'Reset view',exact:true}).click();
 report.checks.push('Real pointer ray selection and Move gizmo with one-step undo');
 await pickCanvas.focus();await pickCanvas.press('Control+a');assert.equal(await host.getAttribute('data-selected-instances'),'3');
 await host.locator('[data-world-focus]').click();bounds=await pickCanvas.boundingBox();handlePoint=null;
 for(let dx=12;dx<=110&&!handlePoint;dx+=8)for(let dy=-38;dy<=38&&!handlePoint;dy+=8){
   const point={x:bounds.x+bounds.width/2+dx,y:bounds.y+bounds.height/2+dy};await page.mouse.move(point.x,point.y);
   if((await host.locator('[data-world-handle]').innerText())==='translate · X')handlePoint=point;
 }
 assert(handlePoint,'Group Move X handle must be reachable');await page.mouse.down();await page.mouse.move(handlePoint.x+45,handlePoint.y,{steps:10});await page.mouse.up();
 assert.match(await page.locator('.world-savebar').innerText(),/3 assets/);await click('[data-action="world-undo"]');
 assert.match(await page.locator('.world-savebar').innerText(),/All changes saved/);
 await host.getByRole('button',{name:'Reset view',exact:true}).click();
 report.checks.push('Multi-instance pointer transform and atomic group undo');
 await picker.selectOption(ids[0]);await host.locator('.world-transform-details summary').click();
 const x=host.getByLabel('Placement X',{exact:true}),baseX=Number(await x.inputValue());
 const moveX=async value=>{await x.fill(String(value));await host.locator('[data-world-apply]').click();};
 const canvas=host.locator('canvas'),beforeImage=await canvas.screenshot();
 await moveX(baseX+2);assert.match(await page.locator('.world-savebar').innerText(),/Unsaved placement/);
 assert.notEqual(createHash('sha256').update(await canvas.screenshot()).digest('hex'),createHash('sha256').update(beforeImage).digest('hex'));
 assert.deepEqual(await fileHash(path.join(project.directory,'project.json')),before,'Draft must not write project');
 assert.equal(report.requests.filter(r=>r.path.endsWith('/world-save')).length,0);
 await click('[data-action="world-undo"]');assert.equal(Number(await x.inputValue()),baseX);
 await moveX(baseX+2);await click('[data-action="world-discard-draft"]');assert.equal(Number(await x.inputValue()),baseX);
 report.checks.push('Immediate unsaved WebGL placement, Undo and Discard with no backend job');
 await moveX(baseX+2);await click('[data-action="tab"][data-tab="film"]');
 assert.match(await page.locator('#dialog').innerText(),/Keep your placement changes/);await click('#dialog [data-action="close"]');
 assert.match(await page.locator('.world-savebar').innerText(),/Unsaved placement/);
 await page.screenshot({path:path.join(out,'02-unsaved.png'),fullPage:true});
 // Edit a second instance before one Save; source object/bone channels stay native.
 await picker.selectOption(ids[1]);const secondX=Number(await x.inputValue());
 await host.getByLabel('Placement Heading',{exact:true}).fill('30');await host.getByLabel('Placement Scale',{exact:true}).fill('1.25');await moveX(secondX-2);
 assert.match(await page.locator('.world-savebar').innerText(),/2 assets/);
 const saved=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/workbench/world-save');
 await page.locator('[data-action="save-world"]').click();const saveResponse=await saved;assert.equal(saveResponse.status(),200,await saveResponse.text());
 await page.waitForFunction(()=>!document.body.classList.contains('working'),null,{timeout:215000});await ready();
 project=await app.store.get(project.id);const afterScene=project.workbench.scenes[0],after=afterScene.checkpoints.find(c=>c.id===afterScene.current);
 assert.notEqual(after.id,cpId);assert.equal(after.parent,cpId);assert.equal(afterScene.candidate,null);assert.deepEqual(afterScene.completed,{});
 const savedJob=await app.runtime.harness(['job-show',after.jobId]);const savedData=await app.workbench.result(savedJob);
 assert.equal(savedData.reopened,true);assert.equal(savedData.transforms.length,2);
 const rotated=savedData.transforms.find(t=>t.instance===ids[1]).after;assert(Math.abs(Math.hypot(rotated[0],rotated[4],rotated[8])-1.25)<1e-4);assert(Math.abs(Math.atan2(rotated[4],rotated[0])-Math.PI/6)<1e-4);
 assert.deepEqual(await fileHash(source),sourceBefore);assert.deepEqual(await fileHash(path.join(project.directory,relative)),sourceBefore);
 await page.screenshot({path:path.join(out,'03-saved.png'),fullPage:true});
 report.checks.push('One Save runs real Blender, verifies two transforms and reopened file, preserves original/checkpoint and does not approve World');
 report.saved={checkpointId:after.id,sha256:after.sha256,jobId:after.jobId,transforms:savedData.transforms};
 assert.equal(report.requests.filter(r=>r.path.endsWith('/world-save')).length,1);
 const newPicker=page.locator('[data-world-pick]');await newPicker.selectOption(ids[0]);
 await page.locator('.world-transform-details summary').click();assert(Math.abs(Number(await page.getByLabel('Placement X',{exact:true}).inputValue())-baseX-2)<1e-4);
 await newPicker.selectOption(ids[1]);assert(Math.abs(Number(await page.getByLabel('Placement X',{exact:true}).inputValue())-secondX+2)<1e-4);
 report.checks.push('Refreshed viewer agrees with saved Blender placements');
 // Controlled transport failure must not erase an unsaved draft or create work.
 const savedX=Number(await page.getByLabel('Placement X',{exact:true}).inputValue());
 await page.getByLabel('Placement X',{exact:true}).fill(String(savedX+1));await page.locator('[data-world-apply]').click();
 await page.route('**/api/workbench/world-save',route=>route.abort());await click('[data-action="save-world"]');
 assert.match(await page.locator('.world-savebar').innerText(),/Unsaved placement/);assert.equal((await app.store.get(project.id)).workbench.scenes[0].current,after.id);
 await page.unroute('**/api/workbench/world-save');await click('[data-action="world-discard-draft"]');
 report.checks.push('Failed Save transport preserves local draft and saved scene');
 // A second controlled writer changes the checkpoint while this browser drafts.
 await page.getByLabel('Placement X',{exact:true}).fill(String(savedX+3));await page.locator('[data-world-apply]').click();
 project=await app.store.get(project.id);const replacement={...after,id:'cp_'+randomUUID(),parent:after.id,source:'synthetic-concurrent-checkpoint'};
 replacement.path='Scenes/'+replacement.id+'.blend';await fs.copyFile(path.join(project.directory,after.path),path.join(project.directory,replacement.path),fs.constants.COPYFILE_EXCL);
 project.workbench.scenes[0].checkpoints.push(replacement);project.workbench.scenes[0].current=replacement.id;await app.store.save(project,project.revision);
 await click('[data-action="refresh"]');assert.match(await page.locator('.world-savebar').innerText(),/Preview out of date/);
 assert.equal(await page.locator('[data-action="save-world"]').isDisabled(),true);assert.equal(Number(await page.getByLabel('Placement X',{exact:true}).inputValue()),savedX+3);
 await page.screenshot({path:path.join(out,'04-stale-draft.png'),fullPage:true});await click('[data-action="world-discard-draft"]');await ready();
 assert.equal((await app.store.get(project.id)).workbench.scenes[0].current,replacement.id);
 report.checks.push('Concurrent checkpoint change retains stale local draft; Save refuses until deliberate discard/reload');
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'04-mobile.png'),fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'No horizontal overflow at 390px');
 approveSyntheticWorld=true;await click('[data-action="approve"]');approveSyntheticWorld=false;
 await page.waitForFunction(()=>document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready'&&document.querySelector('[data-action="action-ready"]')?.disabled===false,null,{timeout:205000});
 assert.equal(await page.getByRole('heading',{name:'Bring your world to life',exact:true}).isVisible(),true);
 assert.equal(await page.locator('#scene-picker').inputValue(),scene.id);
 const transitioned=(await app.store.get(project.id)).workbench.scenes[0];assert.equal(transitioned.stage,'action');assert.equal(transitioned.current,replacement.id);assert.equal(transitioned.completed.action,undefined);
 await page.screenshot({path:path.join(out,'05-world-to-action.png'),fullPage:true});
 await click('[data-action="stage"][data-stage="world"]');await page.reload();await ready();
 assert.equal((await app.store.get(project.id)).workbench.scenes[0].current,replacement.id);
 report.checks.push('SCRIPTED SYNTHETIC World completion enters real inspected Action with the same checkpoint; return/reload preserves it without Action approval');
 assert.deepEqual(report.errors,[]);report.status='PASS';
}catch(error){report.status='FAIL';report.failure=error.stack;if(page){report.page=await page.locator('body').textContent().catch(()=>null);await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}process.exitCode=1;}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,failure:report.failure,output:out}));}
