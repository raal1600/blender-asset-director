/** Immutable transition attempts over the existing checkpoint/job transaction. */
import {randomUUID} from 'node:crypto';
import {assert,digest,json,safe,now,fileHash,writeJson,exists} from './storage.mjs';
import {approveCheckpoint,validId,validHash} from './workbench-model.mjs';

export const reviewVersion='transition-review-v1';
export const generatedRequest=request=>request.changes?.some(c=>c.mode==='timeline'&&c.clips.some(x=>x.transition?.mode==='generated'))===true;
export function requestFingerprint(request,implementation){
  const {requestId,inspectionId,working_request_id,...dependencies}=structuredClone(request);
  // The complete allowed seed set belongs to the request. Each attempt records
  // its actual seed, but alternatives in that set share one dependency identity.
  if(dependencies.sampling_plan)for(const change of dependencies.changes)for(const clip of change.clips||[])if(clip.transition?.mode==='generated')clip.transition.seed='MEMBER_OF_SAMPLING_PLAN';
  const stable=v=>Array.isArray(v)?v.map(stable):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])])):v;
  return digest(stable({version:reviewVersion,dependencies,implementation}));
}
export function reviewState(scene){
  scene.transitionReview ||= {version:reviewVersion,working:null,candidates:[],acceptances:[]};
  return scene.transitionReview;
}
export function downstream(request){
  return request.changes.filter(c=>c.mode==='timeline').map(c=>({performer:c.performer,
    joins:c.clips.filter(x=>x.transition).map(x=>({clipId:x.id,start:x.start,durationFrames:x.transition.frames,mode:x.transition.mode||'blend'}))}));
}
export function setWorking(scene,request,implementation){
  const review=reviewState(scene),fingerprint=requestFingerprint(request,implementation);
  if(review.working?.fingerprint===fingerprint)return review.working;
  assert(review.candidates.length<200&&review.acceptances.length<500,'Transition history reached its bound. Create a new scene revision before more authoring.',409);
  review.working={id:'trq_'+randomUUID(),fingerprint,implementation,request:structuredClone(request),createdAt:now(),
    baseCheckpointId:request.checkpointId,baseSha256:request.sha256,downstream:downstream(request)};
  return review.working;
}
export function candidateStatus(scene,candidate){
  const review=scene.transitionReview;
  if(scene.current===candidate.checkpointId&&review?.acceptances.some(e=>e.checkpointId===candidate.checkpointId))return 'ACCEPTED';
  if(!review?.working||candidate.fingerprint!==review.working.fingerprint||candidate.baseCheckpointId!==scene.current)return 'STALE';
  return candidate.validation?.status==='PASS'?'READY_FOR_REVIEW':candidate.validation?.status==='FAIL'?'FAILED_QUALITY':'VALIDATING';
}
export async function updateTransitionRequest(work,id,sceneId,revision,request,validate){
  validate(request);assert(generatedRequest(request),'Select a generated connection before preparing a transition request.');
  const p=await work.project(id,revision),scene=work.scene(p,sceneId);
  assert(scene.stage==='action'&&!scene.task&&!scene.candidate,'Finish the other scene operation before changing this request.',409);
  if(scene.run){const run=await json(await safe(p.directory,`Runs/${scene.run}.json`));assert(run.publication==='TRANSITION_REVIEW_ONLY','Another operation owns this scene.',409);}
  else await work.unlocked(p);
  assert(request.checkpointId===scene.current,'The request belongs to an older accepted scene.',409);
  const cp=await work.verify(p,scene,scene.current);assert(cp.sha256===request.sha256,'Accepted checkpoint changed.',409);
  const cap=await work.available();assert(validHash(cap.implementation),'Matching runtime is unavailable.',409);
  setWorking(scene,request,cap.implementation);
  return work.store.save(p,p.revision);
}
export async function publishCandidate({scene,checkpoint,data,record,output},working){
  const review=reviewState(scene);
  assert(!review.candidates.some(c=>c.id===record.id),'Generation attempt already has an immutable candidate.',409);
  // A missing report is never a passing quality check. Failed candidates remain inspectable.
  const validation=data.transition_validation||{status:'UNAVAILABLE',reason:'Native quality validation did not return a report.'};
  review.candidates.push({id:record.id,requestId:working.id,fingerprint:working.fingerprint,
    baseCheckpointId:working.baseCheckpointId,baseSha256:working.baseSha256,implementation:working.implementation,
    checkpointId:checkpoint.id,sha256:checkpoint.sha256,size:checkpoint.size,createdAt:now(),
    nativeJobId:record.jobId,artifacts:structuredClone(output.outputs),validation,
    transitions:(data.changes||[]).flatMap(c=>(c.timeline?.connections||[]).map(j=>({performer:c.performer,...j}))),
    previewSource:{checkpointId:checkpoint.id,sha256:checkpoint.sha256},
    requestedTimeline:structuredClone(record.options),samplingPlan:working.request.sampling_plan||null,downstream:working.downstream});
}
export async function acceptTransition(work,id,sceneId,revision,{candidateId,eventId,fingerprint}){
  assert(validId(candidateId,'run_')&&validId(eventId,'run_')&&validHash(fingerprint),'Invalid transition acceptance identity.');
  // Idempotence is scoped to the exact acceptance, including its candidate and dependencies.
  const p=await work.project(id),scene=work.scene(p,sceneId),review=reviewState(scene);
  const prior=review.acceptances.find(e=>e.id===eventId);
  if(prior){assert(prior.candidateId===candidateId&&prior.fingerprint===fingerprint,'Acceptance identity conflict.',409);return p;}
  assert(p.revision===revision,'Project changed. Refresh the candidate before acceptance.',409);
  await work.unlocked(p);assert(scene.stage==='action'&&!scene.run&&!scene.task&&!scene.candidate,'Finish the current operation before acceptance.',409);
  const candidate=review.candidates.find(c=>c.id===candidateId);
  assert(candidate&&candidateStatus(scene,candidate)==='READY_FOR_REVIEW','This candidate is stale or has not passed every hard quality check.',409);
  assert(fingerprint===candidate.fingerprint&&review.working.fingerprint===fingerprint,'Transition dependencies changed. Generate a new candidate.',409);
  const cap=await work.available();assert(cap.implementation===candidate.implementation&&requestFingerprint(review.working.request,cap.implementation)===fingerprint,'Runtime or working input changed. Inspect and regenerate.',409);
  const base=await work.verify(p,scene,candidate.baseCheckpointId);assert(base.sha256===candidate.baseSha256,'Input scene changed.',409);
  const cp=await work.verify(p,scene,candidate.checkpointId);assert(cp.sha256===candidate.sha256,'Candidate scene changed.',409);
  for(const artifact of candidate.artifacts){const actual=await fileHash(await safe(work.config.library,artifact.path));assert(actual.sha256===artifact.sha256&&actual.size===artifact.size,'Candidate evidence or artifact was changed. Regenerate.',409);}
  const previous=scene.current;
  approveCheckpoint(scene,'action',cp.id,false);
  review.acceptances.push({id:eventId,type:'ACCEPT',candidateId,fingerprint,checkpointId:cp.id,sha256:cp.sha256,previousCheckpointId:previous,at:now()});
  // One atomic project save publishes the complete baked revision and its acceptance event.
  return work.store.save(p,p.revision);
}
export async function restoreTransition(work,id,sceneId,revision,{checkpointId,eventId}){
  assert(validId(checkpointId,'cp_')&&validId(eventId,'run_'),'Invalid restore identity.');
  const p=await work.project(id),scene=work.scene(p,sceneId),review=reviewState(scene),prior=review.acceptances.find(e=>e.id===eventId);
  if(prior){assert(prior.type==='RESTORE'&&prior.checkpointId===checkpointId,'Restore identity conflict.',409);return p;}
  assert(p.revision===revision,'Project changed. Refresh before restoring.',409);await work.unlocked(p);
  assert(scene.stage==='action'&&!scene.candidate&&!scene.task&&!scene.run,'Finish the current operation before restoring.',409);
  assert(review.acceptances.some(e=>e.checkpointId===checkpointId||e.previousCheckpointId===checkpointId),'Choose a previously accepted checkpoint.',409);
  const cp=await work.verify(p,scene,checkpointId),previous=scene.current;
  approveCheckpoint(scene,'action',cp.id,false);review.working=null;
  review.acceptances.push({id:eventId,type:'RESTORE',checkpointId,sha256:cp.sha256,previousCheckpointId:previous,at:now()});
  return work.store.save(p,p.revision);
}

function processMayBeAlive(pid){
  if(!Number.isInteger(pid)||pid<=0)return true;
  try{process.kill(pid,0);return true;}catch(error){return error.code!=='ESRCH';}
}
export async function recoverTransitionJobs(work,id){
  const runs=await work.store.runs(id);
  const before=await work.project(id),ownerFile=await safe(before.directory,'Runs/.workbench-writer.lock/owner.json');
  const owner=await exists(ownerFile)?await json(ownerFile):null;
  const interrupted=runs.filter(r=>r.publication==='TRANSITION_REVIEW_ONLY'&&(['PREPARING','RUNNING'].includes(r.state)||owner?.runId===r.id||before.workbench.scenes.some(s=>s.run===r.id))&&!work.running.has(r.id)&&!processMayBeAlive(r.launcherPid));
  if(!interrupted.length)return;
  await work.serialize(async()=>{
    for(const old of interrupted){
      const p=await work.project(id),scene=work.scene(p,old.sceneId),file=await safe(p.directory,`Runs/${old.id}.json`),record=await json(file);
      if(work.running.has(record.id)||processMayBeAlive(record.launcherPid))continue;
      const candidate=scene.transitionReview?.candidates.find(c=>c.id===record.id);
      try{
        if(candidate){
          const cp=await work.verify(p,scene,candidate.checkpointId);assert(cp.sha256===candidate.sha256,'Published candidate hash changed.',409);
          record.resultCheckpointId=cp.id;record.state='SUCCEEDED';record.recovery='Restored existing atomic review publication; no acceptance event created';
        }else{
          if(record.jobId){
            let native=await json(await safe(work.config.library,`jobs/${record.jobId}/job.json`));
            if(native.state==='RUNNING')native=await work.runtime.harness(['job-recover',record.jobId,'--confirm-stopped']);
            assert(native.state!=='RUNNING','Native executor still owns this attempt.',409);
          }
          record.state='INTERRUPTED';record.error='Launcher stopped before an immutable review checkpoint was published. Accepted scene retained; generate a new attempt.';
          record.quarantine={state:'EXCLUDED_FROM_CANDIDATES',nativeJobId:record.jobId||null,reason:'Incomplete publication; retained files must not be treated as success'};
        }
        record.finishedAt=now();await writeJson(file,record);
        if(scene.run===record.id){scene.run=null;await work.store.save(p,p.revision);}
        const owner=await safe(p.directory,'Runs/.workbench-writer.lock/owner.json');
        if(await exists(owner)&&(await json(owner)).runId===record.id)await work.unlock(p,record.id);
      }catch(error){
        // Native recovery checks executor AND Blender process identities. PID
        // ambiguity or a still-live process retains its lease and manual evidence.
        record.recoveryPending=error.message;await writeJson(file,record);
      }
    }
  });
}
