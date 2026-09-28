/** Narrow copies only from an optional byte-bound native observation. */
import path from 'node:path';
import {assert} from './storage.mjs';
const key=filename=>process.platform==='win32'?path.resolve(filename).toLowerCase():path.resolve(filename);
export function checkpointFiles(checkpoint,records){
 const files=new Map();
 for(const record of records){
  const name=key(record.filename),prior=files.get(name);
  assert(!prior||prior.sha256===record.sha256&&prior.size===record.size,'Pinned dependency identities conflict.',409);
  files.set(name,record);
 }
 const observed=checkpoint.audit?.preview_dependencies;
 // Older/unknown observations remain compatible, without a project rewrite.
 if(observed?.version!=='preview-dependencies-v1'||observed.mode==='ALL_PINNED')return [...files.values()];
 assert(observed.mode==='EXACT_ABSOLUTE_FILES'&&Array.isArray(observed.paths)&&observed.paths.length<=4096&&
   /^[a-f0-9]{64}$/.test(observed.source_sha256),'Invalid checkpoint dependency observation.',409);
 if(observed.source_sha256!==checkpoint.sha256)return [...files.values()];
 const selected=new Set([key(records[0].filename)]);
 for(const filename of observed.paths){
  assert(typeof filename==='string'&&path.isAbsolute(filename)&&!/[\0\r\n]/.test(filename),'Invalid observed dependency path.',409);
  const name=key(filename);assert(files.has(name),'Checkpoint needs an unrecorded dependency; inspect in Blender. No source was adopted.',409);selected.add(name);
 }
 return [...files].filter(([name])=>selected.has(name)).map(([,file])=>file);
}
