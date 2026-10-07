import test from 'node:test';
import assert from 'node:assert/strict';
import {openComparison,reviewLabel,comparisonMarkup,comparisonStitches} from '../public/transition-comparison.mjs';

test('A/B labels distinguish current acceptance, history and unaccepted candidates',()=>{
 const scope={acceptedCheckpointId:'now',acceptedCheckpointIds:['old','now']};
 const candidates=['now','old','new'].map(id=>({id,checkpointId:id}));
 assert.deepEqual(candidates.map(c=>reviewLabel(c,scope)),['Accepted result','Previously accepted result','Unaccepted candidate']);
 const html=comparisonMarkup(candidates,candidates[2],String,scope);
 for(const label of ['Accepted result','Previously accepted result','Unaccepted candidate'])assert.match(html,new RegExp(label));
 assert.match(html,/does not accept/);
});

test('selected later stitch aligns in physical seconds and absent joins cannot play a misleading comparison',async()=>{
 const join=(clip,start,end)=>({provider:'motion-bricks.cpp',performer:'Rig',clip_id:clip,start,end});
 const candidates=[{id:'a',checkpointId:'cp_a',sha256:'a'.repeat(64),transitions:[join('first',20,44),join('later',80,104)]},
  {id:'b',checkpointId:'cp_b',sha256:'b'.repeat(64),transitions:[join('first',30,54),join('later',100,148)]}];
 const scope={selectedTransition:{performer:'Rig',clipId:'later'}},nodes=new Map(),events=new Map(),seeks=[];
 const node=key=>{if(!nodes.has(key))nodes.set(key,{dataset:{},value:key.includes('choice="a"')?'a':key.includes('choice="b"')?'b':'0'});return nodes.get(key);};
 const host={querySelector:node,addEventListener:(k,v)=>events.set(k,v),removeEventListener:k=>events.delete(k)};
 const previous=globalThis.cancelAnimationFrame;globalThis.cancelAnimationFrame=()=>{};
 const view=openComparison(host,candidates,(_,source)=>({ready:Promise.resolve({playback:{fps:24}}),seekFrameExact:f=>seeks.push([source.id,f]),dispose(){}}),scope);
 try{
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(comparisonStitches(candidates).length,2);assert.equal(node('[data-compare-time]').max,'2.5');
  assert.equal(node('[data-compare-join]').value,JSON.stringify(['Rig','later']));
  events.get('input')({target:Object.assign(node('[data-compare-time]'),{value:'0.5'})});
  assert.deepEqual(seeks.slice(-2),[['cp_a',92],['cp_b',112]]);
  assert.equal(node('[data-compare-play]').disabled,false);
  candidates[0].transitions.pop();node('[data-compare-choice="a"]').dataset.compareChoice='a';
  events.get('change')({target:node('[data-compare-choice="a"]')});await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(node('[data-compare-play]').disabled,true);
  assert.match(node('[data-compare-identity="a"]').textContent,/absent/);
  const selected=node('[data-compare-join]');selected.value=JSON.stringify(['Rig','first']);events.get('change')({target:selected});
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(node('[data-compare-play]').disabled,false);assert.deepEqual(seeks.slice(-2),[['cp_a',20],['cp_b',30]]);
 }finally{view.dispose();globalThis.cancelAnimationFrame=previous;}
});

test('sequential preview preparation aligns both baked sources without requiring the second record early',async()=>{
 const candidates=[{id:'a',checkpointId:'cp_a',sha256:'a'.repeat(64),transitions:[{provider:'motion-bricks.cpp',start:20,end:44}]},{id:'b',checkpointId:'cp_b',sha256:'b'.repeat(64),transitions:[{provider:'motion-bricks.cpp',start:30,end:78}]}];
 const nodes=new Map(),events=new Map(),seeks=[],started=[];
 const node=key=>{if(!nodes.has(key))nodes.set(key,{value:key.includes('choice="a"')?'a':key.includes('choice="b"')?'b':'0'});return nodes.get(key);};
 const host={querySelector:node,addEventListener:(k,v)=>events.set(k,v),removeEventListener:k=>events.delete(k)};
 const old=globalThis.cancelAnimationFrame;globalThis.cancelAnimationFrame=()=>{};
 const view=openComparison(host,candidates,(_,source)=>{started.push(source.id);return {ready:Promise.resolve({playback:{fps:24}}),seekFrameExact:f=>seeks.push([source.id,f]),dispose(){}};});
 await new Promise(resolve=>setTimeout(resolve,0));
 assert.deepEqual(started,['cp_a','cp_b']);assert.equal(node('[data-compare-time]').max,'2.5');
 events.get('input')({target:Object.assign(node('[data-compare-time]'),{value:'0.5'})});
 assert.deepEqual(seeks.slice(-2),[['cp_a',32],['cp_b',42]]);
 view.dispose();globalThis.cancelAnimationFrame=old;
});
