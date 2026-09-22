/** Private derived geometry, separate from project checkpoints and approval evidence. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {assetPreviewSource} from './asset-preview.mjs';
import {assert,digest,fileHash,inside,json,safe,slash,walk,writeJson} from './storage.mjs';
import {MAX_VIEWER_BYTES,packageGLTF,validateGLB,verifiedPackage} from './viewer-gltf.mjs';

export const MAX_PREVIEW_STORAGE_BYTES=100*1024**3;
export function assertPreviewStorageBudget(disk,sourceBytes) {
  assert(disk+sourceBytes*2+MAX_VIEWER_BYTES<MAX_PREVIEW_STORAGE_BYTES,'Private 3D preview storage would exceed 100 GiB. Review ViewerPreviews before preparing more; nothing was deleted.');
}

async function checkpointSource(work,id,sceneId,revision,request) {
  assert(Object.keys(request).every(k=>['kind','id'].includes(k)),'Unknown checkpoint preview fields.');
  const p=await work.project(id,revision),scene=work.scene(p,sceneId);
  const cp=await work.verify(p,scene,request.id);
  const records=[{...cp,filename:await safe(p.directory,cp.path)}];
  for(const pin of p.workbench.catalogPins||[])for(const f of pin.files)records.push({...f,filename:await safe(work.config.library,f.path)});
  for(const pin of p.assets) {
    const version=await json(await safe(work.store.registry,`versions/${pin.sourceId}/${pin.version}.json`));
    assert(version.sourceId===pin.sourceId&&version.version===pin.version,'Pinned package identity differs.',409);
    const base=await safe(work.store.database,version.relative),folder=(await fs.stat(base)).isDirectory()?base:path.dirname(base);
    for(const f of version.files)records.push({...f,filename:await safe(folder,f.path)});
  }
  const unique=[...new Map(records.map(f=>[f.filename.toLowerCase(),f])).values()];
  assert(unique.length<=4096&&unique.reduce((n,f)=>n+f.size,0)<=512*1024*1024,'Checkpoint and pinned dependencies exceed the 512 MiB interactive-copy limit; inspect in Blender.');
  let root=path.dirname(records[0].filename);
  while(!unique.every(f=>inside(root,f.filename))){const parent=path.dirname(root);assert(parent!==root,'Cross-drive checkpoint dependencies need Blender inspection.');root=parent;}
  return {schema:'asset-director.asset-preview/1',id:cp.id,title:scene.name+' / saved checkpoint',version:cp.sha256,source_kind:'checkpoint',root,
    files:unique.map(f=>({path:slash(path.relative(root,f.filename)),sha256:f.sha256,size:f.size})),file:slash(path.relative(root,records[0].filename)),motion:{}};
}

export class EmbeddedPreviews {
  constructor(work){this.work=work;this.cache=new Map();this.owned=new Map();this.identity=Promise.all(['./embedded-preview.mjs','./viewer-gltf.mjs','./asset-preview.mjs','../public/viewer-3d.mjs','../public/vendor/three/VENDOR.json'].map(async name=>({name,...await fileHash(fileURLToPath(new URL(name,import.meta.url)))}))).then(digest);}
  async prepare(id,sceneId,revision,request) {
    assert(request&&typeof request==='object'&&!Array.isArray(request),'Expected a preview source.');
    const w=this.work,source=request.kind==='checkpoint'?await checkpointSource(w,id,sceneId,revision,request):await assetPreviewSource(w,id,sceneId,revision,request);
    await verifiedPackage(source);
    const implementation=await this.identity,key=digest({project:id,scene:sceneId,source,implementation});
    if(this.cache.has(key)) {
      const record=this.cache.get(key);await this.bytes(id,sceneId,record.previewId);
      return {...record,cached:true};
    }
    assert(this.owned.size<64,'This session reached 64 preview copies. Close the viewer and restart Director before preparing more.');
    const base=await safe(w.store.root,'SystemRuntime/UserData/ViewerPreviews');await fs.mkdir(base,{recursive:true});
    // Never delete user data or historical failure evidence to make room.
    const names=await walk(base,50000);let disk=0;for(const name of names)disk+=(await fs.stat(await safe(base,name))).size;
    assertPreviewStorageBudget(disk,source.files.reduce((n,f)=>n+f.size,0));
    const previewId='view_'+randomUUID(),directory=await safe(base,previewId);await fs.mkdir(directory);
    const requestFile=path.join(directory,'request.json');await writeJson(requestFile,source);
    try {
      let model,adapter,nativeJob=null,nativeImplementation=null,texturePreview=null;
      if(/\.(gltf|glb)$/i.test(source.file)&&!Object.keys(source.motion||{}).length) {
        model=await packageGLTF(source);adapter='verified-gltf';
      } else {
        const receipt=await w.runtime.harness(['workbench-preview','--request',requestFile,'--blender',w.config.blender,'--embedded'],205000);
        assert(receipt.state==='READY'&&receipt.source_id===source.id&&receipt.source_version===source.version,'3D conversion returned a different source.',409);
        assert(/^j_[a-f0-9]{24}$/.test(receipt.job_id),'Invalid conversion job identity.');
        nativeJob=receipt.job_id;nativeImplementation=(await json(await safe(directory,`library/jobs/${nativeJob}/job.json`))).specification.implementation;
        assert(receipt.model&&receipt.model.size<=MAX_VIEWER_BYTES,'No bounded embedded model was produced.');
        const file=await safe(directory,receipt.model.path),actual=await fileHash(file);
        assert(actual.sha256===receipt.model.sha256&&actual.size===receipt.model.size,'Converted model changed.',409);
        model=await fs.readFile(file);adapter='isolated-blender-gltf';
        const textures=receipt.data?.embedded_viewer?.textures;
        assert(textures?.scope==='PREVIEW_ONLY'&&textures.originals_changed===false&&Number.isInteger(textures.reduced_images)&&textures.reduced_images>=0&&textures.reduced_images<=128,'Missing preview texture preservation evidence.');
        texturePreview={reducedImages:textures.reduced_images,sourcePixels:textures.source_pixels,previewPixels:textures.preview_pixels,originalsChanged:false};
      }
      const observed=validateGLB(model);await verifiedPackage(source);
      const filename=path.join(directory,'model.glb');await fs.writeFile(filename,model,{flag:'wx'});
      const record={previewId,projectId:id,sceneId,sourceId:source.id,version:source.version,title:source.title,kind:source.source_kind,
        ...await fileHash(filename),adapter,implementation,nativeJob,nativeImplementation,texturePreview,observed,cached:false,inspectionOnly:true,selectionChanged:false,approved:false};
      await writeJson(path.join(directory,'viewer.json'),record);
      this.owned.set(previewId,{record,filename,source});this.cache.set(key,record);return record;
    }catch(error){await writeJson(path.join(directory,'viewer-failure.json'),{previewId,state:'FAILED',error:error.message});throw Object.assign(new Error(error.message+' 3D attempt retained: '+previewId),{status:error.status});}
  }
  async bytes(projectId,sceneId,previewId) {
    const item=this.owned.get(previewId);
    assert(item&&item.record.projectId===projectId&&item.record.sceneId===sceneId,'3D preview does not belong to this session/scene.',404);
    // Never serve an old derivative as the new saved source, or a replaced cache.
    const p=await this.work.project(projectId);this.work.scene(p,sceneId);
    await verifiedPackage(item.source);
    const actual=await fileHash(item.filename);assert(actual.sha256===item.record.sha256&&actual.size===item.record.size,'3D preview bytes changed.',409);
    return fs.readFile(item.filename);
  }
}
