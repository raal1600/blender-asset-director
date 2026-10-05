/** Real client cancellation of a queued and an observed RUNNING Action save. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,generated,python,blender,playwright,chrome,installedRoot]=process.argv.slice(2);
assert([out,generated,python,blender,playwright,installedRoot].every(x=>x&&path.isAbsolute(x))&&!await exists(out));
assert.equal((await json(path.join(generated,'RESULTS.json'))).status,'PASS');await fs.mkdir(out,{recursive:true});
const source=path.join(generated,'source.blend'),original=await fileHash(source),config=await json(path.join(installedRoot,'SystemRuntime/UserData/Launcher/config.json'));
const factory=(await import(pathToFileURL(path.join(installedRoot,'SystemRuntime/Launcher/server.mjs')).href)).createApp;
const report={kind:'REAL_ACTION_CANCELLATION',checks:[],errors:[],cases:[],queue_gate:'Only delays Action preparation to exercise queue ordering; all native work/results are real',human_acceptance:'NOT_TESTED'};
let app,browser,context,page,releaseQueue;
const until=async(predicate,label,timeout=205000)=>{const deadline=Date.now()+timeout;while(Date.now()<deadline){if(await predicate())return;await new Promise(r=>setTimeout(r,25));}throw Error('Timed out: '+label);};
try{
 app=await factory({root:installedRoot,port:0,config});
 const prepared=await app.runtime.harness(['job-prepare','scene-audit','--input',source]),audit=await app.workbench.result(await app.runtime.harness(['job-run',prepared.id,'--blender',blender]));
 let p=await app.store.create('Synthetic Action cancellation','Generated native animation only');await app.workbench.create(p.id,p.revision,'Cancellation boundary');p=await app.store.get(p.id);
 const scene=p.workbench.scenes[0],cpId='cp_'+randomUUID(),relative='Scenes/'+cpId+'.blend';await fs.copyFile(source,path.join(p.directory,relative),fs.constants.COPYFILE_EXCL);scene.checkpoints.push({id:cpId,path:relative,...original,parent:null,stage:'world',audit});scene.current=cpId;scene.stage='action';scene.completed={world:cpId};p=await app.store.save(p,p.revision);
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});context=await browser.newContext({viewport:{width:1440,height:1100},recordVideo:{dir:path.join(out,'video'),size:{width:1440,height:1100}},serviceWorkers:'block'});page=await context.newPage();page.setDefaultTimeout(30000);
 const clean=v=>String(v).replaceAll(app.token,'[REDACTED]');page.on('pageerror',e=>report.errors.push(clean(e.message)));page.on('console',m=>{if(m.type()==='error')report.errors.push(clean(m.text()));});page.on('dialog',d=>d.dismiss());
 const idle=()=>page.waitForFunction(()=>!document.body.classList.contains('working'));
 const ready=()=>page.waitForFunction(()=>!document.body.classList.contains('working')&&document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready'&&!document.querySelector('[data-action-field="performer"]')?.disabled,null,{timeout:205000});
 const click=async selector=>{await page.locator(selector).click();await idle();};
 await page.goto(app.origin+'/workbench#'+app.token);await click('[data-action="project"][data-id="'+p.id+'"]');await ready();await click('[data-action="motion-enable"]');await page.getByLabel('Performer',{exact:true}).selectOption('TestPerformer0');
 for(const label of ['Observed 0 0','Observed 0 1'])await page.getByLabel('Add animation').selectOption({label});
 const native=app.runtime.harness.bind(app.runtime);let queued=false;
 const queueGate=new Promise(resolve=>releaseQueue=resolve);app.runtime.harness=async(...args)=>{if(args[0][0]==='job-prepare'&&args[0][1]==='action-edit'){queued=true;await queueGate;}return native(...args);};
 await page.locator('[data-action="action-save"]').click();await until(()=>queued,'queued native preparation');
 await page.locator('[data-action="action-cancel"]').click();await until(()=>[...app.workbench.actionSaves.values()].some(e=>e.cancelled),'queued cancellation accepted');releaseQueue();await ready();
 let run=(await app.store.runs(p.id)).find(r=>r.action==='action-edit');assert.equal(run.state,'CANCELLED');let job=await app.runtime.job(run.jobId);assert.equal(job.state,'CANCELLED');assert.equal(job.worker_pid,undefined);assert.equal(job.outputs.length,0);
 p=await app.store.get(p.id);assert.equal(p.workbench.scenes[0].current,cpId);assert.equal(p.workbench.scenes[0].checkpoints.length,1);assert.equal(await page.locator('[data-action="action-save"]').isEnabled(),true);assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),false);
 report.cases.push({phase:'queued',runId:run.id,jobId:job.id,state:run.state,native_state:job.state,worker_started:false});await page.screenshot({path:path.join(out,'01-queued-cancelled.png'),fullPage:true});report.checks.push('Visible Cancel Save cancels queued preparation before a Blender child exists; prior checkpoint and editable draft survive');
 app.runtime.harness=native;
 await page.getByRole('button',{name:'Connection 26 to 31',exact:true}).click();await page.getByLabel('Transition frames',{exact:true}).fill('12');await page.locator('[data-action="action-save"]').click();
 let running,worker;
 await until(async()=>{running=(await app.store.runs(p.id)).find(r=>r.action==='action-edit'&&r.state==='RUNNING');if(!running?.jobId)return false;const filename=path.join(config.library,'jobs',running.jobId,'job.json');if(!await exists(filename))return false;worker=await json(filename);const marker=path.join(config.library,'jobs',running.jobId,'worker-process.json');if(worker.state!=='RUNNING'||!await exists(marker))return false;const processRecord=await json(marker);assert.equal(processRecord.job_id,worker.id);assert.equal(processRecord.implementation,worker.specification.implementation);worker.worker_pid=processRecord.pid;return !!worker.worker_pid;},'actual Blender child RUNNING');
 const pid=worker.worker_pid,started=performance.now();await page.locator('[data-action="action-cancel"]').click();await ready();run=(await app.store.runs(p.id)).find(r=>r.id===running.id);job=await app.runtime.job(running.jobId);assert.equal(run.state,'CANCELLED');assert.equal(job.state,'CANCELLED');assert.equal(job.outputs.length,0);
 await until(()=>{try{process.kill(pid,0);return false;}catch(e){assert.equal(e.code,'ESRCH');return true;}},'owned Blender child reaped',10000);
 p=await app.store.get(p.id);assert.equal(p.workbench.scenes[0].current,cpId);assert.equal(p.workbench.scenes[0].checkpoints.length,1);assert.equal(p.workbench.scenes[0].run,null);assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),false);assert.equal(await exists(path.join(p.directory,'Runs/.interactive-execution.lock')),false);assert.equal(await page.locator('[data-action="action-save"]').isEnabled(),true);
 report.cases.push({phase:'running',runId:run.id,jobId:job.id,worker_pid:pid,state:run.state,native_state:job.state,cancel_to_ready_ms:performance.now()-started,worker_reaped:true});await page.screenshot({path:path.join(out,'02-running-cancelled.png'),fullPage:true});
 assert.deepEqual(await fileHash(source),original);assert.deepEqual(await fileHash(path.join(p.directory,relative)),original);assert.deepEqual(report.errors,[]);report.checks.push('Visible Cancel Save stops and reaps observed running Blender, marks both receipts CANCELLED, releases leases and accepts no checkpoint');report.status='PASS';report.projectId=p.id;
}catch(error){report.status='FAIL';report.error=String(error.stack||error).replaceAll(app?.token||'no-token','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'FAILURE.png'),fullPage:true}).catch(()=>{});}
finally{releaseQueue?.();if(page?.video())report.video=path.relative(out,await page.video().path());await context?.close();await browser?.close();if(app){await until(()=>!app.workbench.running.size,'owned workers finish cleanup').catch(e=>report.errors.push(String(e)));app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error}));}
