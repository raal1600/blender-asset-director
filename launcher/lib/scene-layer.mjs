/** Authenticated scoped camera/shared-light jobs. No generic script endpoint. */
import {isDeepStrictEqual} from 'node:util';
import {assert,json,safe} from './storage.mjs';
import {validHash,validId} from './workbench-model.mjs';
import {checkpointJob} from './checkpoint-job.mjs';
const version='scene-layer-v1',allowed={shots:['camera-fit','camera-plan'],light:['light-adjust','world-adjust','look-adjust','light-rig']};
const object=v=>v&&typeof v==='object'&&!Array.isArray(v);
export function validateSceneLayerRequest(request,inspect=false){
 const keys=['version','layer','requestId','checkpointId','sha256',...(inspect?[]:['inspectionId','audit_sha256','operations'])];
 assert(object(request)&&Object.keys(request).length===keys.length&&Object.keys(request).every(k=>keys.includes(k)),'Invalid camera/light layer fields.');
 assert(request.version===version&&typeof request.layer==='string'&&Object.hasOwn(allowed,request.layer)&&validId(request.requestId,'run_')&&validId(request.checkpointId,'cp_')&&validHash(request.sha256),'Invalid camera/light layer identity.');
 if(inspect)return request;
 assert(validId(request.inspectionId,'run_')&&validHash(request.audit_sha256),'Inspect this saved layer first.');
 assert(Array.isArray(request.operations)&&request.operations.length>=1&&request.operations.length<=(request.layer==='shots'?1:4),'Save one camera or up to four distinct lighting operations.');
 const seen=new Set();
 for(const item of request.operations){
  assert(object(item)&&Object.keys(item).every(k=>['operation','options','name'].includes(k))&&allowed[request.layer].includes(item.operation)&&!seen.has(item.operation)&&object(item.options),'Unknown or duplicate layer operation.');seen.add(item.operation);
  assert(item.name===undefined||item.operation==='camera-fit','Only a fitted camera uses this name field.');
  if(item.operation==='camera-fit')assert(typeof item.name==='string'&&item.name.trim()&&item.name.length<=63,'Name the new camera.');
  if(item.operation==='camera-plan')assert(!('fps' in item.options)&&!('frame_range' in item.options)&&(!item.options.existing_animation||item.options.existing_animation==='preserve'),'Shots preserves Action timing and prior camera animation.');
 }
 assert(JSON.stringify(request.operations).length<=64000,'Layer request exceeds its bounded size.');
 return request;
}
function verifyAudit(data,layer){
 assert(object(data)&&data.version===version&&data.layer===layer&&validHash(data.sha256)&&Array.isArray(data.cameras)&&data.scene&&Array.isArray(data.scene.objects)&&data.look?.state&&data.visual_acceptance==='NOT_EVALUATED','Native camera/light inspection is missing.');
}
export async function inspectSceneLayer(work,id,sceneId,revision,request){
 validateSceneLayerRequest(request,true);
 return checkpointJob(work,id,sceneId,revision,request,{stage:request.layer,operation:'scene-layer-audit',options:{layer:request.layer},readOnly:true,verify:data=>verifyAudit(data,request.layer),sceneAudit:data=>data.scene});
}
export async function saveSceneLayer(work,id,sceneId,revision,request){
 validateSceneLayerRequest(request);
 const p=await work.project(id),scene=work.scene(p,sceneId),options={version,layer:request.layer,audit_sha256:request.audit_sha256,operations:request.operations};
 const affectedShots=(scene.shots||[]).map(({id,revision,name,camera,start,end})=>({id,revision,name,camera,start,end}));
 return checkpointJob(work,id,sceneId,revision,request,{
  stage:request.layer,operation:'scene-layer-edit',options,context:{layer:request.layer,sharedScene:true,affectedShots},
  check:async({p,cp})=>{
   const run=await json(await safe(p.directory,`Runs/${request.inspectionId}.json`));
   assert(run.projectId===id&&run.sceneId===sceneId&&run.action==='scene-layer-audit'&&run.state==='SUCCEEDED'&&run.checkpointId===cp.id&&run.checkpointSha256===cp.sha256&&run.inspection?.sha256===request.audit_sha256,'Camera/light inspection is stale or belongs to another scene.',409);
   verifyAudit(run.inspection,request.layer);const audit=run.inspection;
   for(const {operation:op,options:args} of request.operations){
    if(args.subjects!==undefined)assert(Array.isArray(args.subjects)&&args.subjects.length>0&&args.subjects.every(name=>audit.scene.objects.some(o=>o.name===name&&['MESH','CURVE','SURFACE','FONT','META'].includes(o.type))),'Choose observed geometry from this scene.',409);
    if(op==='camera-plan'&&args.mode==='adapt')assert(audit.cameras.some(c=>c.name===args.camera&&!c.unsupported),'Choose an editable observed camera.',409);
    if(op==='light-adjust')assert(Array.isArray(args.lights)&&args.lights.length>0&&args.lights.every(light=>audit.look.state.lights.some(l=>l.name===light.name&&!l.unsupported)),'Choose editable observed lights from this scene.',409);
    if(op==='world-adjust')assert(Object.keys(args).every(k=>audit.look.editable.world.includes(k)),'This world graph needs detailed Blender editing.',409);
   }
  },
  verify:data=>{
   assert(data.version===version&&data.layer===request.layer&&data.reopened===true&&data.scene_audit&&data.visual_acceptance==='NOT_EVALUATED'&&isDeepStrictEqual(data.request,options),'Native Save did not verify the exact camera/light request.');
   verifyAudit(data.after_audit,request.layer);
  }
 });
}
