import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { json } from './lib/storage.mjs';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const [command,projectId,jobId] = process.argv.slice(2);
const commands = {'scene-info':['GET','/api/blender/scene'],'start-blender':['POST','/api/blender/start'],status:['GET','/api/state'],projects:['GET','/api/state'],verify:['POST','/api/projects/verify'],audit:['POST','/api/projects/audit'],'bind-job':['POST','/api/projects/bind-job'],health:['POST','/api/health']};
try {
  if (!commands[command]) throw new Error('Usage: node cli.mjs status | projects | health | scene-info PROJECT_ID | start-blender PROJECT_ID | verify PROJECT_ID | audit PROJECT_ID | bind-job PROJECT_ID JOB_ID');
  const session = await json(path.join(root,'SystemRuntime/UserData/Launcher/session.json'));
  const [method,route] = commands[command];
  const r = await fetch(session.origin+route+(command==='scene-info'?'?projectId='+encodeURIComponent(projectId||''):''),{method,headers:{Authorization:`Bearer ${session.token}`,'Content-Type':'application/json'},...(method === 'POST' ? {body:JSON.stringify({projectId,jobId})} : {})});
  const result = await r.json(); if (!r.ok) throw new Error(result.error);
  console.log(JSON.stringify(result,null,2));
} catch(e) {console.error(e.message);if(e.code==='ENOENT'||e.message==='fetch failed')console.error('Start the local launcher if it is not running.');process.exitCode=1;}
