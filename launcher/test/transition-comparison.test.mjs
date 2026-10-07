import test from 'node:test';
import assert from 'node:assert/strict';
import {openComparison,reviewLabel,comparisonMarkup} from '../public/transition-comparison.mjs';

test('A/B labels distinguish current acceptance, history and unaccepted candidates',()=>{
 const scope={acceptedCheckpointId:'now',acceptedCheckpointIds:['old','now']};
 const candidates=['now','old','new'].map(id=>({id,checkpointId:id}));
 assert.deepEqual(candidates.map(c=>reviewLabel(c,scope)),['Accepted result','Previously accepted result','Unaccepted candidate']);
 const html=comparisonMarkup(candidates,candidates[2],String,scope);
 for(const label of ['Accepted result','Previously accepted result','Unaccepted candidate'])assert.match(html,new RegExp(label));
 assert.match(html,/does not accept/);
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
