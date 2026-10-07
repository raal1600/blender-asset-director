/** Synthetic boundary tests, not Blender execution or human approval. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {randomUUID} from 'node:crypto';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {validateActionRequest} from '../lib/action-layer.mjs';
import {candidateStatus,recoverTransitionJobs} from '../lib/transition-review.mjs';
import {exists,fileHash,json,writeJson} from '../lib/storage.mjs';
const uid=p=>p+randomUUID(),take='take_'+'b'.repeat(64);
const inspection={version:'action-layer-v1',sha256:'a'.repeat(64),frame_range:[1,48],fps:24,unassigned:[],
  performers:[{name:'Performer',unsupported:null,takes:[{id:take,performer:'Performer'}]},{name:'Other',unsupported:null,takes:[]},{name:'Constrained',unsupported:'Manual review',takes:[]}]};
async function fixture(t,observed=inspection){
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'action-layer-test-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
  for(const name of ['Animations','Characters','Meshes','AssetDirector'])await fs.mkdir(path.join(root,'Database',name),{recursive:true});
  const store=new Store(root);await store.init();let project=await store.create('Action test','Generated transport fixture');
  const config={library:path.join(root,'Database/AssetDirector'),blender:process.execPath};
  const jobs=new Map(),calls=[],control={fail:false,wrong:false,pause:null,implementation:'e'.repeat(64),jobImplementation:null};
  const runtime={config,applicationIdentity:async()=>({status:'VERIFIED',commit:'1'.repeat(40),scope:'SYNTHETIC_TRANSPORT_ONLY'}),harness:async args=>{
    if(args[0]==='workbench-capabilities')return {implementation:control.implementation,action_layer:'action-layer-v1',action_task:'action-task-v1',task_workspace:true,...control.capabilities};
    calls.push(args);if(args[0]==='job-prepare'){
      const job={id:'j_'+randomUUID().replaceAll('-','').slice(0,24),state:'PLANNED',outputs:[],specification:{implementation:control.jobImplementation||control.implementation,operation:args[1],options:await json(args[args.indexOf('--options')+1]),inputs:[]}};jobs.set(job.id,job);return job;
    }
    if(args[0]==='job-cancel'){control.cancelled=true;return {state:'CANCEL_REQUESTED'};}
    assert.equal(args[0],'job-run');const job=jobs.get(args[1]);if(control.pause)await control.pause;if(control.cancelled){job.state='CANCELLED';throw Error('Synthetic worker cancellation');}
    if(control.fail)throw Error('Synthetic native failure');
    const folder=path.join(config.library,'jobs',job.id);await fs.mkdir(folder,{recursive:true});
    let data=observed;
    if(job.specification.operation==='action-edit'){
      data={version:inspection.version,request:job.specification.options,reopened:!control.wrong,performance_acceptance:'NOT_EVALUATED',scene_audit:{objects:[]},action_audit:observed,...(control.validation?{transition_validation:control.validation}:{})};
      await fs.writeFile(path.join(folder,'result.blend'),'BLENDER SYNTHETIC ACTION RESULT');
      job.outputs.push({path:`jobs/${job.id}/result.blend`,...await fileHash(path.join(folder,'result.blend'))});
    }
    await writeJson(path.join(folder,'result.json'),{status:'OK',job_id:job.id,data});job.outputs.push({path:`jobs/${job.id}/result.json`,...await fileHash(path.join(folder,'result.json'))});job.state='SUCCEEDED';return job;
  }};
  const work=new Workbench(store,runtime,config),created=await work.create(project.id,project.revision,'Action scene');project=created.project;
  const scene=project.workbench.scenes[0];scene.stage='action';const source=path.join(project.directory,'Scenes/source.blend');await fs.writeFile(source,'BLENDER SYNTHETIC ACTION SOURCE');
  const cp={id:uid('cp_'),path:'Scenes/source.blend',...await fileHash(source),stage:'world',parent:null};scene.checkpoints=[cp];scene.current=cp.id;scene.completed={world:cp.id,action:cp.id,shots:cp.id};
  project=await store.save(project,project.revision);
  const base={version:inspection.version,requestId:uid('run_'),checkpointId:cp.id,sha256:cp.sha256};
  const wait=async()=>{for(let n=0;n<300;n++){if(!work.running.size)return store.get(project.id);await new Promise(r=>setTimeout(r,5));}throw Error('Fixture job did not finish');};
  const inspect=async()=>{await work.inspectAction(project.id,scene.id,project.revision,base);return wait();};
  const request={...base,requestId:uid('run_'),inspectionId:base.requestId,audit_sha256:inspection.sha256,changes:[{performer:'Performer',mode:'clip',take_id:take,start:3,speed:2}]};
  return {project,scene,cp,work,store,config,source,base,request,inspect,wait,calls,control};
}
test('Action contract refuses guessed transfers, duplicate performers and bad timing',()=>{
  const request={version:inspection.version,requestId:uid('run_'),checkpointId:uid('cp_'),sha256:'c'.repeat(64),inspectionId:uid('run_'),audit_sha256:inspection.sha256,changes:[{performer:'Performer',mode:'clip',take_id:take,start:1,speed:1}]};
  validateActionRequest(request);
  for(const c of [{mode:'retarget'},{slot:'guessed'},{speed:NaN},{speed:true},{speed:5},{start:1.5},{take_id:'Idle'}])assert.throws(()=>validateActionRequest({...request,changes:[{...request.changes[0],...c}]}));
  assert.throws(()=>validateActionRequest({...request,changes:[...request.changes,...request.changes]}));
  assert.throws(()=>validateActionRequest({...request,frame_range:[1,4000]}));
  assert.throws(()=>validateActionRequest({...request,script:'no'}));
  validateActionRequest({...request,changes:[{performer:'Performer',mode:'hold',frame:5}]});
  for(const start of ['',null,true,.1,100001])assert.throws(()=>validateActionRequest({...request,changes:[{...request.changes[0],start}]}),/Start frame must be a whole number/);
  for(const speed of ['',null,true,0,4.1,Infinity])assert.throws(()=>validateActionRequest({...request,changes:[{...request.changes[0],speed}]}),/Speed must be a number from 0.1 to 4/);
  assert.throws(()=>validateActionRequest({...request,changes:[{...request.changes[0],take_id:'unknown'}]}),/Choose an observed take for this performer/);
  validateActionRequest({...request,changes:[{...request.changes[0],start:0,speed:1.25}]});
});
test('inspection is read-only and Save keeps World completion but invalidates later layers',async t=>{
  const f=await fixture(t),before=await fileHash(f.source),p=await f.inspect();
  assert.equal(p.workbench.scenes[0].current,f.cp.id);assert.equal(p.workbench.scenes[0].checkpoints.length,1);assert.deepEqual(p.workbench.scenes[0].completed,f.scene.completed);
  const read=await json(path.join(p.directory,`Runs/${f.base.requestId}.json`));assert.deepEqual(read.inspection,inspection);
  const result=await f.work.saveAction(p.id,f.scene.id,p.revision,f.request);const saved=await f.wait(),s=saved.workbench.scenes[0];
  assert.notEqual(s.current,f.cp.id);assert.equal(s.stage,'action');assert.deepEqual(s.completed,{world:f.cp.id});assert.equal(s.checkpoints.at(-1).source,'action-edit-job');assert.equal(s.candidate,null);
  assert.deepEqual(await fileHash(f.source),before);assert.equal(await exists(path.join(p.directory,'Runs/.interactive-execution.lock')),false);
  assert.equal((await f.work.saveAction(p.id,f.scene.id,p.revision,f.request)).reused,true);assert.equal(f.calls.filter(c=>c[0]==='job-run').length,2);
  assert.equal((await json(path.join(p.directory,`Runs/${result.run.id}.json`))).resultCheckpointId,s.current);
});
test('stale inspection, foreign performer take, unsupported performer and source refusal launch no edit',async t=>{
  const f=await fixture(t),p=await f.inspect(),count=f.calls.length;
  for(const patch of [{audit_sha256:'0'.repeat(64)},{changes:[{...f.request.changes[0],performer:'Other'}]},{changes:[{performer:'Constrained',mode:'hold',frame:5}]},{changes:[{performer:'Performer',mode:'hold',frame:99}]}])await assert.rejects(f.work.saveAction(p.id,f.scene.id,p.revision,{...f.request,...patch}));
  f.work.interactions=()=>({sourceStatus:async()=>({ready:false})});await assert.rejects(f.work.saveAction(p.id,f.scene.id,p.revision,f.request),/source use/);assert.equal(f.calls.length,count);
});
test('inspection also respects manual writer ownership and wrong activity',async t=>{
  const f=await fixture(t);let p=await f.store.get(f.project.id);p.workbench.scenes[0].stage='world';p=await f.store.save(p,p.revision);
  await assert.rejects(f.work.inspectAction(p.id,f.scene.id,p.revision,f.base),/active scene task/);
  p.workbench.scenes[0].stage='action';p=await f.store.save(p,p.revision);await f.work.lock(p,'task_'+randomUUID());
  await assert.rejects(f.work.inspectAction(p.id,f.scene.id,p.revision,f.base),/unfinished/);assert.equal(f.calls.length,0);
});
test('failed or unverified native Action retains checkpoint and review history',async t=>{
  for(const reason of ['fail','wrong']){
    const f=await fixture(t),p=await f.inspect();f.control[reason]=true;await f.work.saveAction(p.id,f.scene.id,p.revision,f.request);const after=await f.wait();
    assert.equal(after.workbench.scenes[0].current,f.cp.id);assert.deepEqual(after.workbench.scenes[0].completed,f.scene.completed);
    assert.equal((await json(path.join(p.directory,`Runs/${f.request.requestId}.json`))).state,'FAILED');assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),false);
    await assert.rejects(f.work.saveAction(p.id,f.scene.id,p.revision,f.request),/failed/);
  }
});
test('inflight Action retry reuses receipt and cannot run a second writer',async t=>{
  const f=await fixture(t),p=await f.inspect();let finish;f.control.pause=new Promise(resolve=>{finish=resolve;});
  await f.work.saveAction(p.id,f.scene.id,p.revision,f.request);assert.equal((await f.work.saveAction(p.id,f.scene.id,p.revision,f.request)).reused,true);
  await assert.rejects(f.work.saveAction(p.id,f.scene.id,p.revision,{...f.request,audit_sha256:'f'.repeat(64)}),/conflicts/);
  const current=await f.store.get(p.id);await assert.rejects(f.work.saveAction(p.id,f.scene.id,current.revision,{...f.request,requestId:uid('run_')}),/active scene task/);
  finish();await f.wait();assert.equal(f.calls.filter(c=>c[0]==='job-run').length,2);
});

test('runtime upgrade refuses legacy and mismatched inspections before any Save or Blender launch',async t=>{
 const f=await fixture(t),p=await f.inspect(),filename=path.join(p.directory,`Runs/${f.base.requestId}.json`),record=await json(filename),count=f.calls.length;
 assert.equal(record.implementation,f.control.implementation);
 let launched=0;f.work.runtime.launchWorkbenchTask=async()=>{launched++;throw Error('Must not launch');};
 const context={version:'action-layer-v1',checkpointId:f.cp.id,sha256:f.cp.sha256,inspectionId:f.base.requestId,audit_sha256:inspection.sha256,performer:'Performer',frame:5};
 for(const implementation of [undefined,'f'.repeat(64)]){
  await writeJson(filename,{...record,implementation});
  await assert.rejects(f.work.saveAction(p.id,f.scene.id,p.revision,f.request),/predates this runtime/);
  await assert.rejects(f.work.openTask(p.id,f.scene.id,p.revision,{actionContext:context}),/predates this runtime/);
  assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),false);
 }
 assert.equal(launched,0);assert.equal(f.calls.length,count);assert.equal((await f.store.get(p.id)).revision,p.revision);
 await writeJson(filename,record);f.control.implementation='f'.repeat(64);
 await assert.rejects(f.work.inspectAction(p.id,f.scene.id,f.project.revision,f.base),/runtime changed/);
 assert.deepEqual(await json(filename),record,'Old receipt is not rewritten');
});

test('inspection refuses a runtime change during preparation and preserves checkpoint',async t=>{
 const f=await fixture(t);f.control.jobImplementation='f'.repeat(64);
 await assert.rejects(f.inspect(),/runtime changed before execution/);
 assert.equal(f.calls.filter(c=>c[0]==='job-run').length,0);
 assert.equal((await f.store.get(f.project.id)).workbench.scenes[0].current,f.cp.id);
 assert.equal((await json(path.join(f.project.directory,`Runs/${f.base.requestId}.json`))).state,'FAILED');
});

test('connection Save preflight requires measured compatible channels before a writer or job',async t=>{
 const second='take_'+'c'.repeat(64);
 for(const problem of ['none','old-inspection','different-channels','native-root','unobserved-channels']){
  const observed=structuredClone(inspection),p=observed.performers[0];
  p.timeline={version:'action-timeline-v1',stitch_version:'native-stitch-v1',error:null,clips:[]};
  p.takes=[take,second].map(id=>({id,performer:p.name,range:[1,25],travel_blocker:null,stitch_blocker:null,stitch_channels:'d'.repeat(64)}));
  if(problem==='old-inspection')delete p.timeline.stitch_version;
  if(problem==='different-channels')p.takes[1].stitch_channels='f'.repeat(64);
  if(problem==='native-root')p.takes[1].stitch_blocker='Native root owns travel';
  if(problem==='unobserved-channels')for(const item of p.takes)delete item.stitch_channels;
  const f=await fixture(t,observed),project=await f.inspect(),calls=f.calls.length;
  const ca={id:'clip_a',take_id:take,start:1,frames:25,speed:1,repeat_reviewed:false,travel:null};
  const cb={...ca,id:'clip_b',take_id:second,start:32,transition:{frames:6,match_phase:true}};
  const request={...f.request,frame_range:[1,80],changes:[{performer:p.name,mode:'timeline',clips:[ca,cb]}]};
  if(problem==='none'){await f.work.saveAction(project.id,f.scene.id,project.revision,request);await f.wait();assert.equal(f.calls.length,calls+2);}
  else{await assert.rejects(f.work.saveAction(project.id,f.scene.id,project.revision,request),/matching connection inspection/);assert.equal(f.calls.length,calls);assert.equal(await exists(path.join(project.directory,'Runs/.workbench-writer.lock')),false);assert.equal((await f.store.get(project.id)).revision,project.revision);}
 }
});

test('native edit preflight checks capability, source range and every heading owner before a job',async t=>{
 const second='take_'+'c'.repeat(64);
 for(const problem of ['none','old-inspection','unobserved-heading','blocked-heading','outside-range','trimmed-travel','heading-with-blend']){
  const observed=structuredClone(inspection),p=observed.performers[0];
  p.timeline={version:'action-timeline-v1',stitch_version:'native-stitch-v1',edit_version:'native-motion-edit-v1',error:null,clips:[]};
  p.takes=[take,second].map(id=>({id,performer:p.name,range:[1,25],travel_blocker:null,heading_blocker:null,stitch_blocker:null,stitch_channels:'d'.repeat(64)}));
  const ca={id:'clip_a',take_id:take,start:1,frames:25,speed:1,repeat_reviewed:false,travel:null};
  const cb={...ca,id:'clip_b',take_id:second,start:32,frames:13,source_range:[7,19],heading_deg:90,transition:{frames:6,match_phase:false,mode:'turn'}};
  if(problem==='old-inspection')delete p.timeline.edit_version;
  if(problem==='unobserved-heading')delete p.takes[0].heading_blocker;
  if(problem==='blocked-heading')p.takes[0].heading_blocker='Native rotation needs Blender';
  if(problem==='outside-range')cb.source_range=[7,31];
  if(problem==='trimmed-travel')cb.travel={delta_m:[0,1],meters_per_cycle:1};
  if(problem==='heading-with-blend')cb.transition.mode='blend';
  const f=await fixture(t,observed),project=await f.inspect(),count=f.calls.length;
  const request={...f.request,frame_range:[1,80],changes:[{performer:p.name,mode:'timeline',clips:[ca,cb]}]};
  if(problem==='none'){
   await f.work.saveAction(project.id,f.scene.id,project.revision,request);const saved=await f.wait();
   assert.notEqual(saved.workbench.scenes[0].current,f.cp.id);assert.equal(f.calls.length,count+2);
   assert.deepEqual((await json(path.join(project.directory,`Runs/${request.requestId}.json`))).state,'SUCCEEDED');
  }else{
   await assert.rejects(f.work.saveAction(project.id,f.scene.id,project.revision,request),/inspect|rotation|Trim|Trimmed|Turn and connect/i);
   assert.equal(f.calls.length,count,problem);assert.equal(await exists(path.join(project.directory,'Runs/.workbench-writer.lock')),false);
   assert.equal((await f.store.get(project.id)).revision,project.revision);
  }
 }
});

test('new motion-edit runtime requires fresh capability-bound inspection without rewriting old receipts',async t=>{
 const f=await fixture(t),project=await f.inspect(),filename=path.join(project.directory,`Runs/${f.base.requestId}.json`),before=await fileHash(filename),count=f.calls.length;
 f.control.capabilities={action_motion_edit:'native-motion-edit-v1'};
 await assert.rejects(f.work.saveAction(project.id,f.scene.id,project.revision,f.request),/predates this runtime/);
 assert.equal(f.calls.length,count);assert.deepEqual(await fileHash(filename),before);
 assert.equal((await f.store.get(project.id)).workbench.scenes[0].current,f.cp.id);
});

test('queued Action cancellation executes no native job and leaves the project unchanged',async t=>{
 const f=await fixture(t),p=await f.inspect(),before=await fileHash(path.join(p.directory,'project.json')),calls=f.calls.length;
 f.work.registerActionSave(p.id,f.scene.id,p.revision,f.request);
 await f.work.cancelActionSave(p.id,f.scene.id,f.request.requestId);
 const response=await f.work.saveAction(p.id,f.scene.id,p.revision,f.request);
 assert.equal(response.run.state,'CANCELLED');assert.equal(f.calls.length,calls);assert.deepEqual(await fileHash(path.join(p.directory,'project.json')),before);
 assert.equal(f.work.actionSaves.size,0);assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),false);
});
test('running Action cancellation stops acceptance and releases the owned lease after worker cleanup',async t=>{
 const f=await fixture(t),p=await f.inspect();let release;f.control.pause=new Promise(resolve=>release=resolve);
 await f.work.saveAction(p.id,f.scene.id,p.revision,f.request);
 await assert.rejects(f.work.cancelActionSave(p.id,'sc_'+randomUUID(),f.request.requestId),/belongs/);
 assert.equal((await f.work.cancelActionSave(p.id,f.scene.id,f.request.requestId)).state,'CANCEL_REQUESTED');
 assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),true,'Keep lease while child has not stopped');release();const after=await f.wait();
 assert.equal(after.workbench.scenes[0].current,f.cp.id);assert.equal(after.workbench.scenes[0].checkpoints.length,1);assert.deepEqual(after.workbench.scenes[0].completed,f.scene.completed);
 assert.equal((await json(path.join(p.directory,`Runs/${f.request.requestId}.json`))).state,'CANCELLED');assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),false);
 assert.equal(f.work.actionSaves.size,0);assert.deepEqual(await fileHash(f.source),{sha256:f.cp.sha256,size:f.cp.size});
});
test('Action cancellation refuses once atomic checkpoint publication has begun',async t=>{
 const f=await fixture(t),p=await f.inspect(),entry=f.work.registerActionSave(p.id,f.scene.id,p.revision,f.request);entry.committing=true;
 await assert.rejects(f.work.cancelActionSave(p.id,f.scene.id,f.request.requestId),/already publishing/);assert.equal(entry.cancelled,false);
});

test('imported checkpoint camera inspection makes its observed shot available without changing the blend',async t=>{
 const observed={version:'scene-layer-v1',layer:'shots',sha256:'c'.repeat(64),cameras:[{name:'Observed camera'}],
  scene:{objects:[{name:'Observed camera',type:'CAMERA'}],frame_range:[1,72]},look:{state:{}},visual_acceptance:'NOT_EVALUATED'};
 const f=await fixture(t,observed);let p=await f.store.get(f.project.id);p.workbench.scenes[0].stage='shots';p=await f.store.save(p,p.revision);
 const before=await fileHash(f.source),request={...f.base,version:observed.version,layer:'shots'};
 await f.work.inspectSceneLayer(p.id,f.scene.id,p.revision,request);p=await f.wait();const scene=p.workbench.scenes[0];
 assert.equal(scene.current,f.cp.id);assert.equal(scene.checkpoints.length,1);assert.deepEqual(scene.checkpoints[0].audit,observed.scene);
 assert.deepEqual(await fileHash(f.source),before);
 const saved=await f.work.saveShot(p.id,scene.id,p.revision,{name:'Actual imported camera',camera:'Observed camera',start:1,end:72});
 assert.equal(saved.workbench.scenes[0].shots[0].camera,'Observed camera');
});

async function generatedFixture(t){
 const observed=structuredClone(inspection),performer=observed.performers[0],second='take_'+'c'.repeat(64);
 performer.timeline={version:'action-timeline-v1',stitch_version:'native-stitch-v1',edit_version:'native-motion-edit-v1',error:null,clips:[],motion_bricks:{status:'CONFIGURED',profile_sha256:'d'.repeat(64)}};
 performer.takes=[take,second].map(id=>({id,performer:performer.name,range:[1,25],travel_blocker:null,heading_blocker:null,stitch_blocker:null,stitch_channels:'e'.repeat(64)}));
 const f=await fixture(t,observed);f.project=await f.inspect();
 const first={id:'clip_a',take_id:take,start:1,frames:25,speed:1,repeat_reviewed:false,travel:null};
 f.request={...f.request,frame_range:[1,70],changes:[{performer:performer.name,mode:'timeline',clips:[first,{...first,id:'clip_b',take_id:second,start:38,transition:{mode:'generated',frames:12,match_phase:false,seed:1234,profile_sha256:'d'.repeat(64)}}]}]};
 return f;
}
test('generated completion publishes immutable review, acceptance and restore keep exact prior artifacts',async t=>{
 const f=await generatedFixture(t);f.control.validation={status:'PASS',scope:'SYNTHETIC_TRANSPORT_ONLY'};
 await f.work.saveAction(f.project.id,f.scene.id,f.project.revision,f.request);
 let p=await f.wait(),s=p.workbench.scenes[0],review=s.transitionReview,candidate=review.candidates[0];
 assert.equal(s.current,f.cp.id);assert.equal(s.candidate,null);assert.equal(candidateStatus(s,candidate),'READY_FOR_REVIEW');
 assert.equal(candidate.previewSource.sha256,candidate.sha256);assert.equal(review.acceptances.length,0);
 const event={candidateId:candidate.id,eventId:uid('run_'),fingerprint:candidate.fingerprint};
 p=await f.work.acceptTransition(p.id,s.id,p.revision,event);s=p.workbench.scenes[0];
 assert.equal(s.current,candidate.checkpointId);assert.equal(s.transitionReview.acceptances.length,1);assert.equal(candidateStatus(s,candidate),'ACCEPTED');
 assert.equal((await f.work.acceptTransition(p.id,s.id,p.revision-1,event)).revision,p.revision);
 await assert.rejects(f.work.acceptTransition(p.id,s.id,p.revision,{...event,fingerprint:'f'.repeat(64)}),/conflict/);
 p=await f.work.restoreTransition(p.id,s.id,p.revision,{checkpointId:f.cp.id,eventId:uid('run_')});
 assert.equal(p.workbench.scenes[0].current,f.cp.id);
 assert.deepEqual(await fileHash(f.source),{sha256:f.cp.sha256,size:f.cp.size});
 assert.equal(p.workbench.scenes[0].transitionReview.candidates[0].sha256,candidate.sha256);
});
test('changed working request during native generation makes completion stale without replacing accepted scene',async t=>{
 const f=await generatedFixture(t);f.control.validation={status:'PASS'};let finish;f.control.pause=new Promise(resolve=>{finish=resolve;});
 await f.work.saveAction(f.project.id,f.scene.id,f.project.revision,f.request);
 let p=await f.store.get(f.project.id),request=structuredClone(f.request);request.changes[0].clips[1].transition.seed=7;
 p=await f.work.updateTransitionRequest(p.id,f.scene.id,p.revision,request);
 finish();p=await f.wait();const s=p.workbench.scenes[0],candidate=s.transitionReview.candidates[0];
 assert.equal(candidateStatus(s,candidate),'STALE');assert.equal(s.current,f.cp.id);
 await assert.rejects(f.work.acceptTransition(p.id,s.id,p.revision,{candidateId:candidate.id,eventId:uid('run_'),fingerprint:candidate.fingerprint}),/stale/);
});
test('repeated generation keeps the dependency fingerprint but creates distinct immutable native attempts',async t=>{
 const f=await generatedFixture(t);f.control.validation={status:'FAIL'};
 await f.work.saveAction(f.project.id,f.scene.id,f.project.revision,f.request);
 let p=await f.wait();const first=p.workbench.scenes[0].transitionReview.candidates[0];
 const nextRequest={...f.request,requestId:uid('run_')};
 await f.work.saveAction(p.id,f.scene.id,p.revision,nextRequest);p=await f.wait();
 const candidates=p.workbench.scenes[0].transitionReview.candidates;
 assert.equal(candidates.length,2);assert.deepEqual(candidates[0],first);
 assert.equal(candidates[1].fingerprint,first.fingerprint);
 assert.notEqual(candidates[1].nativeJobId,first.nativeJobId);
 assert.equal(first.requestedTimeline.generation_attempt,f.request.requestId);
 assert.equal(candidates[1].requestedTimeline.generation_attempt,nextRequest.requestId);
 assert.equal(p.workbench.scenes[0].current,f.cp.id);
});
test('missing or failed quality reports cannot be accepted, and corrupt artifacts are refused',async t=>{
 for(const status of [undefined,'FAIL','PASS']){
  const f=await generatedFixture(t);if(status)f.control.validation={status};
  await f.work.saveAction(f.project.id,f.scene.id,f.project.revision,f.request);const p=await f.wait(),s=p.workbench.scenes[0],c=s.transitionReview.candidates[0];
  if(status==='PASS')await fs.appendFile(path.join(p.directory,s.checkpoints.find(x=>x.id===c.checkpointId).path),'CORRUPT');
  await assert.rejects(f.work.acceptTransition(p.id,s.id,p.revision,{candidateId:c.id,eventId:uid('run_'),fingerprint:c.fingerprint}));
  assert.equal((await f.store.get(p.id)).workbench.scenes[0].current,f.cp.id);
 }
});
test('failed and cancelled generation leave accepted checkpoint and reviewable candidate history intact',async t=>{
 const f=await generatedFixture(t);f.control.validation={status:'PASS'};
 await f.work.saveAction(f.project.id,f.scene.id,f.project.revision,f.request);let p=await f.wait();const previous=structuredClone(p.workbench.scenes[0].transitionReview.candidates);
 f.control.fail=true;await f.work.saveAction(p.id,f.scene.id,p.revision,{...f.request,requestId:uid('run_')});p=await f.wait();
 assert.equal(p.workbench.scenes[0].current,f.cp.id);assert.deepEqual(p.workbench.scenes[0].transitionReview.candidates,previous);
 f.control.fail=false;let finish;f.control.pause=new Promise(resolve=>{finish=resolve;});const request={...f.request,requestId:uid('run_')};
 await f.work.saveAction(p.id,f.scene.id,p.revision,request);await f.work.cancelActionSave(p.id,f.scene.id,request.requestId);finish();p=await f.wait();
 assert.equal(p.workbench.scenes[0].current,f.cp.id);assert.deepEqual(p.workbench.scenes[0].transitionReview.candidates,previous);assert.equal(f.control.cancelled,true);
});

test('candidate acceptance refuses a changed application build even when the Python implementation is unchanged',async t=>{
 const f=await generatedFixture(t);f.control.validation={status:'PASS'};
 await f.work.saveAction(f.project.id,f.scene.id,f.project.revision,f.request);const p=await f.wait(),s=p.workbench.scenes[0],candidate=s.transitionReview.candidates[0];
 f.work.runtime.applicationIdentity=async()=>({status:'VERIFIED',commit:'2'.repeat(40),scope:'SYNTHETIC_TRANSPORT_ONLY'});
 await assert.rejects(f.work.acceptTransition(p.id,s.id,p.revision,{candidateId:candidate.id,eventId:uid('run_'),fingerprint:candidate.fingerprint}),/Application build identity/);
 assert.equal((await f.store.get(p.id)).workbench.scenes[0].current,f.cp.id);
});

test('discarding a working request preserves candidate history and accepted playback while making old work stale',async t=>{
 const f=await generatedFixture(t);f.control.validation={status:'PASS'};
 await f.work.saveAction(f.project.id,f.scene.id,f.project.revision,f.request);let p=await f.wait();
 const before=structuredClone(p.workbench.scenes[0].transitionReview.candidates);
 p=await f.work.discardTransitionRequest(p.id,f.scene.id,p.revision);const scene=p.workbench.scenes[0];
 assert.equal(scene.current,f.cp.id);assert.equal(scene.transitionReview.working,null);
 assert.deepEqual(scene.transitionReview.candidates,before);assert.equal(candidateStatus(scene,before[0]),'STALE');
});

test('restart quarantines an interrupted unpublished attempt and preserves its previous accepted scene',async t=>{
 const f=await generatedFixture(t);let p=await f.store.get(f.project.id);
 const runId=uid('run_'),file=path.join(p.directory,`Runs/${runId}.json`);
 const record={schema:1,id:runId,sceneId:f.scene.id,projectId:p.id,action:'action-edit',state:'PREPARING',publication:'TRANSITION_REVIEW_ONLY',launcherPid:2147483647};
 await f.work.lock(p,runId);p.workbench.scenes[0].run=runId;await f.store.save(p,p.revision);await writeJson(file,record);
 await recoverTransitionJobs(f.work,p.id);p=await f.store.get(p.id);
 assert.equal(p.workbench.scenes[0].current,f.cp.id);assert.equal(p.workbench.scenes[0].run,null);
 const recovered=await json(file);assert.equal(recovered.state,'INTERRUPTED');assert.equal(recovered.quarantine.state,'EXCLUDED_FROM_CANDIDATES');
 assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),false);
 assert.deepEqual(await fileHash(f.source),{sha256:f.cp.sha256,size:f.cp.size});
});

test('restart restores an already published candidate without accepting it and leaves live writers alone',async t=>{
 const f=await generatedFixture(t);f.control.validation={status:'PASS'};
 await f.work.saveAction(f.project.id,f.scene.id,f.project.revision,f.request);let p=await f.wait();
 const candidate=structuredClone(p.workbench.scenes[0].transitionReview.candidates[0]),file=path.join(p.directory,`Runs/${f.request.requestId}.json`);
 const record=await json(file);await f.work.lock(p,record.id);
 record.state='RUNNING';record.launcherPid=process.pid;await writeJson(file,record);
 p.workbench.scenes[0].run=record.id;p=await f.store.save(p,p.revision);
 await recoverTransitionJobs(f.work,p.id);assert.equal((await json(file)).state,'RUNNING');
 assert.equal(await exists(path.join(p.directory,'Runs/.workbench-writer.lock')),true);
 record.launcherPid=2147483647;await writeJson(file,record);await recoverTransitionJobs(f.work,p.id);
 p=await f.store.get(p.id);assert.equal((await json(file)).state,'SUCCEEDED');
 assert.equal(p.workbench.scenes[0].current,f.cp.id);assert.equal(p.workbench.scenes[0].run,null);
 assert.deepEqual(p.workbench.scenes[0].transitionReview.candidates,[candidate]);assert.equal(p.workbench.scenes[0].transitionReview.acceptances.length,0);
});
