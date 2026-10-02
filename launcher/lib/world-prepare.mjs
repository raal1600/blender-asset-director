/** Explicit older-scene compatibility inspection and a separately reviewed candidate. */
import {isDeepStrictEqual} from 'node:util';
import {assert,json,safe} from './storage.mjs';
import {validHash,validId} from './workbench-model.mjs';
import {checkpointJob} from './checkpoint-job.mjs';
const version='world-prepare-v1',object=v=>v&&typeof v==='object'&&!Array.isArray(v);
const key=g=>JSON.stringify([g.asset_id,g.import_job]);
export function validateWorldPrepare(request,inspect=false){
 const keys=['version','requestId','checkpointId','sha256',...(inspect?[]:['inspectionId','audit_sha256','groups'])];
 assert(object(request)&&Object.keys(request).length===keys.length&&Object.keys(request).every(k=>keys.includes(k)),'Invalid World preparation fields.');
 assert(request.version===version&&validId(request.requestId,'run_')&&validId(request.checkpointId,'cp_')&&validHash(request.sha256),'Invalid World preparation identity.');
 if(inspect)return request;
 assert(validId(request.inspectionId,'run_')&&validHash(request.audit_sha256),'Inspect compatibility for this saved scene first.');
 assert(Array.isArray(request.groups)&&request.groups.length>0&&request.groups.length<=64,'Choose one to 64 inspected import groups.');
 const seen=new Set();
 for(const g of request.groups){
  assert(object(g)&&Object.keys(g).length===2&&Object.keys(g).every(k=>['asset_id','import_job'].includes(k))&&
   [g.asset_id,g.import_job].every(v=>typeof v==='string'&&Buffer.byteLength(v)>0&&Buffer.byteLength(v)<=200&&!/[\x00-\x1f]/.test(v))&&!seen.has(key(g)),'Choose distinct exact asset/import-job groups.');seen.add(key(g));
 }
 return request;
}
function verifyAudit(data){
 assert(object(data)&&data.version===version&&validHash(data.sha256)&&validHash(data.preserved)&&object(data.ownership)&&object(data.settings)&&Array.isArray(data.groups)&&data.groups.length<=10000,'Native World compatibility evidence is missing.');
 const seen=new Set();for(const g of data.groups){assert(object(g)&&typeof g.asset_id==='string'&&typeof g.import_job==='string'&&!seen.has(key(g))&&['PREPARABLE','ALREADY_PREPARED','UNSUPPORTED'].includes(g.status)&&Array.isArray(g.members)&&g.members.length<=10000,'Native World group evidence is invalid.');seen.add(key(g));}
}
export async function inspectWorldPreparation(work,id,sceneId,revision,request){
 validateWorldPrepare(request,true);
 return checkpointJob(work,id,sceneId,revision,request,{stage:'world',operation:'world-prepare-audit',options:{},readOnly:true,verify:verifyAudit});
}
export async function prepareWorld(work,id,sceneId,revision,request){
 validateWorldPrepare(request);
 const options={version,audit_sha256:request.audit_sha256,groups:request.groups};
 return checkpointJob(work,id,sceneId,revision,request,{
  stage:'world',operation:'world-prepare',options,candidateOnly:true,
  check:async({p,scene,cp})=>{
   assert(!scene.candidate,'Save or discard the current draft before preparing placement.',409);
   const run=await json(await safe(p.directory,`Runs/${request.inspectionId}.json`));
   assert(run.projectId===id&&run.sceneId===sceneId&&run.action==='world-prepare-audit'&&run.state==='SUCCEEDED'&&run.checkpointId===cp.id&&run.checkpointSha256===cp.sha256&&run.inspection?.sha256===request.audit_sha256,'World compatibility inspection is stale or belongs to another scene.',409);
   verifyAudit(run.inspection);
   assert(p.jobs.some(j=>j.id===run.jobId),'Compatibility job is not bound to this production.',409);
   const job=await work.runtime.job(run.jobId);
   assert(job.state==='SUCCEEDED'&&job.specification?.operation==='world-prepare-audit'&&job.specification.inputs.some(f=>f.sha256===cp.sha256&&f.size===cp.size),'Compatibility job input changed.',409);
   assert(isDeepStrictEqual(await work.result(job),run.inspection),'Compatibility evidence changed after execution.',409);
   for(const chosen of request.groups)assert(run.inspection.groups.some(g=>key(g)===key(chosen)&&g.status==='PREPARABLE'),'Choose only independently preparable groups from this inspection.',409);
  },
  verify:data=>assert(data.version===version&&data.reopened===true&&data.scene_audit&&data.world_placement&&data.publication==='SEPARATE_CANDIDATE_ONLY'&&data.visual_acceptance==='NOT_EVALUATED'&&isDeepStrictEqual(data.request,options),'Native preparation did not verify this exact separate candidate.')
 });
}
