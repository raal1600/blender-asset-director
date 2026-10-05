/** Performer-native Action requests. Retargeting stays in the reviewed workflow. */
import {isDeepStrictEqual} from 'node:util';
import {assert,digest,json,safe} from './storage.mjs';
import {validHash,validId} from './workbench-model.mjs';
import {checkpointJob} from './checkpoint-job.mjs';
import {assertCurrentActionInspection} from './action-inspection.mjs';
import {validateTimeline,timelineTiming,connection,stitchVersion,motionEditVersion} from '../public/action-timeline-contract.mjs';

const version='action-layer-v1';
const object=value=>value&&typeof value==='object'&&!Array.isArray(value);
const integer=value=>Number.isInteger(value)&&value>=-100000&&value<=100000;
export function validateActionRequest(request,inspect=false){
  const fields=['version','requestId','checkpointId','sha256',...(inspect?[]:['inspectionId','audit_sha256','changes','frame_range'])];
  assert(object(request)&&Object.keys(request).every(k=>fields.includes(k)),'Invalid Action request.');
  assert(request.version===version&&validId(request.requestId,'run_')&&validId(request.checkpointId,'cp_')&&validHash(request.sha256),'Invalid Action identity.');
  if(inspect)return request;
  assert(validId(request.inspectionId,'run_')&&validHash(request.audit_sha256),'Inspect the saved performers first.');
  assert(Array.isArray(request.changes)&&request.changes.length>0&&request.changes.length<=32,'Choose one to 32 observed performers.');
  const seen=new Set();
  for(const c of request.changes){
    assert(object(c)&&typeof c.performer==='string'&&c.performer.length>0&&c.performer.length<=255&&!seen.has(c.performer),'Choose distinct observed performers.');seen.add(c.performer);
    if(c.mode==='timeline'){validateTimeline(c);continue;}
    const keys=c.mode==='clip'?['performer','mode','take_id','start','speed']:['performer','mode','frame'];
    assert(Object.keys(c).length===keys.length&&Object.keys(c).every(k=>keys.includes(k)),'Unknown Action fields.');
    if(c.mode==='clip'){
      assert(typeof c.take_id==='string'&&/^take_[a-f0-9]{64}$/.test(c.take_id),'Choose an observed take for this performer.');
      assert(integer(c.start),'Start frame must be a whole number from -100000 to 100000.');
      assert(typeof c.speed==='number'&&Number.isFinite(c.speed)&&c.speed>=.1&&c.speed<=4,'Speed must be a number from 0.1 to 4 (1 is normal speed).');
    }
    else assert(c.mode==='hold'&&integer(c.frame),'Choose native motion or hold an observed pose.');
  }
  if(request.frame_range!==undefined)assert(Array.isArray(request.frame_range)&&request.frame_range.length===2&&request.frame_range.every(integer)&&request.frame_range[0]<=request.frame_range[1]&&request.frame_range[1]-request.frame_range[0]<=3600,'Playback range exceeds the supported bound.');
  assert(!request.changes.some(c=>c.mode==='timeline')||request.changes.every(c=>c.mode==='timeline'),'Save timeline changes separately from legacy changes.');
  return request;
}

function verifyAudit(data){
  assert(object(data)&&data.version===version&&validHash(data.sha256)&&Array.isArray(data.performers)&&data.performers.length<=10000&&Array.isArray(data.unassigned),'Native Action inspection is missing.');
}

export async function inspectAction(work,id,sceneId,revision,request){
  validateActionRequest(request,true);
  return checkpointJob(work,id,sceneId,revision,request,{stage:'action',operation:'action-audit',options:{},readOnly:true,verify:verifyAudit,
    implementation:async()=>{const cap=await work.available();assert(validHash(cap.implementation)&&cap.action_layer===version,'Matching Action runtime identity is unavailable.',409);return cap.implementation;}});
}

export function registerActionSave(work,id,sceneId,revision,request){
  validateActionRequest(request);
  assert(validId(id,'prj_')&&validId(sceneId,'sc_')&&Number.isInteger(revision),'Invalid Action save scope.');
  work.actionSaves ||= new Map();const identity=digest({id,sceneId,revision,request}),prior=work.actionSaves.get(request.requestId);
  if(prior){assert(prior.identity===identity,'Action request conflicts with an active Save.',409);return prior;}
  assert(work.actionSaves.size<64,'Too many pending Action saves.',429);
  const entry={id,sceneId,runId:request.requestId,identity,cancelled:false,committing:false,jobId:null};work.actionSaves.set(request.requestId,entry);return entry;
}
export async function cancelActionSave(work,id,sceneId,runId){
  assert(validId(runId,'run_'),'Invalid Action save identity.');
  const entry=work.actionSaves?.get(runId);
  assert(entry&&entry.id===id&&entry.sceneId===sceneId,'No active Action save belongs to this request and scene.',409);
  assert(!entry.committing,'This Save is already publishing its verified checkpoint. Wait for its receipt.',409);
  entry.cancelled=true;
  if(entry.jobId){try{await work.runtime.harness(['job-cancel',entry.jobId]);}catch(error){entry.nativeCancelError=error.message;}}
  return {runId,state:'CANCEL_REQUESTED',...(entry.nativeCancelError?{detail:entry.nativeCancelError}:{}),message:'Cancellation requested. Waiting for the native worker to stop; the previous scene and local draft are retained.'};
}
export async function saveAction(work,id,sceneId,revision,request){
  const cancellation=registerActionSave(work,id,sceneId,revision,request);
  const options={version,audit_sha256:request.audit_sha256,changes:request.changes,...(request.frame_range?{frame_range:request.frame_range}:{})};
  try{return await checkpointJob(work,id,sceneId,revision,request,{
    stage:'action',operation:'action-edit',options,cancellation,
    check:async({p,cp})=>{
      const run=await json(await safe(p.directory,`Runs/${request.inspectionId}.json`));
      assert(run.projectId===id&&run.sceneId===sceneId&&run.action==='action-audit'&&run.state==='SUCCEEDED'&&run.checkpointId===cp.id&&run.checkpointSha256===cp.sha256&&run.inspection?.sha256===request.audit_sha256,'Action inspection is stale or belongs to another scene.',409);
      verifyAudit(run.inspection);
      await assertCurrentActionInspection(work,run);
      for(const c of request.changes){
        const performer=run.inspection.performers.find(p=>p.name===c.performer);
        assert(performer&&!performer.unsupported,'This performer needs detailed Blender editing.',409);
        if(c.mode==='timeline'){
          assert(performer.timeline?.version==='action-timeline-v1'&&!performer.timeline.error,'Inspect this timeline in the matching runtime.',409);
          const editedMotion=c.clips.some(clip=>clip.source_range!==undefined||clip.heading_deg!==undefined||clip.transition?.mode!==undefined);
          assert(!editedMotion||performer.timeline.edit_version===motionEditVersion,'Inspect this performer again before trimming motion or changing its body heading.',409);
          const changesHeading=c.clips.some(clip=>Math.abs(clip.heading_deg||0)>1e-7);
          const range=request.frame_range||run.inspection.frame_range;
          for(const [index,clip] of c.clips.entries()){
            const take=performer.takes.find(t=>t.id===clip.take_id&&t.performer===c.performer);
            assert(take,'This motion does not belong to the selected performer.',409);
            assert(!changesHeading||take.heading_blocker===null,take.heading_blocker||'Body heading needs a matching native inspection before Save.',409);
            const timing=timelineTiming(clip,take);
            if(clip.transition){
              const previous=c.clips[index-1],previousTake=performer.takes.find(t=>t.id===previous?.take_id);
              assert(performer.timeline.stitch_version===stitchVersion&&previousTake&&take.stitch_blocker===null&&previousTake.stitch_blocker===null&&validHash(take.stitch_channels)&&take.stitch_channels===previousTake.stitch_channels,'These clips need a matching connection inspection or Blender review.',409);
              connection(previous,clip,previousTake,take);
            }
            assert(!(c.clips.some(c=>c.travel)||timing.cycles>1+1e-9)||!take.travel_blocker,take.travel_blocker||'Native travelling cycles need Blender review.',409);
            assert(!clip.travel||!take.travel_blocker,take.travel_blocker||'Travel is unavailable.',409);
            assert(clip.start>=range[0]&&clip.start+clip.frames-1<=range[1],'Playback must contain every clip.');
          }
        }
        else if(c.mode==='clip')assert(performer.takes.some(t=>t.id===c.take_id&&t.performer===c.performer),'This motion does not belong to the selected performer.',409);
        else assert(c.frame>=run.inspection.frame_range[0]&&c.frame<=run.inspection.frame_range[1],'Hold a frame within the observed scene range.',409);
      }
    },
    verify:data=>{
      assert(data.version===version&&data.reopened===true&&data.scene_audit&&data.performance_acceptance==='NOT_EVALUATED'&&
        isDeepStrictEqual(data.request,options),'Native Save did not verify the exact Action request.');
      verifyAudit(data.action_audit);
    }
  });}finally{if(!work.running.has(request.requestId))work.actionSaves.delete(request.requestId);}
}
