/** Performer-native Action requests. Retargeting stays in the reviewed workflow. */
import {isDeepStrictEqual} from 'node:util';
import {assert,json,safe} from './storage.mjs';
import {validHash,validId} from './workbench-model.mjs';
import {checkpointJob} from './checkpoint-job.mjs';
import {assertCurrentActionInspection} from './action-inspection.mjs';
import {validateTimeline,timelineTiming} from '../public/action-timeline-contract.mjs';

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

export async function saveAction(work,id,sceneId,revision,request){
  validateActionRequest(request);
  const options={version,audit_sha256:request.audit_sha256,changes:request.changes,...(request.frame_range?{frame_range:request.frame_range}:{})};
  return checkpointJob(work,id,sceneId,revision,request,{
    stage:'action',operation:'action-edit',options,
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
          const range=request.frame_range||run.inspection.frame_range;
          for(const clip of c.clips){
            const take=performer.takes.find(t=>t.id===clip.take_id&&t.performer===c.performer);
            assert(take,'This motion does not belong to the selected performer.',409);
            const timing=timelineTiming(clip,take);
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
  });
}
