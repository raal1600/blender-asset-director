/** Preload only a verified disposable copy, never the frozen source checkpoint.
 * GUI file loading belongs before --python, not inside its running event loop.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {constants} from 'node:fs';
import {assert,safe,fileHash} from './storage.mjs';
export async function taskArguments(project,task,manifest,helper) {
  const args=['--factory-startup','--disable-autoexec'];
  assert(task.projectId===project.id&&manifest===await safe(project.directory,`Runs/${task.id}.json`),'Task identity changed.');
  assert(typeof task.workingScene==='string'&&/^Scenes\/[^/]+\.blend$/.test(task.workingScene),'Invalid task working copy.');
  if(task.input){
    assert(typeof task.input.path==='string'&&/^Scenes\/[^/]+\.blend$/.test(task.input.path),'Invalid frozen task input.');
    const source=await safe(project.directory,task.input.path),working=await safe(project.directory,task.workingScene);
    assert(source!==working&&path.isAbsolute(source),'Task must not load its original as an editable file.');
    const before=await fileHash(source);assert(before.sha256===task.input.sha256,'Checkpoint changed before launch.',409);
    await fs.copyFile(source,working,constants.COPYFILE_EXCL);
    assert((await fileHash(source)).sha256===before.sha256&&(await fileHash(working)).sha256===before.sha256,
      'Task input changed while copying. The unregistered working file is retained for diagnosis.',409);
    args.push(working);
  }
  return [...args,'--python',helper,'--',manifest];
}
