// Synthetic receipt tests, not Blender/render/visual acceptance.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {Store} from '../lib/projects.mjs';
import {Workbench} from '../lib/workbench.mjs';
import {fileHash,writeJson,json} from '../lib/storage.mjs';
import {lightingPair,matchingLightingStill,lightingEvidenceView} from '../public/lighting-evidence.mjs';
const uid=p=>p+randomUUID();
async function fixture(t){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-preview-evidence-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const store=new Store(root);await store.init();let p=await store.create('Synthetic evidence','Receipt verification only');const library=path.join(root,'Database/AssetDirector');await fs.mkdir(library,{recursive:true});
 const jobs=new Map(),runtime={job:async id=>structuredClone(jobs.get(id))},work=new Workbench(store,runtime,{library});const made=await work.create(p.id,p.revision,'Test scene');p=made.project;const scene=p.workbench.scenes[0],cpId=uid('cp_'),file='Scenes/'+cpId+'.blend';await fs.writeFile(path.join(p.directory,file),'BLENDER synthetic not a real model');
 const cp={id:cpId,path:file,...await fileHash(path.join(p.directory,file)),stage:'light',parent:null};scene.checkpoints.push(cp);scene.current=cpId;scene.stage='light';const shot={id:uid('shot_'),revision:1,name:'Wide',camera:'Camera',start:1,end:9};scene.shots=[shot];scene.selectedShot=shot.id;p=await store.save(p,p.revision);
 await writeJson(path.join(p.directory,'Docs/Workbench',shot.id+'-v1.json'),{kind:'SHOT_DEFINITION',projectId:p.id,sceneId:scene.id,checkpointSha256:cp.sha256,shot});
 async function add({date='2026-09-28T10:00:00Z',frames=[1],dependencies=[]}={}){
  const id='j_'+randomUUID().replaceAll('-','').slice(0,24),directory=path.join(library,'jobs',id);await fs.mkdir(directory,{recursive:true});const basename='preview_'+String(frames[0]).padStart(4,'0')+'.png';await fs.writeFile(path.join(directory,basename),'synthetic image bytes, not a rendered frame');
  const options={camera:'Camera',frames,width:640,height:360,samples:4},data={files:[basename],artifact_kind:'PREVIEW_ARTIFACT',delivery_master:false,engine:'CYCLES_CPU',samples:4,production_settings_restored:true,preview_overrides:{resolution:[640,360],device:'CPU'},camera:'Camera',frames,scene_camera_restored:true,timeline_camera_bindings_restored:true,dependencies};
  await writeJson(path.join(directory,'result.json'),{job_id:id,status:'OK',data});
  const outputs=[];for(const name of ['result.json',basename])outputs.push({path:'jobs/'+id+'/'+name,...await fileHash(path.join(directory,name))});
  const job={id,state:'SUCCEEDED',specification:{operation:'preview',options:structuredClone(options),inputs:[{path:path.join(p.directory,file),sha256:cp.sha256,size:cp.size}]},outputs};jobs.set(id,job);
  let project=await store.get(p.id);project.jobs.push({id,operation:'preview'});await store.save(project,project.revision);
  const run={schema:1,id:uid('run_'),projectId:p.id,sceneId:scene.id,action:'preview',state:'SUCCEEDED',checkpointId:cp.id,jobId:id,options,shotId:shot.id,shotRevision:1,shotName:'Wide',startedAt:date,finishedAt:date};await writeJson(path.join(p.directory,'Runs',run.id+'.json'),run);return {run,job,data,directory};
 }
 const row=await add();return {root,store,work,p,scene,cp,shot,jobs,add,...row};
}
test('verified history is read-only, survives the old 30-run window and rechecks bytes on media access',async t=>{
 const f=await fixture(t);for(let i=0;i<35;i++)await writeJson(path.join(f.p.directory,'Runs',uid('run_')+'.json'),{projectId:f.p.id,sceneId:f.scene.id,action:'scene-layer-audit',state:'SUCCEEDED'});
 const before=await fileHash(path.join(f.p.directory,'project.json')),record=await fileHash(path.join(f.p.directory,'Runs',f.run.id+'.json'));
 let result=await f.work.previewEvidence(f.p.id,f.scene.id,{shotId:f.shot.id});assert.equal(result.items.length,1);assert.equal(result.items[0].status,'VERIFIED');assert.equal(result.items[0].current,true);assert.equal(result.items[0].humanReview,'NOT_EVALUATED');
 const media=await f.work.media(f.p.id,{sceneId:f.scene.id,kind:'preview-evidence',runId:f.run.id});assert.equal(media.evidence.image.sha256,result.items[0].image.sha256);
 assert.deepEqual(await fileHash(path.join(f.p.directory,'project.json')),before);assert.deepEqual(await fileHash(path.join(f.p.directory,'Runs',f.run.id+'.json')),record);
 await fs.appendFile(media.path,'changed');await assert.rejects(f.work.media(f.p.id,{sceneId:f.scene.id,kind:'preview-evidence',runId:f.run.id}),/image changed/);result=await f.work.previewEvidence(f.p.id,f.scene.id);assert.equal(result.items[0].status,'UNAVAILABLE');
});
test('old checkpoint and revised shot stills remain historical, never current',async t=>{
 const f=await fixture(t),p=await f.store.get(f.p.id);p.workbench.scenes[0].shots[0].revision=2;await f.store.save(p,p.revision);
 const result=await f.work.previewEvidence(f.p.id,f.scene.id);assert.equal(result.items[0].status,'VERIFIED');assert.equal(result.items[0].current,false);assert.equal(result.items[0].shot.revision,1);
 assert.equal((await f.work.media(f.p.id,{sceneId:f.scene.id,kind:'preview-evidence',runId:f.run.id})).type,'image/png');
});
test('foreign ownership, shot identity, changed options and source paths fail closed',async t=>{
 const f=await fixture(t),filename=path.join(f.p.directory,'Runs',f.run.id+'.json');
 for(const change of [{projectId:uid('prj_')},{sceneId:uid('sc_')},{state:'FAILED'},{action:'render-frames'},{shotName:'Other'},{options:{...f.run.options,frames:[2]}}]){await writeJson(filename,{...f.run,...change});await assert.rejects(f.work.media(f.p.id,{sceneId:f.scene.id,kind:'preview-evidence',runId:f.run.id}));}
 await writeJson(filename,f.run);f.job.specification.inputs[0].path=path.join(f.p.directory,'Scenes/foreign.blend');await assert.rejects(f.work.media(f.p.id,{sceneId:f.scene.id,kind:'preview-evidence',runId:f.run.id}),/checkpoint and path/);
 await assert.rejects(f.work.previewEvidence(f.p.id,f.scene.id,{shotId:uid('shot_')}),/does not belong/);await assert.rejects(f.work.previewEvidence(f.p.id,f.scene.id,{page:-1}),/bounded/);await assert.rejects(f.work.previewEvidence(f.p.id,f.scene.id,{path:'outside'}),/Unknown/);
 await assert.rejects(f.work.media(f.p.id,{sceneId:f.scene.id,kind:'preview-evidence',runId:'../other'}),/identity/);await assert.rejects(f.work.media(f.p.id,{sceneId:f.scene.id,kind:'preview-evidence',runId:f.run.id,cutId:uid('cut_')}),/Invalid historical/);
});
test('native external dependencies distinguish matching, changed and unrecorded evidence without deleting images',async t=>{
 const f=await fixture(t),dependency=path.join(f.root,'synthetic-texture.txt');await fs.writeFile(dependency,'synthetic texture');
 const row=await f.add({date:'2026-09-28T11:00:00Z',dependencies:[{path:dependency,...await fileHash(dependency)}]});
 let media=await f.work.media(f.p.id,{sceneId:f.scene.id,kind:'preview-evidence',runId:row.run.id});assert.equal(media.evidence.current,true);
 await fs.writeFile(dependency,'changed texture');media=await f.work.media(f.p.id,{sceneId:f.scene.id,kind:'preview-evidence',runId:row.run.id});assert.equal(media.evidence.dependencyStatus,'CHANGED');assert.equal(media.evidence.current,false);
 const result=await json(path.join(f.directory,'result.json'));delete result.data.dependencies;await writeJson(path.join(f.directory,'result.json'),result);Object.assign(f.job.outputs.find(o=>o.path.endsWith('/result.json')),await fileHash(path.join(f.directory,'result.json')));
 media=await f.work.media(f.p.id,{sceneId:f.scene.id,kind:'preview-evidence',runId:f.run.id});assert.equal(media.evidence.dependencyStatus,'NOT_RECORDED');assert.equal(media.evidence.current,false);
});
test('history is time-ordered and paginated, not silently truncated to newest UUIDs',async t=>{
 const f=await fixture(t);for(let i=1;i<=21;i++)await f.add({date:'2026-09-28T11:'+String(i).padStart(2,'0')+':00Z'});
 const page=await f.work.previewEvidence(f.p.id,f.scene.id,{shotId:f.shot.id});assert.equal(page.total,22);assert.equal(page.items.length,20);assert.equal(page.items[0].createdAt,'2026-09-28T11:21:00Z');assert.equal(page.hasMore,true);
 const last=await f.work.previewEvidence(f.p.id,f.scene.id,{page:1,shotId:f.shot.id});assert.equal(last.items.length,2);assert.equal(last.hasMore,false);assert.equal(last.items.at(-1).runId,f.run.id);
});
test('comparison selects matching historical frame/settings and warns when they differ',()=>{
 const current={runId:'now',status:'VERIFIED',current:true,shot:{id:'shot',name:'Wide',revision:2},camera:'Camera',frame:5,width:640,height:360,samples:4,engine:'CYCLES_CPU',image:{sha256:'a',size:1}},old={...current,current:false,runId:'old'},wrong={...old,runId:'wrong',frame:1};
 assert.equal(lightingPair([current,wrong,old],'shot').before,old);assert.equal(matchingLightingStill(current,wrong),false);assert.equal(matchingLightingStill(current,{...old,shot:{...old.shot,revision:1}}),false);
 const html=lightingEvidenceView({data:{items:[current,wrong],issues:[],revision:2,page:0,total:2,hasMore:false},scene:{shots:[{id:'shot',name:'Wide',camera:'Camera',start:1,end:9}]},shotId:'shot',esc:String,b:()=>''});assert.match(html,/Do not treat them as a controlled lighting comparison/);assert.match(html,/historical/);assert.match(html,/not an approval/);assert.match(html,/Exact evidence/);
});
