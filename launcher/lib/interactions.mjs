import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {assert,digest,exists,json,now,safe,writeJson} from './storage.mjs';
import {verifyNative} from './workbench-catalog.mjs';
const disclaimer='This is a user attestation for this project and these exact source versions, not a harness license grant. Retained terms, catalog review, rig inspection and reviewed-job validation remain required.';
const acceptedSource = r => r.kind==='source-use'&&r.state==='ANSWERED'&&r.answer?.decision==='Confirm project use'&&['mcp-elicitation-client-response','launcher-ui-source-confirmation'].includes(r.transport);
function sourceUseMessage(context){
  const mixamo=context.scope.sources.some(s=>/^Animations\/Mixamo\//i.test(s.relative));
  return [`Source-use confirmation for ${context.p.name}.`,`Requested work: ${context.p.brief}`,'Sources (fixed versions):',...context.scope.sources.map(s=>`${s.relative} [${s.version}]`),'Choose Confirm project use only if you have rights to use and adapt all listed sources for this project.',...(mixamo?['For the source(s) listed under Mixamo, confirmation also attests that you obtained them through official Mixamo downloads and reviewed the applicable terms for this project. Folder names alone are not proof of origin.','Review: https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html and https://www.adobe.com/legal/terms.html']:[]),'This excludes future files, raw redistribution, public asset-library publishing and model training. Choose another option if you cannot confirm. The adapter supplies no default answer.',disclaimer].join('\n\n');
}
export class Interactions {
 constructor(store,runtime,projectId,sessionId){Object.assign(this,{store,runtime,projectId,sessionId});}
 async context(){
  const p=await this.store.get(this.projectId),sources=[];
  for(const ref of p.assets){const v=await json(await safe(this.store.registry,`versions/${ref.sourceId}/${ref.version}.json`));sources.push({sourceId:ref.sourceId,version:ref.version,relative:v.relative});}
  for(const pin of p.workbench?.catalogPins||[])sources.push({sourceId:pin.id,version:pin.version,relative:'Catalog/'+pin.title});
  sources.sort((a,b)=>a.sourceId.localeCompare(b.sourceId));
  const scope={projectId:p.id,brief:p.brief,capabilityMode:p.capabilityMode||'auto',capabilities:[...(p.capabilities||[])].sort(),sources};
  return {p,scope,scopeHash:digest(scope)};
 }
 async verifySources(){const p=await this.store.get(this.projectId);await verifyNative(this.store,this.runtime,p);return this.store.verify(this.projectId);}
 async directory(p){const dir=await safe(p.directory,'Docs/Interactions');await fs.mkdir(dir,{recursive:true});return dir;}
 async records(p){const dir=await this.directory(p),records=[];for(const name of await fs.readdir(dir)){if(!/^[a-f0-9-]{36}\.json$/.test(name))continue;const r=await json(await safe(dir,name));if(r.projectId===p.id)records.push(r);}return records;}
 async request(context,kind,message,schema,elicit,signal){
  const id=randomUUID(),file=path.join(await this.directory(context.p),id+'.json');
  const record={schema:1,id,kind,projectId:this.projectId,sessionId:this.sessionId,scopeHash:context.scopeHash,scope:context.scope,message,requestedSchema:schema,state:'PENDING',createdAt:now()};
  await writeJson(file,record);let response;
  try{response=await elicit({mode:'form',message,requestedSchema:schema},signal);}catch(e){record.reason=e.message;record.finishedAt=now();await writeJson(file,record);return {record,file};}
  if(signal?.aborted)record.reason='Request cancelled; no authorization recorded.';
  else if(response?.action==='accept'){
   const c=response.content;
   const valid=c&&typeof c==='object'&&!Array.isArray(c)&&Object.keys(c).every(k=>Object.hasOwn(schema.properties,k))&&schema.required.every(k=>Object.hasOwn(c,k))&&Object.entries(c).every(([k,v])=>typeof v==='string'&&v.length<=(schema.properties[k].maxLength||4000)&&(!schema.properties[k].enum||schema.properties[k].enum.includes(v)));
   if(valid){record.state='ANSWERED';record.answer=c;record.transport='mcp-elicitation-client-response';}else record.reason='Invalid or incomplete response; no authorization recorded.';
  }else record.reason=response?.action==='decline'?'User declined.':'User cancelled or did not submit an answer.';
  record.finishedAt=now();await writeJson(file,record);return {record,file};
 }
 async sourceStatus(){
  const context=await this.context();
  const dir=await safe(context.p.directory,'Docs/Interactions');
  const records=await exists(dir)?await this.records(context.p):[];
  const prior=records.find(r=>r.scopeHash===context.scopeHash&&acceptedSource(r));
  return {ready:context.scope.sources.length===0||!!prior,scope:context.scope,scopeHash:context.scopeHash,message:sourceUseMessage(context),notice:disclaimer};
 }
 async attestFromLauncher(revision,confirmed,preparationConfirmation){
  const context=await this.context();
  assert(context.p.revision===revision,'Project changed. Review the current source list.',409);
  assert(confirmed===true,'Source use needs an explicit user confirmation.');
  assert((await this.verifySources()).ok,'Pinned source bytes changed. Confirmation refused.',409);
  const id=randomUUID(),record={schema:1,id,kind:'source-use',projectId:this.projectId,sessionId:this.sessionId,
   scopeHash:context.scopeHash,scope:context.scope,state:'ANSWERED',createdAt:now(),finishedAt:now(),
   answer:{decision:'Confirm project use'},message:sourceUseMessage(context),transport:'launcher-ui-source-confirmation',notice:disclaimer,...(preparationConfirmation?{preparationConfirmation}: {})};
  await writeJson(path.join(await this.directory(context.p),id+'.json'),record);
  // This is a distinct, honest UI transport, never a fabricated MCP response.
  return {ready:true,receipt:id,scopeHash:context.scopeHash,message:sourceUseMessage(context),notice:disclaimer};
 }
 async prepare(elicit,signal){
  const context=await this.context();assert((await this.verifySources()).ok,'Linked sources changed or are missing. Deliberately relink current versions before authorization.',409);
  if(!context.scope.sources.length)return {status:'NO_LINKED_SOURCES',ready:true,scopeHash:context.scopeHash,projectId:this.projectId,notice:disclaimer};
  const prior=(await this.records(context.p)).find(r=>r.scopeHash===context.scopeHash&&acceptedSource(r));
  if(prior)return {status:'USER_ATTESTED',ready:true,scopeHash:context.scopeHash,receipt:path.join(await this.directory(context.p),prior.id+'.json'),notice:disclaimer};
  const message=sourceUseMessage(context);
  const schema={type:'object',properties:{decision:{type:'string',title:'Source-use decision',enum:['Not sure yet','Provide license details','Confirm project use']},details:{type:'string',title:'License details or questions (optional)',maxLength:4000}},required:['decision']};
  const {record,file}=await this.request(context,'source-use',message,schema,elicit,signal);
  if((await this.context()).scopeHash!==context.scopeHash||!(await this.verifySources()).ok)return {status:'STALE',ready:false,receipt:file,message:'Scope or source bytes changed while the question was open. Review the current inputs and ask again.'};
  const ready=record.state==='ANSWERED'&&record.answer.decision==='Confirm project use';
  return {status:ready?'USER_ATTESTED':'PENDING',ready,scopeHash:context.scopeHash,receipt:file,answer:record.answer,reason:record.reason,notice:disclaimer};
 }
 async question(args,elicit,signal){
  assert(args&&Object.keys(args).every(k=>['question','options'].includes(k)),'Unknown fields. Answers must come from the Codex form, never tool arguments.');
  assert(typeof args.question==='string'&&args.question.trim()&&args.question.length<=3000,'Use a concise question.');
  assert(Array.isArray(args.options)&&args.options.length>=2&&args.options.length<=5&&new Set(args.options).size===args.options.length&&args.options.every(x=>typeof x==='string'&&x.trim()&&x.length<=150),'Provide two to five distinct choices.');
  const c=await this.context(),schema={type:'object',properties:{choice:{type:'string',title:args.question,enum:args.options},details:{type:'string',title:'Additional details (optional)',maxLength:4000}},required:['choice']};
  const {record,file}=await this.request(c,'decision',`Project: ${c.p.name}\n\n${args.question}\n\nThis records a project decision, not a license grant or job approval.`,schema,elicit,signal);
  const stale=(await this.context()).scopeHash!==c.scopeHash;return {status:stale?'STALE':record.state,ready:!stale&&record.state==='ANSWERED',answer:record.answer,receipt:file,reason:record.reason};
 }
 async runJob(jobId,elicit,signal){
  assert(/^j_[a-f0-9]{24}$/.test(jobId),'Invalid job ID.');const p=await this.store.get(this.projectId);assert(p.jobs.some(j=>j.id===jobId),'Bind the prepared job to this project before execution.',409);
  const lock=await safe(p.directory,'Runs/.interactive-execution.lock');try{await fs.mkdir(lock);}catch(e){if(e.code==='EEXIST')throw new Error('An interactive job is pending or running. Inspect its receipt before retrying.');throw e;}
  const file=await safe(p.directory,`Runs/interactive-${randomUUID()}.json`),record={schema:1,projectId:p.id,jobId,action:'interactive-job',state:'PREPARING',startedAt:now()};
  try{
   await writeJson(file,record);const gate=await this.prepare(elicit,signal);
   if(!gate.ready||signal?.aborted){record.state='BLOCKED';record.gate=gate;return {state:'BLOCKED',gate,receipt:file};}
   const job=await this.runtime.job(jobId);assert(job.id===jobId,'Harness job identity mismatch.');await this.store.bindJob(this.projectId,job);assert((await this.context()).scopeHash===gate.scopeHash&&(await this.verifySources()).ok,'Project inputs changed after confirmation; execution refused.',409);
   record.state='RUNNING';await writeJson(file,record);
   const result=await this.runtime.harness(['job-run',jobId,'--blender',this.runtime.config.blender,'--timeout','180'],195000);record.state=result.state;return {...result,interactionReceipt:file};
  }catch(e){record.state='FAILED';record.error=e.message;throw e;}
  finally{record.finishedAt=now();await writeJson(file,record);await fs.rmdir(lock);}
 }
}
