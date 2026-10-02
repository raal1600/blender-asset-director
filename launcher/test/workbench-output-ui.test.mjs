import test from 'node:test';
import assert from 'node:assert/strict';
import {outputContext,outputPreferences,outputValuesValid,outputView} from '../public/workbench-render.mjs';
import {filmViewing,filmCutPicker,staleFilmInputs,mediaIdentity} from '../public/workbench-film.mjs';
import {deviceControl} from '../public/workbench-render-device.mjs';
const esc=v=>String(v??'').replaceAll('<','&lt;').replaceAll('>','&gt;'),b=(text,action,data={},cls='',disabled=false)=>'<button data-action="'+action+'" '+Object.entries(data).map(([k,v])=>'data-'+k+'="'+v+'"').join(' ')+' '+(disabled?'disabled':'')+'>'+esc(text)+'</button>';
function fixture(){
 const shot={id:'shot',name:'Wide',revision:1,camera:'Camera',start:1,end:4},cp={id:'cp',sha256:'a'.repeat(64)},ready={blockers:[],cameras:['Camera'],frame_range:[1,4],dependencies:[],render_devices:[{backend:'OPTIX',id:'gpu1',name:'Observed GPU'}]};
 const scene={id:'scene',name:'Scene',stage:'render',current:cp.id,checkpoints:[cp],completed:{world:cp.id,action:cp.id,shots:cp.id,light:cp.id},shots:[shot],selectedShot:shot.id,renders:[],readiness:{checkpointId:cp.id,data:ready}};
 const cap={encoder:true,gpu_render:true,render_frames:true,task_workspace:true},project={id:'production',workbench:{scenes:[scene],film:{clips:[],cuts:[]}}};
 return {scene,shot,cp,ready,cap,project};
}
test('delivery drafts stay local to production/scene/shot and never implicitly change device',()=>{
 const prefs=outputPreferences(),first=prefs.get('p','s','a');first.width='1280';first.device={backend:'OPTIX',id:'gpu1'};
 assert.equal(prefs.get('p','s','a'),first);assert.equal(prefs.get('p','s','b').width,'640');assert.equal(prefs.get('q','s','a').device.backend,'CPU');
 const {shot,ready,cap}=fixture();assert.equal(outputValuesValid(first,shot,ready,cap),true);
 assert.equal(outputValuesValid(first,shot,{...ready,render_devices:[]},cap),false);
 assert.equal(first.device.backend,'OPTIX');assert.match(deviceControl({},cap,esc,first.device),/value="-1" selected/);assert.doesNotMatch(deviceControl({},cap,esc,first.device),/value="0" selected/);
});
test('delivery validation mirrors bounded dimensions, samples, shot work and observed device',()=>{
 const {shot,ready,cap}=fixture(),draft=outputPreferences().get('p','s','shot');
 assert.equal(outputValuesValid(draft,shot,ready,cap),true);
 for(const value of [{width:''},{width:'17'},{height:'1082'},{samples:'0'},{samples:'1.5'},{width:'1920',height:'1080',samples:'128'},{device:{backend:'AUTO'}},{device:{backend:'OPTIX',id:'unknown'}}])assert.equal(outputValuesValid({...draft,...value},{...shot,end:48},ready,cap),false);
 assert.equal(outputValuesValid(draft,null,ready,cap),false);assert.equal(outputValuesValid(draft,{...shot,end:361},ready,cap),false);
});
test('Render is selected-shot first; unavailable readiness and historical outputs never become current',()=>{
 const {scene,project,cap}=fixture(),draft=outputPreferences().get(project.id,scene.id,scene.selectedShot);
 const render={id:'r',checkpointId:scene.current,shotId:'shot',shotRevision:1,options:{camera:'Camera',start:1,end:4,width:64,height:64},approved:false,data:{engine:'CYCLES_CPU'}};
 scene.renders.push(render);let context=outputContext(scene);assert.equal(context.movie,render);
 let html=outputView({project,scene,stages:[],runs:[],locked:false,cap,draft,esc,b});assert.match(html,/aria-label="Rendered shot movie"/);assert.match(html,/Approve this movie/);assert.match(html,/Earlier shot outputs/);assert.doesNotMatch(html,/asset shelf|class="decision"|Keep checkpoint/);
 scene.shots[0].revision=2;context=outputContext(scene);assert.equal(context.movie,null);html=outputView({project,scene,stages:[],runs:[],locked:false,cap,draft,esc,b});assert.match(html,/Historical/);assert.match(html,/data-action="approve-render" data-id="r" disabled/);
 scene.current='new';assert.equal(outputContext(scene).ready,null);
});
test('older no-shot scenes and active/candidate render states are clear and non-authorizing',()=>{
 const {scene,project,cap}=fixture(),draft=outputPreferences().get(project.id,scene.id);
 delete scene.shots;delete scene.selectedShot;let html=outputView({project,scene,stages:[],runs:[],locked:false,cap,draft,esc,b});assert.match(html,/Name a shot in Shots/);assert.doesNotMatch(html,/data-action="render"/);
 scene.shots=[{id:'shot',name:'Wide',revision:1,camera:'Camera',start:1,end:4}];scene.selectedShot='shot';scene.candidate='candidate';html=outputView({project,scene,stages:[],runs:[],locked:false,cap,draft,esc,b});assert.match(html,/Separate candidate needs review/);assert.match(html,/data-action="render"  disabled/);
});
test('historical cut selection and playback are scoped and never replace the working arrangement',()=>{
 const {scene,project}=fixture(),work=project.workbench,view=filmViewing();
 scene.renders.push({id:'r',checkpointId:scene.current,shotId:'shot',shotRevision:1,options:{camera:'Camera',start:1,end:4},approved:true});work.film.clips=[{sceneId:scene.id,renderId:'r'}];
 const old={id:'cut_old',refs:[],approved:true},latest={id:'cut_new',refs:structuredClone(work.film.clips),approved:false};work.film.cuts=[old,latest];const original=structuredClone(work);
 assert.equal(view.selected('p',work),latest);view.select('p',work,old.id);view.remember('p',old.id,2.5);assert.equal(view.selected('p',work),old);assert.equal(view.selected('q',work),latest);assert.equal(view.time('q',old.id),0);assert.equal(view.time('p',old.id),2.5);
 assert.throws(()=>view.select('p',work,'foreign'));assert.match(filmCutPicker(work,old,esc),/historical/);assert.deepEqual(work,original);assert.equal(staleFilmInputs(work).length,0);
 scene.shots[0].revision++;assert.equal(staleFilmInputs(work).length,1);view.followLatest('p');assert.equal(view.selected('p',work),latest);assert.equal(view.time('p',old.id),2.5);
});
test('reusable media identities cannot cross project, source scene or output kind',()=>{
 const node=dataset=>({dataset}),base={projectId:'p',media:'render',id:'r',sceneId:'s'};
 const identity=mediaIdentity(node(base));for(const change of [{projectId:'q'},{media:'cut'},{id:'other'},{sceneId:'other'}])assert.notEqual(mediaIdentity(node({...base,...change})),identity);
 assert.equal(mediaIdentity(node(base)),identity);
});
