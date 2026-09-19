/** Synthetic envelopes, not claims that arbitrary compressed bytes are valid scenes. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {blendEnvelope,assertBlendEnvelope} from '../lib/workbench-files.mjs';

test('recognizes raw, gzip and Zstandard scene envelopes without decompressing or executing',()=>{
  assert.equal(blendEnvelope(Buffer.from('BLENDER-v405')), 'blend');
  assert.equal(blendEnvelope(Buffer.from('BLENDER17-01v0502')), 'blend');
  assert.equal(blendEnvelope(Buffer.from([0x28,0xb5,0x2f,0xfd,0])), 'zstd');
  assert.equal(blendEnvelope(Buffer.from([0x1f,0x8b,8,0])), 'gzip');
});
test('rejects missing, truncated, ZIP and non-scene envelopes',()=>{
  for(const value of [Buffer.alloc(0),Buffer.from('BLENDER'),Buffer.from('PK\x03\x04'),Buffer.from('{"scene":true}'),Buffer.from([0x1f,0x8b,0])])
    assert.equal(blendEnvelope(value),null);
});
test('envelope probe preserves bytes and closes its file handle',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'workbench-envelope-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
  const filename=path.join(root,'synthetic.blend'),bytes=Buffer.from([0x28,0xb5,0x2f,0xfd,0]);
  await fs.writeFile(filename,bytes);assert.equal(await assertBlendEnvelope(filename),'zstd');
  assert.deepEqual(await fs.readFile(filename),bytes);await fs.rename(filename,path.join(root,'renamed.blend'));
});
