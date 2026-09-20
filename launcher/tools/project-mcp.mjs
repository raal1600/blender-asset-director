import readline from 'node:readline';
import path from 'node:path';
import {Store,projectId as validateId} from '../lib/projects.mjs';
import {Runtime} from '../lib/runtime.mjs';
import {Interactions} from '../lib/interactions.mjs';
import {assert,json,safe} from '../lib/storage.mjs';
const [rootArg,projectId,sessionId]=process.argv.slice(2);validateId(projectId);assert(/^[a-f0-9-]{36}$/.test(sessionId),'Invalid session ID.');const root=path.resolve(rootArg);
const store=new Store(root),project=await store.get(projectId),session=await json(await safe(project.directory,`Docs/Codex/${sessionId}.json`));assert(session.projectId===projectId&&session.directory===project.directory,'Session binding mismatch.');
const runtime=new Runtime(store,await json(await safe(root,'SystemRuntime/UserData/Launcher/config.json'))),service=new Interactions(store,runtime,projectId,sessionId);
const output=value=>process.stdout.write(JSON.stringify({jsonrpc:'2.0',...value})+'\n');
const pending=new Map(),calls=new Map();let clientCapabilities,initialized=false,busy=false,nextId=0;
const noArgs={type:'object',properties:{},additionalProperties:false};
const tools=[
 {name:'prepare_project',description:'Required checkpoint before source-dependent production. Verify pinned sources and request missing project-use attestation INSIDE Codex. PENDING/STALE means stop dependent work. Records answers, not license grants.',inputSchema:noArgs},
 {name:'ask_project_question',description:'Ask a blocking project question with choices INSIDE Codex. Only the MCP client supplies the answer. No credentials. Cancellation stays pending.',inputSchema:{type:'object',properties:{question:{type:'string'},options:{type:'array',items:{type:'string'},minItems:2,maxItems:5}},required:['question','options'],additionalProperties:false}},
 {name:'run_project_job',description:'Execute an already prepared and project-bound harness job after source-use confirmation. Missing attestation triggers the Codex form. Native licensing, reviewed-plan and execution checks remain mandatory. Never bypass a pending checkpoint via raw job-run.',inputSchema:{type:'object',properties:{jobId:{type:'string',pattern:'^j_[a-f0-9]{24}$'}},required:['jobId'],additionalProperties:false}},
 {name:'interaction_test',description:'Display a harmless test question INSIDE Codex. Answers grant no rights and run no Blender operation.',inputSchema:noArgs}
];
function elicit(params,signal){
 const capability=clientCapabilities?.elicitation;
 if(!capability||!(Object.hasOwn(capability,'form')||Object.keys(capability).length===0))return Promise.reject(new Error('Codex did not advertise form elicitation. The checkpoint remains pending.'));
 return new Promise((resolve,reject)=>{const id='question-'+(++nextId);const cancel=()=>{pending.delete(id);reject(new Error('Codex cancelled the question. No answer recorded.'));};if(signal?.aborted)return cancel();signal?.addEventListener('abort',cancel,{once:true});pending.set(id,{resolve:r=>{signal?.removeEventListener('abort',cancel);resolve(r);},reject:e=>{signal?.removeEventListener('abort',cancel);reject(e);}});output({id,method:'elicitation/create',params});});
}
async function handle(message){
 if(!message.method){const r=pending.get(message.id);if(r){pending.delete(message.id);message.error?r.reject(new Error(message.error.message)):r.resolve(message.result);}return;}
 const {id,method,params={}}=message;
 if(method==='notifications/cancelled'){calls.get(params.requestId)?.abort();return;}
 if(method==='notifications/initialized'){initialized=true;return;}
 if(id===undefined)return;
 try{
  if(method==='initialize'){assert(!clientCapabilities,'Already initialized.');clientCapabilities=params.capabilities||{};return output({id,result:{protocolVersion:['2025-11-25','2025-06-18'].includes(params.protocolVersion)?params.protocolVersion:'2025-06-18',capabilities:{tools:{listChanged:false}},serverInfo:{name:'asset-director-interactions',version:'0.1.0'},instructions:'Use prepare_project at source-use checkpoints and ask_project_question for blocking questions. Answers come from the Codex form; pending/cancelled answers never authorize production.'}});}
  assert(initialized,'Initialize MCP first.');if(method==='ping')return output({id,result:{}});if(method==='tools/list')return output({id,result:{tools}});if(method!=='tools/call')return output({id,error:{code:-32601,message:'Method not supported.'}});
  assert(!busy,'A question or job is already pending.');const args=params.arguments||{};assert(args&&typeof args==='object'&&!Array.isArray(args),'Invalid arguments.');assert(tools.some(t=>t.name===params.name),'Unknown tool.');
  if(['prepare_project','interaction_test'].includes(params.name))assert(Object.keys(args).length===0,'This tool takes no arguments. Answers come from the Codex form.');if(params.name==='run_project_job')assert(Object.keys(args).every(k=>k==='jobId'),'Unknown job fields.');
  const controller=new AbortController();calls.set(id,controller);busy=true;
  try{let result;
   if(params.name==='prepare_project')result=await service.prepare(elicit,controller.signal);
   if(params.name==='ask_project_question')result=await service.question(args,elicit,controller.signal);
   if(params.name==='run_project_job')result=await service.runJob(args.jobId,elicit,controller.signal);
   if(params.name==='interaction_test')result=await service.question({question:'Interaction test only: does this question appear inside your Codex session? No asset authorization is requested.',options:['Cancel test','I can see the choices']},elicit,controller.signal);
   output({id,result:{content:[{type:'text',text:JSON.stringify(result)}],structuredContent:result,isError:false}});
  }finally{busy=false;calls.delete(id);}
 }catch(e){output({id,...(method==='tools/call'?{result:{content:[{type:'text',text:e.message}],isError:true}}:{error:{code:-32602,message:e.message}})});}
}
const input=readline.createInterface({input:process.stdin,crlfDelay:Infinity});input.on('line',line=>{if(line.length>1024*1024){output({id:null,error:{code:-32600,message:'Request too large.'}});return;}try{void handle(JSON.parse(line));}catch{output({id:null,error:{code:-32700,message:'Invalid JSON.'}});}});input.on('close',()=>{for(const c of calls.values())c.abort();});
