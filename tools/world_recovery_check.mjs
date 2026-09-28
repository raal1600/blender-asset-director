/** Real owned-worker interruption and explicit recovery; generated scenes only. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createApp} from '../launcher/server.mjs';
import {command} from '../launcher/lib/runtime.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome]=process.argv.slice(2);
assert([out,generated,python,blender,playwright].every(x=>x&&path.isAbsolute(x))&&!await exists(out));
assert.equal((await json(path.join(generated,'world_layers_report.json'))).status,'PASS');
const source=path.join(generated,'placed.blend'),before=await fileHash(source),repo=fileURLToPath(new URL('../',import.meta.url));await fs.mkdir(out,{recursive:true});
const report={kind:'synthetic-world-worker-recovery',checks:[],errors:[],decisions:[],human_review:'NOT_TESTED',native_desktop:'NOT_TESTED',interruption_point:'owned background Blender startup before publication'};
let app,browser,page;
try{
 const config={python,blender,skill:path.join(repo,'skills/blender-asset-director'),library:path.join(out,'Studio/Database/AssetDirector')};
 app=await createApp({root:path.join(out,'Studio'),port:0,config});const headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
 let p=await app.store.create('Synthetic World recovery','Deliberately interrupt only the owned generated test worker');await app.workbench.create(p.id,p.revision,'Preserved World');p=await app.store.get(p.id);
 const scene=p.workbench.scenes[0],cpId='cp_'+randomUUID(),relative='Scenes/'+cpId+'.blend';await fs.copyFile(source,path.join(p.directory,relative),fs.constants.COPYFILE_EXCL);
 const prepared=await app.runtime.harness(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await app.runtime.harness(['job-run',prepared.id,'--blender',blender]));
 scene.checkpoints.push({id:cpId,path:relative,...before,parent:null,stage:'world',audit});scene.current=cpId;scene.completed={world:cpId};p=await app.store.save(p,p.revision);
 const state=async()=>{const r=await fetch(app.origin+'/api/workbench/state?'+new URLSearchParams({projectId:p.id,compact:true}),{headers});assert.equal(r.status,200);return r.json();};
 const native=app.runtime.harness.bind(app.runtime);let interruptNext=false;
 app.runtime.harness=async(args,timeout)=>{
  if(interruptNext&&args[0]==='job-run'){
   const job=await app.runtime.job(args[1]);assert.equal(job.specification.operation,'world-transform');interruptNext=false;
   await writeJson(path.join(out,'TEST_FIXTURE.json'),{kind:'synthetic-world-recovery',library:config.library,job_id:job.id});
   const result=await command(python,['-B',path.join(repo,'tools/world_interrupt_worker.py'),out,config.library,job.id,blender],timeout);
   return JSON.parse(result.stdout);
  }
  return native(args,timeout);
 };
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});page=await browser.newPage({viewport:{width:1440,height:1000},serviceWorkers:'block'});page.setDefaultTimeout(30000);
 page.on('pageerror',error=>report.errors.push(error.message.replaceAll(app.token,'[REDACTED]')));
 let accept=false;page.on('dialog',async dialog=>{report.decisions.push({message:dialog.message(),answer:accept?'ACCEPT':'DECLINE',authority:'SCRIPTED_SYNTHETIC_TEST_ONLY'});if(accept)await dialog.accept();else await dialog.dismiss();});
 const idle=()=>page.waitForFunction(()=>!document.body.classList.contains('working'));
 const click=async action=>{await page.locator('[data-action="'+action+'"]').click();await idle();};
 const ready=async()=>{await idle();await page.waitForFunction(()=>['ready','failed'].includes(document.querySelector('[data-scene-viewer]')?.dataset.viewerState),null,{timeout:205000});assert.equal(await page.locator('[data-scene-viewer]').getAttribute('data-viewer-state'),'ready',await page.locator('[data-scene-viewer]').innerText());};
 await page.goto(app.origin+'/workbench#'+app.token);await idle();await page.locator('[data-action="project"][data-id="'+p.id+'"]').click();await ready();
 const picker=page.locator('[data-world-pick]'),chosen=(await picker.locator('option').evaluateAll(rows=>rows.map(n=>({id:n.value,name:n.textContent})))).find(n=>n.name==='World placement - SyntheticRig0');assert(chosen);
 await picker.selectOption(chosen.id);await page.locator('.world-transform-details summary').click();const input=page.getByLabel('Placement X',{exact:true}),requested=Number(await input.inputValue())+2;
 await input.fill(String(requested));await page.locator('[data-world-apply]').click();interruptNext=true;await click('save-world');
 let v=await state(),s=v.project.workbench.scenes[0],failed=v.runs.find(r=>r.action==='world-transform'&&r.state==='FAILED');assert(failed,JSON.stringify(v.runs));
 const interrupted=await json(path.join(out,'INTERRUPTION.json'));assert.equal(interrupted.stopped,true);assert.equal(interrupted.job_id,failed.jobId);assert.notEqual(interrupted.returncode,0);report.interruption=interrupted;
 const jobDir=path.join(config.library,'jobs',failed.jobId),failedJob=await app.runtime.job(failed.jobId);assert.equal(failedJob.state,'FAILED');assert.equal(failedJob.last_error.code,'BLENDER_FAILED');
 assert.equal(s.current,cpId);assert.equal(s.candidate,null);assert.deepEqual(s.completed,{world:cpId});assert.equal(v.locked,false);assert.match(await page.locator('.world-savebar').innerText(),/Unsaved placement/);assert.equal(Number(await input.inputValue()),requested);
 assert.equal(await exists(path.join(jobDir,'result.blend')),false);const failureBytes={job:await fileHash(path.join(jobDir,'job.json')),log:await fileHash(path.join(jobDir,'worker.log'))};report.failedRun=failed;
 report.checks.push('Exact owned native Blender child was interrupted during startup; native failure is genuine, no scene published, original/completion and local draft retained');
 await click('recover');await click('retry');assert.equal(report.decisions.at(-1)?.answer,'DECLINE','Actual scripted confirmation dialog must be observed, not inferred from unchanged state');assert.match(report.decisions.at(-1).message,/Archive the failed native attempt/);assert.equal((await app.runtime.job(failed.jobId)).state,'FAILED');assert.deepEqual(await fileHash(path.join(jobDir,'job.json')),failureBytes.job);assert.equal((await fs.readdir(jobDir)).some(n=>n.startsWith('attempt-')),false);
 report.checks.push('Scripted decline of explicit retry leaves the failed job and all evidence untouched; no dependent worker executes');
 accept=true;await click('retry');accept=false;
 assert.equal((await app.runtime.job(failed.jobId)).state,'PLANNED',await page.locator('#notice').innerText());
 const archiveNames=(await fs.readdir(jobDir)).filter(n=>n.startsWith('attempt-'));assert.equal(archiveNames.length,1);const archive=path.join(jobDir,archiveNames[0]);
 assert.deepEqual(await fileHash(path.join(archive,'job.json')),failureBytes.job);assert.deepEqual(await fileHash(path.join(archive,'worker.log')),failureBytes.log);assert.equal(await exists(path.join(jobDir,'result.blend')),false);
 v=await state();assert.equal(v.project.workbench.scenes[0].current,cpId);assert.equal(Number(await input.inputValue()),requested);
 report.checks.push('Explicit reset archives exact native failure bytes and only returns the job to PLANNED; it does not rerun or approve the scene');
 await click('recover');accept=true;await click('resolve');accept=false;v=await state();const retained=v.runs.find(r=>r.id===failed.id);assert.equal(retained.state,'INTERRUPTED');assert(retained.recovery);assert.equal(retained.error,failed.error);
 assert.equal(v.project.workbench.scenes[0].current,cpId);assert.equal(Number(await input.inputValue()),requested);
 await click('save-world');await ready();v=await state();s=v.project.workbench.scenes[0];assert.notEqual(s.current,cpId);assert.deepEqual(s.completed,{});const saved=s.checkpoints.find(c=>c.id===s.current),success=v.runs.find(r=>r.resultCheckpointId===saved.id);assert.equal(success.state,'SUCCEEDED');assert.equal(success.jobId,failed.jobId);assert.notEqual(success.id,failed.id);
 const result=await app.workbench.result(await app.runtime.job(success.jobId));assert.equal(result.reopened,true);assert.equal(result.transforms.length,1);assert.equal(result.transforms[0].after[3],requested);
 await picker.selectOption(chosen.id);await page.locator('.world-transform-details summary').click();assert.equal(Number(await page.getByLabel('Placement X',{exact:true}).inputValue()),requested);
 report.saved=saved;report.recovery=retained;report.checks.push('Explicit resolve retains prior run error; a new Save runs actual native placement once, reopens and publishes a separate unapproved checkpoint matching the preserved draft');
 assert.deepEqual(await fileHash(source),before);assert.deepEqual(await fileHash(path.join(p.directory,relative)),before);assert.deepEqual(await fileHash(path.join(archive,'job.json')),failureBytes.job);assert.deepEqual(await fileHash(path.join(archive,'worker.log')),failureBytes.log);assert.deepEqual(report.errors,[]);
 await page.screenshot({path:path.join(out,'recovered-world.png'),fullPage:true});report.checks.push('Original, archived failed attempt and old checkpoint preserved; recovered viewer agrees with native placement and has no page errors');report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error.stack||error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error}));}
