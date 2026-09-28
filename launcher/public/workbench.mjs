import {diagnosticsView,trashView,productionRow,archiveTarget,archiveConfirmation} from './workbench-studio.mjs';
import {previewStorageView,storageConfirmation} from './workbench-preview-storage.mjs';
import {worldView,addWorldAsset} from './workbench-world.mjs';
import {preparationInspection,preparationDialog as worldPreparationDialog,preparationSelection} from './workbench-world-prepare.mjs';
import {worldAddQueue,addCatalogFlow} from './world-add-flow.mjs';
import {openViewer} from './viewer-3d.mjs';
import {worldActionNeedsSave} from './world-draft.mjs';
import {actionView,actionDraft,actionInspection,ensureActionInspection} from './workbench-action.mjs';
import {sceneLayerView,sceneLayerDraft,layerInspection,ensureLayerInspection,cameraForm} from './workbench-scene-layer.mjs';
import {lightingEvidenceView} from './lighting-evidence.mjs';
import {outputView,outputContext,outputPreferences,outputValuesValid} from './workbench-render.mjs';
import {filmViewing,filmCutPicker,staleFilmInputs,mediaIdentity} from './workbench-film.mjs';
import {evidenceView} from './workbench-evidence.mjs';
import {imageLoader} from './workbench-images.mjs';
import {taskBanner,observationKey} from './workbench-task.mjs';
import {catalogDialog} from './workbench-library.mjs';
import {preparationDialog} from './library-preparation.mjs';
import {assetBrowser,ingredientsView,sourceDialog} from './workbench-browser.mjs';
import {shotFor,renderIsCurrent,previewIsCurrent,cutIsCurrent} from './workbench-lineage.mjs';
import {shotPanel,shotEditor,viewerTaskFrame} from './workbench-shots.mjs';
import {progressLabel,progressKey,statusPoller} from './workbench-progress.mjs';
import {deviceControl,selectedDevice,deviceLabel,outputDevice} from './workbench-render-device.mjs';
// A real authenticated client. Only navigation is kept in sessionStorage;
// scene state, approvals, media and jobs always come from the local server.
const $=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let token=location.hash.slice(1)||sessionStorage.getItem('ad-token');
if(token){sessionStorage.setItem('ad-token',token);history.replaceState(null,'',location.pathname);}
let overview=null,state=null,cap=null,projectId=sessionStorage.getItem('wb-project'),sceneId=sessionStorage.getItem('wb-scene'),tab='scenes',target=null,busy=false,blobs=[];
let returnToFilm=false;
const filmView=filmViewing();
function rememberFilmPosition(){for(const node of document.querySelectorAll('#app video[data-media="cut"]'))if(node.readyState>=1)filmView.remember(node.dataset.projectId,node.dataset.id,node.currentTime);}
let assetViewer=null,sceneViewer=null,sceneViewerKey=null;
let draftDestination=null,worldSave=null,actionSave=null;
const actionDrafts=new Map();
const actionInspectionAttempts=new Set();
const layerDrafts=new Map(),layerInspectionAttempts=new Set(),layerSelections=new Map();
let layerSave=null;
let pendingPreparation=null;
function showWorldPreparation(run){
 if(s()?.stage!=='world'||s().candidate||run!==preparationInspection(state.runs,s(),cp()))throw Error('Placement check changed. Refresh and inspect the saved scene again.');
 const view=worldPreparationDialog({project:p(),run,esc,b});
 modal('Enable asset placement',view.body,view.buttons,'Back to World');$('dialog').classList.add('world-preparation-dialog');
}
function scheduleWorldPreparation(){
 setTimeout(()=>{
  const pending=pendingPreparation;if(!pending||busy||$('dialog').open||browser.isOpen)return;
  if(projectId!==pending.projectId||sceneId!==pending.sceneId||tab!=='scenes'||s()?.stage!=='world'||cp()?.id!==pending.checkpointId||cp()?.sha256!==pending.sha256){pendingPreparation=null;return;}
  const run=state.runs.find(r=>r.id===pending.requestId);
  if(state.locked||!run||['PREPARING','RUNNING'].includes(run.state))return;
  pendingPreparation=null;
  if(run.state==='SUCCEEDED'){try{showWorldPreparation(run);}catch(error){notice(error.message);}}
  else notice(run.error||'Placement check did not finish. Inspect its retained attempt; your scene is unchanged.');
 },0);
}
const outputDrafts=outputPreferences();
function currentOutputDraft(){return s()?.stage==='render'?outputDrafts.get(projectId,sceneId,s().selectedShot):null;}
function syncOutputUI(){const draft=currentOutputDraft(),button=document.querySelector('.output-workspace [data-action="render"]');if(!draft||!button)return;const context=outputContext(s(),state.runs,state.locked);button.disabled=busy||context.active||!!s().candidate||!cap?.encoder||!context.ready||!!context.ready.blockers.length||!outputValuesValid(draft,context.shot,context.ready,cap);}
function editOutputSetting(node){const draft=currentOutputDraft();if(!draft)return;const key=node.dataset.renderSetting;if(key==='device'){try{draft.device=selectedDevice(s().readiness?.data,cap,node.value);notice('');}catch(error){draft.device={backend:'UNAVAILABLE'};notice(error.message);}}else if(['width','height','samples'].includes(key))draft[key]=node.value;syncOutputUI();}
let lightingBlobs=[];
function clearLightingMedia(){for(const url of lightingBlobs)URL.revokeObjectURL(url);lightingBlobs=[];}
async function showLightingEvidence(d){
 const context={projectId,sceneId},shotId=d.shot||s().selectedShot||s().shots?.[0]?.id;
 if(!shotId)throw Error('Name a shot in Shots before reviewing its lighting.');
 const data=await api('workbench/preview-evidence?'+new URLSearchParams({...context,shotId,page:d.page||0}));
 if(projectId!==context.projectId||sceneId!==context.sceneId||data.revision!==p().revision)throw Error('Scene changed while inspecting stills. Refresh and open the comparison again.');
 modal('Review shared lighting',lightingEvidenceView({data,scene:s(),shotId,beforeId:d.before,esc,b}),b('Open this shot in the scene','lighting-open-shot',{id:shotId},'primary'),'Back to Light');
 $('dialog').classList.add('lighting-evidence-dialog');$('dialog').dataset.evidencePage=String(data.page);
 for(const node of $('dialog').querySelectorAll('[data-lighting-run]')){
  const entry=data.items.find(x=>x.runId===node.dataset.lightingRun);
  void (async()=>{try{
   const response=await fetch('/api/workbench/media?'+new URLSearchParams({...context,kind:'preview-evidence',runId:entry.runId}),{headers:requestHeaders()});
   if(!response.ok)throw Error((await response.json()).error);const bytes=await response.arrayBuffer();
   if(bytes.byteLength!==entry.image.size)throw Error('Rendered still size changed; not displayed.');
   const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('');if(hash!==entry.image.sha256)throw Error('Rendered still hash changed; not displayed.');
   if(!node.isConnected||!$('dialog').open)return;const url=URL.createObjectURL(new Blob([bytes],{type:'image/png'}));lightingBlobs.push(url);node.src=url;
  }catch(error){if(node.isConnected){node.hidden=true;node.insertAdjacentHTML('afterend','<p class="note warn">'+esc(error.message)+'</p>');}}})();
 }
}
const layerKey=()=>projectId+':'+sceneId;
function currentLayerDraft(){
 if(!state||!projectId||!sceneId)return null;const old=layerDrafts.get(layerKey()),checkpoint=cp();
 if(old&&(old.dirty||old.layer===s()?.stage&&old.checkpointId===checkpoint?.id&&old.sha256===checkpoint?.sha256))return old;
 if(!['shots','light'].includes(s()?.stage)||!checkpoint)return null;
 const run=layerInspection(state.runs,s(),checkpoint);if(!run)return null;
 const draft=sceneLayerDraft(checkpoint,run),selection=layerSelections.get(layerKey());
 if(selection&&draft.audit.look.state.lights.some(l=>l.name===selection))draft.select(selection);
 layerDrafts.set(layerKey(),draft);return draft;
}
function scheduleLayerInspection(){
 setTimeout(()=>{
  if(busy||tab!=='scenes'||!['shots','light'].includes(s()?.stage)||!cp()||state.locked||cap?.scene_layer!=='scene-layer-v1'||currentLayerDraft())return;
  const chosen={projectId,sceneId,checkpointId:cp().id,sha256:cp().sha256,layer:s().stage},key=JSON.stringify(chosen);
  if(layerInspectionAttempts.has(key))return;layerInspectionAttempts.add(key);
  perform(async()=>{await ensureLayerInspection({...chosen,read:()=>api('workbench/state?'+new URLSearchParams({projectId:chosen.projectId,compact:true})),create:revision=>api('workbench/scene-layer-inspect',{projectId:chosen.projectId,sceneId:chosen.sceneId,revision,request:{version:'scene-layer-v1',layer:chosen.layer,requestId:'run_'+crypto.randomUUID(),checkpointId:chosen.checkpointId,sha256:chosen.sha256}})});await load();});
 },0);
}
function reconcileLayerSave(){
 if(!layerSave)return;const run=state.runs.find(r=>r.id===layerSave.body.request.requestId);
 if(run?.state==='SUCCEEDED'){if(!s().checkpoints.some(c=>c.id===run.resultCheckpointId))throw Error('Layer Save receipt has no matching checkpoint.');layerSave.draft.discard();layerDrafts.delete(layerKey());layerSave=null;}
 else if(run&&['FAILED','INTERRUPTED'].includes(run.state)){layerSave=null;notice(run.error||'Save failed. Your draft and previous scene are preserved.');}
}
async function saveLayerDraft(){
 if(document.querySelector('[data-layer-field]:invalid'))throw Error('Correct the highlighted lighting value before saving.');
 const draft=currentLayerDraft();if(!draft?.dirty)return;
 if(draft.checkpointId!==cp()?.id||draft.sha256!==cp()?.sha256||draft.layer!==s()?.stage)throw Error('Camera/light draft is stale. Discard and reload before saving.');
 if(!layerSave)layerSave={draft,body:{projectId,sceneId,revision:p().revision,request:draft.request('run_'+crypto.randomUUID())}};
 const attempt=layerSave;render();
 try{await api('workbench/scene-layer-save',attempt.body);}catch(error){await load();if(!state.runs.some(r=>r.id===attempt.body.request.requestId)){layerSave=null;throw error;}}
 const deadline=Date.now()+205000;
 while(Date.now()<deadline){await load();const run=state.runs.find(r=>r.id===attempt.body.request.requestId);
  if(run?.state==='SUCCEEDED'){notice('Changes saved. Review the new result before marking this layer ready.','success');return;}
  if(run&&['FAILED','INTERRUPTED'].includes(run.state))throw Error(run.error||'Save failed; previous scene and draft retained.');
  await new Promise(r=>setTimeout(r,500));
 }
 throw Error('Save is awaiting its receipt. Refresh status; do not start another Save.');
}
function editLayerField(node){
 if(busy||state.locked)return;const draft=currentLayerDraft();
 if(!draft||draft.checkpointId!==cp()?.id||draft.sha256!==cp()?.sha256||draft.layer!==s()?.stage)throw Error('Reload the current camera/light inspection before editing.');
 const key=node.dataset.layerField,kind=node.dataset.layerKind;
 if(key==='selected'){draft.select(node.value);target=node.value;layerSelections.set(layerKey(),node.value);render();return;}
 else if(kind==='light'){let value=node.value;if(node.dataset.layerIndex!==undefined){value=[...draft.value(draft.selected)[key]];value[Number(node.dataset.layerIndex)]=node.value;}draft.changeLight(draft.selected,key,value);}
 else draft.changeSetting(kind,key,node.value);
 syncLayerDraftUI();
}
function syncLayerDraftUI(){
 const workspace=document.querySelector('.layer-workspace');if(!workspace)return;
 const draft=currentLayerDraft(),invalid=!!workspace.querySelector('[data-layer-field]:invalid'),stale=draft&&(draft.checkpointId!==cp()?.id||draft.sha256!==cp()?.sha256);
 const active=busy||state.locked||!!s()?.task||!!s()?.run||!!layerSave;
 const save=workspace.querySelector('[data-action="layer-save"]'),discard=workspace.querySelector('[data-action="layer-discard"]'),undo=workspace.querySelector('[data-action="layer-undo"]');
 if(save){save.disabled=active||stale||invalid||!draft?.dirty;save.className=draft?.dirty?'primary':'ghost';}
 if(discard)discard.disabled=active||(!draft?.dirty&&!invalid);
 if(undo)undo.disabled=active||stale||!draft?.canUndo;
 const disabled=active||stale||invalid||!draft||!!draft.dirty;
 for(const action of ['layer-ready','preview','layer-camera']){const button=workspace.querySelector('[data-action="'+action+'"]');if(button)button.disabled=disabled||(action==='preview'?(!cap?.render_frames||!shotFor(s())):action==='layer-ready'?!(s().shots||[]).length:cap?.scene_layer!=='scene-layer-v1');}
 const status=workspace.querySelector('.action-savebar [role="status"]');if(status&&!active)status.textContent=invalid?'Correct the highlighted value · saved scene unchanged':stale?'Saved scene changed elsewhere · local draft retained':draft?.dirty?'Unsaved '+(s().stage==='light'?'lighting':'camera')+' changes':'All changes saved';
 const scope=workspace.querySelector('.layer-view-scope');if(scope&&draft?.dirty)scope.textContent='This is still the saved scene. Save changes to update its preview. Use a Blender-rendered still to judge actual lighting.';
}
let addPrompt=null;
const worldPanels=new Map();
let previewStoragePlan=null;
function clearAssetViewer(){assetViewer?.dispose();assetViewer=null;}
function clearSceneViewer(){sceneViewer?.dispose();sceneViewer=null;sceneViewerKey=null;}
const sceneViewKey=()=>cp()?projectId+':'+sceneId+':'+s().stage+':'+cp().id+':'+cp().sha256+':'+JSON.stringify(shotFor(s())):null;
function showSceneViewer(host){clearSceneViewer();sceneViewer=startViewer(host,{kind:'checkpoint',id:cp().id});sceneViewerKey=sceneViewKey();}
function startViewer(host,request){const context={projectId,sceneId,revision:p().revision},viewerId='viewer_'+crypto.randomUUID();return openViewer({host,
 worldEdit:request.kind==='checkpoint'&&s().stage==='world'?{labels:Object.fromEntries((p().workbench.catalogPins||[]).map(a=>[a.id,a.title])),changed:()=>syncWorldDraftUI()}:undefined,
 inspectInBlender:request.kind==='checkpoint'?undefined:()=>perform(async()=>{if(projectId!==context.projectId||sceneId!==context.sceneId||$(request.kind==='catalog'?'catalog-file':'source-file')?.value!==request.file)throw Error('Preview context changed; reopen the asset first.');await dispatch('asset-preview-open',request);}),
 prepare:()=>api('workbench/viewer-prepare',{...context,request,viewerId}),
 release:()=>fetch('/api/workbench/viewer-release',{method:'POST',headers:requestHeaders(),body:JSON.stringify({...context,viewerId}),keepalive:true}),
 fetchModel:async(record,signal)=>{const r=await fetch('/api/workbench/viewer-model?'+new URLSearchParams({projectId:context.projectId,sceneId:context.sceneId,previewId:record.previewId}),{headers:requestHeaders(),signal});if(!r.ok)throw Error((await r.json()).error);return r.arrayBuffer();}});}
const requestHeaders=()=>({'Authorization':`Bearer ${token}`,'Content-Type':'application/json'});
async function api(route,data){const r=await fetch('/api/'+route,{method:data===undefined?'GET':'POST',headers:requestHeaders(),...(data===undefined?{}:{body:JSON.stringify(data)})});const v=await r.json();if(!r.ok)throw Object.assign(new Error(v.error||'Request failed.'),{status:r.status});return v;}
const thumbnails=imageLoader({fetchImage:async url=>{const r=await fetch(url,{headers:requestHeaders()});if(r.status===204)return null;if(!r.ok)throw new Error((await r.json()).error||'Package image request failed.');return r.blob();}});
const p=()=>state?.project,s=()=>p()?.workbench.scenes.find(x=>x.id===sceneId),cp=()=>s()?.checkpoints.find(c=>c.id===(s().candidate||s().current));
const b=(text,action,data={},cls='',disabled=false)=>`<button class="${cls}" data-action="${action}" ${Object.entries(data).map(([k,v])=>`data-${k}="${esc(v)}"`).join(' ')} ${disabled?'disabled':''}>${esc(text)}</button>`;
const next=(name,args={})=>api('workbench/'+name,{projectId,sceneId,revision:p().revision,...args});
function notice(message,kind='error'){$('notice').hidden=!message;$('notice').textContent=message||'';$('notice').dataset.kind=kind;$('notice').setAttribute('role',kind==='success'?'status':'alert');const local=$('browser-notice');if(local){local.hidden=!message;local.textContent=message||'';}}
async function perform(fn){if(busy)return;busy=true;syncWorldDraftUI();document.body.classList.add('working');$('app').classList.add('busy');notice('');try{await fn();}catch(e){try{if(projectId)await load();}catch{}notice(e.message);}finally{busy=false;document.body.classList.remove('working');$('app').classList.remove('busy');syncConsentButtons();syncWorldDraftUI();syncLayerDraftUI();syncOutputUI();scheduleActionInspection();scheduleLayerInspection();scheduleWorldPreparation();}}
function acceptSnapshot(value){if(currentLayerDraft()?.dirty&&value.project.workbench.scenes.find(x=>x.id===sceneId)?.stage!==currentLayerDraft().layer)throw Error('Activity changed elsewhere. Your camera/light draft is retained; discard it before reloading.');if(currentActionDraft()?.dirty&&value.project.workbench.scenes.find(x=>x.id===sceneId)?.stage!=='action')throw Error('Activity changed elsewhere. Your Action draft is retained; discard it before reloading.');if(sceneViewer?.dirty&&value.project.workbench.scenes.find(x=>x.id===sceneId)?.stage!=='world')throw Error('This scene or activity changed elsewhere. Your local placement draft remains open. Discard it before reloading the changed activity.');state=value;reconcileWorldSave();reconcileLayerSave();if(actionSave){const run=state.runs.find(r=>r.id===actionSave.body.request.requestId);if(run?.state==='SUCCEEDED'){if(!s().checkpoints.some(c=>c.id===run.resultCheckpointId))throw Error('Action Save receipt has no matching checkpoint.');actionSave.draft.discard();actionDrafts.delete(projectId+':'+sceneId);actionSave=null;}else if(run&&['FAILED','INTERRUPTED'].includes(run.state)){actionSave=null;notice(run.error||'Action Save failed. Your draft is preserved.');}}}
async function load(){overview=await api('state?compact=true');if(projectId&&!overview.projects.some(x=>x.id===projectId)){if(sceneViewer?.dirty||currentActionDraft()?.dirty||actionSave||currentLayerDraft()?.dirty||layerSave)throw Error('This production is no longer available. Your local draft remains open; restore the production before saving.');projectId=null;}if(projectId){acceptSnapshot(await api('workbench/state?'+new URLSearchParams({projectId,compact:true})));if(!p().workbench.scenes.some(x=>x.id===sceneId))sceneId=p().workbench.scenes[0]?.id;sessionStorage.setItem('wb-project',projectId);sessionStorage.setItem('wb-scene',sceneId||'');}else state=null;render();if(browser.isOpen)await browser.refresh();}
function reconcileWorldSave(){
 if(!worldSave)return;const run=state?.runs.find(r=>r.id===worldSave.body.request.requestId);
 if(run?.state==='SUCCEEDED'){if(!s()?.checkpoints.some(c=>c.id===run.resultCheckpointId))throw Error('Saved receipt has no matching checkpoint. Inspect the retained run.');worldSave.viewer.discard();worldSave=null;}
 else if(run&&['FAILED','INTERRUPTED'].includes(run.state)){worldSave=null;notice('Save failed; your placement draft and previous scene are preserved. '+(run.error||'Inspect the retained attempt.'));}
}
function currentActionDraft(){
 if(!state||!projectId||!sceneId)return null;
 const key=projectId+':'+sceneId,old=actionDrafts.get(key),checkpoint=cp();
 if(old&&(old.dirty||old.checkpointId===checkpoint?.id&&old.sha256===checkpoint?.sha256))return old;
 if(s()?.stage!=='action'||!checkpoint)return null;
 const run=actionInspection(state.runs,s(),checkpoint);if(!run)return null;
 const draft=actionDraft(checkpoint,run);actionDrafts.set(key,draft);return draft;
}
function scheduleActionInspection(){
 setTimeout(()=>{
  if(busy||tab!=='scenes'||s()?.stage!=='action'||!cp()||state.locked||cap?.action_layer!=='action-layer-v1'||currentActionDraft())return;
  const key=projectId+':'+sceneId+':'+cp().id+':'+cp().sha256;
  const attempted=actionInspectionAttempts.has(key)||state.runs.some(r=>r.action==='action-audit'&&r.sceneId===sceneId&&r.checkpointId===cp().id&&r.checkpointSha256===cp().sha256);
  if(!attempted){actionInspectionAttempts.add(key);const chosen={projectId,sceneId,checkpointId:cp().id,sha256:cp().sha256};perform(async()=>{
   await ensureActionInspection({...chosen,read:()=>api('workbench/state?'+new URLSearchParams({projectId:chosen.projectId,compact:true})),create:revision=>api('workbench/action-inspect',{projectId:chosen.projectId,sceneId:chosen.sceneId,revision,request:{version:'action-layer-v1',requestId:'run_'+crypto.randomUUID(),checkpointId:chosen.checkpointId,sha256:chosen.sha256}})});
   await load();
  });}
 },0);
}
async function saveActionDraft(){
 const draft=currentActionDraft();if(!draft?.dirty)return;
 if((draft.checkpointId!==cp()?.id||draft.sha256!==cp()?.sha256))throw Error('Action draft is stale. Discard it and reload the saved scene.');
 if(!actionSave)actionSave={draft,body:{projectId,sceneId,revision:p().revision,request:draft.request('run_'+crypto.randomUUID())}};
 const attempt=actionSave;
 try{await api('workbench/action-save',attempt.body);}catch(error){await load();if(!state.runs.some(r=>r.id===attempt.body.request.requestId)){actionSave=null;throw error;}}
 const deadline=Date.now()+205000;
 while(Date.now()<deadline){await load();const run=state.runs.find(r=>r.id===attempt.body.request.requestId);
  if(run?.state==='SUCCEEDED'){notice('Performance saved. Review playback before marking Action ready.','success');return;}
  if(run&&['FAILED','INTERRUPTED'].includes(run.state))throw Error(run.error||'Save failed; prior scene and draft retained.');
  await new Promise(r=>setTimeout(r,500));
 }
 throw Error('Action Save is awaiting its receipt. Refresh status; do not start a second Save.');
}
function editActionField(field,value){
 if(busy||state.locked)return;const draft=currentActionDraft();
 if(!draft||(draft.checkpointId!==cp()?.id||draft.sha256!==cp()?.sha256))throw Error('Refresh the current performers before editing.');
 if(field==='performer'){draft.select(value);render();return;}
 const name=draft.selected,old=draft.value(name);
 if(field==='mode'){
  const pose=Math.max(draft.audit.frame_range[0],Math.min(draft.audit.frame_range[1],sceneViewer?.currentFrame??draft.audit.reference_frame));
  draft.change(name,value==='keep'?{mode:'keep'}:value==='hold'?{mode:'hold',frame:pose}:{mode:'clip',take_id:value,start:draft.audit.frame_range[0],speed:1});
 }else draft.change(name,{...old,[field]:Number(value)});
 render();
}
function syncWorldDraftUI(){
 const draft=sceneViewer?.draft,stale=!!draft&&sceneViewerKey!==sceneViewKey(),blocked=busy||!!worldSave||state?.locked||!!s()?.task||!!s()?.run||!!additions.state().count;
 sceneViewer?.setEnabled(!blocked&&!stale);
 const bar=document.querySelector('.world-savebar');if(!bar)return;
 const save=bar.querySelector('[data-action="save-world"]'),undo=bar.querySelector('[data-action="world-undo"]'),discard=bar.querySelector('[data-action="world-discard-draft"]');
 if(save){save.disabled=blocked||stale||!(draft?.dirty||s()?.candidate);save.className=draft?.dirty||s()?.candidate?'primary':'ghost';}
 if(undo)undo.disabled=blocked||stale||!(draft?.canUndo||s()?.candidate);
 if(discard){discard.hidden=!draft?.dirty;discard.disabled=!!worldSave||!!draft?.editing;}
 const count=additions.state().count;
 bar.querySelector('[role="status"]').textContent=worldSave?'Saving placement in Blender — previous scene preserved':stale?'Preview out of date — discard this local draft and reload before editing':draft?.dirty?'Unsaved placement · '+draft.count+' asset'+(draft.count===1?'':'s'):count?count+' additions in progress or queued':s()?.candidate?'Unsaved changes · recovery copy stored':cp()?'All changes saved':'No assets imported yet';
 const scope=document.querySelector('.world-view-scope');if(scope)scope.textContent=stale?'Older checkpoint · local placement draft preserved':draft?.dirty?'Unsaved visual draft · Save changes to keep this arrangement':(s()?.candidate?'Working draft':'Saved scene')+' · imported assets appear together here';
}
async function saveWorldDraft(){
 if(!sceneViewer?.dirty)return;
 if(sceneViewerKey!==sceneViewKey())throw Error('This placement draft is out of date. Discard it and reload the current scene.');
 const viewer=sceneViewer;
 if(!worldSave)worldSave={viewer,body:{projectId,sceneId,revision:p().revision,request:viewer.request('run_'+crypto.randomUUID())}};
 const attempt=worldSave;syncWorldDraftUI();
 try{await api('workbench/world-save',attempt.body);}catch(error){
   // A lost HTTP response is not permission to execute a second job.
   await load();const run=state.runs.find(r=>r.id===attempt.body.request.requestId);
   if(!run){worldSave=null;throw error;}if(['FAILED','INTERRUPTED'].includes(run.state))throw Error(run.error||'Save failed; inspect its retained attempt.');
 }
 const deadline=Date.now()+205000;
 while(Date.now()<deadline){await load();const run=state.runs.find(r=>r.id===attempt.body.request.requestId);
   if(run?.state==='SUCCEEDED'){notice('Arrangement saved. World is not marked complete.','success');return;}
   if(run&&['FAILED','INTERRUPTED'].includes(run.state))throw Error(run.error||'Save failed; the previous scene and local draft are preserved.');
   await new Promise(resolve=>setTimeout(resolve,600));
 }
 throw Error('Save is still awaiting a final receipt. Refresh status; do not start another Save. Your previous scene is preserved.');
}
function modal(title,body,buttons,back='Cancel'){clearLightingMedia();clearAssetViewer();$('dialog').className='';delete $('dialog').dataset.returnLibrary;delete $('dialog').dataset.catalogId;$('dialog').setAttribute('aria-labelledby','detail-title');$('dialog').innerHTML=`<header class="detail-head"><h2 id="detail-title">${esc(title)}</h2>${b('Close','dismiss',{},'ghost small')}</header>${body}<footer>${b(back,'close',{},'ghost')}${buttons||''}</footer>`;if(!$('dialog').open)$('dialog').showModal();$('dialog').querySelector('input,button')?.focus();}
function finishAddPrompt(value){const prompt=addPrompt;addPrompt=null;prompt?.resolve(value);}
function syncConsentButtons(){for(const [input,action] of [['world-use-confirm','world-use-confirm'],['prepare-confirm','source-prepare']]){const checkbox=$(input),button=$('dialog').querySelector('[data-action="'+action+'"]');if(checkbox&&button)button.disabled=!checkbox.checked||busy;}}
function close(){clearLightingMedia();finishAddPrompt(false);clearAssetViewer();$('dialog').close();}
$('dialog').addEventListener('close',clearAssetViewer);
$('dialog').addEventListener('close',clearLightingMedia);
$('dialog').addEventListener('close',()=>finishAddPrompt(false));
$('dialog').addEventListener('cancel',e=>{if($('dialog').dataset.returnLibrary==='true'){e.preventDefault();perform(()=>dispatch('close',{}));}});
$('dialog').addEventListener('change',e=>{if(e.target.id==='catalog-file'&&$('dialog').dataset.catalogId){const id=$('dialog').dataset.catalogId,file=e.target.value,back=$('dialog').dataset.returnLibrary;perform(()=>dispatch('catalog-detail',{id,file,back}));}});
$('dialog').addEventListener('change',e=>{if(['catalog-file','source-file'].includes(e.target.id)){clearAssetViewer();const host=$('dialog').querySelector('[data-viewer-host]');if(host){host.textContent='Source file changed. Choose View in 3D to inspect this member.';delete host.dataset.viewerState;}}});
window.addEventListener('pagehide',()=>{clearAssetViewer();clearSceneViewer();});
const browser=assetBrowser({dialog:$('library-dialog'),context:()=>({project:p(),scene:s(),locked:state.locked,queueCount:additions.state().count}),api,esc,b,loadImages:root=>{root.querySelectorAll('[data-source-image]').forEach(loadSourceImage);root.querySelectorAll('[data-catalog-image]').forEach(loadCatalogImage);},releaseImages:root=>{for(const img of root.querySelectorAll('img[src^="blob:"]')){const url=img.src;URL.revokeObjectURL(url);blobs=blobs.filter(x=>x!==url);}},onError:notice});
const additions=worldAddQueue({context:()=>({projectId,sceneId}),run:processWorldAdd,
 changed:()=>{if(state)render();if(browser.isOpen)void browser.refresh().catch(e=>notice(e.message));},failed:e=>notice(e.message)});
window.addEventListener('beforeunload',e=>{if(additions.state().count||sceneViewer?.dirty||worldSave||currentActionDraft()?.dirty||actionSave||currentLayerDraft()?.dirty||layerSave){e.preventDefault();e.returnValue='';}});
function askAdd(title,body,buttons,kind,extra={}){browser.close();modal(title,body,buttons,'Cancel addition');if(kind==='prepare'||kind==='use')$('dialog').classList.add('preparation-dialog');return new Promise(resolve=>{addPrompt={resolve,kind,...extra};});}
async function askSourcePermission(snapshot){
 const use=snapshot.sourceUse;
 return askAdd('Permission to use these assets',`<p>For production <strong>${esc(snapshot.project.name)}</strong></p><label class="preparation-confirm"><input id="world-use-confirm" type="checkbox"><span>I have the right to use and adapt these exact assets for this production and will follow their terms and required credits.</span></label><p>No permission for future versions, redistribution or model training.</p><details><summary>Assets and exact scope</summary><pre>${esc(use.message)}</pre></details>`,b('Confirm & continue','world-use-confirm',{},'primary',true),'use',{revision:snapshot.project.revision,projectId:snapshot.project.id,scopeHash:use.scopeHash});
}
async function processWorldAdd(intent,check){
 const read=async()=>{check();const v=await api('workbench/state?'+new URLSearchParams({projectId:intent.projectId,compact:true}));check();const scene=v.project.workbench.scenes.find(x=>x.id===intent.sceneId);if(!scene||scene.stage!=='world')throw Error('World context changed. Reopen the asset before adding.');state=v;render();return {...v,scene};};
 const command=async(name,args={})=>{const v=await read();check();return api('workbench/'+name,{projectId:intent.projectId,sceneId:intent.sceneId,revision:v.project.revision,...args});};
 const wait=async runId=>{for(let i=0;i<620;i++){await new Promise(r=>setTimeout(r,500));const v=await read(),run=v.runs.find(x=>x.id===runId);if(!run)throw Error('Addition receipt unavailable. Inspect operation before retrying.');if(['FAILED','INTERRUPTED'].includes(run.state))throw Error(run.error||'Addition failed. Previous draft and failure evidence are preserved.');if(run.state==='SUCCEEDED'&&!v.locked)return run;}throw Error('Addition is still running. Inspect its operation; it was not stopped or retried.');};
 const asset=id=>api('workbench/catalog-detail?'+new URLSearchParams({projectId:intent.projectId,assetId:id}));
 let item=intent;
 if(intent.kind==='source'){
   let v=await read();if(!v.sourceUse.ready){if(!await askSourcePermission(v))return 'cancelled';v=await read();}
   const source=await api('workbench/source-detail?'+new URLSearchParams({projectId:intent.projectId,sourceId:intent.id}));check();
   if(source.version!==intent.version||!source.available)throw Error('Source package changed or is unavailable.');
   if(source.prepared){if(source.prepared.sourceFile!==intent.file)throw Error('This package was prepared from another member. Inspect its prepared version before adding.');item={...intent,kind:'catalog',id:source.prepared.assetId,version:source.prepared.assetVersion,file:source.prepared.file};}
   else{
     const view=preparationDialog({source,file:intent.file,projectName:v.project.name,esc,b});
     if(!await askAdd('Add '+source.name,view.body,view.buttons,'prepare'))return 'cancelled';
     check();const started=await command('source-prepare',{request:{id:intent.id,version:intent.version,file:intent.file,confirmation:'local-project-use-v1',confirmed:true,projectUse:true}});
     const prepared=await wait(started.run.id);item={...intent,kind:'catalog',id:prepared.assetId,version:prepared.assetVersion,file:prepared.file};
   }
 }
 const result=await addCatalogFlow(item,{read,asset,command,wait,check,permission:askSourcePermission,
   collections:names=>askAdd('Choose what to add',`<p>This file contains several collections. Choose the parts you want in this scene.</p><fieldset><legend>Observed Blender collections</legend>${names.map(n=>`<label><input name="world-collection" type="checkbox" value="${esc(n)}"> ${esc(n)}</label>`).join('')}</fieldset>`,b('Add selected','world-collections-selected',{},'primary')+b('Add all '+names.length,'world-collections-all'),'collections',{names})});
 check();await read();return result;
}
async function enqueueWorldAsset(d){
 const kind=d.kind||'catalog',asset=await api('workbench/'+(kind==='source'?'source-detail?':'catalog-detail?')+new URLSearchParams({projectId,[kind==='source'?'sourceId':'assetId']:d.id}));
 if(d.version&&d.version!==asset.version)throw Error('Asset changed. Reopen it before adding.');
 const files=kind==='source'?(asset.entrypoints||[]).filter(f=>/\.(blend|gltf|glb|fbx)$/i.test(f)):asset.models||[];
 const file=d.file||(files.length===1?files[0]:null);
 if(!file){await dispatch(kind==='source'?'source-detail':'catalog-detail',{id:d.id});notice('Choose the exact source file, then Add to scene.');return;}
 if(!files.includes(file))throw Error('Choose an observed source file.');
 const selection=Array.from(document.querySelectorAll('[name="catalog-collection"]:checked'),n=>n.value);
 close();const added=additions.add({kind,id:d.id,version:asset.version,file,selection});
 if(!added)notice('This asset is already being added.');
}
function objects(){return cp()?.audit?.objects||[];}
function activityName(id){return state.stages.find(x=>x.id===id)?.label||id;}
function block(message){return `<div class="note warn">${esc(message)}</div>`;}
function sourceUseBanner(){return state.sourceUse&&!state.sourceUse.ready?`<div class="note warn"><strong>Source use needs your review</strong><p>Confirm the exact pinned sources once for this production. This is your attestation, not a license grant; normal native evidence gates still apply.</p>${b('Review source use','source-review',{},'',state.locked)}</div>`:'';}
function render(){rememberFilmPosition();const keptVideos=new Map(Array.from(document.querySelectorAll('#app video[data-media]'),node=>[mediaIdentity(node),node])),usedVideos=new Set(),videoURLs=new Set([...keptVideos.values()].map(n=>n.src).filter(url=>url.startsWith('blob:')));const releaseUnusedVideos=()=>{for(const node of keptVideos.values())if(!usedVideos.has(node)&&node.src.startsWith('blob:')){URL.revokeObjectURL(node.src);blobs=blobs.filter(url=>url!==node.src);}};const layerDetails=Array.from(document.querySelectorAll('.layer-details'),n=>n.open);const priorWorld=document.querySelector('.world-workspace');if(priorWorld?.dataset.contextKey)worldPanels.set(priorWorld.dataset.contextKey,Object.fromEntries(['world-inspection','rendered-evidence','world-ingredient-list'].map(name=>[name,!!priorWorld.querySelector('.'+name)?.open])));const keptHost=tab==='scenes'&&['world','action','shots','light','render'].includes(s()?.stage)&&(sceneViewer?.dirty||currentActionDraft()?.dirty||currentLayerDraft()?.dirty||sceneViewerKey===sceneViewKey())?document.querySelector('[data-scene-viewer]'):null;if(!keptHost)clearSceneViewer();for(const url of blobs)if(!videoURLs.has(url))URL.revokeObjectURL(url);blobs=blobs.filter(url=>videoURLs.has(url));
 const root=$('app');if(!overview){releaseUnusedVideos();return;}
 if(!projectId){root.innerHTML=`<section class="picker"><div class="eyebrow">Your local studio</div><h1>Productions</h1><p>Choose a production. Each scene keeps its own creative workflow and checkpoints. Archive removes a production from this list without deleting its files; restore it from Archived productions.</p>${b('New production','new-production',{},'primary')}${b('Archived productions','archived-productions',{},'ghost')}${overview.errors.map(e=>block(e.folder+': '+e.message)).join('')}${overview.projects.map(project=>productionRow({project,esc,b})).join('')}${!overview.projects.length?'<p class="empty">No productions yet. Create one to begin.</p>':''}</section>`;releaseUnusedVideos();return;}
 root.innerHTML=`<header class="projectbar">${b(p().name+' ▾','picker',{},'production ghost')}<nav aria-label="Production">${b('Scenes','tab',{tab:'scenes'},tab==='scenes'?'active':'')}${b('Final film','tab',{tab:'film'},tab==='film'?'active':'')}</nav><span class="grow"></span><span class="status">${state.locked?'Adding / preparing':s()?.candidate?'Unsaved scene changes':'Saved · revision '+p().revision}</span>${b('Refresh','refresh',{},'ghost')}${b('Studio','settings',{},'ghost')}</header>${returnToFilm&&tab==='scenes'?'<div class="note">Editing a source scene. The film arrangement is preserved. '+b('Return to Final film','return-film')+'</div>':''}${tab==='film'?film():scenePage()}`;
 root.querySelectorAll('[data-media]').forEach(node=>{const kept=keptVideos.get(mediaIdentity(node));if(kept){node.replaceWith(kept);usedVideos.add(kept);}else loadMedia(node);});releaseUnusedVideos();root.querySelectorAll('[data-source-image]').forEach(loadSourceImage);root.querySelectorAll('[data-catalog-image]').forEach(loadCatalogImage);
 const world=root.querySelector('.world-workspace');if(world){const key=projectId+':'+sceneId;world.dataset.contextKey=key;for(const [name,open] of Object.entries(worldPanels.get(key)||{})){const panel=world.querySelector('.'+name);if(panel)panel.open=open;}}
 const worldHost=['world','action','shots','light','render'].includes(s()?.stage)?root.querySelector('[data-scene-viewer]'):null;if(worldHost){if(keptHost)worldHost.replaceWith(keptHost);else if((s().stage!=='render'||!worldHost.closest('details'))&&cp()&&!state.locked&&!s().task&&!s().run&&(s().stage!=='action'||currentActionDraft())&&(!['shots','light'].includes(s().stage)||currentLayerDraft()))showSceneViewer(worldHost);}
 document.querySelectorAll('.layer-details').forEach((n,i)=>{n.open=layerDetails[i]||false;});syncWorldDraftUI();
}
function scenePage(){const scene=s();if(scene?.stage==='render')return `<section class="workspace layered-scene output-layer">${outputView({project:p(),scene,stages:state.stages,runs:state.runs,locked:state.locked,taskStatus:state.taskStatuses?.[scene.id],cap,draft:currentOutputDraft(),esc,b})}${sourceUseBanner()}${runList(scene)}</section>`;if(['shots','light'].includes(scene?.stage))return `<section class="workspace layered-scene">${sceneLayerView({project:p(),scene,stages:state.stages,checkpoint:cp(),runs:state.runs,locked:state.locked,taskStatus:state.taskStatuses?.[scene.id],cap,draft:currentLayerDraft(),saving:layerSave,esc,b})}${sourceUseBanner()}${runList(scene)}</section>`;if(scene?.stage==='action')return `<section class="workspace layered-action">${actionView({project:p(),scene,stages:state.stages,checkpoint:cp(),runs:state.runs,locked:state.locked,taskStatus:state.taskStatuses?.[scene.id],cap,draft:currentActionDraft(),saving:actionSave,esc,b})}${sourceUseBanner()}${runList(scene)}</section>`;if(scene?.stage==='world')return `<section class="workspace world-workspace">${worldView({project:p(),scene,stages:state.stages,locked:state.locked,sourceUse:state.sourceUse,runs:state.runs,taskStatus:state.taskStatuses?.[scene.id],cap,inventory:state.inventory,queueCount:additions.state().count,esc,b})}</section>`;return `<div class="shell"><aside class="scenes"><h2>Scenes</h2>${p().workbench.scenes.map((x,i)=>b(`${String(i+1).padStart(2,'0')}  ${x.name} · ${activityName(x.stage)}`,'scene',{id:x.id},'scene-link'+(x.id===sceneId?' active':''))).join('')}${b('+ Add scene','new-scene',{},'ghost')}</aside><section class="workspace">${!scene?`<div class="empty"><h1>Build your first scene</h1><p>Start with your library. Assemble a world, stage the action, then decide how to film it.</p>${b('Create scene','new-scene',{},'primary')}</div>`:sceneBody(scene)}</section></div>`;}
function sceneBody(scene){const checkpoint=cp(),current=scene.checkpoints.find(c=>c.id===scene.current),candidate=!!scene.candidate;
 const activeRun=state.runs.find(r=>r.id===(scene.task||scene.run));
 return `<select class="mobile-scenes" aria-label="Selected scene" id="scene-picker">${p().workbench.scenes.map(x=>`<option value="${x.id}" ${x.id===sceneId?'selected':''}>${esc(x.name)}</option>`).join('')}</select><div class="scene-head"><div class="grow"><div class="eyebrow">Scene · ${esc(scene.id.slice(3,11))}</div><h1>${esc(scene.name)}</h1><p>${esc(p().brief||'Add your scene intent in Studio.')}</p></div>${b('History','history',{},'ghost')}${b('+ Scene','new-scene',{},'ghost')}</div><div class="steps" aria-label="Activities in this scene">${state.stages.map((st,i)=>b((scene.completed[st.id]?'✓ ':String(i+1)+' ')+st.short,'stage',{stage:st.id},`${scene.stage===st.id?'active ':''}${scene.completed[st.id]?'done':''}`,!!scene.task||!!scene.candidate||!!scene.run||state.stages.slice(0,i).some(x=>!scene.completed[x.id]))).join('')}</div>${sourceUseBanner()}${!cap?.task_workspace?block(cap?.message||'The configured harness does not expose this development workbench. No installed runtime has been changed.'):''}${scene.task?taskBanner(scene,state.taskStatuses?.[scene.id],esc,b):''}${scene.run?`<div class="note"><strong>${esc(activeRun?.action||'Harness operation')} · ${esc(activeRun?.state||'Checking receipt')}</strong><p>${esc(progressLabel(activeRun))}. Progress is not estimated. You can refresh or inspect the preserved run.</p>${b('Refresh status','refresh')}${b('Inspect operation','recover',{run:scene.run})}</div>`:''}${candidate?`<div class="note good"><strong>New checkpoint saved · review before continuing</strong><p>${esc(checkpoint.path)}. Saving did not approve the result or replace the previous checkpoint.</p></div>`:''}<div class="activity-head"><h2>${esc(activityName(scene.stage))}</h2><p>${esc({world:'Choose your ingredients, then assemble and edit the real scene in Blender.',action:'Work with the performers and actions in this saved scene—not a new scene.',shots:'Choose an existing camera or create one in Blender to capture the staged action.',light:'Refine the scene’s real lights and look. Preserve what already works.',render:'Render an explicit shot range, inspect its movie, and approve the actual output.'}[scene.stage])}</p></div>${['world','action','light'].includes(scene.stage)?library():''}<div class="workbench ${scene.stage} ${checkpoint?'has-checkpoint':''}">${scene.stage==='world'?'':scene.stage==='render'?'<div class="library-stack">'+shotPanel({scene,checkpoint,locked:state.locked,esc,b})+readiness()+'</div>':scene.stage==='action'?'<div class="library-stack">'+objectPanel()+'</div>':'<div class="library-stack">'+shotPanel({scene,checkpoint,locked:state.locked,esc,b})+objectPanel()+'</div>'}<section class="evidence">${evidence(scene,checkpoint)}<div class="summary"><h3>${candidate?'Candidate checkpoint':checkpoint?'Saved checkpoint':'No scene checkpoint yet'}</h3><p>${esc(checkpoint?.path||'Choose assets and prepare a Blender task. Nothing has been instantiated yet.')}</p>${scene.stage==='world'?'<p class="muted">Scene contents come from the saved Blender checkpoint audit, not your selection.</p>':''}${checkpoint?`<details><summary>Checkpoint provenance and observed contents</summary><pre>${esc(JSON.stringify({sha256:checkpoint.sha256,parent:checkpoint.parent,source:checkpoint.source,audit:checkpoint.audit||'Not audited; imported saved file'},null,2))}</pre></details>`:''}</div>${scene.stage==='render'?renderList(scene):''}</section><aside class="decision"><div class="role">${esc(state.stages.find(x=>x.id===scene.stage).role)} · this scene</div>${decision(scene,checkpoint,current)}</aside></div>${runList(scene)}`;
}
function library(){return ingredientsView({project:p(),scene:s(),inventory:state.inventory,esc,b});}
function objectPanel(){const types={action:['ARMATURE','MESH','EMPTY','CURVE'],shots:['CAMERA'],light:['LIGHT']},rows=objects().filter(o=>(types[s().stage]||[]).includes(o.type));if(target&&!rows.some(o=>o.name===target))target=null;
 return `<section class="library"><header><h3>${esc({action:'Performers & action',shots:'Scene cameras',light:'Scene lights'}[s().stage])}</h3><p>Observed in the saved checkpoint.</p></header><div class="object-list">${rows.map(o=>b(o.name,'target',{name:o.name},o.name===target?'selected':'')).join('')||'<p>No matching objects were observed. Prepare or edit this task in Blender, then collect a checkpoint.</p>'}</div><footer>${s().stage==='action'?'Motion intake, compatibility and transfer remain in the reviewed harness specialist workflow.':s().stage==='shots'?'Multiple cameras capture the same world. Select a camera here to target the Blender handoff.':'These are actual light objects, not look presets.'}</footer></section>`;
}
function evidence(scene,checkpoint){return evidenceView({scene,checkpoint,esc,b,canPreview:!!cap?.render_frames&&!state.locked&&!scene.task&&!scene.run});
}
function decision(scene,checkpoint,current){const active=state.locked||!!scene.task||!!scene.run;
 if(scene.stage==='render')return renderDecision(scene,current,active);
 const title={world:'Open Blender · assemble world',action:'Edit performance in Blender',shots:'Refine cameras in Blender',light:'Refine lighting in Blender'}[scene.stage];
 return `<h2>${scene.candidate?'Does this checkpoint work?':checkpoint?'Continue the creative work':'Build the first version'}</h2>${b(title,'task',{},scene.candidate?'':'primary',active||!!scene.candidate||!cap?.task_workspace)}<p>${scene.candidate?'Inspect the saved file in Blender. Keeping it records your decision for this activity and moves to the next one.':'You edit directly in Blender. Opens a separate working copy; selected assets are not automatically imported. Save checkpoint and return here to review. Existing windows and checkpoints stay untouched.'}</p>${scene.candidate?`${b('Inspect saved candidate','inspect-candidate',{},'',active)}${b('Keep & continue building','keep-building',{},'',active)}${b('Keep checkpoint & continue','approve',{},'primary',active)}${b('Reject candidate','discard',{},'ghost',active)}`:checkpoint?b('This activity is complete →','approve',{},'',active):''}<div class="rule"></div>${b('Open Codex specialist','codex',{},'',active||!cap?.task_workspace)}<p class="muted">AI-assisted route: opens your configured Codex session with this scene, activity and selected sources. It does not control the manual task. Review its plan and required approvals; import its separately saved result here.</p>${b('Import saved working scene','import',{},'ghost',active||!!scene.candidate)}<details><summary>What Blender receives</summary><p>${esc(activityName(scene.stage))} · ${esc(target||'whole scene')} · ${esc(current?.path||'new empty working scene')}.</p><p>Task workspace setup is not a live MCP connection. Detailed modeling, animation, camera and lighting edits remain in Blender.</p></details>`;
}
function readiness(){const ready=s().readiness;return `<section class="library"><header><h3>Render readiness</h3></header><div class="object-list">${ready?`<p>${ready.data.blockers.length?'Needs attention':'Checked against this saved file'}</p>${ready.data.blockers.map(x=>`<p class="warn">${esc(x)}</p>`).join('')}<p>${ready.data.cameras.length} cameras · ${esc(ready.data.frame_range.join('–'))} frames</p><p>${ready.data.dependencies.length} external files verified</p><p>CPU / detected OptiX GPU · silent output</p>`:'<p>Check the actual saved scene before requesting a render.</p>'}</div><footer>This bounded adapter refuses unsupported caches and compositor output rather than silently changing the film.</footer></section>`;}
function renderDecision(scene,current,active){const shot=shotFor(scene),ready=scene.readiness?.checkpointId===current?.id?scene.readiness:null;
 return `<h2>Make a real shot movie</h2><p>${shot?'Rendering '+esc(shot.name)+' · v'+shot.revision+'. Camera and timing come from its saved definition.':'Select a camera and frame range from the saved scene.'} Every run writes new frame evidence and a separate movie.</p>${b('Check saved-scene readiness','readiness',{},ready?'':'primary',active||!current||!cap?.render_frames)}${ready&&!ready.data.blockers.length?`<div class="fields">${deviceControl(ready.data,cap,esc)}<label class="full">Camera<select id="render-camera" ${shot?'disabled':''}>${ready.data.cameras.map(c=>`<option ${c===(shot?.camera||ready.data.camera)?'selected':''}>${esc(c)}</option>`).join('')}</select></label><label>First frame<input id="render-start" type="number" ${shot?'disabled':''} value="${shot?.start??ready.data.frame_range[0]}"></label><label>Last frame<input id="render-end" type="number" ${shot?'disabled':''} value="${shot?.end??Math.min(ready.data.frame_range[1],ready.data.frame_range[0]+47)}"></label><label>Width<input id="render-width" type="number" value="640" min="16" max="1920" step="2"></label><label>Height<input id="render-height" type="number" value="360" min="16" max="1080" step="2"></label><label class="full">Samples<input id="render-samples" type="number" value="8" min="1" max="128"></label></div><p>Suggested low-cost test: 640 × 360, up to 48 frames, 8 samples. Adjust deliberately; these are not your saved production settings.</p>${b('Authorize & render this shot','render',{},'primary',active||!cap?.encoder||!ready.data.cameras.length)}`:''}${!cap?.encoder?'<p class="warn">Configure absolute FFmpeg and FFprobe paths to enable movie output. Nothing is installed automatically.</p>':''}<details><summary>Initial output limits</summary><p>1–360 frames per shot; even dimensions up to 1920 × 1080; at most 2 billion pixel-samples; 900-second Blender deadline. Silent H.264 review movie, no audio mix, simulations, compositor or automatic quality certification.</p></details>`;
}
function renderList(scene){return `<section class="section"><h3>Shot outputs</h3>${[...scene.renders].reverse().map(r=>`<div class="render-row"><div><strong>${esc(r.shotName||r.options.camera)} · ${r.options.start}–${r.options.end}${r.shotRevision?' · v'+r.shotRevision:''}</strong><small class="${!renderIsCurrent(scene,r)?'warn':r.approved?'good':''}">${!renderIsCurrent(scene,r)?'Historical · scene or shot changed':r.approved?'Approved for film':'Needs your review'}</small></div><small>${esc(outputDevice(r))}</small>${b('Play','play-render',{id:r.id},'small')}${b('Approve','approve-render',{id:r.id},'small',state.locked||r.approved||!renderIsCurrent(scene,r))}</div>`).join('')||'<p>No shot renders yet.</p>'}</section>`;}
function runList(scene){const rows=state.runs.filter(r=>r.sceneId===scene.id).slice(0,8);return `<details><summary>Task and job history · ${rows.length} recent records</summary>${rows.map(r=>`<div class="run-row"><div>${esc(r.action||r.stage||'Blender task')} · <span class="${r.state==='FAILED'?'bad':''}">${esc(r.state)}</span><small>${esc(r.error||r.id||'')}</small></div>${b('Inspect','recover',{run:r.id},'small')}</div>`).join('')}</details>`;}
function film(){const w=p().workbench,latest=filmView.selected(projectId,w),choices=w.scenes.flatMap(scene=>scene.renders.filter(r=>r.approved&&renderIsCurrent(scene,r)).map(r=>({scene,r}))),refs=w.film.clips,currentCut=cutIsCurrent(w,latest);
 return `<section class="film"><div class="eyebrow">Production output</div><h1>Final film</h1>${filmCutPicker(w,latest,esc)}${sourceUseBanner()}<p>Arrange approved shot movies. Editing a source scene never silently changes an existing cut.</p><div class="film-layout"><div><div class="viewport"><header>Whole-film review<small>${latest?latest.id.slice(4,12):'No cut yet'}</small></header>${latest?`<video data-media="cut" data-project-id="${esc(projectId)}" data-id="${latest.id}" controls playsinline preload="metadata" aria-label="Final film"></video>`:'<div class="empty-media"><div class="symbol">▥</div><h3>Your scenes, together</h3><p>Render and approve a shot in Scenes, then add it below.</p></div>'}<footer>Real H.264 encoding · no audio or frame-rate conversion · not approved until you decide</footer></div><div class="film-strip">${refs.map((c,i)=>{const scene=w.scenes.find(s=>s.id===c.sceneId),r=scene.renders.find(r=>r.id===c.renderId);return `<article class="clip"><strong>${i+1}. ${esc(scene.name)}</strong><small class="${!renderIsCurrent(scene,r)?'warn':''}">${!renderIsCurrent(scene,r)?'Source changed · rebuild required':esc(r.options.camera)}</small><div class="row">${b('←','reorder',{index:i,delta:-1},'small',state.locked||i===0)}${b('→','reorder',{index:i,delta:1},'small',state.locked||i===refs.length-1)}${b('Remove','remove-clip',{index:i},'small',state.locked)}${b('Edit source','edit-source',{id:scene.id,shot:r.shotId||''},'small',state.locked)}</div></article>`;}).join('')}</div><section class="section"><h3>Available approved shots</h3>${choices.map(({scene,r})=>`<div class="render-row"><div>${esc(scene.name)} · ${esc(r.options.camera)}<small>${r.options.start}–${r.options.end} · ${r.options.width} × ${r.options.height}</small></div>${b('Add to film','add-clip',{scene:scene.id,id:r.id},'small',state.locked||refs.length>=32)}${b('Edit source','edit-source',{id:scene.id,shot:r.shotId||''},'small',state.locked)}</div>`).join('')||'<p>Approved scene outputs will appear here.</p>'}</section></div><aside class="film-inspector"><div class="eyebrow">Editing / finishing</div><h2>${latest&&!currentCut?'Historical cut':latest?.approved?'Reviewed cut':'Build the film'}</h2>${staleFilmInputs(w).length?'<p class="note warn">'+staleFilmInputs(w).length+' film input(s) need a current approved replacement. Use Edit source, then replace the old input. Previous cuts stay playable.</p>':''}<p>${refs.length} shot inputs. Their frame rates and dimensions must match; no silent retiming or scaling.</p>${b('Build this cut','build-film',{},'primary',state.locked||!refs.length||!cap?.encoder||!!staleFilmInputs(w).length)}${latest?`${b('Approve reviewed cut','approve-cut',{id:latest.id},'',state.locked||latest.approved||!currentCut)}${b('Download film','download',{id:latest.id},'ghost')}${b('View provenance','cut-record',{id:latest.id},'ghost')}`:''}<p class="muted">A changed source or arrangement makes the old cut historical. Approval of an outdated cut is refused.</p><details><summary>Production tasks</summary>${state.runs.filter(r=>r.sceneId===null).map(r=>`<div class="run-row"><div>${esc(r.action)} · ${esc(r.state)}</div>${b('Inspect','recover',{run:r.id},'small')}</div>`).join('')}</details></aside></div></section>`;
}
async function mediaURL(kind,id){const q=new URLSearchParams({projectId});if(kind==='cut')q.set('cutId',id);else{q.set('sceneId',sceneId);if(kind==='render')q.set('renderId',id);else q.set('kind','preview');}const r=await fetch('/api/workbench/media?'+q,{headers:requestHeaders()});if(!r.ok)throw new Error((await r.json()).error);return URL.createObjectURL(await r.blob());}
async function loadMedia(node){try{const url=await mediaURL(node.dataset.media,node.dataset.id);if(!node.isConnected){URL.revokeObjectURL(url);return;}blobs.push(url);node.src=url;if(node.dataset.media==='cut'){const time=filmView.time(node.dataset.projectId,node.dataset.id);if(time)node.addEventListener('loadedmetadata',()=>{node.currentTime=Math.min(time,node.duration||0);},{once:true});}}catch(e){node.insertAdjacentHTML('afterend',`<p class="note warn">${esc(e.message)}</p>`);}}
async function loadPackageImage(node,kind){try{const id=kind==='source'?node.dataset.sourceImage:node.dataset.catalogImage;const version=node.dataset.version;const url='/api/workbench/'+kind+'-image?'+new URLSearchParams({projectId,[kind==='source'?'sourceId':'assetId']:id});const blob=await thumbnails.load(projectId+':'+kind+':'+id+':'+version,url,()=>node.isConnected);if(!node.isConnected)return;if(!blob){if(node.nextElementSibling)node.nextElementSibling.textContent='3D preview available';return;}const objectURL=URL.createObjectURL(blob);blobs.push(objectURL);node.src=objectURL;node.hidden=false;node.previousElementSibling.hidden=true;if(node.nextElementSibling)node.nextElementSibling.textContent='Source reference';}catch(e){if(node.isConnected)node.insertAdjacentHTML('afterend',`<small class="warn">${esc(e.message)}</small>`);}}
const loadSourceImage=node=>loadPackageImage(node,'source');
const loadCatalogImage=node=>loadPackageImage(node,'catalog');
async function dispatch(a,d){
 if(a==='lighting-evidence'){await showLightingEvidence(d);return;}
 if(a==='layer-draft-save'||a==='layer-draft-discard'){
  const destination=draftDestination;if(!destination)return;
  if(a==='layer-draft-save')await saveLayerDraft();else{currentLayerDraft()?.discard();layerDrafts.delete(layerKey());}
  draftDestination=null;close();await dispatch(destination.action,destination.data);return;
 }
 if(a==='layer-discard'){if(layerSave)throw Error('Wait for the Save receipt.');currentLayerDraft()?.discard();layerDrafts.delete(layerKey());clearSceneViewer();await load();return;}
 if(a==='layer-undo'){currentLayerDraft()?.undo();render();return;}
 if(a==='layer-save'){await saveLayerDraft();return;}
 if(a==='layer-camera-save'){
  const draft=currentLayerDraft();if(!draft)throw Error('Inspect this layer first.');
  draft.fitCamera({name:$('layer-camera-name').value,subjects:Array.from(document.querySelectorAll('[name="layer-subject"]:checked'),n=>n.value),direction:[0,1,2].map(i=>$('layer-direction-'+i).value),lens:$('layer-lens').value,frame:$('layer-frame').value});close();await saveLayerDraft();return;
 }
 if(layerSave&&worldActionNeedsSave(a))throw Error('Layer Save is still running. Refresh status or inspect its receipt.');
 if(currentLayerDraft()?.dirty&&worldActionNeedsSave(a)){
  draftDestination={action:a,data:{...d}};modal('Keep your camera / lighting changes?','<p>Save these edits before continuing, or discard only the local draft. Your previous scene file stays intact.</p>',b('Discard & continue','layer-draft-discard',{},'ghost')+b('Save & continue','layer-draft-save',{},'primary',currentLayerDraft().checkpointId!==cp()?.id||currentLayerDraft().sha256!==cp()?.sha256),'Stay here');return;
 }
 if(a==='layer-inspect'){if(!cp())throw Error('Save a World first.');layerDrafts.delete(layerKey());await next('scene-layer-inspect',{request:{version:'scene-layer-v1',layer:s().stage,requestId:'run_'+crypto.randomUUID(),checkpointId:cp().id,sha256:cp().sha256}});await load();return;}
 if(a==='layer-camera'){modal('Create a camera',cameraForm(currentLayerDraft(),esc),b('Save new camera','layer-camera-save',{},'primary'),'Cancel');return;}
 if(a==='layer-ready'){
  const text=s().stage==='light'?'Have you reviewed real lighting for every affected shot ('+(s().shots||[]).map(x=>x.name).join(', ')+')? Lights are shared scene state.':'Have you reviewed every named shot’s camera, framing and timing?';
  if(!confirm(text+' Mark this layer ready and continue?'))return;await next('approve',{stage:s().stage,checkpointId:cp().id});target=null;await load();return;
 }
 if(a==='action-draft-save'||a==='action-draft-discard'){
  const destination=draftDestination;if(!destination)return;
  if(a==='action-draft-save')await saveActionDraft();else{currentActionDraft()?.discard();actionDrafts.delete(projectId+':'+sceneId);}
  draftDestination=null;close();await dispatch(destination.action,destination.data);return;
 }
 if(a==='action-discard'){if(actionSave)throw Error('Wait for the Save receipt.');currentActionDraft()?.discard();actionDrafts.delete(projectId+':'+sceneId);clearSceneViewer();await load();return;}
 if(a==='action-undo'){currentActionDraft()?.undo();render();return;}
 if(a==='action-save'){await saveActionDraft();return;}
 if(a==='action-hold-all'){const draft=currentActionDraft();draft.holdAll(sceneViewer?.currentFrame??draft.audit.reference_frame);render();return;}
 if(actionSave&&worldActionNeedsSave(a))throw Error('Action Save is still running. Refresh status or inspect its receipt.');
 if(currentActionDraft()?.dirty&&worldActionNeedsSave(a)){
  draftDestination={action:a,data:{...d}};modal('Keep your Action changes?','<p>Save the local motion choices before continuing, or discard only this draft. Your saved scene stays intact.</p>',b('Discard & continue','action-draft-discard',{},'ghost')+b('Save & continue','action-draft-save',{},'primary',currentActionDraft().checkpointId!==cp()?.id||currentActionDraft().sha256!==cp()?.sha256),'Stay here');return;
 }
 if(a==='action-inspect'){
  if(!cp())throw Error('Save a World first.');
  actionDrafts.delete(projectId+':'+sceneId);
  await next('action-inspect',{request:{version:'action-layer-v1',requestId:'run_'+crypto.randomUUID(),checkpointId:cp().id,sha256:cp().sha256}});await load();return;
 }
 if(a==='action-ready'){
  if(!confirm('Have you reviewed this exact saved performance over time, or chosen a static scene? Mark Action ready and continue to Shots?'))return;
  await next('approve',{stage:'action',checkpointId:cp().id});target=null;await load();return;
 }
 if(a==='world-draft-stay'){draftDestination=null;close();render();return;}
 if(a==='world-draft-save'||a==='world-draft-discard'){
   const destination=draftDestination;if(!destination)return;
   if(a==='world-draft-save')await saveWorldDraft();else sceneViewer?.discard();
   draftDestination=null;close();await dispatch(destination.action,destination.data);return;
 }
 if(a==='world-discard-draft'){if(worldSave)throw Error('Wait for the Save receipt before discarding.');sceneViewer?.discard();await load();return;}
 if(worldSave&&worldActionNeedsSave(a))throw Error('Save is still running. Refresh status or inspect its receipt first.');
 if(sceneViewer?.dirty&&worldActionNeedsSave(a)){
   draftDestination={action:a,data:{...d}};browser.close();
   modal('Keep your placement changes?', '<p>You have an unsaved visual draft. Save it before continuing, or discard only these placement edits. The previous scene file stays intact.</p>',b('Discard & continue','world-draft-discard',{},'ghost')+b('Save & continue','world-draft-save',{},'primary',sceneViewerKey!==sceneViewKey()),'Stay here');
   return;
 }
 if(a==='world-prepare-inspect'){
  if(s()?.stage!=='world'||!cp()||s().candidate)throw Error('Save or undo the current World draft before checking placement.');
  const inspected=preparationInspection(state.runs,s(),cp());if(inspected){showWorldPreparation(inspected);return;}
  const request={version:'world-prepare-v1',requestId:'run_'+crypto.randomUUID(),checkpointId:cp().id,sha256:cp().sha256};
  pendingPreparation={projectId,sceneId,...request};
  try{await next('world-prepare-inspect',{request});}catch(error){pendingPreparation=null;throw error;}
  await load();return;
 }
 if(a==='world-prepare-confirm'){
  const run=preparationInspection(state.runs,s(),cp());
  if(!run||run.id!==d.run||s().candidate)throw Error('Placement inspection is stale. Close this review and inspect again.');
  const groups=preparationSelection(run,Array.from($('dialog').querySelectorAll('[name="world-prepare-group"]:checked'),n=>n.value));
  await next('world-prepare',{request:{version:'world-prepare-v1',requestId:'run_'+crypto.randomUUID(),checkpointId:cp().id,sha256:cp().sha256,inspectionId:run.id,audit_sha256:run.inspection.sha256,groups}});
  close();await load();return;
 }
 if(a==='library-add'){await enqueueWorldAsset({...d,kind:'catalog'});return;}
 if(a==='library-prepare'){await enqueueWorldAsset({...d,kind:'source'});return;}
 if(a==='world-add'){await enqueueWorldAsset({...d,file:d.file||($('dialog').open?$(d.kind==='source'?'source-file':'catalog-file')?.value:undefined)});return;}
 if(a==='save-world'||a==='world-undo'){if(additions.state().count)throw Error('Wait for the additions to finish before saving or undoing.');if(a==='save-world'&&sceneViewer?.dirty){await saveWorldDraft();return;}if(a==='world-undo'&&sceneViewer?.draft?.canUndo){sceneViewer.undo();syncWorldDraftUI();return;}await next(a==='save-world'?'keep-building':'world-undo');close();browser.close();await load();return;}
 if(a==='world-use-confirm'){
   if(addPrompt?.kind!=='use'||!$('world-use-confirm').checked)throw Error('Check permission only if you have the right to use these assets.');
   const prompt=addPrompt;
   if(projectId!==prompt.projectId||state.sourceUse.scopeHash!==prompt.scopeHash)throw Error('Source scope changed. Cancel and review it again.');
   await api('workbench/attest-sources',{projectId:prompt.projectId,sceneId,revision:prompt.revision,confirmed:true});finishAddPrompt(true);close();return;
 }
 if(a==='world-collections-selected'||a==='world-collections-all'){
   if(addPrompt?.kind!=='collections')throw Error('Collection request is no longer active.');
   const names=a==='world-collections-all'?addPrompt.names:Array.from(document.querySelectorAll('[name="world-collection"]:checked'),n=>n.value);
   if(!names.length)throw Error('Choose at least one collection or cancel.');finishAddPrompt(names);close();return;
 }
 if(a==='source-prepare'&&addPrompt?.kind==='prepare'){if(!$('prepare-confirm').checked)throw Error('Confirm rights or cancel this addition.');finishAddPrompt(true);close();return;}
 if(a==='viewer-open'){clearAssetViewer();assetViewer=startViewer($('dialog').querySelector('[data-viewer-host]'),{kind:d.kind,id:d.id,version:d.version,file:$(d.kind==='catalog'?'catalog-file':'source-file').value});return;}
 if(a==='library-scene'){close();browser.close();await load();const host=document.querySelector('[data-scene-viewer]');host?.scrollIntoView({block:'center',behavior:'auto'});if(host&&!sceneViewer)showSceneViewer(host);const names=objects().filter(o=>o.asset_id===d.id).map(o=>o.name);notice(names.length?'Observed in this saved view: '+names.slice(0,8).join(', ')+(names.length>8?'…':''):'This checkpoint has no verified presence for this asset. Inspect it before adding another copy.');return;}
 if(a==='source-prepare-form'){const file=$('source-file')?.value,source=await api('workbench/source-detail?'+new URLSearchParams({projectId,sourceId:d.id}));if(source.version!==d.version)throw Error('Source changed. Reopen the package before preparing.');if(!file)throw Error('Choose an exact supported source member.');const view=preparationDialog({source,file,esc,b});browser.close();modal('Prepare & add',view.body,view.buttons,'Cancel');$('dialog').classList.add('preparation-dialog');$('dialog').dataset.returnLibrary='true';return;}
 if(a==='source-prepare'){const confirmed=$('prepare-confirm').checked;if(!confirmed)throw Error('Confirm only if you have the right to use this asset; otherwise cancel.');await next('source-prepare',{request:{id:d.id,version:d.version,file:d.file,confirmation:'local-project-use-v1',confirmed}});close();browser.close();await load();notice('Checking a separate package copy in Blender. When ready, continue with source-use review and import. Nothing has been added to the scene yet.');return;}
 if(a==='scene-viewer'){showSceneViewer(document.querySelector('[data-scene-viewer]'));return;}
 if(a==='close'||a==='dismiss'){draftDestination=null;const back=$('dialog').dataset.returnLibrary==='true';close();if(back)await browser.open();return;}
 if(a==='world-ingredients'){modal('Chosen ingredients',library(),'', 'Back to World');return;}
 if(a==='world-details'){modal('Scene details',`<p>${esc(p().brief||'No production intent recorded.')}</p>${cp()?'<details><summary>Saved checkpoint and observed contents</summary><pre>'+esc(JSON.stringify(cp(),null,2))+'</pre></details>':''}`+runList(s()),'', 'Back to World');return;}
 if(a==='archived-productions'){overview=await api('state?compact=true');modal('Archived productions',trashView({trash:overview.trash,esc,b}).body);return;}
 if(a==='restore-production'){if(!confirm('Restore this production to its original project folder? Existing files will not be overwritten.'))return;await api('projects/restore',{projectId:d.id});projectId=d.id;close();await load();return;}
 if(a==='archive-production'){const chosen=archiveTarget({projects:overview.projects,current:p(),id:d.id});if(!confirm(archiveConfirmation(chosen)))return;await api('projects/trash',{projectId:chosen.id,revision:chosen.revision});if(projectId===chosen.id){projectId=null;sceneId=null;close();}await load();return;}
 if(a==='diagnostics'){const detail=await api('project?projectId='+projectId);modal('Production diagnostics',diagnosticsView({detail,esc,b,locked:state.locked}).body);return;}
 if(a==='verify-sources'){const result=await api('projects/verify',{projectId});$('source-verification').textContent=result.ok?'Source files verified. This is not a rights or creative approval.':'Source files changed or missing. Inspect source identities before continuing.';return;}
 if(a==='audit-saved'){await api('projects/audit',{projectId,scene:$('diagnostic-scene').value});await load();await dispatch('diagnostics',{});return;}
 if(a==='new-production'){modal('New production','<label>Name<input id="new-name" maxlength="100"></label><label>Production intent (optional)<textarea id="new-brief" maxlength="10000" rows="3"></textarea></label>',b('Create production','save-production',{},'primary'));return;}
 if(a==='save-production'){const v=await api('projects/create',{name:$('new-name').value,brief:$('new-brief').value});projectId=v.id;close();await load();return;}
 if(a==='project'){projectId=d.id;sceneId=null;tab='scenes';await load();return;}
 if(a==='picker'){projectId=null;state=null;render();return;}
 if(a==='new-scene'){modal('Create a scene','<p>Its world, performance, shots, lights and renders stay together.</p><label>Scene name<input id="new-name" maxlength="100"></label>',b('Create scene','save-scene',{},'primary'));return;}
 if(a==='save-scene'){const v=await next('create',{name:$('new-name').value});sceneId=v.sceneId;tab='scenes';close();await load();return;}
 if(a==='scene'||a==='edit-source'){returnToFilm=a==='edit-source';if(returnToFilm)rememberFilmPosition();sceneId=d.id;target=null;tab='scenes';await load();if(a==='edit-source'&&d.shot!==undefined){await next('shot-select',{shotId:d.shot||null});await load();}return;}
 if(a==='return-film'){returnToFilm=false;tab='film';await load();return;}
 if(a==='tab'){tab=d.tab;render();return;}
 if(a==='stage'){await next('enter',{stage:d.stage});target=null;await load();return;}
 if(a==='new-shot'||a==='edit-shot'){modal(a==='edit-shot'?'Revise shot':'Save camera as shot',shotEditor({scene:s(),checkpoint:cp(),id:d.id,esc}),b('Save shot','save-shot',{id:d.id||''},'primary'));return;}
 if(a==='save-shot'){const previous=shotFor(s(),d.id),shot={name:$('shot-name').value,camera:$('shot-camera').value,start:Number($('shot-start').value),end:Number($('shot-end').value),...(previous?{id:previous.id,revision:previous.revision}:{})};await next('shot-save',{shot});close();target=null;await load();return;}
 if(a==='lighting-open-shot'){close();await dispatch('select-shot',{id:d.id});return;}
 if(a==='select-shot'||a==='scene-context'){await next('shot-select',{shotId:a==='scene-context'?null:d.id});target=null;await load();return;}
 if(a==='target'){target=d.name;render();return;}
 if(a==='refresh'){thumbnails.clear();await load();return;}
if(a==='browse-assets'){close();await browser.open({...(d.selected==='true'?{selected:true}:{}),all:d.all==='true'});return;}
 if(await browser.dispatch(a,d))return;
if(a==='source-preview-detail'){await dispatch('source-detail',{...d,preview:'true'});return;}
if(a==='catalog-preview-detail'){await dispatch('catalog-detail',{...d,preview:'true'});return;}
if(a==='source-detail'){const source=await api('workbench/source-detail?'+new URLSearchParams({projectId,sourceId:d.id}));const view=sourceDialog({source,scene:s(),locked:state.locked,esc,b});modal(source.name,view.body,view.buttons,'Back to browser');if(d.preview==='true'){const button=$('dialog').querySelector('[data-action="viewer-open"]');if(button)await dispatch('viewer-open',button.dataset);}return;}
 if(a==='catalog-label'){await next('catalog-label',{request:{assetId:d.id,version:d.version,subcategory:$('asset-subcategory').value}});await load();await dispatch('catalog-detail',{id:d.id});return;}
 if(a==='catalog-detail-select'){const back=$('dialog').dataset.returnLibrary;await next('catalog-select',{assetId:d.id,selected:!(s().catalog||[]).includes(d.id)});await load();await dispatch('catalog-detail',{id:d.id,back});return;}
 if(a==='asset-preview-open'){const status=$('asset-preview-status');status.textContent='Verifying and copying this exact package, then preparing Blender. This may take up to three minutes; no scene changes or rendering.';try{const r=await next('asset-preview',{request:{kind:d.kind,id:d.id,version:d.version,file:$(d.kind==='catalog'?'catalog-file':'source-file').value}});status.textContent=r.message+' Observed '+r.objects+' objects and '+r.takes+' bound takes.';}catch(e){status.textContent=e.message;status.className='note warn';}return;}
 if(a==='catalog-select'){await next('catalog-select',{assetId:d.id,selected:!(s().catalog||[]).includes(d.id)});await load();return;}
 if(a==='catalog-detail'){const back=browser.isOpen||d.back==='true',asset=await api('workbench/catalog-detail?'+new URLSearchParams({projectId,assetId:d.id}));if(d.expectedVersion&&asset.version!==d.expectedVersion)throw Error('The prepared catalog version changed. Inspect its current evidence before choosing a new version.');const view=catalogDialog({asset,scene:s(),locked:state.locked,queueCount:additions.state().count,sourceReady:state.sourceUse?.ready,fileChoice:d.file,esc,b});if(s().stage==='world')browser.close();modal(asset.title,view.body,view.buttons,back?'Back to assets':'Back to World');$('dialog').dataset.catalogId=d.id;$('dialog').dataset.returnLibrary=String(back);if(s().stage==='world')$('dialog').classList.add('world-asset-dialog');if(d.preview==='true'||(s().stage==='world'&&view.autoPreview)){const button=$('dialog').querySelector('[data-action="viewer-open"]');if(button)await dispatch('viewer-open',button.dataset);}return;}
 if(a==='catalog-inspect'||a==='catalog-import'){const file=$('catalog-file').value,operation=a==='catalog-import'?'import':'asset-contents',selection=Array.from(document.querySelectorAll('[name="catalog-collection"]:checked'),n=>n.value);const run=async()=>{const status=$('catalog-operation-status');status.hidden=false;status.textContent='Checking source files and preparing the Blender job. Originals and previous checkpoints stay unchanged.';await next('catalog-job',{request:{assetId:d.id,file,operation,...(operation==='import'&&file.toLowerCase().endsWith('.blend')?{selection}:{}),confirmed:operation==='import'}});};if(operation==='import'){const result=await addWorldAsset({selected:(s().catalog||[]).includes(d.id),confirm:()=>confirm('Add this exact source to a NEW World change? This may add another copy if it is already present. Originals and previous checkpoints stay unchanged. You will review the result before keeping it.'),pin:()=>next('catalog-select',{assetId:d.id,selected:true}),reload:async()=>{await load();return state;},sourceReady:state.sourceUse?.ready===true,run});if(result==='cancelled')return;if(result==='needs-rights'){close();browser.close();await load();notice('Asset chosen, not imported. Review source use, then choose Add to world again.');return;}}else{if(!(s().catalog||[]).includes(d.id)){await next('catalog-select',{assetId:d.id,selected:true});await load();}await run();}close();browser.close();await load();return;}
 if(a==='keep-building'){if(s().stage!=='world'&&!confirm('Keep this reviewed checkpoint and stay in the same activity?'))return;await next('keep-building');await load();return;}
if(a==='scan'){if(!confirm('Rescan the original database packages? This updates the source registry; existing pins and originals are preserved.'))return;await api('library/scan',{});thumbnails.clear();await load();return;}
 if(a==='source'){await next('source',{sourceId:d.id,selected:!s().sources.includes(d.id)});if($('dialog').open)close();await load();return;}
 if(a==='task'||a==='action-rig'){const shot=shotFor(s()),context={targets:s().stage==='world'?sceneViewer?.targets()||[]:s().stage==='action'?currentActionDraft()?.selected?[currentActionDraft().selected]:[]:s().stage==='light'&&currentLayerDraft()?.selected?[currentLayerDraft().selected]:target?[target]:[],...viewerTaskFrame(s(),sceneViewer?.currentFrame),...(s().stage==='action'&&currentActionDraft()?.selected?{actionContext:currentActionDraft().handoff(sceneViewer?.currentFrame),rigControls:a==='action-rig'}:{}),camera:shot&&['shots','light','render'].includes(s().stage)?shot.camera:s().stage==='shots'?target:null};await next('task-open',{context});await load();return;}
 if(a==='focus-task'){const r=await next('task-focus');notice(r.focused?'Blender task focused.':r.message||'Task window requested; select it on the taskbar.');return;}
 if(a==='collect'){await next('task-collect');await load();return;}
 if(a==='approve'){if(!confirm('Have you inspected this saved checkpoint in Blender? Keep it for '+activityName(s().stage)+'?'))return;await next('approve',{stage:s().stage,checkpointId:cp().id});target=null;await load();return;}
 if(a==='discard'){await next('discard');await load();return;}
 if(a==='inspect-candidate'){await next('inspect',{checkpointId:cp().id});return;}
 if(a==='import'){modal('Import a saved working scene',`<p>Copies the file to a new frozen checkpoint. Originals and their relative asset paths are preserved. This is not an approval.</p><label>Project Scenes folder<select id="import-file">${state.savedScenes.map(f=>`<option value="${esc(f)}">${esc(f.slice(7))}</option>`).join('')}</select></label>`,b('Copy as candidate','save-import',{},'primary',!state.savedScenes.length));return;}
 if(a==='save-import'){await next('import',{sourceScene:$('import-file').value});close();await load();return;}
 if(a==='codex'){await next('codex',{context:s().stage==='action'&&currentActionDraft()?.selected?{actionContext:currentActionDraft().handoff(sceneViewer?.currentFrame)}:{}});modal('Specialist session requested','<p>Your configured Codex terminal receives this exact scene task and selected sources. Respond to its normal trust, source-use and job-review prompts. Save results to this project’s Scenes folder, then import the working scene here. This does not attach to the dedicated manual Blender task.</p>');return;}
 if(a==='preview'){const shot=shotFor(s());modal('One CPU preview frame',`<p>Produces a 640 × 360, 4-sample still from the displayed ${s().candidate?'unapproved candidate':'kept checkpoint'}. This does not keep the candidate or approve any activity. ${shot?'Shot: '+esc(shot.name)+' · '+esc(shot.camera)+'.':'An existing saved camera is required.'}</p><label>Frame<input id="preview-frame" type="number" value="${sceneViewer?.currentFrame??shot?.start??cp()?.audit?.frame_range?.[0]??1}"></label>`,b('Authorize preview','save-preview',{},'primary'));return;}
 if(a==='save-preview'){await next('run',{operation:'preview',options:{frame:Number($('preview-frame').value)},confirmed:true});close();await load();return;}
 if(a==='film-cut'){rememberFilmPosition();filmView.select(projectId,p().workbench,d.id);render();return;}
 if(a==='render-film'){await dispatch('tab',{tab:'film'});return;}
 if(a==='render-shots'){await dispatch('stage',{stage:'shots'});return;}
 if(a==='render-settings'){const panel=document.querySelector('details.output-settings');if(panel){panel.open=true;panel.scrollIntoView({block:'center'});}return;}
 if(a==='readiness'){await next('run',{operation:'render-readiness'});await load();return;}
 if(a==='render'){const chosen=selectedDevice(s().readiness?.data,cap,$('render-device')?.value??0);const options={camera:$('render-camera').value,...(chosen.backend==='CPU'?{}:{render_device:chosen})};for(const k of ['start','end','width','height','samples'])options[k]=Number($('render-'+k).value);if(!confirm(`Authorize ${deviceLabel(chosen,s().readiness?.data,cap)} render: ${options.camera}, frames ${options.start}–${options.end}, ${options.width}×${options.height}, ${options.samples} samples? The 900-second deadline remains enforced.`))return;await next('run',{operation:'render-frames',options,confirmed:true});await load();return;}
 if(a==='approve-render'){if(!confirm('Have you watched the real movie and accepted this exact output for use in the film?'))return;await next('approve-render',{renderId:d.id});await load();return;}
 if(a==='play-render'){modal('Rendered shot','<video id="review-video" controls playsinline></video>');const url=await mediaURL('render',d.id);blobs.push(url);$('review-video').src=url;return;}
 if(['add-clip','remove-clip','reorder'].includes(a)){const clips=[...p().workbench.film.clips];if(a==='add-clip')clips.push({sceneId:d.scene,renderId:d.id});if(a==='remove-clip')clips.splice(Number(d.index),1);if(a==='reorder'){const i=Number(d.index),j=i+Number(d.delta);[clips[i],clips[j]]=[clips[j],clips[i]];}await next('arrange',{clips});await load();return;}
 if(a==='build-film'){if(!confirm('Encode this exact ordered list of approved shots into a new silent film cut?'))return;filmView.followLatest(projectId);await next('assemble',{confirmed:true});await load();return;}
 if(a==='approve-cut'){if(!confirm('Have you watched the complete cut and approved this exact movie?'))return;await next('approve-cut',{cutId:d.id});await load();return;}
 if(a==='download'){const url=await mediaURL('cut',d.id);blobs.push(url);const a=document.createElement('a');a.href=url;a.download=d.id+'.mp4';a.click();return;}
 if(a==='cut-record'){modal('Film provenance','<pre>'+esc(JSON.stringify(p().workbench.film.cuts.find(c=>c.id===d.id),null,2))+'</pre>');return;}
 if(a==='history'){modal('Scene checkpoints',s().checkpoints.map(c=>`<div class="checkpoint-row"><div><h3>${esc(c.path)}</h3><p>${esc(activityName(c.stage))} · ${c.id===s().current?'Current':c.id===s().candidate?'Candidate':'Historical'}</p><small>${esc(c.sha256)}</small></div></div>`).join('')||'<p>No saved checkpoints yet.</p>');return;}
 if(a==='source-review'){const use=state.sourceUse;modal('Review production source use',`<pre>${esc(use.message)}</pre><p>${esc(use.notice)}</p><p>Confirm only when you have rights to use and adapt all sources below for this production. This excludes future files, raw redistribution and model training. Folder names alone do not establish origin or rights.</p>${use.scope.sources.map(a=>`<div class="section"><h3>${esc(a.relative)}</h3><pre>${esc(a.version)}</pre></div>`).join('')}<p>Cancel or uncertainty leaves rendering blocked. The application does not supply a default answer.</p>`,b('I confirm this exact project use','source-confirm',{},'primary'));return;}
 if(a==='source-confirm'){await next('attest-sources',{confirmed:true});close();await load();return;}
 if(a==='preview-storage'){
  previewStoragePlan=null;modal('Preview storage','<p role="status">Checking disposable copies and their originals. Nothing is being removed…</p>');
  const plan=await api('viewer-cache/plan',{});previewStoragePlan=plan;const view=previewStorageView(plan,esc,b);modal('Preview storage',view.body,view.buttons,'Keep everything');return;
 }
 if(a==='preview-storage-apply'){
  if(!previewStoragePlan)throw Error('Review preview storage first.');
  if(!confirm(storageConfirmation(previewStoragePlan)))return;
  const result=await api('viewer-cache/apply',{id:previewStoragePlan.id,digest:previewStoragePlan.digest,confirmed:true,closedNativePreviews:true});previewStoragePlan=null;
  modal('Preview storage',`<p role="status">${esc(result.message)}</p>${result.error?'<p class="warn">'+esc(result.error)+'</p>':''}<p>Removal journal: <code>${esc(result.journal)}</code> inside ViewerPreviews.</p>`,'','Done');return;
 }
 if(a==='settings'){modal('Local studio',`<p>This is the Asset Director workbench. No Vercel server, private asset upload, remote-control port or model service is required.</p><p>Executable paths remain in <code>SystemRuntime/UserData/Launcher/config.json</code>. Add absolute <code>ffmpeg</code> and <code>ffprobe</code> paths for silent movie encoding. Runtime updates use verified staging and reversible replacement; project data stays separate.</p>${p()?'<label>Production intent<textarea id="production-intent" rows="3" maxlength="10000">'+esc(p().brief)+'</textarea></label>':''}${b('Preview storage','preview-storage',{},'ghost')}${p()?b('Production diagnostics','diagnostics',{},'',state.locked)+b('Archive production','archive-production',{},'ghost',state.locked):''}<details><summary>Capability response</summary><pre>${esc(JSON.stringify(cap,null,2))}</pre></details>`,p()?b('Save intent','save-intent',{},'',state.locked):'');return;}
 if(a==='save-intent'){await api('projects/update',{projectId,revision:p().revision,brief:$('production-intent').value});close();await load();return;}
 if(a==='recover'){const run=state.runs.find(r=>r.id===d.run);modal('Task evidence and recovery',`<pre>${esc(JSON.stringify(run||{id:d.run,message:'Refresh or inspect the Runs folder for this record.'},null,2))}</pre><p>Do not resolve a task while Blender or the native worker is still using it. Recovery records your confirmation and retains every file; it does not kill a process or repair native job evidence.</p>`,`${run?.jobId&&['FAILED','INTERRUPTED'].includes(run.state)?b('Reset failed native job for retry','retry',{job:run.jobId}):''}${b('I stopped it · resolve task','resolve',{run:d.run,scene:run?.sceneId||''},'',run?.state==='SUCCEEDED')}`);return;}
 if(a==='retry'){if(!confirm('Archive the failed native attempt using job-retry? Starting it again is a separate action.'))return;await next('retry',{jobId:d.job,confirmed:true});close();await load();return;}
 if(a==='resolve'){if(!confirm('Confirm you stopped the external Blender task or encoder. The launcher does not terminate it for you.'))return;await next('resolve',{sceneId:d.scene||null,runId:d.run,confirmStopped:true});close();await load();return;}
}
document.addEventListener('click',e=>{const button=e.target.closest('button[data-action]');if(button&&!button.disabled)perform(()=>dispatch(button.dataset.action,button.dataset));});
document.addEventListener('input',e=>{if(e.target.dataset.renderSetting){editOutputSetting(e.target);return;}if(!e.target.dataset.layerField||e.target.dataset.layerField==='selected')return;e.target.setCustomValidity('');try{editLayerField(e.target);}catch(error){e.target.setCustomValidity(error.message);}syncLayerDraftUI();});
document.addEventListener('change',e=>{if(e.target.id==='film-cut'){perform(()=>dispatch('film-cut',{id:e.target.value}));return;}if(e.target.dataset.renderSetting){editOutputSetting(e.target);return;}if(e.target.id==='lighting-evidence-shot'||e.target.id==='lighting-evidence-before'){perform(()=>dispatch('lighting-evidence',{shot:$('lighting-evidence-shot').value,before:e.target.id==='lighting-evidence-before'?e.target.value:undefined,page:e.target.id==='lighting-evidence-before'?$('dialog').dataset.evidencePage:0}));return;}if(e.target.dataset.layerField){e.target.setCustomValidity('');try{editLayerField(e.target);notice('');}catch(error){e.target.setCustomValidity(error.message);notice(error.message);}currentLayerDraft()?.finishEdit();syncLayerDraftUI();return;}if(e.target.dataset.actionField){try{editActionField(e.target.dataset.actionField,e.target.value);}catch(error){notice(error.message);}return;}if(e.target.id==='world-use-confirm'){const button=$('dialog').querySelector('[data-action="world-use-confirm"]');if(button)button.disabled=!e.target.checked||busy;}if(e.target.id==='prepare-confirm'){const button=$('dialog').querySelector('[data-action="source-prepare"]');if(button)button.disabled=!e.target.checked||busy;}if(e.target.id==='scene-picker')perform(()=>dispatch('scene',{id:e.target.value}));if(['browser-kind','browser-scope','browser-activity','browser-subcategory'].includes(e.target.id))perform(()=>dispatch(e.target.id,{value:e.target.value}));});
document.addEventListener('submit',e=>{if(e.target.id==='browser-search'){e.preventDefault();perform(()=>dispatch('browser-search',{}));}});
document.addEventListener('change',e=>{if(e.target.name==='world-prepare-group'){const button=$('dialog').querySelector('[data-action="world-prepare-confirm"]');if(button){const count=$('dialog').querySelectorAll('[name="world-prepare-group"]:checked').length;button.disabled=busy||count<1||count>64;}}});
let lastObservationAt=Date.now();
const pollStatus=statusPoller();
setInterval(async()=>{
 if(!projectId||!state||busy||$('dialog').open||browser.isOpen||!state.locked)return;
 const selectedProject=projectId,selectedScene=sceneId;
 try {
  const v=await pollStatus(!!s()?.run,Date.now(),async()=>{
   if(s()?.task) {
    try {const result=await api('workbench/task-sync',{projectId:selectedProject,sceneId:selectedScene,revision:p().revision});if(result.changed)notice(result.message,'success');}
    catch(e){notice(e.message);}
   }
   return api('workbench/state?projectId='+encodeURIComponent(selectedProject)+'&compact=true');
  });
  if(!v)return;
  if(projectId!==selectedProject||sceneId!==selectedScene||busy||$('dialog').open)return;
  const at=Date.now();
  const changed=v.project.revision!==p().revision||v.locked!==state.locked||progressKey(v.runs)!==progressKey(state.runs)||
    observationKey(v.taskStatuses?.[sceneId],s()?.task,at)!==observationKey(state.taskStatuses?.[sceneId],s()?.task,lastObservationAt);
  acceptSnapshot(v);lastObservationAt=at;
  if(changed){render();scheduleActionInspection();scheduleLayerInspection();scheduleWorldPreparation();}
 }catch(e){notice(e.message);}
},500);
if(!token){notice('Open the desktop launcher or its Start shortcut to establish a local session.');$('app').innerHTML='<div class="empty"><h1>Local session required</h1><p>The workbench does not accept a public or unauthenticated studio connection.</p></div>';}else perform(async()=>{cap=await api('workbench/capabilities');await load();});
