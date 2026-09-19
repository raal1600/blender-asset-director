import {taskArguments} from './workbench-launch.mjs';
import {randomUUID} from 'node:crypto';
import {buildSessionContext} from './onboarding.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import net from 'node:net';
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
const toolsDir=fileURLToPath(new URL('../tools/',import.meta.url));
import { assert, exists, json, now, safe, writeJson } from './storage.mjs';

const exec = promisify(execFile);
const ps = path.join(process.env.SystemRoot || 'C:\\Windows','System32/WindowsPowerShell/v1.0/powershell.exe');
export async function command(exe, args, timeout = 30000) {
  try { return await exec(exe, args, { timeout, maxBuffer: 4*1024*1024, windowsHide: true, encoding: 'utf8', env: {...process.env, PYTHONIOENCODING:'utf-8'} }); }
  catch (e) { throw new Error(`Command failed (${e.code || 'timeout'}): ${(e.stdout || e.stderr || e.message).slice(0,1000)}`); }
}
export function addonQuery(type, port = 9876) {
  assert(['get_addon_info','get_scene_info'].includes(type), 'Only read-only Blender queries are allowed.');
  return new Promise((resolve,reject) => {
    const socket = net.createConnection({ host:'127.0.0.1', port }); let text = ''; let finished = false;
    function finish(error, data) { if (finished) return; finished = true; socket.destroy(); error ? reject(error) : resolve(data); }
    socket.setEncoding('utf8'); socket.setTimeout(4000);
    socket.on('timeout', () => finish(new Error('Blender MCP did not respond.')));
    socket.on('error', e => finish(e));
    socket.on('end', () => { if (!finished) finish(new Error('Blender closed the connection.')); });
    socket.on('connect', () => socket.write(JSON.stringify({ type, params:{} })));
    socket.on('data', chunk => {
      text += chunk.toString('utf8'); if (text.length > 2*1024*1024) return finish(new Error('Blender response exceeded the size limit.'));
      let result; try { result = JSON.parse(text); } catch { return; }
      if (result.status !== 'success') return finish(new Error(result.message || 'Blender query failed.'));
      finish(null,result.result);
    });
  });
}
export class Runtime {
  constructor(store, config) { this.store = store; this.config = config; this.health = null; }
  async harness(args, timeout = 30000) {
    const { stdout } = await command(this.config.python, [path.join(this.config.skill,'scripts/director.py'),'--library',this.config.library,...args],timeout);
    return JSON.parse(stdout.replace(/^\uFEFF/,''));
  }
  async doctor() {
    assert(await exists(path.join(this.config.library,'catalog.sqlite')), 'The configured harness database is missing.');
    const result = await this.harness(['doctor']);
    const {stdout} = await command(this.config.python,[path.join(this.config.skill,'scripts/manage_install.py'),'--dest',this.config.skill,'--verify']);
    const installed = JSON.parse(stdout);
    this.health = { ...result, installed, checkedAt: now() };
    await writeJson(path.join(this.store.root,'SystemRuntime/UserData/Launcher/health.json'),this.health);
    return this.health;
  }
  async blender() {
    try { const info = await addonQuery('get_addon_info',this.config.mcpPort); return { connected:true, ...info }; }
    catch { return { connected:false, message:'Open Blender and start its existing MCP add-on server.' }; }
  }
  async liveScene(projectId){
    await this.store.get(projectId);
    const scene=await addonQuery('get_scene_info',this.config.mcpPort);
    return {projectId,observedAt:now(),scene,ownership:'Not established by this query. The live scene may belong to another project.',review:'Read-only scene metadata; not a visual review or saved-file audit.'};
  }
  async processes() {
    if (process.platform !== 'win32') return [];
    const { stdout } = await command(ps,['-NoProfile','-NonInteractive','-Command',"@(Get-CimInstance Win32_Process -Filter \"Name = 'blender.exe'\" | Select-Object ProcessId,ExecutablePath) | ConvertTo-Json -Compress"],10000);
    const data = stdout.trim() ? JSON.parse(stdout) : []; return Array.isArray(data) ? data : [data];
  }
  async showBlender(processId) {
    const {stdout}=await command(ps,['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(toolsDir,'show-blender.ps1'),'-ProcessIdentifier',String(processId),'-Executable',this.config.blender],10000);
    return JSON.parse(stdout);
  }
  async startBlender(projectId, openScene = false) {
    const project = await this.store.get(projectId);
    if(openScene)return this.openReviewScene(project);
    const connected = await this.blender();
    if (connected.connected) {
      const processes=(await this.processes()).filter(p=>p.ExecutablePath?.toLowerCase()===this.config.blender.toLowerCase());
      for(const p of processes){const window=await this.showBlender(p.ProcessId);if(window.visible)return {started:false,connected:true,...window,message:window.focused?'Blender is now in front. Its current scene was preserved.':'Blender is visible. Select its window on the taskbar; its current scene was preserved.'};}
      throw new Error('Blender responds, but its editor is on another Windows desktop or is not available. Close that instance before starting a visible editor. No scene was changed.');
    }
    const running=await this.processes();
    if(running.length){for(const p of running.filter(p=>p.ExecutablePath?.toLowerCase()===this.config.blender.toLowerCase())){const window=await this.showBlender(p.ProcessId);if(window.visible)return {started:false,connected:false,...window,message:'Blender is visible. Start its MCP Server in the add-on panel to connect; the current scene was preserved.'};}
      throw new Error('A Blender process is running without an accessible editor. Close it or finish its background work before starting another instance.');}
    assert(await exists(this.config.blender), 'Configured Blender executable is missing.');
    let args = ['--disable-autoexec'];
    if (openScene) { assert(project.scene,'Select a saved project scene first.'); args.push(await safe(project.directory,project.scene)); }
    const child = spawn(this.config.blender,args,{detached:true,stdio:'ignore',windowsHide:false,cwd:project.directory});
    await new Promise((resolve,reject) => {child.once('spawn',resolve);child.once('error',reject);}); child.unref();
    for (let i=0;i<20;i++) {
      await new Promise(r => setTimeout(r,750));
      const current = await this.blender();
      if (current.connected) {const window=await this.showBlender(child.pid);return {started:true,connected:true,...window,message:window.visible?(openScene?'Blender opened the project scene and connected.':'Blender opened and connected.'):'Blender connected but its editor is not visible on this desktop.'};}
    }
    return {started:true,connected:false,message:'Blender opened. Its MCP server has not responded yet; use Refresh or Start MCP Server in Blender.'};
  }
  async openFolder(projectId, key) {
    const shared = { animations:'Database/Animations', characters:'Database/Characters', meshes:'Database/Meshes', database:'Database', projects:'Workspace/Projects', docs:'Docs' };
    let destination;
    if (shared[key]) destination = await safe(this.store.root,shared[key]);
    else {
      const p = await this.store.get(projectId); const owned = {project:'',scenes:'Scenes',renders:'Renders',deliverables:'Deliverables'};
      assert(Object.hasOwn(owned,key),'Unknown folder.'); destination = await safe(p.directory,owned[key]);
    }
    assert(process.platform === 'win32','Folder opening is available on Windows.');
    await command(path.join(process.env.SystemRoot,'explorer.exe'),[destination],10000).catch(e => { if (!e.message.includes('(1)')) throw e; });
    return {opened:destination};
  }
  async launchWorkbenchTask(project,manifest) {
    const helper=path.join(this.config.skill,'scripts/task_workspace.py');
    assert(path.isAbsolute(this.config.blender)&&await exists(this.config.blender),'Configured Blender executable is missing.');
    assert(await exists(helper),'Install the matching development harness; the task helper is missing.');
    const task=await json(manifest);
    assert(manifest===await safe(project.directory,`Runs/${task.id}.json`)&&task.projectId===project.id,'Invalid task manifest.');
    // A new factory-startup process preserves every existing Blender window and
    // user preference. There is deliberately no claim to an existing MCP socket.
    const args=await taskArguments(project,task,manifest,helper);
    const child=spawn(this.config.blender,args,
      {detached:true,stdio:'ignore',windowsHide:false,cwd:project.directory});
    await new Promise((resolve,reject)=>{child.once('spawn',resolve);child.once('error',reject);});
    child.unref();return child.pid;
  }
  async launchReview(project,filename){
    assert(await exists(this.config.blender),'Configured Blender executable is missing.');
    const child=spawn(this.config.blender,['--disable-autoexec',filename],{detached:true,stdio:'ignore',windowsHide:false,cwd:project.directory});
    await new Promise((resolve,reject)=>{child.once('spawn',resolve);child.once('error',reject);});child.unref();return child.pid;
  }
  async openReviewScene(project){
    assert(project.scene,'Select a saved project scene first.');
    const filename=await safe(project.directory,project.scene);
    assert((await fs.stat(filename)).isFile(),'Selected scene is missing. Refresh the scene list.');
    const processId=await this.launchReview(project,filename);
    for(let i=0;i<20;i++){
      await new Promise(r=>setTimeout(r,500));
      const window=await this.showBlender(processId).catch(()=>({visible:false}));
      if(window.visible)return {started:true,processId,...window,scene:project.scene,message:'Selected scene opened in a separate Blender review window. Existing windows were preserved.'};
    }
    return {started:true,processId,visible:false,scene:project.scene,message:'Blender was started with the selected file, but its review window is not visible yet. Check the taskbar or refresh.'};
  }
  async launchTerminal(projectId,sessionId){
    assert(await exists(this.config.codex),'Codex executable is missing.');
    const {stdout}=await command(ps,['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(toolsDir,'launch-codex.ps1'),'-ProjectId',projectId,'-SessionId',sessionId]);
    return JSON.parse(stdout);
  }
  async openCodex(id,revision) {
    const context=await buildSessionContext(this.store,this.config,id);
    assert(context.revision===revision,'Project changed. Review the refreshed startup prompt before launching.',409);
    assert(context.ready,'Describe the project and finish the library step before starting Codex.');
    assert((await this.store.verify(id)).ok,'Linked sources changed or are missing. Resolve them in the library step before starting Codex.',409);
    let blenderSetup;
    try {blenderSetup=await this.startBlender(id,false);}catch(e){blenderSetup={started:false,connected:false,message:e.message};}
    const sessionId=randomUUID();
    const directory=await safe(context.directory,'Docs/Codex');await fs.mkdir(directory,{recursive:true});
    const promptFile=await safe(context.directory,'Docs/Codex/'+sessionId+'.md');await fs.writeFile(promptFile,context.prompt,{flag:'wx'});
    await writeJson(await safe(context.directory,'Docs/Codex/'+sessionId+'.json'),{...context,sessionId,createdAt:now(),promptFile,blenderSetup});
    const terminal=await this.launchTerminal(id,sessionId);
    return {message:'Codex terminal started with your saved brief, capabilities and linked sources. '+blenderSetup.message+' Continue the conversation in the terminal.',directory:context.directory,processId:terminal.processId,sessionId,blenderSetup};
  }
  async job(id) { assert(/^j_[0-9a-f]{24}$/.test(id),'Invalid job ID.'); return this.harness(['job-show',id]); }
  async bind(id,jid) { return this.store.bindJob(id,await this.job(jid)); }
  async jobs(id) {
    const p = await this.store.get(id); const result = [];
    for (const ref of p.jobs) {
      try {
        // Display historical state even when inputs have since changed. Do not
        // pretend a raw record is a currently executable/validated harness job.
        const data = await json(await safe(this.config.library,`jobs/${ref.id}/job.json`));
        assert(data.id === ref.id,'Job identity mismatch.');
        result.push({...ref,state:data.state,outputs:data.outputs,validation:'Historical record; revalidated before execution'});
      } catch(e) { result.push({...ref,state:'UNAVAILABLE',message:e.message}); }
    }
    return result;
  }
  async audit(id) {
    const p = await this.store.get(id); assert(p.scene,'Choose a saved project scene before auditing.');
    const verified = await this.store.verify(id); assert(verified.ok,'A pinned source changed or is missing. Resolve project asset checks before running jobs.',409);
    const input = await safe(p.directory,p.scene);
    const receipt = {schema:1,projectId:id,action:'scene-audit',startedAt:now(),state:'PREPARING',input};
    const receiptFile = await safe(p.directory,`Runs/audit-${Date.now()}.json`);
    await writeJson(receiptFile,receipt);
    try {
      const job = await this.harness(['job-prepare','scene-audit','--input',input]);
      receipt.jobId = job.id; await writeJson(receiptFile,receipt);
      await this.store.bindJob(id,job);
      receipt.state = 'RUNNING'; await writeJson(receiptFile,receipt);
      const result = await this.harness(['job-run',job.id,'--blender',this.config.blender,'--timeout','180'],195000);
      receipt.state = result.state; receipt.finishedAt = now(); await writeJson(receiptFile,receipt);
      return result;
    } catch(e) { receipt.state='FAILED'; receipt.error=e.message; receipt.finishedAt=now(); await writeJson(receiptFile,receipt); throw e; }
  }
}
