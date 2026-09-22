import test from 'node:test';
import assert from 'node:assert/strict';
import {addCatalogFlow,worldAddQueue} from '../public/world-add-flow.mjs';
const intent={id:'asset',version:'v1',file:'model.blend'};
function setup({ready=true,collectionNames=['Observed'],permit=true}={}){
 const calls=[],state={scene:{catalog:[],assetContents:{}},sourceUse:{ready}};
 const deps={check:()=>{},read:async()=>structuredClone(state),asset:async()=>({version:'v1',models:['model.blend'],policy:{eligible:true}}),
 command:async(name,args)=>{calls.push({name,args});if(name==='catalog-select')state.scene.catalog=['asset'];if(args.request?.operation==='asset-contents')state.scene.assetContents.asset={version:'v1',file:'model.blend',collections:collectionNames};return {run:{id:'run'}};},
 wait:async()=>{calls.push({name:'wait'});},permission:async()=>{calls.push({name:'permission'});state.sourceUse.ready=permit;return permit;},collections:async names=>{calls.push({name:'collections'});return names;}};
 return {calls,state,deps};
}
test('one add inspects a single collection and imports without another human confirmation',async()=>{
 const f=setup();assert.equal(await addCatalogFlow(intent,f.deps),'added');
 assert.deepEqual(f.calls.map(c=>c.name),['catalog-select','catalog-job','wait','catalog-job','wait']);
 assert.deepEqual(f.calls.at(-2).args.request.selection,['Observed']);assert.equal(f.calls.at(-2).args.request.confirmed,true);
});
test('missing permission continues the same add only after an actual answer; decline runs no dependent job',async()=>{
 for(const permit of [false,true]){const f=setup({ready:false,permit});assert.equal(await addCatalogFlow(intent,f.deps),permit?'added':'cancelled');assert.equal(f.calls.filter(c=>c.name==='permission').length,1);assert.equal(f.calls.filter(c=>c.name==='catalog-job').length,permit?2:0);}
});
test('multiple observed collections require a choice, while missing/changed evidence refuses import',async()=>{
 const f=setup({collectionNames:['One','Two']});await addCatalogFlow(intent,f.deps);assert.equal(f.calls.filter(c=>c.name==='collections').length,1);
 const empty=setup({collectionNames:[]});await assert.rejects(addCatalogFlow(intent,empty.deps),/No verified/);assert.equal(empty.calls.filter(c=>c.args?.request?.operation==='import').length,0);
 const stale=setup();await assert.rejects(addCatalogFlow({...intent,version:'old'},stale.deps),/Asset changed/);assert.deepEqual(stale.calls,[]);
});
test('context loss after inspection prevents the queued import',async()=>{
 const f=setup();let valid=true;f.deps.check=()=>{if(!valid)throw Error('stale context');};f.deps.wait=async()=>{valid=false;};
 await assert.rejects(addCatalogFlow(intent,f.deps),/stale context/);assert.equal(f.calls.filter(c=>c.args?.request?.operation==='import').length,0);
});
const tick=()=>new Promise(r=>setTimeout(r,0));
test('queue serializes explicit intents, rejects duplicate clicks and never survives a context switch',async()=>{
 let current={projectId:'p',sceneId:'s'},release;const calls=[],errors=[];
 const q=worldAddQueue({context:()=>current,run:async(item,check)=>{calls.push(item.id);await new Promise(r=>release=r);check();},failed:e=>errors.push(e.message)});
 assert.equal(q.add({id:'one'}),true);assert.equal(q.add({id:'one'}),false);q.add({id:'two'});assert.deepEqual(calls,['one']);
 current={projectId:'other',sceneId:'s'};release();await tick();assert.equal(q.state().count,0);assert.deepEqual(calls,['one']);assert.match(errors[0],/Scene changed/);
});
test('a declined queued addition cancels dependents instead of silently proceeding',async()=>{
 let release;const calls=[];const q=worldAddQueue({context:()=>({projectId:'p',sceneId:'s'}),run:async item=>{calls.push(item.id);await new Promise(r=>release=r);return 'cancelled';}});
 q.add({id:'one'});q.add({id:'two'});release();await tick();assert.equal(q.state().count,0);assert.deepEqual(calls,['one']);
});
