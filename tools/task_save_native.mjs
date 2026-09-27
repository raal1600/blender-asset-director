/** Real background Blender + normal launcher state/store + HTTP reconciliation.
 * No user projects, keyboard automation, GPU render or creative approval.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import assert from 'node:assert/strict';
import {createApp} from '../launcher/server.mjs';
import {json,writeJson,fileHash,exists} from '../launcher/lib/storage.mjs';
const [out,blender]=process.argv.slice(2);
assert(out&&path.isAbsolute(out)&&blender&&path.isAbsolute(blender),'Explicit new output and Blender paths required');
assert(!await exists(out),'Output must be new');await fs.mkdir(out,{recursive:true});
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url))),children=new Map(),results=[];
let mode;
const runtime={harness:async()=>({task_workspace:true,explicit_save_handoff:true}),
  launchWorkbenchTask:async(p,manifest)=>{
    const child=spawn(blender,['--background','--factory-startup','--disable-autoexec','--python-exit-code','12','--python',path.join(root,'tools/task_save_native.py'),'--',manifest,mode],{windowsHide:true});
    const chunks=[];child.stdout.on('data',x=>chunks.push(x));child.stderr.on('data',x=>chunks.push(x));
    const done=new Promise((resolve,reject)=>{child.on('error',reject);child.on('close',async code=>{await fs.writeFile(path.join(p.directory,'Docs/native-save.log'),Buffer.concat(chunks));resolve(code);});});
    children.set(child.pid,{child,done});return child.pid;
  },
  inspectWorkbenchTask:async(_p,t)=>({state:children.get(t.processId)?.child.exitCode===null?'verified':'stopped'})};
const app=await createApp({root:out,config:{library:path.join(out,'Database/AssetDirector')},port:0,runtime});
const api=async(route,body)=>{const r=await fetch(app.origin+'/api/'+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+app.token,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});const v=await r.json();assert(r.ok,JSON.stringify(v));return v;};
try {
  for(mode of ['no-save','save','saved-then-unsaved','repeat-save','recovery-copy']) {
    let p=await app.store.create('Synthetic Save Return '+mode),c=await app.workbench.create(p.id,p.revision,'Test scene');p=c.project;
    const opened=await api('workbench/task-open',{projectId:p.id,sceneId:c.sceneId,revision:p.revision});
    assert.equal(await children.get(opened.task.processId).done,0,'Native worker failed');
    p=await app.store.get(p.id);
    const beforeRevision=p.revision;
    await api('workbench/state?projectId='+p.id);assert.equal((await app.store.get(p.id)).revision,beforeRevision,'GET must not mutate');
    const result=await api('workbench/task-sync',{projectId:p.id,sceneId:c.sceneId,revision:p.revision});
    p=await app.store.get(p.id);const scene=p.workbench.scenes[0];
    assert.equal(scene.task,null);assert.equal(scene.candidate,null);assert.deepEqual(scene.completed,{});assert.equal(scene.stage,'world');
    const saved=['save','saved-then-unsaved','repeat-save'].includes(mode);
    assert.equal(result.outcome,saved?'saved':'no-save');
    if(saved){const cp=scene.checkpoints[0];assert.equal((await fileHash(path.join(p.directory,cp.path))).sha256,cp.sha256);
      const subject=cp.audit.objects.find(x=>x.name==='ExplicitSaveSubject');assert(subject);
      assert.equal(subject.matrix_world[3],mode==='repeat-save'?9:1);
    }else assert.equal(scene.current,null);
    results.push({mode,status:'PASS',outcome:result.outcome,checkpoint:scene.current,native:await json(path.join(p.directory,'Docs/native-save-result.json'))});
  }
  await writeJson(path.join(out,'RESULTS.json'),{status:'PASS',scope:'REAL_HEADLESS_SAVE_AND_HTTP',native_dialogs:'NOT_TESTED',results});
  console.log(JSON.stringify({status:'PASS',cases:results.length,output:out}));
}finally{await new Promise(resolve=>app.server.close(resolve));}
