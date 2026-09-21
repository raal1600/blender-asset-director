/** One explicit, version-bound local preparation. No downloader or alternate executor. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {assert,exists,json,now,safe,writeJson,snapshot} from './storage.mjs';
import {assetPreviewSource} from './asset-preview.mjs';

async function base(work) {
  return safe(work.store.root,'SystemRuntime/UserData/LibraryPreparations');
}
export async function preparedSource(work,source) {
  const root=await base(work);
  if(!await exists(root))return null;
  assert(/^src_[a-f0-9-]{36}$/.test(source.id)&&/^[a-f0-9]{64}$/.test(source.version),'Invalid preparation source.');
  const file=await safe(root,`links/${source.id}-${source.version}.json`);
  if(!await exists(file))return null;
  const record=await json(file);
  assert(record.sourceId===source.id&&record.version===source.version&&/^a_[a-f0-9]{24}$/.test(record.assetId)&&/^[a-f0-9]{64}$/.test(record.assetVersion),'Invalid prepared source identity.',409);
  return record;
}

export async function preparedProductionSources(work,project,inventory) {
  const root=await base(work);if(!await exists(root))return [];
  const directory=await safe(root,'links');if(!await exists(directory))return [];
  const names=await fs.readdir(directory);assert(names.length<=20000,'Preparation index exceeds the bounded scan limit.');
  const current=new Map(inventory.sources.map(s=>[s.id,s.version]));
  const pins=new Map((project.workbench.catalogPins||[]).map(a=>[a.id,a.version])),ids=[];
  for(const name of names) {
    if(!/^src_[a-f0-9-]{36}-[a-f0-9]{64}\.json$/.test(name))continue;
    const record=await json(await safe(directory,name));
    if(current.get(record.sourceId)===record.version&&pins.get(record.assetId)===record.assetVersion)ids.push(record.sourceId);
  }
  return ids;
}

export async function prepareSource(work,id,sceneId,revision,request) {
  assert(request&&typeof request==='object'&&!Array.isArray(request)&&Object.keys(request).every(k=>['id','version','file','evidence','confirmed','confirmation'].includes(k)),'Unknown preparation fields.');
  assert(request.confirmed===true,'Preparation requires your explicit rights confirmation.');
  const local=request.confirmation==='local-project-use-v1';
  assert(request.confirmation===undefined||local,'Unknown preparation confirmation.');
  assert(!local||request.evidence===undefined,'A local-use confirmation must not supply invented license fields.');
  let e=request.evidence;
  if(!local){
  assert(e&&Object.keys(e).every(k=>['source_url','license_id','license_url','author'].includes(k)),'Unknown rights fields.');
  for(const key of ['source_url','license_id','license_url','author'])assert(typeof e[key]==='string'&&e[key].trim().length>0&&e[key].length<=2000&&!/[\x00-\x1f]/.test(e[key]),'Provide actual source, creator and license evidence.');
  assert(['CC0','CC0-1.0','CC-BY-4.0','CC-BY-3.0'].includes(e.license_id),'These rights require the existing specialist review.');
  for(const key of ['source_url','license_url']){let url;try{url=new URL(e[key]);}catch{}assert(url?.protocol==='https:'&&url.hostname&&!url.username&&!url.password,'Use HTTPS evidence references without credentials.');}
  }
  const p=await work.project(id,revision),s=work.scene(p,sceneId);await work.unlocked(p);
  assert(s.stage==='world'&&!s.candidate&&!s.task&&!s.run,'Finish the current task or candidate before preparing a World asset.',409);
  const source=await work.sourceDetail(id,request.id);
  assert(['Meshes','Characters'].includes(source.kind),'Animation intake and transfer use the reviewed Action specialist workflow.');
  const prior=p.assets.find(a=>a.sourceId===source.id);
  assert(!prior||prior.version===request.version,'This production pins an older source version. Resolve it explicitly first.',409);
  const input=await assetPreviewSource(work,id,sceneId,revision,{kind:'source',id:request.id,version:request.version,file:request.file});
  assert(/\.(blend|gltf|glb|fbx)$/i.test(input.file),'This package needs reviewed format conversion.');
  assert(input.files.reduce((n,f)=>n+f.size,0)<=500*1024*1024,'Prepare a package of at most 500 MiB.');
  if(local)e={source_url:'',author:'',license_id:'UNKNOWN',license_url:'',local_confirmation:{
    policy:'local-project-use-v1',confirmed:true,source_id:source.id,source_version:source.version,
    member:input.file,project_id:id,confirmed_at:now()}};
  const root=await base(work);await fs.mkdir(root,{recursive:true});
  const runId='run_'+randomUUID(),directory=await safe(root,runId);
  const record={schema:1,id:runId,projectId:id,sceneId,action:'source-prepare',state:'PREPARING',startedAt:now(),sourceId:source.id,sourceVersion:source.version,checkpointId:s.current,authorization:'explicit-launcher-user-action'};
  const runFile=await safe(p.directory,`Runs/${runId}.json`);
  await work.lock(p,runId);
  try {
    await fs.mkdir(directory);await writeJson(runFile,record);
    const evidence={...e,title:source.name,kind:'model',price:0,tags:[source.subcategory.id],attested:true};
    await writeJson(path.join(directory,'request.json'),input);
    await writeJson(path.join(directory,'evidence.json'),evidence);
    await writeJson(path.join(directory,'authorization.json'),{projectId:id,sceneId,revision,sourceId:source.id,version:source.version,member:input.file,confirmedAt:now(),transport:'launcher-ui-package-preparation',confirmation:local?'local-project-use-v1':'recorded-source-evidence',notice:local?'User confirmed rights to use and adapt this exact local asset in their productions and follow its original terms. No license/creator is inferred; future files, raw redistribution and model training are excluded. Production-scope and creative approvals remain separate.':'User-supplied source evidence; no source-use or creative approval is generated.'});
    s.run=runId;await work.store.save(p,p.revision);
    record.state='RUNNING';await writeJson(runFile,record);work.running.add(runId);
  }catch(error){record.state='FAILED';record.error=error.message;record.finishedAt=now();await writeJson(runFile,record);await work.unlock(p,runId);throw error;}
  const complete=async()=>{
    try {
      let prepared=await preparedSource(work,source),asset;
      if(prepared){
        asset=await work.catalogDetail(id,prepared.assetId,true);
        assert(asset.version===prepared.assetVersion&&asset.policy?.eligible,'Previously prepared catalog version changed or is blocked. Inspect its evidence.',409);
        assert(prepared.sourceFile===request.file,'Choose the already prepared member or prepare a separately reviewed package.',409);
        record.reused=true;
      }else{
        const result=await work.runtime.harness(['workbench-intake','--request',path.join(directory,'request.json'),'--evidence',path.join(directory,'evidence.json'),'--blender',work.config.blender],240000);
        assert(result.state==='READY'&&result.source_id===source.id&&result.source_version===source.version&&result.source_file===input.file,'Preparation returned the wrong source identity.',409);
        asset=await work.catalogDetail(id,result.asset_id,true);
        assert(asset.version===result.asset_version&&asset.policy?.eligible&&asset.models.includes(result.file),'Prepared catalog record failed verification.',409);
        prepared={sourceId:source.id,version:source.version,sourceFile:request.file,assetId:asset.id,assetVersion:asset.version,file:result.file,runId,preparedAt:now()};
      }
      assert((await snapshot(await safe(work.store.database,source.relative))).version===source.version,'Original changed during preparation. Catalog copy is retained, but scene selection is refused.',409);
      await work.serialize(async()=>{
        const q=await work.project(id),scene=work.scene(q,sceneId);
        assert(scene.run===runId&&scene.current===record.checkpointId&&!scene.candidate&&scene.stage==='world','Scene changed during preparation.',409);
        q.workbench.catalogPins||=[];scene.catalog||=[];
        const pin=q.workbench.catalogPins.find(a=>a.id===asset.id);
        assert(!pin||pin.version===asset.version,'Production already pins another catalog version.',409);
        if(!pin)q.workbench.catalogPins.push({id:asset.id,version:asset.version,title:asset.title,kind:asset.kind,provider:asset.provider,files:asset.files,subcategory:asset.subcategory,motion:asset.motion});
        if(!scene.catalog.includes(asset.id))scene.catalog.push(asset.id);
        scene.run=null;await work.store.save(q,q.revision);
        await writeJson(await safe(root,`links/${source.id}-${source.version}.json`),prepared);
      });
      record.state='SUCCEEDED';record.assetId=asset.id;record.assetVersion=asset.version;record.file=prepared.file;
      record.message='Prepared in My library and chosen for this scene. Review production source use and exact collections, then Add to world. No scene objects were imported.';
    }catch(error){record.state='FAILED';record.error=error.message;}
    finally {
      record.finishedAt=now();await writeJson(runFile,record);
      await work.serialize(async()=>{const q=await work.project(id),scene=work.scene(q,sceneId);if(scene.run===runId){scene.run=null;await work.store.save(q,q.revision);}});
      await work.unlock(p,runId);work.running.delete(runId);
    }
  };
  void complete().catch(error=>console.error('Package preparation requires recovery: '+error.message));
  return {run:record};
}
