import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {Store} from '../lib/projects.mjs';
import {fileHash,writeJson} from '../lib/storage.mjs';

test('missing or foreign active receipts stay visible as unavailable without dropping their IDs',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-runs-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const store=new Store(root);await store.init();let p=await store.create('Synthetic unavailable receipts');
 const missing='run_'+randomUUID(),foreign='task_'+randomUUID();
 p.workbench={schema:1,scenes:[{id:'sc_'+randomUUID(),name:'Synthetic',stage:'world',sources:[],checkpoints:[],renders:[],completed:{},run:missing,task:foreign}],film:{clips:[],cuts:[]}};
 p=await store.save(p,p.revision);
 await writeJson(path.join(p.directory,'Runs',foreign+'.json'),{id:foreign,projectId:'another-project',state:'RUNNING'});
 const result=await store.runs(p.id);assert.equal(result.length,2);
 for(const id of [missing,foreign])assert.equal(result.find(r=>r.id===id)?.state,'UNAVAILABLE');
 assert.match(result.find(r=>r.id===foreign).error,/different project/);
});

test('recent receipts are ordered by update time and retain old active writers, not random IDs',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-runs-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const store=new Store(root);await store.init();let p=await store.create('Synthetic run ordering');
 const active='run_00000000-0000-0000-0000-000000000000',newest='run_00000000-0000-0000-0000-000000000001',retained=[];
 for(let i=0;i<37;i++){
  const id=i===35?active:i===36?newest:'run_f0000000-0000-0000-0000-'+String(i).padStart(12,'0');
  const file=path.join(p.directory,'Runs',id+'.json'),date=new Date(i===35?1000:10000+i*1000);
  await writeJson(file,{id,projectId:p.id,state:i===35?'RUNNING':'SUCCEEDED',action:'synthetic'});await fs.utimes(file,date,date);retained.push({file,...await fileHash(file)});
 }
 p.workbench={schema:1,scenes:[{id:'sc_'+randomUUID(),name:'Synthetic scene',stage:'world',sources:[],checkpoints:[],renders:[],completed:{},run:active}],film:{clips:[],cuts:[]}};
 p=await store.save(p,p.revision);const manifest=await fileHash(path.join(p.directory,'project.json'));
 const rows=await store.runs(p.id);assert.equal(rows.length,30);assert.equal(rows[0].id,active);assert.equal(rows[1].id,newest);
 assert.equal(rows.filter(r=>r.id===active).length,1);assert.equal(rows.filter(r=>r.id===newest).length,1);
 for(const old of retained)assert.deepEqual(await fileHash(old.file),{sha256:old.sha256,size:old.size});
 assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),manifest);
});
