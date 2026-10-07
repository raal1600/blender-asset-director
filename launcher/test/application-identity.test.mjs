import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {applicationIdentity} from '../lib/application-identity.mjs';
import {fileHash,writeJson} from '../lib/storage.mjs';

test('application provenance requires checked source history and refuses changed installed bytes',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'application-identity-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 assert.equal((await applicationIdentity(root)).status,'UNVERIFIED');
 const name='SystemRuntime/Launcher/synthetic-source.mjs',file=path.join(root,name);await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file,'synthetic source');
 const manifest={status:'CREATED',source_commit:'a'.repeat(40),source_commit_verified:false,files:{[name]:(await fileHash(file)).sha256}};
 await writeJson(path.join(root,'studio-setup.json'),manifest);assert.equal((await applicationIdentity(root)).status,'UNVERIFIED','A label is not proof of a clean source commit');
 manifest.source_commit_verified=true;await writeJson(path.join(root,'studio-setup.json'),manifest);
 const identity=await applicationIdentity(root);assert.equal(identity.status,'VERIFIED');assert.equal(identity.commit,manifest.source_commit);assert.equal(identity.source_files,1);
 await fs.appendFile(file,' changed');await assert.rejects(applicationIdentity(root),/differs from its installation receipt/);
});
