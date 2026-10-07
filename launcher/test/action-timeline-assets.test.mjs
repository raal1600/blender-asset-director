import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createApp} from '../server.mjs';
test('timeline module graph is explicitly served with script MIME and original CSP',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'timeline-assets-'));let app;
 t.after(async()=>{if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await fs.rm(root,{recursive:true,force:true});});
 app=await createApp({root,config:{library:path.join(root,'Database/AssetDirector')},runtime:{harness:async()=>{throw Error('Static module test must not run Blender');}},port:0});
 for(const name of ['action-timeline-contract','action-timeline-draft','action-timeline-view','action-path-editor','action-selection','action-rotation-editor','action-turn-preview']){const r=await fetch(app.origin+'/'+name+'.mjs');assert.equal(r.status,200);assert.match(r.headers.get('content-type'),/javascript/);assert.doesNotMatch(r.headers.get('content-security-policy'),/unsafe-inline/);assert((await r.text()).length>100);}
 // A missing transitive import prevents the entire native WebView from booting.
 // Walk the actual application imports, rather than maintaining a second list.
 const pending=['/workbench.mjs'],visited=new Set();
 while(pending.length){
  const name=pending.pop();if(visited.has(name))continue;visited.add(name);
  const r=await fetch(app.origin+name);assert.equal(r.status,200,`Unserved client module: ${name}`);
  assert.match(r.headers.get('content-type'),/javascript/);
  const source=await r.text();
  for(const match of source.matchAll(/(?:\bfrom\s*|\bimport\s*)['"]([^'"]+)['"]/g)){
   if(match[1].startsWith('.'))pending.push(new URL(match[1],app.origin+name).pathname);
  }
 }
 assert(visited.has('/performer-framing.mjs'),'Preview camera helper must be reachable in the served graph');
});
