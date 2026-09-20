import path from 'node:path';
import fs from 'node:fs/promises';
import {exists,json,safe} from './storage.mjs';
import {validId} from './workbench-model.mjs';

// Read-only status across launcher receipts and independently running Codex jobs.
export async function unfinishedWork(store,config) {
  return (await unfinishedState(store,config)).reasons;
}
export async function unfinishedState(store,config) {
  const {projects,errors}=await store.list();
  const reasons=errors.map(e=>`${e.folder}: ${e.message}`);
  const tasks=[];let needsAttention=false;
  for(const project of projects) {
    const writer=await exists(await safe(project.directory,'Runs/.workbench-writer.lock'));
    const interactive=await exists(await safe(project.directory,'Runs/.interactive-execution.lock'));
    const ownerFile=await safe(project.directory,'Runs/.workbench-writer.lock/owner.json');
    const owner=writer&&await exists(ownerFile)?await json(ownerFile):null;
    let accounted=false;
    for(const name of await fs.readdir(await safe(project.directory,'Runs'))) {
      if(!name.endsWith('.json')) continue;
      const run=await json(await safe(project.directory,`Runs/${name}`));
      if(run.projectId!==project.id) throw new Error('Operation belongs to a different project.');
      if(['PREPARING','RUNNING'].includes(run.state)) {
        if(owner?.projectId===project.id&&owner.runId===run.id)accounted=true;
        const scene=project.workbench?.scenes.find(s=>s.id===run.sceneId);
        let detail='unfinished '+(run.action || 'operation');
        if(run.action==='workbench-edit'&&validId(run.id,'task_')&&scene?.task===run.id) {
          const statusFile=await safe(project.directory,`Docs/Workbench/${run.id}-status.json`);
          if(await exists(statusFile)) {
            const status=await json(statusFile);
            if(status.taskId!==run.id||status.projectId!==project.id||status.sceneId!==run.sceneId) throw new Error('Task status belongs to another operation.');
            if(status.state==='FAILED'){detail='Blender task failed: '+String(status.message||'setup failed').slice(0,500);needsAttention=true;}
          }
          tasks.push({projectId:project.id,runId:run.id,label:`${project.name} / ${scene.name}: ${detail}`});
        }
        reasons.push(`${project.name}${scene?' / '+scene.name:''}: ${detail}`);
      }
    }
    // One workbench task owns both semaphores; do not present it as three jobs.
    if(writer&&!accounted)reasons.push(`${project.name}: scene writer active or recovery required`);
    if(interactive&&!accounted)reasons.push(`${project.name}: interactive job pending or running`);
    for(const ref of project.jobs) {
      if(!config.library) continue;
      const file=await safe(config.library,`jobs/${ref.id}/job.json`);
      if(await exists(file) && (await json(file)).state==='RUNNING') reasons.push(`${project.name}: running harness job`);
    }
  }
  return {reasons,tasks,needsAttention};
}
