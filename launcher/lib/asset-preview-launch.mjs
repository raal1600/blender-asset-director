/** Owned new Blender process, no reuse of an MCP or unrelated window. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {assert,exists,json,safe,writeJson} from './storage.mjs';

export function previewEnvironment(temporary,source=process.env) {
  const allowed=new Set(['PATH','SYSTEMROOT','WINDIR','HOME','USERPROFILE','APPDATA','LOCALAPPDATA','LANG','LC_ALL']);
  const env=Object.fromEntries(Object.entries(source).filter(([key])=>allowed.has(key.toUpperCase())));
  // Blender writes quit.blend on exit; never replace another window's recovery.
  return {...env,TEMP:temporary,TMP:temporary,TMPDIR:temporary};
}

export async function launchAssetPreview(runtime,directory,receipt) {
  const receiptFile=await safe(directory,'receipt.json'),blend=await safe(directory,receipt.blend.path);
  const helper=path.join(runtime.config.skill,'scripts/runtime/asset_director/asset_preview_workspace.py');
  assert(await exists(helper),'Matching preview workspace helper is missing.');
  const temporary=await safe(directory,'native-temp');await fs.mkdir(temporary);
  const log=await fs.open(await safe(directory,'window.log'),'wx');let child;
  const env=previewEnvironment(temporary);
  try {
    child=spawn(runtime.config.blender,['--factory-startup','--disable-autoexec',blend,'--python',helper,'--',receiptFile],
      {cwd:directory,detached:true,stdio:['ignore',log.fd,log.fd],windowsHide:false,env});
    await new Promise((resolve,reject)=>{child.once('spawn',resolve);child.once('error',reject);});
    child.unref();
  } finally {await log.close();}
  await writeJson(await safe(directory,'process.json'),{pid:child.pid,executable:runtime.config.blender,receipt:receiptFile,blend,state:'STARTED'});
  const readyFile=await safe(directory,'window-ready.json');
  const deadline=Date.now()+15000;
  while(Date.now()<deadline) {
    assert(!await exists(await safe(directory,'window-failure.json')),'Preview controls did not initialize. Inspect the retained window-failure.json and window log.');
    if(await exists(readyFile)) {
      const ready=await json(readyFile);
      assert(ready.state==='READY'&&ready.pid===child.pid&&ready.source_id===receipt.source_id&&
        ready.source_version===receipt.source_version&&ready.blend_sha256===receipt.blend.sha256,'Preview window identity mismatch.',409);
      return {pid:child.pid,state:'OPENED',humanReview:'PENDING'};
    }
    if(child.exitCode!==null)break;
    await new Promise(resolve=>setTimeout(resolve,150));
  }
  // No forced termination: Blender may have reached a prompt or unsaved edits.
  throw new Error('Blender preview did not confirm readiness. Inspect its retained window log and close only that preview window if needed.');
}
