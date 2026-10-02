/** Progressive output presentation. No job, scene mutation or review is implied. */
import {shotFor,renderIsCurrent} from './workbench-lineage.mjs';
import {deviceControl,outputDevice,renderDevices} from './workbench-render-device.mjs';
import {taskBanner} from './workbench-task.mjs';
import {progressLabel} from './workbench-progress.mjs';
export function outputContext(scene,runs=[],locked=false){
 const checkpoint=scene.checkpoints.find(c=>c.id===scene.current)||null,shot=shotFor(scene);
 const ready=checkpoint&&scene.readiness?.checkpointId===checkpoint.id?scene.readiness.data:null;
 const rows=[...scene.renders].reverse().filter(r=>shot?r.shotId===shot.id:true);
 const movie=rows.find(r=>renderIsCurrent(scene,r)&&(!shot?!r.shotId:true))||null;
 return {checkpoint,shot,ready,rows,movie,active:locked||!!scene.task||!!scene.run,run:runs.find(r=>r.id===scene.run)};
}
export function outputPreferences(){
 const values=new Map(),key=(p,s,shot)=>JSON.stringify([p,s,shot||null]);
 return {get(p,s,shot){const k=key(p,s,shot);if(!values.has(k))values.set(k,{width:'640',height:'360',samples:'8',device:{backend:'CPU'}});return values.get(k);}};
}
export function outputValuesValid(draft,shot,ready,cap){
 const parse=value=>typeof value==='string'&&!value.trim()?NaN:Number(value),width=parse(draft.width),height=parse(draft.height),samples=parse(draft.samples);
 if(![width,height,samples].every(Number.isInteger)||width<16||width>1920||height<16||height>1080||width%2||height%2||samples<1||samples>128)return false;
 if(!shot||shot.end<shot.start||shot.end-shot.start>=360||width*height*samples*(shot.end-shot.start+1)>2e9)return false;
 return renderDevices(ready,cap).some(d=>d.backend===draft.device?.backend&&(d.backend==='CPU'||d.id===draft.device.id));
}
export function outputForm({scene,context,cap,draft,esc,b}){
 const {checkpoint,shot,ready,active}=context,blocked=!ready||ready.blockers.length>0;
 const check=b(ready?'Recheck saved scene':'Check saved-scene readiness','readiness',{},ready?'ghost':'primary',active||!checkpoint||!!scene.candidate||!cap?.render_frames);
 if(!checkpoint)return '<p>Save a World before rendering.</p>';
 if(!shot)return '<p>Choose a named shot above. Its saved camera and range will stay bound to this render.</p>';
 return check+(ready?'<p class="render-readiness">'+(blocked?'Needs attention':'Readiness checked for this saved checkpoint')+'</p>'+ready.blockers.map(x=>'<p class="note warn">'+esc(x)+'</p>').join(''):'')+
 (!blocked?'<div class="fields">'+deviceControl(ready,cap,esc,draft.device,active)+'<label class="full">Camera<select id="render-camera" disabled><option>'+esc(shot.camera)+'</option></select></label><label>First frame<input id="render-start" type="number" disabled value="'+shot.start+'"></label><label>Last frame<input id="render-end" type="number" disabled value="'+shot.end+'"></label>'+
 [['width','Width',16,1920,2],['height','Height',16,1080,2],['samples','Samples',1,128,1]].map(([key,label,min,max,step])=>'<label>'+label+'<input id="render-'+key+'" data-render-setting="'+key+'" type="number" min="'+min+'" max="'+max+'" step="'+step+'" value="'+esc(draft[key])+'" '+(active?'disabled':'')+'></label>').join('')+'</div><p>Each render writes a new movie. These delivery choices do not change the saved scene or approve its output.</p>'+
 b('Authorize & render this shot','render',{},'primary',active||!!scene.candidate||!cap?.encoder||!outputValuesValid(draft,shot,ready,cap)):'')+
 (!cap?.encoder?'<p class="note warn">Configure absolute FFmpeg and FFprobe paths to enable movie output. Nothing is installed automatically.</p>':'')+
 '<details><summary>Delivery limits and readiness details</summary><p>Silent H.264; 1–360 frames per shot; even dimensions up to 1920 × 1080; up to 2 billion pixel-samples and a 900-second Blender deadline. No audio, simulation, compositor/VSE delivery or automatic quality approval.</p><p>Keep frame rates and dimensions identical across film inputs. GPU selection is explicit; there is no automatic CPU fallback.</p>'+(ready?'<p>'+ready.dependencies.length+' external files checked. Source/dependency changes are checked again by the worker.</p>':'')+'</details>';
}
export function outputView({project,scene,stages,runs,locked,taskStatus,cap,draft,esc,b}){
 const context=outputContext(scene,runs,locked),{checkpoint,shot,rows,movie,active,run}=context,shots=scene.shots||[];
 const button=(label,action,data={},cls='',disabled=false)=>b(label,action,data,cls,active||disabled);
 const history=rows.filter(r=>r!==movie);
 const source='<section class="viewer-3d" data-scene-viewer aria-label="Saved shot in 3D"></section><p class="muted">Saved camera and geometry; approximate materials and lighting. This is not the rendered movie.</p>';
 const form=outputForm({scene,context,cap,draft,esc,b});
 return '<div class="world-top"><label>Scene<select id="scene-picker" aria-label="Selected scene">'+project.workbench.scenes.map(x=>'<option value="'+esc(x.id)+'" '+(x.id===scene.id?'selected':'')+'>'+esc(x.name)+'</option>').join('')+'</select></label><span class="grow"></span><details class="world-more"><summary>More</summary><div class="world-menu">'+b('Add scene','new-scene')+b('Checkpoint history','history')+button('Reviewed specialist','codex')+'</div></details></div>'+
 '<nav class="steps world-steps" aria-label="Activities in this scene">'+stages.map((st,i)=>b((scene.completed[st.id]?'✓ ':i+1+' ')+st.short,'stage',{stage:st.id},scene.stage===st.id?'active':'',active||!!scene.candidate||stages.slice(0,i).some(x=>!scene.completed[x.id]))).join('')+'</nav>'+
 '<section class="output-workspace" aria-label="Render layer"><header class="action-heading"><div><h1>Render and review</h1><p>Choose a shot, render its saved source, then watch the actual movie.</p></div>'+button('Inspect source in Blender','task',{},'ghost',!checkpoint||!!scene.candidate||!cap?.task_workspace)+'</header>'+
 (scene.task?taskBanner(scene,taskStatus,esc,b):'')+
 (run?'<div class="note" role="status"><strong>'+esc(run.action==='render-frames'?'Rendering / encoding the selected shot':run.action==='render-readiness'?'Checking the saved scene':progressLabel(run))+'</strong><p>Previous files stay intact. Progress is reported from the real job; no estimated percentage.</p>'+b('Inspect operation','recover',{run:run.id},'ghost')+'</div>':'')+
 (scene.candidate?'<div class="note warn"><strong>Separate candidate needs review</strong><p>It has not replaced the saved render source.</p>'+button('Inspect candidate','inspect-candidate')+button('Use as working scene','keep-building')+button('Reject candidate','discard',{},'ghost')+'</div>':'')+
 '<div class="layer-shotbar" aria-label="Shots in this scene">'+shots.map(x=>button(x.name,'select-shot',{id:x.id},shot?.id===x.id?'active':'ghost',!!scene.candidate)).join('')+(shots.length?'':button('Name a shot in Shots','render-shots',{},'primary',!!scene.candidate))+'</div>'+
 (shot?'<p class="layer-scope">'+esc(shot.camera)+' · frames '+shot.start+'–'+shot.end+' · shot v'+shot.revision+' '+button('Edit shot','render-shots',{},'small ghost',!!scene.candidate)+'</p>':'')+
 '<div class="output-main">'+
 (movie?'<div class="viewport"><header><span>'+esc(movie.shotName||movie.options.camera)+' · actual shot movie</span><small>'+movie.options.width+' × '+movie.options.height+' · '+esc(outputDevice(movie))+'</small></header><video data-media="render" data-project-id="'+esc(project.id)+'" data-scene-id="'+esc(scene.id)+'" data-id="'+esc(movie.id)+'" controls playsinline preload="metadata" aria-label="Rendered shot movie"></video><footer>Exact retained movie. Playback is not approval.</footer></div><div class="output-review"><p>'+(movie.approved?'Approved movie for this saved source.':'Watch timing, motion, framing and lighting before deciding.')+'</p>'+button(movie.approved?'Approved':'Approve this movie','approve-render',{id:movie.id},movie.approved?'ghost':'primary',movie.approved||!!scene.candidate)+button('Continue to Final film','render-film',{},movie.approved?'primary':'ghost')+button('Render another version','render-settings',{},'ghost',!!scene.candidate)+'</div>':checkpoint&&shot?source:'<div class="empty-media"><p>Choose the shot you want to render.</p></div>')+
 (movie?'<details class="output-settings"><summary>Render another version · delivery settings</summary>'+form+'</details><details class="output-source"><summary>Inspect saved source in 3D</summary>'+b('Load 3D inspection','scene-viewer',{},'ghost',active)+source+'</details>':'<section class="output-settings"><h2>Delivery settings</h2>'+form+'</section>')+'</div>'+
 '<details class="output-history"><summary>Earlier shot outputs · '+history.length+'</summary><p>Old movies remain available. Historical outputs cannot be approved for current delivery.</p>'+history.map(r=>'<div class="render-row"><div><strong>'+esc(r.shotName||r.options.camera)+' · '+r.options.start+'–'+r.options.end+'</strong><small>'+(renderIsCurrent(scene,r)?r.approved?'Approved for this source':'Needs review':'Historical · source or shot changed')+'</small></div>'+b('Play','play-render',{id:r.id},'small')+button('Approve','approve-render',{id:r.id},'small',r.approved||!renderIsCurrent(scene,r)||!!scene.candidate)+'</div>').join('')+'</details></section>';
}
