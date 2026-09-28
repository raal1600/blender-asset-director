/** Private derived geometry, separate from project checkpoints and approval evidence. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {assetPreviewSource} from './asset-preview.mjs';
import {assert,digest,fileHash,inside,json,safe,slash,walk,writeJson} from './storage.mjs';
import {MAX_VIEWER_BYTES,packageGLTF,validateGLB,verifiedPackage} from './viewer-gltf.mjs';
import {bindWorldPreview} from './world-preview-bindings.mjs';
import {selectedShotPreview,shotProfiles,validateShotCamera} from './shot-preview.mjs';
import {PreviewCache} from './preview-cache.mjs';

export const MAX_PREVIEW_STORAGE_BYTES=100*1024**3;
export const MAX_PREVIEW_METADATA_BYTES=32*1024**2;
export const previewProfile = (stage,kind='checkpoint',shot=null) => stage==='world'?'world-static-v1':kind==='checkpoint'&&shot&&['shots','light','render'].includes(stage)?stage==='light'?'look-inspection-v1':'shot-framing-v1':stage==='action'&&kind==='checkpoint'?'action-playback-v1':'inspection-v1';
export function validateActionPlayback(playback,observed,geometryOnly=false){
  assert(playback?.version==='scene-playback-v1'&&playback.scope==='SAVED_SCENE'&&
    Number.isInteger(playback.start)&&Number.isInteger(playback.end)&&playback.end>=playback.start&&playback.end-playback.start<=3600&&
    Number.isFinite(playback.fps)&&playback.fps>0&&Number.isFinite(playback.duration)&&playback.duration>=0&&
    Math.abs(playback.duration-(playback.end-playback.start)/playback.fps)<1e-4,
    'Action preview differs from its saved-scene timebase.');
  assert(observed.animations.length===(playback.static===true?0:1)&&
    (playback.static!==true||playback.clip===null&&playback.static_evidence===(geometryOnly?'NO_EVALUATED_GEOMETRY_MOTION_SOURCES':'NO_EVALUATED_MOTION_SOURCES')),
    'Action preview needs one combined animation or verified static scene evidence.');
}
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
  const shot=selectedShotPreview(scene,cp);
  return {schema:'asset-director.asset-preview/1',id:cp.id,title:scene.name+(shot?' / '+shot.name:' / saved checkpoint'),version:cp.sha256,source_kind:'checkpoint',root,...(shot?{shot_view:shot}:{}),
    files:unique.map(f=>({path:slash(path.relative(root,f.filename)),sha256:f.sha256,size:f.size})),file:slash(path.relative(root,records[0].filename)),motion:{}};
}

export class EmbeddedPreviews {
  constructor(work){this.work=work;this.owned=new Map();this.queue=Promise.resolve();this.identity=Promise.all(['./embedded-preview.mjs','./preview-cache.mjs','./viewer-gltf.mjs','./asset-preview.mjs','./world-preview-bindings.mjs','./shot-preview.mjs','../public/world-draft.mjs','../public/world-editor.mjs','../public/viewer-3d.mjs','../public/shot-view.mjs','../public/vendor/three/VENDOR.json'].map(async name=>({name,...await fileHash(fileURLToPath(new URL(name,import.meta.url)))}))).then(digest);}
  remember(item){
    const weight=Buffer.byteLength(JSON.stringify({record:item.record,source:item.source}));
    assert(weight<=MAX_PREVIEW_METADATA_BYTES,'Preview metadata exceeds the active-memory bound.',409);
    this.ownedBytes=(this.ownedBytes||0)-(this.owned.get(item.record.previewId)?.weight||0)+weight;
    this.owned.delete(item.record.previewId);this.owned.set(item.record.previewId,{...item,weight});
    // Bound active metadata, not lifetime usage. Eviction never deletes a file.
    while(this.owned.size>64||this.ownedBytes>MAX_PREVIEW_METADATA_BYTES){
      const id=this.owned.keys().next().value;this.ownedBytes-=this.owned.get(id).weight;this.owned.delete(id);
    }
  }
  protectedPreview(previewId){return [...(this.views?.values()||[])].some(v=>v.previewId===previewId)||!!this.legacy?.has(previewId);}
  forget(previewId){const item=this.owned.get(previewId);if(item){this.ownedBytes-=item.weight;this.owned.delete(previewId);}}
  release(projectId,sceneId,viewerId){
    const view=this.views?.get(viewerId);if(!view)return {released:false};
    assert(view.projectId===projectId&&view.sceneId===sceneId,'Preview view belongs to another scene.',404);
    // Release cleanup protection, not the bounded historical media descriptor.
    // Explicit cleanup or LRU eviction revokes that separate session grant.
    this.views.delete(viewerId);
    return {released:true};
  }
  exclusive(action){const pending=this.queue.then(action);this.queue=pending.catch(()=>{});return pending;}
  prepare(id,sceneId,revision,request,viewerId){
    return this.exclusive(async()=>{
      if(viewerId!==undefined){
        assert(typeof viewerId==='string'&&/^viewer_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(viewerId),'Invalid preview view identity.');
        this.views||=new Map();assert(!this.views.has(viewerId)&&this.views.size<256,'Close an existing 3D view before opening another.',409);
      }
      const record=await this.prepareOne(id,sceneId,revision,request);
      if(viewerId)this.views.set(viewerId,{previewId:record.previewId,projectId:id,sceneId});
      else {this.legacy||=new Set();this.legacy.add(record.previewId);while(this.legacy.size>64)this.legacy.delete(this.legacy.values().next().value);}
      return record;
    });
  }
  async prepareOne(id,sceneId,revision,request) {
    assert(request&&typeof request==='object'&&!Array.isArray(request),'Expected a preview source.');
    const w=this.work,source=request.kind==='checkpoint'?await checkpointSource(w,id,sceneId,revision,request):await assetPreviewSource(w,id,sceneId,revision,request);
    const project=await w.project(id,revision),profile=previewProfile(w.scene(project,sceneId).stage,source.source_kind,source.shot_view);
    source.preview_profile=profile;
    await verifiedPackage(source);
    const base=await safe(w.store.root,'SystemRuntime/UserData/ViewerPreviews');await fs.mkdir(base,{recursive:true});
    const direct=/\.(gltf|glb)$/i.test(source.file)&&!Object.keys(source.motion||{}).length;
    let converter=null;
    if(!direct){
      const native=await w.runtime.harness(['workbench-capabilities']);
      assert(/^[a-f0-9]{64}$/.test(native.implementation),'Preview requires a verified native runtime identity.',409);
      converter={implementation:native.implementation,blender:await fileHash(w.config.blender)};
    }
    const implementation=await this.identity,key=digest({project:id,scene:sceneId,source,implementation,converter}),cache=new PreviewCache(base);
    const reused=await cache.load(key,{source,projectId:id,sceneId,implementation,converter});
    if(reused){
      const observed=validateGLB(await fs.readFile(reused.filename));
      assert(digest(observed)===digest(reused.record.observed),'Cached geometry description changed.',409);
      this.remember(reused);return {...reused.record,cached:true};
    }
    // Never delete user data or historical failure evidence to make room.
    const names=await walk(base,50000);let disk=0;for(const name of names)disk+=(await fs.stat(await safe(base,name))).size;
    assertPreviewStorageBudget(disk,source.files.reduce((n,f)=>n+f.size,0));
    const previewId='view_'+randomUUID(),directory=await safe(base,previewId);await fs.mkdir(directory);
    const requestFile=path.join(directory,'request.json');await writeJson(requestFile,source);
    try {
      let model,adapter,nativeJob=null,nativeImplementation=null,texturePreview=null,referenceFrame=null,placement=null,playback=null,shotView=null;
      if(direct) {
        model=await packageGLTF(source);adapter='verified-gltf';
      } else {
        const receipt=await w.runtime.harness(['workbench-preview','--request',requestFile,'--blender',w.config.blender,'--embedded'],205000);
        assert(receipt.state==='READY'&&receipt.source_id===source.id&&receipt.source_version===source.version,'3D conversion returned a different source.',409);
        assert(/^j_[a-f0-9]{24}$/.test(receipt.job_id),'Invalid conversion job identity.');
        nativeJob=receipt.job_id;nativeImplementation=(await json(await safe(directory,`library/jobs/${nativeJob}/job.json`))).specification.implementation;
        assert(nativeImplementation===converter.implementation,'Native runtime changed during preview preparation.',409);
        assert(receipt.model&&receipt.model.size<=MAX_VIEWER_BYTES,'No bounded embedded model was produced.');
        const file=await safe(directory,receipt.model.path),actual=await fileHash(file);
        assert(actual.sha256===receipt.model.sha256&&actual.size===receipt.model.size,'Converted model changed.',409);
        model=await fs.readFile(file);adapter='isolated-blender-gltf';
        const textures=receipt.data?.embedded_viewer?.textures;
        assert(receipt.data?.embedded_viewer?.preview_profile===profile,'Preview profile differs from this activity.',409);
        referenceFrame=receipt.data.embedded_viewer.reference_frame;
        if(profile==='action-playback-v1'||shotProfiles.includes(profile)){
          playback=receipt.data.embedded_viewer.playback;
          assert(playback?.version==='scene-playback-v1'&&playback.scope==='SAVED_SCENE'&&Number.isInteger(playback.start)&&Number.isInteger(playback.end)&&playback.end>=playback.start&&playback.end-playback.start<=3600&&Number.isFinite(playback.fps)&&playback.fps>0&&Number.isFinite(playback.duration),'Missing saved-scene playback timing.');
        }
        if(shotProfiles.includes(profile)){
          shotView=receipt.data.embedded_viewer.shot_view;validateShotCamera(shotView,source.shot_view,playback);
        }
        if(source.source_kind==='checkpoint'&&profile==='world-static-v1')placement=bindWorldPreview(model,receipt.data.embedded_viewer);
        assert(textures?.scope==='PREVIEW_ONLY'&&textures.originals_changed===false&&Number.isInteger(textures.reduced_images)&&textures.reduced_images>=0&&textures.reduced_images<=128,'Missing preview texture preservation evidence.');
        texturePreview={reducedImages:textures.reduced_images,sourcePixels:textures.source_pixels,previewPixels:textures.preview_pixels,originalsChanged:false};
      }
      const observed=validateGLB(model);await verifiedPackage(source);
      if(profile==='action-playback-v1'||shotProfiles.includes(profile))validateActionPlayback(playback,observed,shotProfiles.includes(profile));
      const filename=path.join(directory,'model.glb');await fs.writeFile(filename,model,{flag:'wx'});
      const record={previewId,projectId:id,sceneId,sourceId:source.id,version:source.version,title:source.title,kind:source.source_kind,
        ...await fileHash(filename),profile,referenceFrame,placement,playback,shotView,adapter,implementation,converter,nativeJob,nativeImplementation,texturePreview,observed,cached:false,inspectionOnly:true,selectionChanged:false,approved:false};
      await writeJson(path.join(directory,'viewer.json'),record);
      await cache.publish(key,source,record);this.remember({record,filename,source});return record;
    }catch(error){await writeJson(path.join(directory,'viewer-failure.json'),{previewId,state:'FAILED',error:error.message});throw Object.assign(new Error(error.message+' 3D attempt retained: '+previewId),{status:error.status});}
  }
  bytes(projectId,sceneId,previewId) {return this.exclusive(()=>this.readBytes(projectId,sceneId,previewId));}
  async readBytes(projectId,sceneId,previewId) {
    const item=this.owned.get(previewId);
    assert(item&&item.record.projectId===projectId&&item.record.sceneId===sceneId,'3D preview is not active in this session/scene. Reopen its preview; no restart is needed.',404);
    this.remember(item);
    // Never serve an old derivative as the new saved source, or a replaced cache.
    const p=await this.work.project(projectId);this.work.scene(p,sceneId);
    await verifiedPackage(item.source);
    const actual=await fileHash(item.filename);assert(actual.sha256===item.record.sha256&&actual.size===item.record.size,'3D preview bytes changed.',409);
    return fs.readFile(item.filename);
  }
}
