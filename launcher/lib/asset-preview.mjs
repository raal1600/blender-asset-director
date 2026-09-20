/** Preview is an isolated inspection, never a project job, pin or rights grant. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {assert, fileHash, json, safe, snapshot, writeJson} from './storage.mjs';

export const previewMember = file => /\.(blend|gltf|glb|fbx|bvh)$/i.test(file);
export const previewLimit = 512*1024*1024;

export async function openAssetPreview(work,id,sceneId,revision,request) {
  assert(request&&Object.keys(request).every(k=>['kind','id','version','file'].includes(k)), 'Unknown preview request fields.');
  assert(['catalog','source'].includes(request.kind),'Choose a catalog asset or original package.');
  assert(typeof request.file==='string'&&previewMember(request.file),'Preview supports blend, glTF, GLB, FBX and BVH. Other formats need the specialist workflow.');
  const project=await work.project(id,revision);work.scene(project,sceneId);
  // The project is read only. Preview can coexist with a scene task/candidate.
  let title,root,files,file,motion={};
  if(request.kind==='catalog') {
    const asset=await work.catalogDetail(id,request.id);
    assert(asset.version===request.version,'This asset version changed; reopen Details.',409);
    assert(asset.files.some(f=>f.path===request.file),'Choose an exact recorded asset member.');
    title=asset.title;root=work.config.library;files=asset.files;file=request.file;
    if(asset.kind==='animation') {
      const m=asset.metadata;
      assert(m?.file?.path===file&&m.action&&m.source_object&&m.fps,'Choose the indexed native take member; an unindexed animation needs inspection first.',409);
      motion=Object.fromEntries(['file','action','slot','source_object','fps','frame_start','frame_end'].filter(k=>m[k]!==undefined).map(k=>[k,m[k]]));
    } else assert(['model','pack'].includes(asset.kind),'Material/HDRI preview requires the reviewed look-development workflow.');
  } else {
    const source=await work.sourceDetail(id,request.id);
    assert(source.available&&source.version===request.version,'Package changed or is unavailable; refresh the library.',409);
    assert(source.entrypoints.includes(request.file),'Choose a recorded package member.');
    const version=await json(await safe(work.store.registry,`versions/${source.id}/${source.version}.json`));
    assert(version.sourceId===source.id&&version.version===source.version&&version.relative===source.relative,'Package snapshot identity differs.',409);
    assert(version.files.length<=4096&&version.bytes<=previewLimit,'Preview copy exceeds 4096 files or 512 MiB; use a smaller reviewed package.');
    const base=await safe(work.store.database,source.relative),directory=(await fs.stat(base)).isDirectory();
    assert((await snapshot(base)).version===source.version,'Original package changed; refresh the library.',409);
    root=directory?base:path.dirname(base);files=version.files;title=source.name;
    file=directory?request.file.slice(source.relative.length+1):path.basename(base);
    assert(!directory||request.file.startsWith(source.relative+'/'),'Member leaves its package.');
  }
  assert(files.length<=4096&&files.reduce((n,f)=>n+f.size,0)<=previewLimit,'Preview copy exceeds 4096 files or 512 MiB; use a smaller reviewed package.');
  const previewId='preview_'+randomUUID();
  const base=await safe(work.store.root,'SystemRuntime/UserData/AssetPreviews');
  await fs.mkdir(base,{recursive:true});
  const directory=await safe(base,previewId);await fs.mkdir(directory);
  const requestFile=path.join(directory,'request.json');
  await writeJson(requestFile,{schema:'asset-director.asset-preview/1',id:request.id,title,
    version:request.version,source_kind:request.kind,root,files,file,motion});
  try {
    const receipt=await work.runtime.harness(['workbench-preview','--request',requestFile,'--blender',work.config.blender],205000);
    assert(receipt.state==='READY'&&receipt.source_id===request.id&&receipt.source_version===request.version,'Preview preparation identity mismatch.',409);
    const blend=await safe(directory,receipt.blend.path),bytes=await fileHash(blend);
    assert(bytes.sha256===receipt.blend.sha256&&bytes.size===receipt.blend.size,'Prepared preview changed.',409);
    const launched=await work.runtime.launchAssetPreview(directory,receipt);
    return {previewId,...launched,sourceId:request.id,version:request.version,
      objects:receipt.data.objects.length,takes:receipt.data.takes.length,
      message:'Preview copy opened in a separate Blender window. Nothing was selected or imported. Close that window with X when finished.'};
  } catch(error) {
    // Retain both the native receipt/log and launcher failure; never fabricate READY.
    await writeJson(path.join(directory,'launch-failure.json'),{previewId,state:'FAILED',error:error.message,sourceId:request.id,version:request.version});
    throw new Error(error.message+' Preview attempt retained: '+previewId);
  }
}
