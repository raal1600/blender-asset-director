import {unfinishedState} from './lib/lifecycle.mjs';
import {taskForExit,actOnExitTask} from './lib/exit-task.mjs';
import {Console} from 'node:console';
import {createWriteStream} from 'node:fs';
import {listenPort} from './lib/listen-port.mjs';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { randomBytes, timingSafeEqual } from 'node:crypto';
import {capabilities,buildSessionContext} from './lib/onboarding.mjs';
import { Store } from './lib/projects.mjs';
import {Workbench} from './lib/workbench.mjs';
import { Runtime } from './lib/runtime.mjs';
import { assert, exists, json, writeJson } from './lib/storage.mjs';

export const here = path.dirname(fileURLToPath(import.meta.url));
export async function createApp({root,config,port=48731,runtime:injected}) {
  const store = new Store(root); await store.init();
  const runtime = injected || new Runtime(store,config);
  const token = randomBytes(32).toString('hex'); let queue = Promise.resolve(); let origin; let pending = 0; let stopping = false;
  const serialize = action => { const p = queue.then(action); queue = p.catch(()=>{}); return p; };
  const workbench=new Workbench(store,runtime,config,serialize);
  const server = http.createServer(async(req,res) => {
    res.setHeader('Cache-Control','no-store'); res.setHeader('X-Content-Type-Options','nosniff'); res.setHeader('Referrer-Policy','no-referrer');
    res.setHeader('X-Frame-Options','DENY'); res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
    const send = (code,value) => {res.writeHead(code,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(value));};
    try {
      assert(req.headers.host === new URL(origin).host,'Invalid host.',403);
      assert(!req.headers.origin || req.headers.origin === origin,'Cross-origin request refused.',403);
      assert(!req.headers['sec-fetch-site'] || ['same-origin','none'].includes(req.headers['sec-fetch-site']),'Cross-site request refused.',403);
      const url = new URL(req.url,origin);
      if (!url.pathname.startsWith('/api/')) {
        assert(req.method === 'GET','Method not allowed.',405);
        const assets = {'/workbench-browser.mjs':'workbench-browser.mjs','/workbench-images.mjs':'workbench-images.mjs','/':'index.html','/app.mjs':'app.mjs','/style.css':'style.css','/workbench':'workbench.html','/workbench.mjs':'workbench.mjs','/workbench.css':'workbench.css','/workbench-library.mjs':'workbench-library.mjs','/workbench-task.mjs':'workbench-task.mjs','/workbench-shots.mjs':'workbench-shots.mjs','/workbench-lineage.mjs':'workbench-lineage.mjs'};
        assert(Object.hasOwn(assets,url.pathname),'Not found.',404);
        const ext = path.extname(assets[url.pathname]); res.setHeader('Content-Type',ext === '.html' ? 'text/html; charset=utf-8' : ext === '.css' ? 'text/css; charset=utf-8' : 'text/javascript; charset=utf-8');
        return res.end(await fs.readFile(path.join(here,'public',assets[url.pathname])));
      }
      const supplied = Buffer.from(req.headers.authorization?.replace(/^Bearer /,'') || '');
      assert(supplied.length === 64 && timingSafeEqual(supplied,Buffer.from(token)),'Open the launcher using its Start shortcut.',401);
      assert(['GET','POST'].includes(req.method),'Method not allowed.',405);
      let body = {};
      if (req.method === 'POST') {
        assert(req.headers['content-type']?.startsWith('application/json'),'Expected JSON.',415);
        let data = ''; for await (const part of req) { data += part; assert(data.length <= 65536,'Request too large.',413); }
        body = data ? JSON.parse(data) : {};
      }
      const lifecycle = async () => {
        const {reasons,tasks,needsAttention} = await unfinishedState(store,config);
        if(pending) reasons.unshift(`${pending} launcher operation(s) in progress`);
        return {version:2,busy:reasons.length > 0,reasons,tasks,needsAttention,stopping};
      };
      if(req.method === 'GET' && url.pathname === '/api/lifecycle') return send(200,await lifecycle());
      if(req.method === 'POST' && url.pathname === '/api/stop') {
        const status=await lifecycle();
        if(status.busy) return send(409,{error:'Work is still running. Keep the launcher open or wait for completion.',...status});
        stopping=true;
        setTimeout(()=>{server.close();server.closeIdleConnections();},100);
        return send(200,{message:'Launcher stopped. Blender and Codex remain open.'});
      }
      assert(!stopping,'Launcher is shutting down.',503);
      if(req.method==='GET'&&['/api/workbench/media','/api/workbench/source-image','/api/workbench/catalog-image'].includes(url.pathname)) {
        const parameters=Object.fromEntries(url.searchParams),id=parameters.projectId;
        const media=url.pathname.endsWith('catalog-image')?await workbench.catalogImage(id,parameters.assetId):url.pathname.endsWith('source-image')?await workbench.sourcePreview(id,parameters.sourceId):await workbench.media(id,parameters);
        if(!media){res.writeHead(204);return res.end();}
        const stat=await fs.stat(media.path);assert(stat.size<=256*1024*1024,'Media exceeds this MVP browser limit.',413);
        res.writeHead(200,{'Content-Type':media.type,'Content-Length':stat.size});
        return res.end(await fs.readFile(media.path));
      }
      const action = async () => {
        const p = url.pathname; const id = body.projectId || url.searchParams.get('projectId');
        if (req.method === 'GET') {
          if(p==='/api/lifecycle/task')return taskForExit(workbench,id,url.searchParams.get('runId'));
          if (p === '/api/workbench/catalog') return workbench.catalogPage(id,{query:url.searchParams.get('query')||'',offset:Number(url.searchParams.get('offset')||0),kind:url.searchParams.get('kind')||null});
          if (p === '/api/workbench/catalog-detail') return workbench.catalogDetail(id,url.searchParams.get('assetId'));
          if (p === '/api/workbench/sources') return workbench.sourcePage(id,{query:url.searchParams.get('query')||'',kind:url.searchParams.get('kind')||'',offset:Number(url.searchParams.get('offset')||0),sceneId:url.searchParams.get('sceneId'),selected:url.searchParams.get('selected')==='true'});
          if (p === '/api/workbench/source-detail') return workbench.sourceDetail(id,url.searchParams.get('sourceId'));
          if (p === '/api/workbench/state') return workbench.state(id,{compact:url.searchParams.get('compact')==='true'});
          if (p === '/api/workbench/capabilities') return workbench.available();
          if (p === '/api/state') return {capabilities,...await store.list(),trash:await store.trashList(),...(url.searchParams.get('compact')==='true'?{}:{inventory:await store.inventory()}),health:runtime.health,root,version:'0.1.0'};
          if (p === '/api/project') return {project:await store.get(id),scenes:await store.scenes(id),jobs:await runtime.jobs(id),runs:await store.runs(id)};
          if (p === '/api/codex/preview') return buildSessionContext(store,config,id);
          if (p === '/api/blender/scene') return runtime.liveScene(id);
          if (p === '/api/blender') return runtime.blender();
          if (p === '/api/session') return {app:'asset-director-launcher',version:'0.1.0',root};
        } else {
          if(p==='/api/lifecycle/task-close')return actOnExitTask(workbench,body,'close');
          if(p==='/api/lifecycle/task-recover')return actOnExitTask(workbench,body,'recover');
          if(p.startsWith('/api/workbench/')) {
            const sid=body.sceneId,rev=body.revision,command=p.slice('/api/workbench/'.length);
            assert(Number.isInteger(rev),'Expected a project revision.');
            if(command==='attest-sources')return workbench.attest(id,rev,body.confirmed);
            if(command==='create')return workbench.create(id,rev,body.name);
            if(command==='shot-save')return workbench.saveShot(id,sid,rev,body.shot);
            if(command==='shot-select')return workbench.selectShot(id,sid,rev,body.shotId);
            if(command==='enter')return workbench.enter(id,sid,rev,body.stage);
            if(command==='catalog-select')return workbench.selectCatalog(id,sid,rev,body.assetId,body.selected);
            if(command==='catalog-job')return workbench.catalogJob(id,sid,rev,body.request);
            if(command==='keep-building')return workbench.keepBuilding(id,sid,rev);
            if(command==='source')return workbench.selectSource(id,sid,rev,body.sourceId,body.selected);
            if(command==='inspect')return workbench.inspect(id,sid,rev,body.checkpointId);
            if(command==='import')return workbench.importCheckpoint(id,sid,rev,body.sourceScene);
            if(command==='approve')return workbench.approve(id,sid,rev,body.stage,body.checkpointId);
            if(command==='discard')return workbench.discard(id,sid,rev);
            if(command==='task-open')return workbench.openTask(id,sid,rev,body.context);
            if(command==='task-focus')return workbench.focusTask(id,sid,rev);
            if(command==='task-collect')return workbench.collectTask(id,sid,rev);
            if(command==='resolve')return workbench.resolve(id,sid,rev,body.runId,body.confirmStopped);
            if(command==='run')return workbench.startJob(id,sid,rev,body.operation,body.options,body.confirmed);
            if(command==='retry')return workbench.retry(id,rev,body.jobId,body.confirmed);
            if(command==='approve-render')return workbench.approveRender(id,sid,rev,body.renderId);
            if(command==='arrange')return workbench.arrange(id,rev,body.clips);
            if(command==='assemble')return workbench.assemble(id,rev,body.confirmed);
            if(command==='approve-cut')return workbench.approveCut(id,rev,body.cutId);
            if(command==='codex')return workbench.codex(id,sid,rev);
            assert(false,'Unknown workbench action.',404);
          }
          // Legacy manifest edits cannot retarget an in-flight workbench writer.
          // Job binding is intentionally allowed for the existing scoped executor.
          if(id&&['/api/projects/update','/api/projects/attach','/api/projects/detach','/api/projects/trash','/api/projects/audit','/api/codex'].includes(p)) {
            const project=await store.get(id);
            assert(!await exists(path.join(project.directory,'Runs/.workbench-writer.lock')),'A workbench task owns this project. Collect or resolve it first.',409);
          }
          if (p === '/api/projects/trash') return store.trash(id,body.revision);
          if (p === '/api/projects/restore') return store.restore(id);
          if (p === '/api/projects/create') return store.create(body.name,body.brief);
          if (p === '/api/projects/update') return store.update(id,body);
          if (p === '/api/library/scan') return store.scan();
          if (p === '/api/projects/attach') return store.attach(id,body.sourceId,body.revision);
          if (p === '/api/projects/detach') return store.detach(id,body.sourceId,body.revision);
          if (p === '/api/projects/verify') return store.verify(id);
          if (p === '/api/projects/audit') return runtime.audit(id);
          if (p === '/api/projects/bind-job') return runtime.bind(id,body.jobId);
          if (p === '/api/health') return runtime.doctor();
          if (p === '/api/blender/start') return runtime.startBlender(id,body.openScene === true);
          if (p === '/api/folder') return runtime.openFolder(id,body.key);
          if (p === '/api/codex') return runtime.openCodex(id,body.revision);

        }
        assert(false,'Not found.',404);
      };
      if(req.method === 'POST') {
        pending++;
        try { send(200,await serialize(action)); } finally { pending--; }
      } else send(200,await action());
    } catch(e) { if (!res.headersSent) send(e.status || 500,{error:e.message}); else res.end(); }
  });
  server.requestTimeout = 220000;
  await new Promise((resolve,reject)=> {server.once('error',reject);server.listen(port,'127.0.0.1',resolve);});
  origin = `http://127.0.0.1:${server.address().port}`;
  return {server,origin,token,store,runtime,workbench};
}
async function main() {
  const root = path.resolve(process.argv[2] || path.join(here,'../..'));
  const settings = path.join(root,'SystemRuntime/UserData/Launcher');
  if(process.argv[3]==='--desktop-logs') {
    // The server owns its logs, not pipes in the desktop host. Exiting only the
    // desktop cannot break logging or terminate an ongoing worker via EPIPE.
    const stdout=createWriteStream(path.join(settings,'server.log'),{flags:'a'});
    const stderr=createWriteStream(path.join(settings,'server-error.log'),{flags:'a'});
    await Promise.all([stdout,stderr].map(stream=>new Promise((resolve,reject)=>{stream.once('open',resolve);stream.once('error',reject);})));
    globalThis.console=new Console({stdout,stderr});
  }
  const config = await json(path.join(settings,'config.json'));
  for (const key of ['python','blender','skill','library','codex']) assert(path.isAbsolute(config[key]),`Invalid ${key} path in launcher configuration.`);
  const app = await createApp({root,config,port:listenPort(config)});
  try { await app.runtime.doctor(); } catch(e) { console.error('Startup health check: '+e.message); }
  const sessionPath = path.join(settings,'session.json');
  await writeJson(sessionPath,{origin:app.origin,token:app.token,pid:process.pid,root});
  console.log(`Asset Director Launcher 0.1.0 listening at ${app.origin}`);
  app.server.on('close',async()=> { if (await exists(sessionPath) && (await json(sessionPath)).pid === process.pid) await fs.rm(sessionPath); });
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main().catch(e=> { console.error(e.message);process.exitCode=1; });
