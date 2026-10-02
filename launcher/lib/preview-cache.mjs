/** Immutable preview provenance. Indexes grant reuse, never scene approval. */
import fs from 'node:fs/promises';
import {assert,digest,exists,fileHash,json,safe,writeJson} from './storage.mjs';
const schema='asset-director.viewer-cache/1';
const hash=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const view=value=>typeof value==='string'&&/^view_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(value);
async function smallJson(filename,limit=16*1024*1024){
 assert((await fs.stat(filename)).size<=limit,'Preview cache metadata exceeds its bound.',409);
 return json(filename);
}
async function verifyFile(base,member){
 assert(member&&typeof member.path==='string'&&hash(member.sha256)&&Number.isSafeInteger(member.size)&&member.size>=0&&member.size<=(member.path==='model.glb'?128:16)*1024*1024,'Invalid or oversized preview cache member.',409);
 const filename=await safe(base,member.path),stat=await fs.stat(filename);
 assert(stat.isFile()&&stat.size===member.size,'Preview cache member size changed; files were preserved.',409);
 const actual=await fileHash(filename);
 assert(actual.sha256===member.sha256&&actual.size===member.size,'Preview cache evidence changed; its files were preserved.',409);
 return filename;
}
export class PreviewCache {
 constructor(base){this.base=base;}
 async index(key){assert(hash(key),'Invalid preview cache identity.');return safe(this.base,`Index/${key}.json`);}
 async publish(key,source,record){
  assert(view(record.previewId),'Invalid preview identity.');
  const directory=await safe(this.base,record.previewId),files=[];
  for(const relative of ['request.json','viewer.json','model.glb'])files.push({path:relative,...await fileHash(await safe(directory,relative))});
  if(record.nativeJob){
   assert(/^j_[a-f0-9]{24}$/.test(record.nativeJob),'Invalid native preview identity.');
   for(const relative of ['receipt.json',`library/jobs/${record.nativeJob}/job.json`,`library/jobs/${record.nativeJob}/result.json`])files.push({path:relative,...await fileHash(await safe(directory,relative))});
  }
  await writeJson(await this.index(key),{schema,key,previewId:record.previewId,sourceDigest:digest(source),files});
 }
 async load(key,expected){
  const filename=await this.index(key);if(!await exists(filename))return null;
  const index=await smallJson(filename,16384);
  assert(index?.schema===schema&&index.key===key&&view(index.previewId)&&index.sourceDigest===digest(expected.source)&&Array.isArray(index.files),'Preview cache identity changed; files were preserved.',409);
  const directory=await safe(this.base,index.previewId),members=new Map();
  assert(index.files.length===3||index.files.length===6,'Incomplete preview provenance.',409);
  for(const member of index.files){assert(member&&typeof member.path==='string'&&!members.has(member.path),'Invalid or duplicate preview provenance.',409);members.set(member.path,await verifyFile(directory,member));}
  assert(['request.json','viewer.json','model.glb'].every(name=>members.has(name)),'Missing preview provenance.',409);
  const source=await smallJson(members.get('request.json')),record=await smallJson(members.get('viewer.json'));
  assert(record&&typeof record==='object'&&!Array.isArray(record)&&Object.hasOwn(record,'converter'),'Invalid preview record.',409);
  assert(digest(source)===index.sourceDigest&&record.previewId===index.previewId&&record.projectId===expected.projectId&&record.sceneId===expected.sceneId&&record.implementation===expected.implementation&&digest(record.converter)===digest(expected.converter),'Preview cache scope/runtime differs.',409);
  assert(record.sourceId===source.id&&record.version===source.version&&record.kind===source.source_kind&&record.profile===source.preview_profile&&record.inspectionOnly===true&&record.selectionChanged===false&&record.approved===false,'Preview provenance is not an inspection-only derivative.',409);
  const model=index.files.find(f=>f.path==='model.glb');
  assert(record.sha256===model.sha256&&record.size===model.size,'Preview model identity differs.',409);
  if(expected.converter){
   assert(record.adapter==='isolated-blender-gltf'&&/^j_[a-f0-9]{24}$/.test(record.nativeJob)&&record.nativeImplementation===expected.converter.implementation,'Native converter identity differs.',409);
   const jobName=`library/jobs/${record.nativeJob}/job.json`,resultName=`library/jobs/${record.nativeJob}/result.json`;
   assert(['receipt.json',jobName,resultName].every(name=>members.has(name)),'Native provenance is missing.',409);
   const receipt=await smallJson(members.get('receipt.json')),job=await smallJson(members.get(jobName)),result=await smallJson(members.get(resultName));
   assert(receipt.state==='READY'&&receipt.job_id===record.nativeJob&&receipt.source_id===source.id&&receipt.source_version===source.version&&job.id===record.nativeJob&&job.state==='SUCCEEDED'&&job.specification?.implementation===record.nativeImplementation&&result.status==='OK'&&result.job_id===record.nativeJob,'Native preview evidence does not prove successful conversion.',409);
   assert(receipt.model?.sha256===record.sha256&&receipt.model?.size===record.size&&job.outputs?.some(f=>f.path===`jobs/${record.nativeJob}/preview.glb`&&f.sha256===record.sha256&&f.size===record.size),'Native model evidence differs from the cached geometry.',409);
  }else assert(record.adapter==='verified-gltf'&&!record.nativeJob&&index.files.length===3,'Direct glTF provenance differs.',409);
  return {record,source,filename:members.get('model.glb')};
 }
}
