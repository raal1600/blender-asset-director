import test from 'node:test';
import assert from 'node:assert/strict';
import {imageLoader} from '../public/workbench-images.mjs';

test('thumbnail redraws share requests and cache both image and absent-image results',async()=>{
  let calls=0;const loader=imageLoader({fetchImage:async url=>{calls++;return url==='none'?null:new Blob(['image']);}});
  const a=loader.load('project/version/a','image'),b=loader.load('project/version/a','image');
  assert.equal(a,b);assert.equal((await a).size,5);await loader.load('project/version/a','image');
  await loader.load('project/version/b','none');await loader.load('project/version/b','none');assert.equal(calls,2);
  await loader.load('project/new-version/a','image');assert.equal(calls,3);
  loader.clear();await loader.load('project/version/a','image');assert.equal(calls,4);
});
test('thumbnail concurrency is bounded and disconnected queued images do not execute',async()=>{
  let active=0,peak=0,calls=0;const releases=[];
  const loader=imageLoader({limit:2,fetchImage:async()=>{calls++;active++;peak=Math.max(peak,active);await new Promise(r=>releases.push(r));active--;return new Blob(['x']);}});
  const first=loader.load('a','a'),second=loader.load('b','b'),skip=loader.load('c','c',()=>false);
  await new Promise(r=>setImmediate(r));assert.equal(calls,2);releases.splice(0).forEach(r=>r());
  await Promise.all([first,second,skip]);assert.equal(peak,2);assert.equal(calls,2);
});
test('thumbnail failures retry and refresh cannot cache an older in-flight response',async()=>{
  let calls=0,release;const loader=imageLoader({fetchImage:async()=>{calls++;if(calls===1)throw Error('source changed');if(calls===2)await new Promise(r=>release=r);return new Blob(['x']);}});
  await assert.rejects(loader.load('a','a'),/source changed/);await new Promise(r=>setImmediate(r));
  const old=loader.load('a','a');await new Promise(r=>setImmediate(r));loader.clear();release();await old;
  await loader.load('a','a');assert.equal(calls,3);
});
test('thumbnail memory is bounded and eviction never caches scene evidence',async()=>{
  let calls=0;const loader=imageLoader({maxEntries:2,maxBytes:3,fetchImage:async()=>{calls++;return new Blob(['xx']);}});
  await loader.load('a','a');await loader.load('b','b');await loader.load('a','a');assert.equal(calls,3);
});

test('a redraw keeps a queued request wanted by its new connected image',async()=>{
  let release,calls=0;
  const loader=imageLoader({limit:1,fetchImage:async()=>{calls++;if(calls===1)await new Promise(r=>release=r);return new Blob(['x']);}});
  const first=loader.load('a','a'),old=loader.load('b','b',()=>false),current=loader.load('b','b',()=>true);
  assert.equal(old,current);await new Promise(r=>setImmediate(r));release();await first;
  assert.equal((await current).size,1);assert.equal(calls,2);
});
