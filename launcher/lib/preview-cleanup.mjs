/** Explicit, reviewed derivative cleanup. Never recursive deletion or receipt edits. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {assert,digest,exists,fileHash,json,safe,walk,writeJson} from './storage.mjs';
import {PreviewCache} from './preview-cache.mjs';
import {verifiedPackage,validateGLB} from './viewer-gltf.mjs';
import {previewUsers} from './preview-processes.mjs';
const viewId=/^view_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
const hash=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
async function readSmall(filename){assert((await fs.stat(filename)).size<=16*1024**2,'Cleanup metadata exceeds its bound.',409);return json(filename);}
async function exactFile(base,relative,expected){
 const filename=await safe(base,relative),parts=relative.split('/');
 for(let n=1;n<=parts.length;n++){
  const stat=await fs.lstat(path.join(base,...parts.slice(0,n)));
  assert(!stat.isSymbolicLink(),'Linked preview paths are protected.',409);
 }
 const stat=await fs.lstat(filename);
 assert(stat.isFile()&&stat.nlink===1,'Non-regular or shared preview files are protected.',409);
 if(expected)assert(stat.size===expected.size,'Preview changed after review; nothing further was removed.',409);
 const actual=await fileHash(filename);
 if(expected)assert(actual.sha256===expected.sha256,'Preview changed after review; nothing further was removed.',409);
 return {path:relative,...actual};
}
export class PreviewCleanup {
 constructor(viewers,findUsers=previewUsers){this.viewers=viewers;this.work=viewers.work;this.review=null;this.findUsers=findUsers;}
 async base(){return safe(this.work.store.root,'SystemRuntime/UserData/ViewerPreviews');}
 async candidate(base,id,key,names){
  assert(!this.viewers.protectedPreview(id),'Active preview is protected.',409);
  const directory=await safe(base,id),indexPath=`Index/${key}.json`,index=await readSmall(await safe(base,indexPath));
  const source=await readSmall(await safe(directory,'request.json')),record=await readSmall(await safe(directory,'viewer.json'));
  assert(record?.previewId===id&&hash(record.implementation),'Unknown preview identity.',409);
  await new PreviewCache(base).load(key,{source,projectId:record.projectId,sceneId:record.sceneId,implementation:record.implementation,converter:record.converter});
  await verifiedPackage(source); // Never discard a possible last good source copy.
  validateGLB(await fs.readFile(await safe(directory,'model.glb')));
  const targets=[{path:'model.glb',sha256:record.sha256,size:record.size}],kept=['request.json','viewer.json'];
  if(record.nativeJob){
   const receipt=await readSmall(await safe(directory,'receipt.json')),job=await readSmall(await safe(directory,`library/jobs/${record.nativeJob}/job.json`));
   assert(job.specification.operation==='asset-preview'&&job.specification.options.embedded===true&&job.specification.inputs.length===0&&/^a_[a-f0-9]{24}$/.test(job.specification.asset_id),'Unknown native preview operation.',409);
   const native=job.specification.source_files;
   assert(Array.isArray(native)&&native.length===source.files.length,'Preview copy inventory differs.',409);
   const identities=rows=>rows.map(f=>f.sha256+':'+f.size).sort();
   assert(digest(identities(native))===digest(identities(source.files)),'Preview source-copy identities differ.',409);
   for(const f of native){assert(/^incoming\/package\//.test(f.path),'Unknown preview copy path.',409);targets.push({...f,path:'library/'+f.path});}
   for(const [member,relative] of [[receipt.blend,'PREVIEW_COPY.blend'],[receipt.job_blend,`library/jobs/${record.nativeJob}/result.blend`],[receipt.model,`library/jobs/${record.nativeJob}/preview.glb`]]){
    assert(member?.path===relative,'Unknown derived output path.',409);targets.push({path:relative,sha256:member.sha256,size:member.size});
   }
   kept.push('receipt.json','library/catalog.sqlite',`library/manifests/${job.specification.asset_id}.json`,...['job.json','result.json','worker.log'].map(n=>`library/jobs/${record.nativeJob}/${n}`));
  }
  const allowed=[...kept,...targets.map(f=>f.path)].sort();
  assert(new Set(allowed).size===allowed.length&&digest(names)===digest(allowed),'Unknown, failed, interrupted or changed preview files are protected.',409);
  const files=[];
  for(const name of names)files.push(await exactFile(directory,name,targets.find(f=>f.path===name)));
  return {previewId:id,key,title:record.title,index:await exactFile(base,indexPath),indexRecord:index,
   files,targets:targets.map(t=>files.find(f=>f.path===t.path)),bytes:targets.reduce((n,f)=>n+f.size,0)};
 }
 async plan(){
  this.review=null;
  const base=await this.base(),names=await exists(base)?await walk(base,50000):[],groups=new Map(),indexes=new Map();let usedBytes=0;
  for(const name of names){
   const filename=await safe(base,name);usedBytes+=(await fs.stat(filename)).size;
   const [prefix,...rest]=name.split('/');if(viewId.test(prefix)){if(!groups.has(prefix))groups.set(prefix,[]);groups.get(prefix).push(rest.join('/'));}
   if(/^Index\/[a-f0-9]{64}\.json$/.test(name)){
    try{const entry=await readSmall(filename);if(viewId.test(entry.previewId)){const rows=indexes.get(entry.previewId)||[];rows.push(name.slice(6,-5));indexes.set(entry.previewId,rows);}}catch{}
   }
  }
  const eligible=[],protectedRows=[];
  for(const [id,files] of groups){
   try{
    assert(eligible.length<128,'Additional copies are reserved for another cleanup batch.',409);
    const keys=indexes.get(id)||[];assert(keys.length===1,'Unindexed or ambiguous evidence is protected.',409);
    eligible.push(await this.candidate(base,id,keys[0],files.sort()));
   }catch(error){protectedRows.push({previewId:id,reason:error.message});}
  }
  const review={id:'cleanup_'+randomUUID(),base:await exists(base)?await fs.realpath(base):base,eligible,usedBytes,protected:protectedRows};
  review.digest=digest(review);assert(Buffer.byteLength(JSON.stringify(review))<=16*1024**2,'Cleanup review exceeds its metadata bound; nothing was removed.',409);
  this.review=review;
  return {id:review.id,digest:review.digest,usedBytes,removableBytes:eligible.reduce((n,c)=>n+c.bytes,0),
   eligible:eligible.map(c=>({previewId:c.previewId,title:c.title,bytes:c.bytes,files:c.targets.map(f=>f.path)})),protected:protectedRows,
   preserved:'Originals, scene checkpoints, databases, conversion receipts and logs are retained. Active, failed and unrecognized copies are protected.'};
 }
 async apply({id,digest:identity,confirmed,closedNativePreviews}){
  const review=this.review;
  assert(review&&id===review.id&&identity===review.digest&&confirmed===true&&closedNativePreviews===true,'Review and explicitly confirm this exact cleanup first.',409);
  assert(review.eligible.length>0,'No verified disposable payloads were selected.',409);
  const base=await this.base();assert(await fs.realpath(base)===review.base,'Preview storage moved; review again.',409);
  const native=review.eligible.filter(c=>c.targets.some(f=>f.path==='PREVIEW_COPY.blend'));
  if(native.length){
    const users=await this.findUsers(native.map(c=>({previewId:c.previewId,directory:path.join(base,c.previewId)})));
    assert(users.length===0,'A reviewed preview is still open in Blender. Close only that preview and review cleanup again.',409);
  }
  // Validate the entire decision before deleting the first byte.
  for(const original of review.eligible){
    const directory=await safe(base,original.previewId),names=await walk(directory,10000);
    const current=await this.candidate(base,original.previewId,original.key,names);
    assert(digest(current)===digest(original),'Preview storage changed after review; inspect a new cleanup plan.',409);
  }
  const journal={schema:'asset-director.preview-cleanup/1',id,reviewDigest:identity,state:'RUNNING',startedAt:new Date().toISOString(),removedBytes:0,removed:[],preservedEvidence:true,review};
  const journalPath=await safe(base,`Cleanup/${id}.json`);assert(!await exists(journalPath),'This cleanup already has a journal. Inspect its result; do not repeat it.',409);
  await writeJson(journalPath,journal);this.review=null;
  const remove=async(filename,member)=>{
    // Persist intent before unlink so interruption cannot conceal the last target.
    journal.pending=member;await writeJson(journalPath,journal);
    await fs.unlink(filename);
    journal.removed.push(member);if(member.kind==='disposable-payload')journal.removedBytes+=member.size;
    delete journal.pending;await writeJson(journalPath,journal);
  };
  try{
    for(const candidate of review.eligible){
      assert(!this.viewers.protectedPreview(candidate.previewId),'Preview became active; remaining files retained.',409);
      await exactFile(base,candidate.index.path,candidate.index);
      this.viewers.forget(candidate.previewId);
      // Drop the reuse pointer first; retain its original content in the journal.
      await remove(await safe(base,candidate.index.path),{...candidate.index,kind:'cache-index'});
      const directory=await safe(base,candidate.previewId);
      for(const member of candidate.targets){
        await exactFile(directory,member.path,member);
        await remove(await safe(directory,member.path),{...member,path:candidate.previewId+'/'+member.path,kind:'disposable-payload'});
      }
    }
    journal.state='SUCCEEDED';
  }catch(error){journal.state='PARTIAL';journal.error=error.message;}
  journal.finishedAt=new Date().toISOString();await writeJson(journalPath,journal);
  return {id,state:journal.state,removedBytes:journal.removedBytes,error:journal.error,journal:`Cleanup/${id}.json`,preservedEvidence:true,
    message:journal.state==='SUCCEEDED'?'Verified preview payloads removed. Originals and conversion evidence were retained; previews can be rebuilt.':'Cleanup stopped. Remaining files and the exact removal journal were retained; inspect it before continuing.'};
 }
}
