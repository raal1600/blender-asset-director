import path from 'node:path';
import fs from 'node:fs/promises';
import {exists,json,safe} from './storage.mjs';

// Read-only status across launcher receipts and independently running Codex jobs.
export async function unfinishedWork(store,config) {
  const {projects,errors}=await store.list();
  const reasons=errors.map(e=>`${e.folder}: ${e.message}`);
  for(const project of projects) {
    if(await exists(await safe(project.directory,'Runs/.interactive-execution.lock')))
      reasons.push(`${project.name}: interactive job pending or running`);
    for(const name of await fs.readdir(await safe(project.directory,'Runs'))) {
      if(!name.endsWith('.json')) continue;
      const run=await json(await safe(project.directory,`Runs/${name}`));
      if(run.projectId!==project.id) throw new Error('Operation belongs to a different project.');
      if(['PREPARING','RUNNING'].includes(run.state)) reasons.push(`${project.name}: unfinished ${run.action || 'operation'}`);
    }
    for(const ref of project.jobs) {
      if(!config.library) continue;
      const file=await safe(config.library,`jobs/${ref.id}/job.json`);
      if(await exists(file) && (await json(file)).state==='RUNNING') reasons.push(`${project.name}: running harness job`);
    }
  }
  return reasons;
}
