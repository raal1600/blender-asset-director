/** Real local scene work. No prototype fixtures, fake progress, or model calls. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {constants} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {assert, exists, fileHash, json, now, safe, snapshot, writeJson, digest} from './storage.mjs';
import {stages, stageIndex, initialWorkbench, checkpointFor, canEnter, approveCheckpoint, validId} from './workbench-model.mjs';
import {referenceImage,sourceCategory} from '../public/asset-presentation.mjs';
import {shotFor,renderIsCurrent,previewIsCurrent} from '../public/workbench-lineage.mjs';
import {assertObservedShot} from './workbench-shots.mjs';
import {Interactions} from './interactions.mjs';
import {buildSessionContext} from './onboarding.mjs';
import {sourcePage,selectedSourceSummary} from './source-browser.mjs';
import {preparedSource,prepareSource,preparedProductionSources} from './library-preparation.mjs';
const uid = prefix => prefix+randomUUID();
const lockName='Runs/.workbench-writer.lock';
const sharedLock='Runs/.interactive-execution.lock';
const nameOK = name => assert(typeof name==='string'&&name.trim().length>=2&&name.length<=100&&!/[\r\n\0]/.test(name),'Use a name of 2–100 characters.');

export class Workbench {
  constructor(store,runtime,config,serialize=action=>action()) {Object.assign(this,{store,runtime,config,serialize});this.running=new Set();}
  async project(id,revision) {
    const p=await this.store.get(id);
    if(revision!==undefined) assert(p.revision===revision,'Project changed. Refresh before continuing.',409);
    p.workbench ||= initialWorkbench(); return p;
  }
  scene(p,id) {const s=p.workbench.scenes.find(s=>s.id===id);assert(s,'Scene not found.',404);return s;}
  interactions(id){return new Interactions(this.store,this.runtime,id,'launcher-workbench');}
  async attest(id,revision,confirmed){const p=await this.project(id,revision);await this.unlocked(p);return this.interactions(id).attestFromLauncher(revision,confirmed);}
  async available() {
    try {const encoder=[this.config.ffmpeg,this.config.ffprobe].every(x=>typeof x==='string'&&path.isAbsolute(x))&&await exists(this.config.ffmpeg)&&await exists(this.config.ffprobe);
      return {...await this.runtime.harness(['workbench-capabilities']),encoder};}
    catch(e) {return {schema:1,available:false,message:'This workbench needs the matching development harness. The installed runtime was not changed.',detail:e.message};}
  }
  async prepareSource(...args){return prepareSource(this,...args);}
  async sourcePage(id,{sceneId,selected=false,production=false,...options}={}) {
    const p=await this.project(id);
    assert(typeof selected==='boolean','Invalid source scope.');
    assert(typeof production==='boolean','Invalid production scope.');
    const inventory=await this.store.inventory();
    const selectedIds=selected?this.scene(p,sceneId).sources:production?[...p.assets.map(a=>a.sourceId),...await preparedProductionSources(this,p,inventory)]:null;
    const page=sourcePage(inventory,{...options,selectedIds});
    page.items=await Promise.all(page.items.map(async source=>({...source,prepared:await preparedSource(this,source)})));
    return page;
  }
  async sourceDetail(id,sourceId) {
    await this.store.get(id);
    assert(validId(sourceId,'src_'),'Invalid source identity.');
    const source=(await this.store.inventory()).sources.find(a=>a.id===sourceId);
    assert(source,'Source not found.',404);return {...source,subcategory:sourceCategory(source),prepared:await preparedSource(this,source)};
  }
  async state(id,{compact=false}={}) {
    const p=await this.project(id);
    const locked=await exists(await safe(p.directory,lockName))||await exists(await safe(p.directory,sharedLock));
    const taskStatuses={};
    for(const scene of p.workbench.scenes.filter(s=>s.task)) {
      const file=await safe(p.directory,`Docs/Workbench/${scene.task}-status.json`);
      if(await exists(file)) {const status=await json(file);assert(status.taskId===scene.task&&status.projectId===id&&status.sceneId===scene.id,'Wrong task status identity.');taskStatuses[scene.id]=status;}
    }
    const inventory=await this.store.inventory();
    return {project:p,stages,taskStatuses,savedScenes:await this.store.scenes(id),inventory:compact?selectedSourceSummary(inventory,p):inventory,locked,sourceUse:await this.interactions(id).sourceStatus(),runs:await this.store.runs(id)};
  }
  async unlocked(p) {
    assert(!await exists(await safe(p.directory,lockName)),'This project has an unfinished workbench task. Collect or resolve it first.',409);
    assert(!await exists(await safe(p.directory,'Runs/.interactive-execution.lock')),'A Codex job is pending or running. Finish it before editing.',409);
    for(const name of await fs.readdir(await safe(p.directory,'Runs'))) {
      if(!name.endsWith('.json'))continue;
      const run=await json(await safe(p.directory,`Runs/${name}`));
      assert(run.projectId===p.id,'A run has an invalid project identity.',409);
      assert(!['RUNNING','PREPARING'].includes(run.state),'An operation is unfinished. Resolve its receipt before starting new work.',409);
    }
    for(const ref of p.jobs) {
      if(!this.config.library) continue;
      const f=await safe(this.config.library,`jobs/${ref.id}/job.json`);
      if(await exists(f)) assert((await json(f)).state!=='RUNNING','A project-bound harness job is still running.',409);
    }
  }
  async lock(p,runId) {
    await this.unlocked(p);
    // Same atomic semaphore as the existing project MCP executor. Separate
    // check-then-lock paths would permit a human/agent race across processes.
    const shared=await safe(p.directory,sharedLock),directory=await safe(p.directory,lockName);
    try {await fs.mkdir(shared);} catch(e) {if(e.code==='EEXIST')assert(false,'Another writer acquired this project.',409);throw e;}
    let own=false;
    try {await fs.mkdir(directory);own=true;await writeJson(path.join(directory,'owner.json'),{projectId:p.id,runId,createdAt:now()});}
    catch(e) {if(own)await fs.rmdir(directory).catch(()=>{});await fs.rmdir(shared);throw e;}
  }
  async unlock(p,runId) {
    const directory=await safe(p.directory,lockName);
    assert((await json(path.join(directory,'owner.json'))).runId===runId,'Writer lease belongs to another task.',409);
    await fs.unlink(path.join(directory,'owner.json'));await fs.rmdir(directory);
    await fs.rmdir(await safe(p.directory,sharedLock));
  }
  async verify(p,scene,checkpointId=scene.current) {
    const verified=await this.store.verify(p.id); assert(verified.ok,'A pinned source changed or is missing. Resolve source versions first.',409);
    const cp=checkpointFor(scene,checkpointId); assert(cp,'Save and approve a scene checkpoint first.',409);
    const bytes=await fileHash(await safe(p.directory,cp.path));
    assert(bytes.sha256===cp.sha256&&bytes.size===cp.size,'Saved checkpoint changed. Import the edited file as a new candidate, never replace an approval.',409);
    return cp;
  }
  async create(id,revision,name) {
    nameOK(name);const p=await this.project(id,revision);await this.unlocked(p);
    assert(p.workbench.scenes.length<200,'This production reached the scene limit.');
    const scene={id:uid('sc_'),name:name.trim(),stage:'world',sources:[],checkpoints:[],current:null,candidate:null,completed:{},renders:[],task:null,run:null,createdAt:now()};
    p.workbench.scenes.push(scene);return {project:await this.store.save(p,p.revision),sceneId:scene.id};
  }
  async enter(id,sceneId,revision,stage) {
    const p=await this.project(id,revision),s=this.scene(p,sceneId);
    assert(!s.task&&!s.candidate&&!s.run,'Finish or resolve the current scene task before changing activity.',409);
    assert(stageIndex(stage)>=0,'Unknown scene activity.');assert(canEnter(s,stage),'Finish the preceding scene activity first.',409);
    s.stage=stage;return this.store.save(p,p.revision);
  }
  async selectSource(id,sceneId,revision,sourceId,selected) {
    const p=await this.project(id,revision),s=this.scene(p,sceneId);await this.unlocked(p);
    assert(validId(sourceId,'src_')&&typeof selected==='boolean','Invalid source selection.');
    if(selected) {
      const item=(await this.store.inventory()).sources.find(a=>a.id===sourceId);assert(item?.available,'Source unavailable. Refresh library.');
      const snap=await snapshot(await safe(this.store.database,item.relative));assert(snap.version===item.version,'Source changed; refresh the library.',409);
      const ref=p.assets.find(a=>a.sourceId===sourceId);
      assert(!ref||ref.version===item.version,'Project pins a different source version. Reconcile it explicitly in the library.',409);
      if(!ref)p.assets.push({sourceId,version:item.version,linkedAt:now()});
      if(!s.sources.includes(sourceId))s.sources.push(sourceId);
    } else s.sources=s.sources.filter(x=>x!==sourceId);
    // Selection is intention, never evidence of import. Existing pins are retained
    // on deselection because other scenes/jobs may still depend on their bytes.
    return this.store.save(p,p.revision);
  }
  async importCheckpoint(id,sceneId,revision,sourceScene) {
    const p=await this.project(id,revision),s=this.scene(p,sceneId);await this.unlocked(p);
    assert(!s.candidate,'Review or discard the existing candidate first.',409);
    assert((await this.store.scenes(id)).includes(sourceScene),'Choose an existing saved file from this project.');
    const source=await safe(p.directory,sourceScene),before=await fileHash(source),cpId=uid('cp_');
    const handle=await fs.open(source);let header;try{header=Buffer.alloc(7);await handle.read(header,0,7,0);}finally{await handle.close();}
    assert(header.toString()==='BLENDER','This file is not an uncompressed Blender scene. Save an uncompressed working copy in Blender.');
    const relative=`Scenes/${s.id}--${cpId}.blend`,destination=await safe(p.directory,relative);
    await fs.copyFile(source,destination,constants.COPYFILE_EXCL);
    const after=await fileHash(source),saved=await fileHash(destination);
    assert(before.sha256===after.sha256&&saved.sha256===before.sha256,'File changed while checkpointing. Candidate was not registered.',409);
    const cp={id:cpId,path:relative,...saved,parent:s.current,stage:s.stage,createdAt:now(),source:'saved-project-file',audit:null};
    await writeJson(await safe(p.directory,`Docs/Workbench/${cp.id}.json`),cp);
    s.checkpoints.push(cp);s.candidate=cp.id;
    return this.store.save(p,p.revision);
  }
  async inspect(id,sceneId,revision,checkpointId) {
    const p=await this.project(id,revision),scene=this.scene(p,sceneId);
    const cp=checkpointFor(scene,checkpointId);assert(cp,'Unknown saved checkpoint.');
    const source=await safe(p.directory,cp.path),before=await fileHash(source);
    assert(before.sha256===cp.sha256,'Checkpoint changed; inspection refused.',409);
    const review=await safe(p.directory,`Scenes/${sceneId}--review-${randomUUID()}.blend`);
    await fs.copyFile(source,review,constants.COPYFILE_EXCL);
    assert((await fileHash(review)).sha256===cp.sha256,'Review copy changed during creation.',409);
    return {processId:await this.runtime.launchReview(p,review),message:'Separate review copy requested. Checkpoint preserved; review-window edits are not automatically collected.'};
  }
  async approve(id,sceneId,revision,stage,checkpointId) {
    const p=await this.project(id,revision),s=this.scene(p,sceneId);await this.unlocked(p);
    assert(checkpointId===s.current||checkpointId===s.candidate,'Approve the current checkpoint or candidate only.',409);
    assert(stage===s.stage&&stage!=='render','Review the current activity; render approval has a separate control.',409);
    const cp=checkpointFor(s,checkpointId);assert(cp,'Checkpoint missing.');
    assert(!s.candidate||cp.stage===stage,'Candidate belongs to another activity.',409);
    assert((await fileHash(await safe(p.directory,cp.path))).sha256===cp.sha256,'Checkpoint changed; approval refused.',409);
    assert((await this.store.verify(id)).ok,'Pinned sources changed; approval refused.',409);
    const record={id:uid('review_'),projectId:id,sceneId,checkpointId,sha256:cp.sha256,stage,decision:'KEEP',createdAt:now(),transport:'launcher-ui'};
    await writeJson(await safe(p.directory,`Docs/Workbench/${record.id}.json`),record);
    approveCheckpoint(s,stage,checkpointId);return this.store.save(p,p.revision);
  }
  async discard(id,sceneId,revision) {
    const p=await this.project(id,revision),s=this.scene(p,sceneId);await this.unlocked(p);
    assert(s.candidate,'No candidate to discard.');s.candidate=null;return this.store.save(p,p.revision);
  }
  async openTask(id,sceneId,revision,{targets=[],camera=null,frame=null,frameRange=null}={}) {
    const p=await this.project(id,revision),s=this.scene(p,sceneId);
    assert(!s.candidate&&!s.task&&!s.run,'Review or resolve the existing scene task first.',409);
    assert(Array.isArray(targets)&&targets.length<=64&&targets.every(x=>typeof x==='string'&&x.length<=255),'Invalid targets.');
    assert(camera===null||typeof camera==='string'&&camera.length<=255,'Invalid camera.');
    assert(frame===null||Number.isInteger(frame)&&frame>=-100000&&frame<=100000,'Invalid frame.');
    assert(frameRange===null||Array.isArray(frameRange)&&frameRange.length===2&&frameRange.every(Number.isInteger)&&frameRange[0]>=-100000&&frameRange[1]<=100000&&frameRange[1]>=frameRange[0]&&frameRange[1]-frameRange[0]<360,'Invalid task playback range.');
    const cap=await this.available();assert(cap.task_workspace,'Install the matching development harness to enable task workspaces.',409);
    assert((await this.store.verify(id)).ok,'Pinned sources changed before task launch.',409);
    let input=null;if(s.current){const cp=await this.verify(p,s);input={path:cp.path,sha256:cp.sha256};}
    const selectedSources=[];
    for(const ref of p.assets.filter(a=>s.sources.includes(a.sourceId))) {
      const v=await json(await safe(this.store.registry,`versions/${ref.sourceId}/${ref.version}.json`));
      selectedSources.push({sourceId:ref.sourceId,version:ref.version,path:await safe(this.store.database,v.relative)});
    }
    const taskId=uid('task_');await this.lock(p,taskId);
    const task={schema:1,id:taskId,projectId:id,sceneId,stage:s.stage,projectDirectory:p.directory,library:this.config.library,
      input,workingScene:`Scenes/${sceneId}--edit-${taskId}.blend`,checkpointScene:`Scenes/${sceneId}--saved-${taskId}.blend`,
      returnFile:`Docs/Workbench/${taskId}-return.json`,selectedSources,targets,camera,frame,...(frameRange?{frameRange}:{}),action:'workbench-edit',state:'RUNNING',startedAt:now()};
    const file=await safe(p.directory,`Runs/${taskId}.json`);
    try {
      await writeJson(file,task);s.task=taskId;await this.store.save(p,p.revision);
      task.processId=await this.runtime.launchWorkbenchTask(p,file);await writeJson(file,task);
      return {task,project:await this.store.get(id),message:'A dedicated Blender working window was requested. Its existing MCP connection is not claimed. Save using F3 → Save checkpoint and return to launcher.'};
    } catch(e) {task.state='FAILED';task.error=e.message;await writeJson(file,task);
      const q=await this.project(id);this.scene(q,sceneId).task=null;await this.store.save(q,q.revision);
      await this.unlock(p,taskId);throw e;}
  }
  async collectTask(id,sceneId,revision) {
    const p=await this.project(id,revision),s=this.scene(p,sceneId);assert(validId(s.task,'task_'),'No task is waiting.');
    const task=await json(await safe(p.directory,`Runs/${s.task}.json`));
    assert(task.projectId===id&&task.sceneId===sceneId,'Task identity mismatch.');
    const returned=await safe(p.directory,task.returnFile);
    const statusFile=await safe(p.directory,`Docs/Workbench/${task.id}-status.json`);
    if(await exists(statusFile)){const status=await json(statusFile);assert(status.state!=='FAILED','Blender task setup failed: '+status.message,409);}
    assert(await exists(returned),'No checkpoint receipt yet. In Blender use F3 → Save checkpoint and return to launcher.',409);
    const result=await json(returned);
    assert(result.taskId===task.id&&result.projectId===id&&result.sceneId===sceneId&&result.path===task.checkpointScene&&result.stage===task.stage,'Checkpoint returned for another task.',409);
    const saved=await fileHash(await safe(p.directory,result.path));assert(saved.sha256===result.sha256&&saved.size===result.size,'Returned checkpoint changed.',409);
    const prior=s.checkpoints.find(c=>c.taskId===task.id);
    const cp=prior||{id:uid('cp_'),taskId:task.id,path:result.path,...saved,parent:s.current,stage:task.stage,audit:result.audit,source:'blender-checkpoint-operator',createdAt:now()};
    if(!prior) {
      await writeJson(await safe(p.directory,`Docs/Workbench/${cp.id}.json`),cp);
      s.checkpoints.push(cp);s.candidate=cp.id;s.stage=task.stage;
      // Retain the task reference until both persistence and lease release
      // succeed, so collecting again after a crash is idempotent.
      await this.store.save(p,p.revision);
    }
    task.state='SUCCEEDED';task.finishedAt=now();task.checkpointId=cp.id;await writeJson(await safe(p.directory,`Runs/${task.id}.json`),task);
    if(await exists(await safe(p.directory,lockName)))await this.unlock(p,task.id);
    const q=await this.project(id);this.scene(q,sceneId).task=null;return this.store.save(q,q.revision);
  }
  async resolve(id,sceneId,revision,runId,confirmStopped) {
    const p=await this.project(id,revision),s=sceneId?this.scene(p,sceneId):null;
    assert(confirmStopped===true,'Confirm the external process has stopped.');
    assert(validId(runId,'task_')||validId(runId,'run_'),'Invalid run identity.');
    assert(!this.running.has(runId),'This process still owns the running operation. Wait for it to finish.',409);
    const file=await safe(p.directory,`Runs/${runId}.json`),r=await json(file);
    assert(r.projectId===id&&r.sceneId===sceneId,'Operation belongs to another scene.',409);
    if(r.action==='source-prepare') {
      const attempt=await safe(this.store.root,`SystemRuntime/UserData/LibraryPreparations/${runId}`);
      const jobs=await safe(attempt,'library/jobs');
      if(await exists(jobs))for(const name of await fs.readdir(jobs)) {
        if(!/^j_[a-f0-9]{24}$/.test(name))continue;
        const native=await json(await safe(jobs,name+'/job.json'));
        assert(native.state!=='RUNNING','The isolated preparation worker is still RUNNING or needs native recovery. Inspect its retained attempt before releasing this project.',409);
      }
    }
    if(r.jobId) {const native=await json(await safe(this.config.library,`jobs/${r.jobId}/job.json`));assert(native.state!=='RUNNING','Native job is still RUNNING. Inspect it before recovery.',409);}
    assert(r.state!=='SUCCEEDED','Collect the completed task instead of interrupting it.',409);
    // Explicit recovery never rewrites native job history or removes working files.
    r.state='INTERRUPTED';r.recovery='User confirmed process stopped; all files retained';r.finishedAt=now();await writeJson(file,r);
    if(s?.task===runId)s.task=null;if(s?.run===runId)s.run=null;
    if(await exists(await safe(p.directory,lockName)))await this.unlock(p,runId);
    return this.store.save(p,p.revision);
  }
  async result(job) {
    assert(job.state==='SUCCEEDED','Harness operation did not succeed.',409);
    const output=job.outputs.find(o=>o.path===`jobs/${job.id}/result.json`);assert(output,'Missing result evidence.');
    const file=await safe(this.config.library,output.path),hash=await fileHash(file);assert(hash.sha256===output.sha256,'Harness result changed.',409);
    const result=await json(file);assert(result.job_id===job.id&&result.status==='OK','Harness result identity mismatch.');return result.data;
  }
  async startJob(id,sceneId,revision,operation,options,confirmed=false) {
    assert(['render-readiness','preview','render-frames'].includes(operation),'Unknown workbench operation.');
    const p=await this.project(id,revision),s=this.scene(p,sceneId);
    assert(operation==='preview'||!s.candidate,'Finish reviewing the checkpoint candidate first.',409);
    const cp=await this.verify(p,s,operation==='preview'?(s.candidate||s.current):s.current);
    const cap=await this.available();assert(cap.render_frames,'Matching development harness required.',409);
    if(operation!=='render-readiness')assert((await this.interactions(id).sourceStatus()).ready,'Review the exact production source use before rendering. This does not replace native licensing gates.',409);
    const selected=shotFor(s),shot=selected&&['shots','light','render'].includes(s.stage)?selected:null;
    const shotRef=shot?{shotId:shot.id,shotRevision:shot.revision,shotName:shot.name}:{};
    if(operation!=='render-readiness'&&shot)assertObservedShot(s,cp,shot);
    if(operation==='render-frames'){
      assert(canEnter(s,'render')&&s.stage==='render','Finish scene development before rendering a shot.',409);
      assert(confirmed===true,'Explicit render authorization required.');assert(cap.encoder,'Configure FFmpeg and FFprobe before rendering a review movie.',409);
      assert(s.readiness?.checkpointId===cp.id,'Check render readiness for this exact checkpoint first.',409);
      if(shot)assert(options?.camera===shot.camera&&options.start===shot.start&&options.end===shot.end,'Render camera or timing differs from the selected shot. Edit the shot definition first.',409);
      options={...options,readiness_job:s.readiness.jobId};
    }
    if(operation==='preview') {
      assert(confirmed===true,'Explicit CPU preview authorization required.');
      const frame=options?.frame;assert(Number.isInteger(frame)&&frame>=-100000&&frame<=100000,'Choose a frame.');
      if(shot){assert(cap.preview_camera,'Matching shot-preview harness required.',409);assert(frame>=shot.start&&frame<=shot.end,'Preview frame is outside the selected shot.',409);}
      options={frames:[frame],width:640,height:360,samples:4,...(shot?{camera:shot.camera}:{})};
    }
    if(operation==='render-readiness')options={};
    const runId=uid('run_');await this.lock(p,runId);
    const file=await safe(p.directory,`Runs/${runId}.json`),r={schema:1,id:runId,projectId:id,sceneId,action:operation,state:'PREPARING',checkpointId:cp.id,startedAt:now(),authorization:confirmed?'explicit-launcher-user-action':'read-only',options,...shotRef};
    try {
      await writeJson(file,r);
      const optionFile=await safe(p.directory,`Docs/Workbench/${runId}-options.json`);await writeJson(optionFile,options);
      const job=await this.runtime.harness(['job-prepare',operation,'--input',await safe(p.directory,cp.path),'--options',optionFile]);
      await this.store.bindJob(id,job);r.jobId=job.id;
      assert(!['FAILED','INTERRUPTED','RUNNING'].includes(job.state),'The native job needs explicit recovery or retry. Its evidence was preserved.',409);
      r.state='RUNNING';await writeJson(file,r);
      const current=await this.project(id),scene=this.scene(current,sceneId);scene.run=runId;await this.store.save(current,current.revision);
      this.running.add(runId);
      const complete=async()=>{
        try {
          const rendered=await this.runtime.harness(['job-run',job.id,'--blender',this.config.blender,'--timeout',operation==='render-frames'?'900':'180'],operation==='render-frames'?930000:195000);
          const data=await this.result(rendered);
          let video=null;
          if(operation==='render-frames') {
            const plan={schema:1,id:uid('cut_'),project_id:id,clips:[{scene_id:sceneId,job_id:job.id,checkpoint_sha256:cp.sha256}]};
            const planFile=await safe(p.directory,`Docs/Workbench/${plan.id}-plan.json`);await writeJson(planFile,plan);
            video=await this.runtime.harness(['film-assemble','--plan',planFile,'--project',p.directory,'--ffmpeg',this.config.ffmpeg,'--ffprobe',this.config.ffprobe],1050000);
            assert(video.state==='SUCCEEDED','Review movie encoding failed.');
          }
          await this.serialize(async()=>{
            const current=await this.project(id),s=this.scene(current,sceneId);
            assert(s.run===runId&&(operation==='preview'?(s.candidate||s.current):s.current)===cp.id,'Scene changed during the operation; output retained for inspection.',409);
            await this.verify(current,s,cp.id);
            if(operation==='render-readiness')s.readiness={jobId:job.id,checkpointId:cp.id,data};
            if(operation==='preview')s.preview={jobId:job.id,checkpointId:cp.id,camera:options.camera||null,...shotRef};
            if(operation==='render-frames')s.renders.push({id:uid('rnd_'),jobId:job.id,checkpointId:cp.id,createdAt:now(),options,data,video,approved:false,...shotRef});
            s.run=null;await this.store.save(current,current.revision);
          });
          r.state='SUCCEEDED';
        } catch(e) {r.state='FAILED';r.error=e.message;}
        finally {r.finishedAt=now();await writeJson(file,r);
          await this.serialize(async()=>{const q=await this.project(id);const scene=this.scene(q,sceneId);if(scene.run===runId){scene.run=null;await this.store.save(q,q.revision);}});
          await this.unlock(p,runId);this.running.delete(runId);}
      };
      void complete().catch(e=>console.error('Workbench operation requires recovery: '+e.message));
      return {run:r};
    } catch(e) {r.state='FAILED';r.error=e.message;r.finishedAt=now();await writeJson(file,r);await this.unlock(p,runId);throw e;}
  }
  async retry(id,revision,jobId,confirmed) {
    const p=await this.project(id,revision);await this.unlocked(p);
    assert(confirmed===true&&p.jobs.some(j=>j.id===jobId),'Confirm retry of a project-owned job.');
    const job=await this.runtime.job(jobId);
    assert(['render-readiness','preview','render-frames'].includes(job.specification.operation)&&['FAILED','INTERRUPTED'].includes(job.state),
      'Only failed workbench jobs can be reset for explicit retry.',409);
    // Native job-retry archives the failed attempt; the next Run is separate.
    return this.runtime.harness(['job-retry',jobId]);
  }
  async approveRender(id,sceneId,revision,renderId) {
    const p=await this.project(id,revision),s=this.scene(p,sceneId);await this.unlocked(p);const cp=await this.verify(p,s);
    assert(canEnter(s,'render'),'Complete scene development before approving its output.',409);
    const r=s.renders.find(r=>r.id===renderId);assert(r&&renderIsCurrent(s,r),'Render belongs to an older checkpoint or shot revision.',409);
    await this.runtime.job(r.jobId);await this.verifyCut(p,r.video);
    r.approved=true;r.approvedAt=now();s.completed.render=cp.id;
    await writeJson(await safe(p.directory,`Docs/Workbench/${uid('review_')}.json`),{projectId:id,sceneId,renderId,checkpointSha256:cp.sha256,videoSha256:r.video.sha256,decision:'APPROVE_RENDER',createdAt:now(),transport:'launcher-ui'});
    return this.store.save(p,p.revision);
  }
  async clips(p,refs) {
    assert(Array.isArray(refs)&&refs.length>0&&refs.length<=32,'Choose one to 32 reviewed shots.');const clips=[];
    for(const ref of refs) {
      const s=this.scene(p,ref.sceneId),r=s.renders.find(r=>r.id===ref.renderId),cp=await this.verify(p,s);
      assert(r?.approved&&renderIsCurrent(s,r),'A film input is unapproved or outdated. Review its source scene and shot.',409);
      clips.push({scene_id:s.id,job_id:r.jobId,checkpoint_sha256:cp.sha256});
    }
    return clips;
  }
  async arrange(id,revision,clips) {
    const p=await this.project(id,revision);await this.unlocked(p);assert(Array.isArray(clips)&&clips.length<=32,'Invalid film inputs.');
    // Existing stale inputs can be removed/reordered one at a time. Only the
    // render/assembly gates require every retained input to be current.
    for(const ref of clips){
      assert(ref&&Object.keys(ref).every(k=>['sceneId','renderId'].includes(k)),'Invalid film reference.');
      const scene=this.scene(p,ref.sceneId),render=scene.renders.find(r=>r.id===ref.renderId);
      assert(render,'Unknown or unapproved film input.',404);
      if(!p.workbench.film.clips.some(c=>c.sceneId===ref.sceneId&&c.renderId===ref.renderId))await this.clips(p,[ref]);
    }
    p.workbench.film.clips=clips.map(c=>({sceneId:c.sceneId,renderId:c.renderId}));return this.store.save(p,p.revision);
  }
  async assemble(id,revision,confirmed) {
    assert(confirmed===true,'Approve the exact film inputs before encoding.');
    assert((await this.interactions(id).sourceStatus()).ready,'Review the current production source use first.',409);
    const p=await this.project(id,revision);assert(this.config.ffmpeg&&this.config.ffprobe,'Configure FFmpeg and FFprobe first.',409);
    const clips=await this.clips(p,p.workbench.film.clips),plan={schema:1,id:uid('cut_'),project_id:id,clips};
    const runId=uid('run_');await this.lock(p,runId);
    const file=await safe(p.directory,`Runs/${runId}.json`),r={schema:1,id:runId,projectId:id,sceneId:null,action:'film-assemble',state:'RUNNING',startedAt:now(),plan};
    const planFile=await safe(p.directory,`Docs/Workbench/${plan.id}-plan.json`);
    try{await writeJson(planFile,plan);await writeJson(file,r);}catch(e){await this.unlock(p,runId);throw e;}
    this.running.add(runId);
    const complete=async()=>{
      try {
        const result=await this.runtime.harness(['film-assemble','--plan',planFile,'--project',p.directory,'--ffmpeg',this.config.ffmpeg,'--ffprobe',this.config.ffprobe],1050000);
        assert(result.state==='SUCCEEDED','Film encoder did not succeed.');
        await this.serialize(async()=>{const q=await this.project(id);q.workbench.film.cuts.push({id:plan.id,refs:p.workbench.film.clips,result,approved:false,createdAt:now()});await this.store.save(q,q.revision);});r.state='SUCCEEDED';
      }catch(e){r.state='FAILED';r.error=e.message;}
      finally{r.finishedAt=now();await writeJson(file,r);await this.unlock(p,runId);this.running.delete(runId);}
    };void complete().catch(e=>console.error('Film operation requires recovery: '+e.message));return {run:r};
  }
  async verifyCut(p,result) {
    assert(result?.state==='SUCCEEDED'&&validId(result.plan?.id,'cut_'),'Missing encoded movie.');
    const file=await safe(p.directory,`Deliverables/${result.plan.id}/film.mp4`),actual=await fileHash(file);
    assert(actual.sha256===result.sha256&&actual.size===result.size,'Encoded movie changed after validation.',409);return file;
  }
  async approveCut(id,revision,cutId) {
    const p=await this.project(id,revision);await this.unlocked(p);const cut=p.workbench.film.cuts.find(c=>c.id===cutId);assert(cut,'Cut not found.',404);
    assert(digest(cut.refs)===digest(p.workbench.film.clips),'Film arrangement changed. Build a new cut.',409);await this.clips(p,cut.refs);await this.verifyCut(p,cut.result);
    cut.approved=true;cut.approvedAt=now();await writeJson(await safe(p.directory,`Docs/Workbench/${uid('review_')}.json`),{projectId:id,cutId,sha256:cut.result.sha256,decision:'APPROVE_FILM',createdAt:now(),transport:'launcher-ui'});
    return this.store.save(p,p.revision);
  }
  async media(id,{sceneId,renderId,cutId,kind}) {
    const p=await this.project(id);
    if(cutId) {const cut=p.workbench.film.cuts.find(c=>c.id===cutId);assert(cut,'Cut not found.',404);return {path:await this.verifyCut(p,cut.result),type:'video/mp4'};}
    const s=this.scene(p,sceneId);
    if(renderId){const r=s.renders.find(r=>r.id===renderId);assert(r,'Render not found.',404);return {path:await this.verifyCut(p,r.video),type:'video/mp4'};}
    assert(kind==='preview'&&s.preview,'No preview is available.',404);
    const cp=await this.verify(p,s,s.candidate||s.current);
    assert(previewIsCurrent(s,cp.id),'Preview belongs to another checkpoint or shot.',409);
    assert(p.jobs.some(j=>j.id===s.preview.jobId),'Preview job is not bound to this production.',409);
    const job=await this.runtime.job(s.preview.jobId);assert(job.state==='SUCCEEDED','Preview job did not succeed.',409);
    assert(job.specification?.operation==='preview'&&job.specification.inputs.some(input=>input.sha256===cp.sha256&&input.size===cp.size),'Preview input does not match this checkpoint.',409);
    const output=job.outputs.find(o=>/^jobs\/j_[a-f0-9]{24}\/preview_-?\d+\.png$/.test(o.path));assert(output,'Preview image is missing.');
    assert(output.path.startsWith(`jobs/${job.id}/`),'Preview output belongs to another job.',409);
    const file=await safe(this.config.library,output.path),bytes=await fileHash(file);assert(bytes.sha256===output.sha256&&bytes.size===output.size,'Preview changed.',409);return {path:file,type:'image/png'};
  }
  async sourcePreview(id,sourceId) {
    await this.store.get(id);const item=(await this.store.inventory()).sources.find(s=>s.id===sourceId);assert(item?.available,'Source unavailable.',404);
    const version=await json(await safe(this.store.registry,`versions/${item.id}/${item.version}.json`));
    const image=version.files.find(f=>referenceImage(f.path)&&f.size<=8*1024*1024);if(!image)return null;
    const base=await safe(this.store.database,item.relative);assert((await fs.stat(base)).isDirectory(),'No package image preview.',404);
    const file=await safe(base,image.path);assert((await fileHash(file)).sha256===image.sha256,'Package image changed; refresh library.',409);
    assert(image.size<=8*1024*1024,'Package image is too large to preview.');return {path:file,type:/\.png$/i.test(file)?'image/png':'image/jpeg'};
  }
  async codex(id,sceneId,revision) {
    const p=await this.project(id,revision),s=this.scene(p,sceneId);await this.unlocked(p);assert((await this.store.verify(id)).ok,'Pinned sources changed.',409);
    const context=await buildSessionContext(this.store,this.config,id);
    assert(p.brief.trim(),'Add the production intent before asking a specialist to propose work.');
    const cp=checkpointFor(s);
    const task={projectId:id,sceneId,activity:s.stage,checkpoint:cp,selectedSources:p.assets.filter(a=>s.sources.includes(a.sourceId)),role:stages[stageIndex(s.stage)].role};
    context.prompt+='\n\n## Scene-scoped workbench task (authoritative target for this session)\n'+JSON.stringify(task,null,2)+'\n\nDo not retarget an existing Blender/MCP window by assumption. This is a proposal and reviewed-worker session, not permission to overwrite an open GUI or a checkpoint. Use the scoped scene checkpoint above, not an unrelated legacy scene pointer. Selected sources are not imported instances or license grants. Call prepare_project and retain all native intake/license/review gates. Save a NEW candidate directly under this project Scenes/ with correct asset path remapping. The user will import and approve that candidate in the scene workbench. Do not mark lifecycle stages complete, approve your own outputs, or run full renders without the separate explicit render authorization. No automatic model cost is introduced by merely selecting this activity.';
    const sessionId=randomUUID(),directory=await safe(p.directory,'Docs/Codex');await fs.mkdir(directory,{recursive:true});
    const promptFile=await safe(p.directory,`Docs/Codex/${sessionId}.md`);await fs.writeFile(promptFile,context.prompt,{flag:'wx'});
    await writeJson(await safe(p.directory,`Docs/Codex/${sessionId}.json`),{...context,sessionId,promptFile,createdAt:now(),task});
    const terminal=await this.runtime.launchTerminal(id,sessionId);
    return {sessionId,processId:terminal.processId,message:'A scene-scoped Codex terminal was requested. Authentication, permissions and model costs remain with your existing Codex setup.'};
  }
}
