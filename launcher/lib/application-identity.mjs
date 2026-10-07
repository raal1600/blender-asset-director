/** Verify a copied installation's source manifest; never infer a commit from names. */
import path from 'node:path';
import {assert,exists,fileHash,json,safe} from './storage.mjs';

export async function applicationIdentity(root){
 const filename=path.join(root,'studio-setup.json');
 if(!await exists(filename))return {status:'UNVERIFIED',commit:null,reason:'No isolated installation source receipt'};
 const receipt=await json(filename),entries=Object.entries(receipt.files||{});
 assert(receipt.status==='CREATED'&&entries.length>0&&entries.length<=4096,'Application installation receipt is incomplete.',409);
 for(const [name,sha256] of entries){
  assert(/^[a-f0-9]{64}$/.test(sha256)&&/^(SystemRuntime\/Skills\/|SystemRuntime\/Launcher\/)/.test(name),'Invalid application source manifest entry.',409);
  assert((await fileHash(await safe(root,name))).sha256===sha256,'Application source differs from its installation receipt. Rebuild an isolated candidate installation.',409);
 }
 const commit=/^[a-f0-9]{40}$/.test(receipt.source_commit||'')?receipt.source_commit:null;
 const host=path.join(root,'SystemRuntime/Launcher/Asset Director.exe');
 return {status:commit&&receipt.source_commit_verified===true?'VERIFIED':'UNVERIFIED',commit,
  source_manifest:await fileHash(filename),source_files:entries.length,
  native_host:await exists(host)?await fileHash(host):null,
  commit_evidence:receipt.source_commit_verified===true?'Clean source HEAD checked during isolated installation creation':'Installation commit label only; Git cleanliness was not recorded'};
}
