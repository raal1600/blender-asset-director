const $ = id => document.getElementById(id);
let token = location.hash.slice(1) || sessionStorage.getItem('ad-token');
if (token) {sessionStorage.setItem('ad-token',token);history.replaceState(null,'',location.pathname);}
let state, current, detail, blender, verification, preview;
let wizardStep=2, activeView="workspace";
let selected = localStorage.getItem('ad-project');
function node(tag,text,cls) {const e=document.createElement(tag);if(text !== undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function notice(text,error=false) { $('notice').textContent=text;$('notice').className=error?'error':'';$('notice').hidden=false; }
async function api(route,data) {
  const r=await fetch('/api/'+route,{method:data===undefined?'GET':'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},...(data===undefined?{}:{body:JSON.stringify(data)})});
  const value=await r.json();if(!r.ok)throw new Error(value.error);return value;
}
async function action(fn) {
  if(document.body.classList.contains('busy'))return; $('notice').hidden=true;
  document.body.classList.add('busy'); const buttons=[...document.querySelectorAll('button')]; const prior=buttons.map(b=>b.disabled); buttons.forEach(b=>b.disabled=true);
  try {await fn();} catch(e){notice(e.message,true);} finally {buttons.forEach((b,i)=>b.disabled=prior[i]);document.body.classList.remove('busy');if(current)renderWizard();}
}
function view(name) {activeView=name;moveLibrary();for(const e of document.querySelectorAll('.view'))e.hidden=e.id!==name;for(const e of document.querySelectorAll('.nav'))e.classList.toggle('active',e.dataset.view===name);$('page-crumb').textContent=name==='workspace'?'PROJECTS':name==='library'?'SHARED LIBRARY':'SYSTEM';}
const bytes=n=>n>1024*1024?`${(n/1024/1024).toFixed(1)} MB`:`${Math.ceil(n/1024)} KB`;
const glyph=kind=>({Animations:'∿',Characters:'♙',Meshes:'▱'}[kind]||'◇');
function requireProject(){if(!current)throw new Error('Select or create a project first.');return current.id;}
async function refresh() {
  state=await api('state');$('workspace-path').textContent=state.root;
  if(state.errors.length)notice(state.errors.map(e=>e.folder+': '+e.message).join('; '),true);
  if(!state.projects.some(p=>p.id===selected))selected=state.projects[0]?.id;
  renderProjects();renderLibrary();renderSystem();await selectProject(selected);
}
async function selectProject(id) {
  selected=id;verification=null;preview=null; if(id)localStorage.setItem('ad-project',id);
  current=state.projects.find(p=>p.id===id);
  if(current){detail=await api('project?projectId='+encodeURIComponent(id));if(selected!==id)return;current=detail.project;}
  wizardStep=current?.onboarding?.step||(detail?.scenes?.length?6:2);
  renderProjects();renderProject();renderLibrary();
  if(current&&wizardStep===5)await loadPreview();
}
function renderProjects(){const list=$('project-list');list.replaceChildren();$('project-picker').replaceChildren();for(const p of state.projects){const b=node('button',p.name,p.id===selected?'selected':'');b.onclick=()=>action(async()=>{await saveDraft();await selectProject(p.id);view('workspace');});const row=node('div',undefined,'project-selector-row');row.append(b);const menu=node('details',undefined,'project-menu');const summary=node('summary','...');summary.setAttribute('aria-label','Project menu: '+p.name);menu.append(summary);const remove=node('button','Move project to Trash','trash-action');remove.onclick=()=>{menu.open=false;if(!confirm('Move "'+p.name+'" to Trash? Close this project in Blender or Codex first. Its folder will be recoverable in Archive/Trash; shared assets and job evidence stay intact.'))return;action(async()=>{await api('projects/trash',{projectId:p.id,revision:p.revision});await refresh();notice('Project moved to Trash. Restore it from System > Project Trash.');});};menu.append(remove);row.append(menu);list.append(row);$('project-picker').append(new Option(p.name,p.id));}$('project-picker').value=selected||'';}
function renderProject(){
  $('project-empty').hidden=!!current;$('project-content').hidden=!current;$('project-title').textContent=current?.name||'Projects';
  $('project-subtitle').textContent=current?'From a first idea to a scene you can review.':'A clear home for every scene, source, and output.';
  if(!current)return;
  $('metric-assets').textContent=current.assets.length;$('metric-scenes').textContent=detail.scenes.length;$('metric-jobs').textContent=current.jobs.length;
  $('edit-project-name').value=current.name;$('project-directory').textContent=current.directory;
  $('brief').value=current.brief;$('project-short-id').textContent='PROJECT / '+current.id.slice(4,12);
  $('scene-select').replaceChildren(new Option('No saved scene selected',''));for(const s of detail.scenes)$('scene-select').append(new Option(s.slice(7),s));$('scene-select').value=current.scene||'';
  $('project-assets').replaceChildren();
  if(!current.assets.length)$('project-assets').append(node('div','No sources linked yet. Choose from the shared library when you know what this project needs.','empty'));
  for(const ref of current.assets){
    const source=state.inventory.sources.find(x=>x.id===ref.sourceId);const row=node('div',undefined,'asset-row');row.append(node('span',glyph(source?.kind),'asset-glyph'));
    const text=node('div',undefined,'row-main');text.append(node('strong',source?.name||ref.sourceId),node('small',`${source?.kind||'Source'} · Version ${ref.version.slice(0,10)} · Review required`));row.append(text);
    const checked=verification?.assets.find(a=>a.sourceId===ref.sourceId);const stale=source?.version!==ref.version || !source?.available;
    row.append(node('span',checked?.status||(stale?'Refresh needed':'Pinned'),`badge ${checked?.status==='VERIFIED'?'good':stale?'warn':''}`));
    const remove=node('button','Unlink','text-button');remove.title='Remove this project reference; keep the shared original';remove.onclick=()=>action(async()=>{await api('projects/detach',{projectId:current.id,sourceId:ref.sourceId,revision:current.revision});await refresh();notice('Reference removed. The shared source is still in the database.');});row.append(remove);$('project-assets').append(row);
  }
  renderCapabilities();renderWizard();
  $('jobs').replaceChildren();if(!detail.jobs.length)$('jobs').append(node('div','No operations recorded for this project yet.','empty'));
  for(const j of detail.jobs){const row=node('div',undefined,'job-row'),text=node('div',undefined,'row-main');text.append(node('strong',j.operation),node('small',j.id));row.append(text,node('span',j.state,'badge '+(j.state==='SUCCEEDED'?'good':'')));$('jobs').append(row);}
  for(const r of (detail.runs||[]).filter(r=>r.state==='FAILED'||r.state==='UNAVAILABLE'||r.state==='PREPARING'||r.state==='RUNNING')){const row=node('div',undefined,'job-row'),text=node('div',undefined,'row-main');text.append(node('strong',r.action+' · '+new Date(r.startedAt).toLocaleString()),node('small',r.error||'Operation has not recorded completion. Inspect its receipt before retrying.'));row.append(text,node('span',r.state,'badge warn'));$('jobs').append(row);}
}
function renderLibrary(){
  if(!state)return;const {sources,scannedAt}=state.inventory;$('library-count').textContent=sources.filter(s=>s.available).length;
  $('library-time').textContent=scannedAt?'Last refreshed '+new Date(scannedAt).toLocaleString():'Refresh to discover local source packages.';
  $('link-target').textContent=current?'Link to: '+current.name:'Select a project to link sources.';
  const grid=$('source-grid');grid.replaceChildren();const query=$('search').value.toLowerCase(),kind=$('kind').value;
  for(const s of sources.filter(s=>(!kind||s.kind===kind)&&s.name.toLowerCase().includes(query))){
    const card=node('article',undefined,'source-card'),visual=node('div',undefined,'source-visual '+s.kind.toLowerCase());visual.append(node('span',glyph(s.kind)),node('small',s.kind));
    const content=node('div',undefined,'source-content');content.append(node('h3',s.name),node('p',s.relative));
    const meta=node('div',undefined,'source-meta');meta.append(node('span',`${s.fileCount} files · ${bytes(s.bytes)}`),node('span',s.available?'Unreviewed source':'Missing'));content.append(meta);
    const linked=current?.assets.some(a=>a.sourceId===s.id);const b=node('button',linked?'Linked to project':current?'Link to project':'Select a project first','button secondary');b.disabled=linked||!current||!s.available;
    b.onclick=()=>action(async()=>{await api('projects/attach',{projectId:requireProject(),sourceId:s.id,revision:current.revision});await refresh();notice('Source version linked. The original package stays in the database.');});content.append(b);card.append(visual,content);grid.append(card);
  }
  if(!grid.children.length)grid.append(node('div','No matching sources. Drop files into a source folder and refresh the library.','empty'));
}
function renderSystem(){
  if(!state)return;const trash=$('trash-list');trash.replaceChildren();for(const p of state.trash?.projects||[]){const row=node('div',undefined,'job-row'),text=node('div',undefined,'row-main');text.append(node('strong',p.name),node('small','Moved '+new Date(p.trashedAt).toLocaleString()));const restore=node('button','Restore','button secondary');restore.onclick=()=>action(async()=>{const restored=await api('projects/restore',{projectId:p.id});selected=restored.id;await refresh();view('workspace');notice('Project restored to its original folder.');});row.append(text,restore);trash.append(row);}if(!trash.children.length)trash.append(node('div','No projects in Trash.','empty'));for(const e of state.trash?.errors||[])trash.append(node('p',e.folder+': '+e.message));const container=$('system-cards');container.replaceChildren();const h=state.health;
  const cards=[['Harness',h?`v${h.version} · ${h.installed.status}`:'Not checked this session',h?'Python '+h.python:'Run Verify setup to check the installed package.',!!h],['Database',h?`${h.records} catalog records`:'Awaiting health check',h?.library||'Source inventory and the harness catalog are separate.',!!h],['Blender',blender?.connected?'Connected':'Not connected',blender?.connected?`Add-on ${blender.addon_version?.join('.')} · Protocol ${blender.protocol_version}`:'Start Blender with its existing MCP add-on.',!!blender?.connected]];
  for(const [title,status,description,ok]of cards){const p=node('section',undefined,'panel');p.append(node('div',title.toUpperCase(),'section-kicker'),node('h2',status),node('p',description),node('span',ok?'Verified':'Not yet verified','badge '+(ok?'good':'')));container.append(p);}
}
async function checkBlender(){blender=await api('blender');$('connection').textContent=blender.connected?'Blender connected':'Blender offline';$('connection').className='badge '+(blender.connected?'good':'');renderSystem();}
for(const b of document.querySelectorAll('.nav'))b.onclick=()=>action(async()=>{await saveDraft();view(b.dataset.view);});
for(const b of document.querySelectorAll('[data-folder]'))b.onclick=()=>action(async()=>{await api('folder',{projectId:current?.id,key:b.dataset.folder});});
for(const id of ['new-side','new-project'])$(id).onclick=()=>{$('create-dialog').showModal();$('project-name').focus();};
$('cancel-create').onclick=()=>$('create-dialog').close();
$('create-form').onsubmit=e=>{e.preventDefault();action(async()=>{await saveDraft();const p=await api('projects/create',{name:$('project-name').value,brief:''});selected=p.id;$('create-dialog').close();$('create-form').reset();await refresh();view('workspace');notice('Project created. Its scenes and outputs have their own folders.');});};
$('refresh').onclick=()=>action(async()=>{await saveDraft();await refresh();await checkBlender();notice('Workspace refreshed.');});
$('save-brief').onclick=()=>action(async()=>{await api('projects/update',{projectId:requireProject(),revision:current.revision,brief:$('brief').value});await refresh();notice('Brief saved.');});
$('scene-select').onchange=()=>action(async()=>{await api('projects/update',{projectId:requireProject(),revision:current.revision,scene:$('scene-select').value||null});await refresh();});
$('open-codex').onclick=()=>action(async()=>{if(!preview?.ready)throw new Error('Complete the brief and library steps first.');const r=await api('codex',{projectId:requireProject(),revision:preview.revision});await goStep(6);notice(r.message);});
for(const [id,openScene]of [['start-blender',false],['open-scene',true]])$(id).onclick=()=>action(async()=>{notice('Checking Blender…');const r=await api('blender/start',{projectId:requireProject(),openScene});notice(r.message);await checkBlender();});

$('scan-library').onclick=()=>action(async()=>{notice('Reading source packages and verifying file hashes…');await api('library/scan',{});await refresh();notice('Source library refreshed. Existing project references retain their pinned versions.');});
$('verify-assets').onclick=()=>action(async()=>{verification=await api('projects/verify',{projectId:requireProject()});renderProject();notice(!verification.assets.length?'This project has no linked source references yet.':verification.ok?'All linked source files match their pinned versions.':'Some project sources have changed or are missing.',!verification.ok);});
$('search').oninput=renderLibrary;$('kind').onchange=renderLibrary;
$('project-picker').onchange=()=>action(async()=>{const id=$('project-picker').value;await saveDraft();await selectProject(id);});
$('health-check').onclick=()=>action(async()=>{notice('Verifying harness installation and database…');await api('health',{});await refresh();await checkBlender();notice('Setup checks completed.');});
$('audit-scene').onclick=()=>action(async()=>{notice('Auditing the saved scene in background Blender. This can take a few minutes…');const r=await api('projects/audit',{projectId:requireProject()});await refresh();notice('Scene audit: '+r.state,r.state!=='SUCCEEDED');});
$('bind-form').onsubmit=e=>{e.preventDefault();action(async()=>{await api('projects/bind-job',{projectId:requireProject(),jobId:$('job-id').value.trim()});await refresh();notice('Harness job associated with this project.');});};
$('stop-launcher').onclick=()=>action(async()=>{await api('stop',{});notice('Launcher stopped. You can close this tab.');});

const stepNames=['Project','Describe','Capabilities','Library','Start Codex','Working scenes'];
function moveLibrary(){const host=activeView==='workspace'?$('wizard-library'):$('library');host.append($('library-browser'));}
function renderCapabilities(){
  const mode=current.capabilityMode||'auto';
  for(const input of document.querySelectorAll('[name="capability-mode"]'))input.checked=input.value===mode;
  const host=$('capability-options');host.replaceChildren();
  for(const group of [...new Set(state.capabilities.map(c=>c.group))]){
    const field=node('fieldset');field.append(node('legend',group));
    for(const c of state.capabilities.filter(c=>c.group===group)){
      const label=node('label',undefined,'capability-card'),input=node('input');input.type='checkbox';input.value=c.id;input.checked=(current.capabilities||[]).includes(c.id);input.disabled=mode==='auto';
      const text=node('span');text.append(node('strong',c.label),node('small',c.description));label.append(input,text);field.append(label);
    }host.append(field);
  }
  syncCapabilityMode();
}
function syncCapabilityMode(){const auto=document.querySelector('[name="capability-mode"]:checked')?.value==='auto';$('capability-options').classList.toggle('automatic',auto);for(const i of $('capability-options').querySelectorAll('input'))i.disabled=auto;}
for(const input of document.querySelectorAll('[name="capability-mode"]'))input.onchange=syncCapabilityMode;
function renderWizard(){
  const steps=$('wizard-steps');steps.replaceChildren();
  stepNames.forEach((name,index)=>{const number=index+1,b=node('button',undefined,number===wizardStep?'current':'');b.type='button';b.append(node('span',String(number),'step-number'),node('span',name));b.setAttribute('aria-label','Step '+number+': '+name);if(number===wizardStep)b.setAttribute('aria-current','step');b.onclick=()=>action(()=>goStep(number));steps.append(b);});
  for(const section of document.querySelectorAll('[data-step]'))section.hidden=Number(section.dataset.step)!==wizardStep;
  $('step-position').textContent='STEP '+wizardStep+' OF 6 / '+stepNames[wizardStep-1].toUpperCase();
  $('wizard-back').hidden=wizardStep===1;$('wizard-next').hidden=wizardStep>=5;
  $('wizard-next').textContent=wizardStep===4?'Review & continue':'Continue';
  $('wizard-hint').textContent=wizardStep===6?'Refresh this list after Codex saves a working scene.':wizardStep===5?'Start a new terminal when you are ready.':'Your progress is saved when you continue.';
  $('scene-empty').hidden=detail.scenes.length>0;$('open-scene').disabled=!current.scene||!detail.scenes.includes(current.scene);$('audit-scene').disabled=!current.scene;
  $('open-codex').disabled=!preview?.ready;
  const summary=$('launch-summary');summary.replaceChildren();
  for(const [label,value] of [['Brief',current.brief||'Add a brief in step 2.'],['Capabilities',current.capabilityMode==='selected'?(current.capabilities||[]).map(id=>state.capabilities.find(c=>c.id===id)?.label).join(', '):'Codex will propose the scope from your brief'],['Sources',current.assets.length+' linked source versions'],['Starting scene',current.scene||'New scene / no file selected']])summary.append(node('dt',label),node('dd',value));
  $('prompt-preview').textContent=preview?.prompt||'Loading the saved startup prompt...';moveLibrary();
}
async function loadPreview(){const id=current.id;const result=await api('codex/preview?projectId='+encodeURIComponent(id));if(current?.id!==id)return;preview=result;renderWizard();}
function draft(){
  if(!current||activeView!=='workspace')return {};
  if(wizardStep===1)return {name:$('edit-project-name').value};
  if(wizardStep===2)return {brief:$('brief').value};
  if(wizardStep===3)return {capabilityMode:document.querySelector('[name="capability-mode"]:checked').value,capabilities:[...$('capability-options').querySelectorAll('input:checked')].map(i=>i.value)};
  return {};
}
function hasDraft(){return Object.entries(draft()).some(([k,v])=>JSON.stringify(v)!==JSON.stringify(current[k]??(k==='capabilities'?[]:k==='capabilityMode'?'auto':undefined)));}
async function saveDraft(extra={}){
  if(!current)return;
  if(!Object.keys(extra).length&&!hasDraft())return;
  current=await api('projects/update',{projectId:current.id,revision:current.revision,...draft(),...extra});
  state.projects=state.projects.map(p=>p.id===current.id?current:p);
}
async function goStep(number){
  if(number===wizardStep)return;
  const brief=wizardStep===2?$('brief').value:current.brief;
  if(number>=3&&number<=5&&!brief.trim())throw new Error('Describe what you want to create before continuing.');
  const libraryReviewed=current.onboarding?.libraryReviewed||wizardStep===4&&number===5;
  if(number===5&&!libraryReviewed)throw new Error('Review the library in step 4 first. You can continue with no linked assets.');
  await saveDraft({onboarding:{step:number,libraryReviewed:!!libraryReviewed}});
  await refresh();view('workspace');
}
$('wizard-next').onclick=()=>action(()=>goStep(wizardStep+1));
$('wizard-back').onclick=()=>action(()=>goStep(wizardStep-1));
$('refresh-scenes').onclick=()=>action(async()=>{await refresh();notice('Working scene list refreshed.');});
window.addEventListener('beforeunload',e=>{if(hasDraft()){e.preventDefault();e.returnValue='';}});
if(!token)notice('Open the launcher using Start Launcher.ps1 or the desktop shortcut.',true);
else action(async()=>{await refresh();await checkBlender();});
