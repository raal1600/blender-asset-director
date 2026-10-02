/** Read-only, source-bound access to retained rendered stills. No approval/migration. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {isDeepStrictEqual} from 'node:util';
import {assert,safe,json,fileHash} from './storage.mjs';
import {validId,validHash} from './workbench-model.mjs';
const MAX_FILES=10000,MAX_RECEIPT=65536,MAX_SCAN_BYTES=32*1024*1024,PAGE_SIZE=20;
const jobId=id=>typeof id==='string'&&/^j_[a-f0-9]{24}$/.test(id);
function request(parameters){
 assert(parameters&&Object.keys(parameters).every(k=>['shotId','page'].includes(k)),'Unknown lighting evidence fields.');
 const page=parameters.page===undefined?0:Number(parameters.page);
 assert(Number.isSafeInteger(page)&&page>=0&&page<500,'Choose a bounded evidence page.');
 assert(parameters.shotId===undefined||validId(parameters.shotId,'shot_'),'Invalid evidence shot.');return {shotId:parameters.shotId,page};
}
async function receipt(p,runId){
 assert(validId(runId,'run_'),'Invalid preview run identity.');const file=await safe(p.directory,`Runs/${runId}.json`);
 assert((await fs.stat(file)).size<=MAX_RECEIPT,'Preview receipt exceeds the bounded size.',409);
 const run=await json(file);assert(run.id===runId&&run.projectId===p.id,'Preview receipt belongs to another production.',409);return run;
}
function current(scene,checkpoint,run,camera,frame){
 if(checkpoint.id!==(scene.candidate||scene.current))return false;
 if(!run.shotId)return false; // Legacy scene stills cannot establish named-shot currency.
 const shot=scene.shots?.find(s=>s.id===run.shotId);
 return !!shot&&shot.revision===run.shotRevision&&shot.camera===camera&&frame>=shot.start&&frame<=shot.end;
}
export async function verifyPreviewEvidence(work,p,scene,run,{checkpoints=new Map(),dependencies=new Map(),sources=true}={}){
 assert(run.projectId===p.id&&run.sceneId===scene.id&&validId(run.id,'run_')&&run.action==='preview'&&run.state==='SUCCEEDED','Only a successful preview from this scene can be viewed.',409);
 assert(jobId(run.jobId)&&p.jobs.some(j=>j.id===run.jobId&&j.operation==='preview'),'Preview job is not bound to this production.',409);
 let cp=checkpoints.get(run.checkpointId);
 if(!cp){
  if(sources)cp=await work.verify(p,scene,run.checkpointId);
  else {cp=scene.checkpoints.find(c=>c.id===run.checkpointId);assert(cp,'Preview checkpoint is missing.',409);const bytes=await fileHash(await safe(p.directory,cp.path));assert(bytes.sha256===cp.sha256&&bytes.size===cp.size,'Historical checkpoint changed.',409);}
  checkpoints.set(cp.id,cp);
 }
 const job=await work.runtime.job(run.jobId),options=run.options;
 assert(job.id===run.jobId&&job.state==='SUCCEEDED'&&job.specification?.operation==='preview','Native preview did not succeed.',409);
 assert(options&&isDeepStrictEqual(job.specification.options,options),'Preview options differ from the authorized receipt.',409);
 assert(options.frames?.length===1&&Number.isInteger(options.frames[0])&&options.width===640&&options.height===360&&options.samples===4&&!options.stage,'Not a bounded workbench still.',409);
 const frame=options.frames[0],source=await safe(p.directory,cp.path);
 assert(job.specification.inputs.some(input=>path.resolve(input.path)===path.resolve(source)&&input.sha256===cp.sha256&&input.size===cp.size),'Native input does not match this checkpoint and path.',409);
 let shot=null;
 if(run.shotId){
  assert(validId(run.shotId,'shot_')&&Number.isSafeInteger(run.shotRevision)&&run.shotRevision>=1,'Invalid historical shot reference.',409);
  const definition=await json(await safe(p.directory,`Docs/Workbench/${run.shotId}-v${run.shotRevision}.json`));shot=definition.shot;
  assert(definition.kind==='SHOT_DEFINITION'&&definition.projectId===p.id&&definition.sceneId===scene.id&&validHash(definition.checkpointSha256)&&shot?.id===run.shotId&&shot.revision===run.shotRevision&&shot.name===run.shotName&&shot.camera===options.camera&&frame>=shot.start&&frame<=shot.end,'Historical shot definition does not match this preview.',409);
 }
 const data=await work.result(job);
 assert(data.artifact_kind==='PREVIEW_ARTIFACT'&&data.delivery_master===false&&data.production_settings_restored===true&&data.engine==='CYCLES_CPU'&&data.samples===options.samples,'Native still lacks preview/preservation evidence.',409);
 assert(isDeepStrictEqual(data.preview_overrides?.resolution,[options.width,options.height])&&data.preview_overrides?.device==='CPU','Native preview settings do not match.',409);
 if(options.camera)assert(data.camera===options.camera&&isDeepStrictEqual(data.frames,options.frames)&&data.scene_camera_restored===true&&data.timeline_camera_bindings_restored===true,'Native camera/frame evidence does not match.',409);
 let dependencyStatus='NOT_RECORDED';
 if(data.dependencies!==undefined){
  assert(Array.isArray(data.dependencies)&&data.dependencies.length<=2048,'Unbounded native dependency evidence.',409);
  let total=0;dependencyStatus='MATCH';const seen=new Set();
  for(const input of data.dependencies){
   assert(typeof input.path==='string'&&path.isAbsolute(input.path)&&!seen.has(input.path)&&validHash(input.sha256)&&Number.isSafeInteger(input.size)&&input.size>=0&&input.size<=2*1024**3,'Invalid native dependency identity.',409);
   seen.add(input.path);total+=input.size;assert(total<=4*1024**3,'Native dependency evidence exceeds its bound.',409);
   const key=input.path+':'+input.sha256+':'+input.size;
   if(!dependencies.has(key)){try{const actual=await fileHash(input.path);dependencies.set(key,actual.sha256===input.sha256&&actual.size===input.size);}catch{dependencies.set(key,false);}}
   if(!dependencies.get(key))dependencyStatus='CHANGED';
  }
 }
 assert(Array.isArray(data.files)&&data.files.length===1&&/^preview_-?\d+\.png$/.test(data.files[0]),'Preview image evidence is ambiguous.',409);
 assert(Number(/^preview_(-?\d+)\.png$/.exec(data.files[0])[1])===frame,'Preview image frame does not match.',409);
 const outputs=job.outputs.filter(o=>o.path===`jobs/${job.id}/${data.files[0]}`);assert(outputs.length===1,'Exact preview image is missing or ambiguous.',409);
 const output=outputs[0];assert(validHash(output.sha256)&&Number.isSafeInteger(output.size)&&output.size>0&&output.size<=16*1024*1024,'Preview image exceeds its bounded size.',409);
 const file=await safe(work.config.library,output.path),bytes=await fileHash(file);assert(bytes.sha256===output.sha256&&bytes.size===output.size,'Preview image changed.',409);
 return {path:file,type:'image/png',evidence:{runId:run.id,jobId:job.id,checkpointId:cp.id,checkpointSha256:cp.sha256,frame,camera:options.camera||null,width:options.width,height:options.height,samples:options.samples,engine:data.engine,image:{sha256:bytes.sha256,size:bytes.size},shot:shot?{id:shot.id,revision:shot.revision,name:shot.name,start:shot.start,end:shot.end}:null,createdAt:run.finishedAt||run.startedAt,status:'VERIFIED',dependencyStatus,dependencyCount:data.dependencies?.length??null,current:dependencyStatus==='MATCH'&&current(scene,cp,run,options.camera,frame),humanReview:'NOT_EVALUATED'}};
}
export async function previewEvidence(work,id,sceneId,parameters={}){
 const filter=request(parameters),p=await work.project(id),scene=work.scene(p,sceneId);
 if(filter.shotId)assert(scene.shots?.some(s=>s.id===filter.shotId),'Shot does not belong to this scene.',404);
 const directory=await safe(p.directory,'Runs'),names=(await fs.readdir(directory)).filter(n=>n.endsWith('.json')&&validId(n.slice(0,-5),'run_'));
 assert(names.length<=MAX_FILES,'Preview history exceeds the bounded receipt scan; use retained job records.',413);
 let scannedBytes=0;const rows=[],issues=[];
 for(const name of names){
  const file=await safe(directory,name),stat=await fs.stat(file);
  // Other operations can embed large native audits. Preview receipts are small.
  if(stat.size>MAX_RECEIPT)continue;
  scannedBytes+=stat.size;assert(scannedBytes<=MAX_SCAN_BYTES,'Preview receipt scan exceeds 32 MiB; no data was removed.',413);
  let run;try{run=await json(file);}catch{issues.push({runId:name.slice(0,-5),message:'Unreadable receipt retained.'});continue;}
  if(run.action!=='preview'||run.sceneId!==scene.id)continue;
  if(run.projectId!==p.id||run.id!==name.slice(0,-5)){issues.push({runId:name.slice(0,-5),message:'Preview identity mismatch; not displayed.'});continue;}
  if(run.state!=='SUCCEEDED')continue;
  if(!filter.shotId||run.shotId===filter.shotId)rows.push(run);
 }
 rows.sort((a,b)=>String(b.finishedAt||b.startedAt).localeCompare(String(a.finishedAt||a.startedAt))||b.id.localeCompare(a.id));
 const sourceStatus=await work.store.verify(id),checkpoints=new Map(),dependencies=new Map(),items=[];
 for(const run of rows.slice(filter.page*PAGE_SIZE,(filter.page+1)*PAGE_SIZE)){
  try{assert(sourceStatus.ok,'Pinned source verification failed; inspect source versions.',409);items.push((await verifyPreviewEvidence(work,p,scene,run,{checkpoints,dependencies,sources:false})).evidence);}
  catch(error){items.push({runId:run.id,status:'UNAVAILABLE',current:false,error:error.message});}
 }
 return {version:'preview-evidence-v1',projectId:id,sceneId,revision:p.revision,checkpointId:scene.candidate||scene.current,page:filter.page,pageSize:PAGE_SIZE,total:rows.length,hasMore:(filter.page+1)*PAGE_SIZE<rows.length,items,issues,readOnly:true};
}
export async function previewEvidenceMedia(work,id,sceneId,runId){
 const p=await work.project(id),scene=work.scene(p,sceneId),run=await receipt(p,runId);return verifyPreviewEvidence(work,p,scene,run);
}
