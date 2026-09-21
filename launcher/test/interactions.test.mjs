import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {Store} from '../lib/projects.mjs';
import {Interactions} from '../lib/interactions.mjs';
import {json,writeJson} from '../lib/storage.mjs';
async function fixture(t){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-interaction-test-'));t.after(async()=>{const resolved=await fs.realpath(root),temp=await fs.realpath(os.tmpdir());assert.equal(path.dirname(resolved),temp);assert.ok(path.basename(resolved).startsWith('ad-interaction-test-'));await fs.rm(resolved,{recursive:true,force:true});});
 for(const kind of ['Animations','Characters','Meshes'])await fs.mkdir(path.join(root,'Database',kind),{recursive:true});
 await fs.mkdir(path.join(root,'Database/Animations/Mixamo'));const source=path.join(root,'Database/Animations/Mixamo/fixture.fbx');await fs.writeFile(source,'SYNTHETIC TEST ONLY');
 const store=new Store(root);await store.init();const inventory=await store.scan();let p=await store.create('Synthetic interaction','Test source use');p=await store.attach(p.id,inventory.sources[0].id,p.revision);const sessionId=randomUUID();
 await writeJson(path.join(p.directory,'Docs/Codex',sessionId+'.json'),{projectId:p.id,directory:p.directory});await writeJson(path.join(root,'SystemRuntime/UserData/Launcher/config.json'),{});
 const runtime={config:{blender:'fixture-only'},job:async id=>({id,specification:{inputs:[]}}),harness:async()=>({state:'SUCCEEDED'})};const service=new Interactions(store,runtime,p.id,sessionId);return {root,source,store,p,sessionId,runtime,service};
}
const confirmed=async()=>({action:'accept',content:{decision:'Confirm project use'}});
test('exact client attestation is reused only within its project, scope and pinned versions',async t=>{
 const {service,store,p,source}=await fixture(t);let form;
 const first=await service.prepare(async request=>{form=request;return confirmed();});assert.equal(first.ready,true);assert.equal(form.mode,'form');assert.equal(Object.hasOwn(form.requestedSchema.properties.decision,'default'),false);assert.match(form.message,/official Mixamo downloads/);
 const receipt=await json(first.receipt);assert.equal(receipt.transport,'mcp-elicitation-client-response');assert.equal(receipt.scope.sources.length,1);
 assert.equal((await service.prepare(async()=>{throw Error('Must reuse exact answer');})).ready,true);
 const current=await store.get(p.id);await store.update(p.id,{revision:current.revision,brief:'Changed scope'});assert.equal((await service.prepare(async()=>({action:'cancel'}))).ready,false);
 await fs.writeFile(source,'changed bytes');await assert.rejects(service.prepare(confirmed),/sources changed/);
});
test('cancel, decline, missing answers, uncertainty and unsupported clients leave the checkpoint pending',async t=>{
 const {service}=await fixture(t);
 for(const result of [{action:'cancel'},{action:'decline'},{action:'accept',content:{}},{action:'accept',content:{decision:'Not sure yet'}},{action:'accept',content:{decision:'Provide license details',details:'Need review'}}])assert.equal((await service.prepare(async()=>result)).ready,false);
 const unavailable=await service.prepare(async()=>{throw Error('No form support');});assert.equal(unavailable.ready,false);assert.match(unavailable.reason,/No form/);
 let resolve,finished=false;const pending=service.prepare(()=>new Promise(r=>{resolve=r;})).then(r=>{finished=true;return r;});
 while(!resolve)await new Promise(r=>setTimeout(r,5));await new Promise(r=>setTimeout(r,30));assert.equal(finished,false);resolve({action:'cancel'});assert.equal((await pending).ready,false);
});
test('scope changes during an open form invalidate the answer',async t=>{
 const {service,store,p}=await fixture(t);const result=await service.prepare(async()=>{await store.update(p.id,{revision:p.revision,brief:'Different requested work'});return confirmed();});assert.equal(result.status,'STALE');assert.equal(result.ready,false);
});
test('questions reject model-supplied answers and never create source authorization',async t=>{
 const {service}=await fixture(t);await assert.rejects(service.question({question:'Which?',options:['A','B'],answer:'A'},confirmed),/Answers must come/);
 const result=await service.question({question:'Which?',options:['A','B']},async()=>({action:'accept',content:{choice:'A'}}));assert.equal(result.answer.choice,'A');assert.equal((await service.prepare(async()=>({action:'cancel'}))).ready,false);
});
test('dependent job never reaches executor on cancellation and preserves native failure on confirmation',async t=>{
 const {service,store,p,runtime}=await fixture(t);const jobId='j_'+'a'.repeat(24);await store.bindJob(p.id,await runtime.job(jobId));let runs=0;runtime.harness=async()=>{runs++;throw Error('Native LICENSE_SCOPE_MISMATCH');};
 assert.equal((await service.runJob(jobId,async()=>({action:'cancel'}))).state,'BLOCKED');assert.equal(runs,0);
 await assert.rejects(service.runJob(jobId,confirmed),/LICENSE_SCOPE_MISMATCH/);assert.equal(runs,1);
});
test('stdio MCP negotiates forms, rejects injected answers and waits for the actual client response',async t=>{
 const {root,p,sessionId}=await fixture(t),child=spawn(process.execPath,[fileURLToPath(new URL('../tools/project-mcp.mjs',import.meta.url)),root,p.id,sessionId],{stdio:['pipe','pipe','pipe'],windowsHide:true});
 t.after(()=>{child.stdin.end();child.kill();});let buffer='',next=0;const queue=[],waiters=[];let stderr='';child.stderr.on('data',d=>stderr+=d);
 child.stdout.on('data',d=>{buffer+=d;let i;while((i=buffer.indexOf('\n'))>=0){const value=JSON.parse(buffer.slice(0,i));buffer=buffer.slice(i+1);const waiter=waiters.shift();if(waiter)waiter(value);else queue.push(value);}});
 const receive=()=>queue.length?Promise.resolve(queue.shift()):new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('MCP response timeout '+stderr)),5000);waiters.push(v=>{clearTimeout(timer);resolve(v);});});
 const send=m=>child.stdin.write(JSON.stringify({jsonrpc:'2.0',...m})+'\n');
 send({id:++next,method:'initialize',params:{protocolVersion:'2025-11-25',capabilities:{elicitation:{form:{}}},clientInfo:{name:'synthetic-test',version:'1'}}});assert.equal((await receive()).result.serverInfo.name,'asset-director-interactions');send({method:'notifications/initialized'});
 send({id:++next,method:'tools/call',params:{name:'prepare_project',arguments:{answer:true}}});assert.equal((await receive()).result.isError,true);
 const callId=++next;send({id:callId,method:'tools/call',params:{name:'prepare_project',arguments:{}}});const question=await receive();assert.equal(question.method,'elicitation/create');assert.equal(question.params.mode,'form');
 send({id:question.id,result:{action:'cancel'}});const result=await receive();assert.equal(result.id,callId);assert.equal(result.result.structuredContent.ready,false);
});
