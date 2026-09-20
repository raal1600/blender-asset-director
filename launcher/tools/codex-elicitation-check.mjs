import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import assert from 'node:assert/strict';
import {Store} from '../lib/projects.mjs';
import {writeJson} from '../lib/storage.mjs';
const audit=await fs.mkdtemp(path.join(os.tmpdir(),'asset-director-elicitation-'));
const root=await fs.mkdtemp(path.join(audit,'synthetic-elicitation-'));
for(const kind of ['Animations','Characters','Meshes'])await fs.mkdir(path.join(root,'Database',kind),{recursive:true});
const store=new Store(root);await store.init();const p=await store.create('Synthetic Codex form test','Test form transport only');const sessionId=randomUUID();
await writeJson(path.join(p.directory,'Docs/Codex',sessionId+'.json'),{projectId:p.id,directory:p.directory});await writeJson(path.join(root,'SystemRuntime/UserData/Launcher/config.json'),{});
const adapter=fileURLToPath(new URL('./project-mcp.mjs',import.meta.url));
const config='{command='+JSON.stringify(process.execPath)+',args='+JSON.stringify([adapter,root,p.id,sessionId])+',tool_timeout_sec=120}';
const codex=process.env.CODEX_EXECUTABLE || 'codex';
const child=spawn(codex,['-c','mcp_servers.asset_director='+config,'-c','mcp_servers.blender.enabled=false','-c','mcp_servers.blender-teaching-overlay.enabled=false','-c','mcp_servers.node_repl.enabled=false','-c','features.plugins=false','app-server','--stdio'],{stdio:['pipe','pipe','pipe'],windowsHide:true,cwd:p.directory});
let buffer='',counter=0,elicited=0;const pending=new Map();let threadId;
const send=value=>child.stdin.write(JSON.stringify(value)+'\n');
const rpc=(method,params)=>new Promise((resolve,reject)=>{const id=++counter,timer=setTimeout(()=>{pending.delete(id);reject(Error(method+' timed out'));},45000);pending.set(id,{resolve:v=>{clearTimeout(timer);resolve(v);},reject:e=>{clearTimeout(timer);reject(e);}});send({id,method,params});});
child.stdout.on('data',data=>{buffer+=data;let i;while((i=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,i);buffer=buffer.slice(i+1);let m;try{m=JSON.parse(line);}catch{continue;}
 if(m.method==='mcpServer/elicitation/request'){
  elicited++;assert.equal(m.params.serverName,'asset_director');assert.equal(m.params.mode,'form');assert.deepEqual(m.params.requestedSchema.properties.choice.enum,['Cancel test','I can see the choices']);
  // Synthetic protocol-client response; never a production attestation.
  send({id:m.id,result:{action:'cancel',content:null}});
 }else if(m.id!==undefined&&pending.has(m.id)){const r=pending.get(m.id);pending.delete(m.id);m.error?r.reject(Error(JSON.stringify(m.error))):r.resolve(m.result);}
 else if(m.id!==undefined&&m.method)send({id:m.id,error:{code:-32601,message:'Unsupported synthetic client request'}});
}});child.stderr.on('data',()=>{});
try{
 await rpc('initialize',{clientInfo:{name:'asset_director_integration_check',version:'0.1.0'},capabilities:{experimentalApi:true}});send({method:'initialized',params:{}});
 const thread=await rpc('thread/start',{cwd:p.directory,ephemeral:true,experimentalRawEvents:false});threadId=thread.thread.id;
 const inventory=await rpc('mcpServerStatus/list',{threadId,detail:'toolsAndAuthOnly'});const server=inventory.data.find(s=>s.name==='asset_director');assert.ok(server,'Project MCP missing from installed Codex inventory');
 const result=await rpc('mcpServer/tool/call',{threadId,server:'asset_director',tool:'interaction_test',arguments:{}});assert.equal(elicited,1);const content=result.content||result.result?.content;assert.ok(content,'Missing tool content');const record=JSON.parse(content.find(c=>c.type==='text').text);assert.equal(record.ready,false);assert.equal(record.status,'PENDING');
 await writeJson(path.join(audit,'codex-elicitation-check.json'),{status:'PASS',actualInstalledCodex:true,modelRequests:0,questionForwarded:true,cancelStayedPending:true,productionApprovalRecorded:false,nativeTerminalVisualCheck:'Not performed by this protocol test',fixture:root});console.log('Installed Codex forwarded the structured question and returned cancellation as pending. No model request, production approval or Blender operation.');
}finally{for(const r of pending.values())r.reject(Error('Test ending'));pending.clear();child.stdin.end();child.kill();}
