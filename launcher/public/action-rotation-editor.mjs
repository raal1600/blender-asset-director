/** Orientation-only visual draft. Playback and native Save remain separate. */
import {createTurnPreview,savedHeadingAt} from './action-turn-preview.mjs';
import {turnAngle} from './action-timeline-contract.mjs';

export function attachActionRotation({THREE,host,model,gltf,world,camera,canvas,orbit,getDraft,onChange,
 canEdit=()=>true,currentFrame,seekFrame,isPlaying,invalidate}){
 const surface=host.querySelector('.viewer-canvas'),listeners=[];
 const toolbar=document.createElement('div');toolbar.className='motion-turn-toolbar';
 toolbar.innerHTML='<strong>Character rotation</strong><output data-motion-heading></output><span data-motion-turn-status role="status"></span>';
 surface.before(toolbar);
 const handle=document.createElement('button');handle.type='button';handle.className='motion-turn-handle';
 handle.setAttribute('aria-label','Rotate character');handle.title='Drag to rotate; arrow keys turn 5°, Shift 15°. Save changes to keep.';handle.textContent='↻';surface.append(handle);
 const group=new THREE.Group(),material=new THREE.MeshBasicMaterial({color:0xffbd69,depthTest:false,transparent:true,opacity:.9});
 const ring=new THREE.Mesh(new THREE.TorusGeometry(1,.018,8,80),material);ring.rotation.x=Math.PI/2;ring.renderOrder=1002;group.add(ring);world.add(group);
 const ray=new THREE.Raycaster(),mouse=new THREE.Vector2(),plane=new THREE.Plane(new THREE.Vector3(0,1,0)),hit=new THREE.Vector3();
 const heading=toolbar.querySelector('[data-motion-heading]'),status=toolbar.querySelector('[data-motion-turn-status]');
 let binding=null,owner=null,selection=null,lastHeading=null,preview=false,updating=false,disposed=false,gesture=null,radius=1,pivot=new THREE.Vector3(),failure='';
 const listen=(node,type,fn,options)=>{node.addEventListener(type,fn,options);listeners.push(()=>node.removeEventListener(type,fn,options));};
 function restore(){binding?.restore();preview=false;delete host.dataset.turnPreview;}
 function pausePreview(){restore();if(gesture)endGesture();draw();}
 function state(){const d=getDraft(),c=d?.timeline?d.selectedClip:null,p=d?.audit.performers.find(p=>p.name===d.selected);return {d,c,p};}
 function blocker(d,c,p){
  if(!d?.supportsEditing)return 'Inspect saved performers to enable rotation.';
  if(p?.unsupported||p?.timeline?.error)return p.unsupported||p.timeline.error;
  const clips=d.clips(p.name),previous=clips[clips.findIndex(x=>x.id===c.id)-1];
  if(previous&&!c.transition)return 'Connect to previous clip to rotate into this animation.';
  for(const clip of clips){const take=p.takes.find(t=>t.id===clip.take_id);if(take?.heading_blocker!==null)return take?.heading_blocker||'Inspect this performer before rotating.';}
  return binding?.available?'':binding?.reason||'This performer cannot be isolated safely in this preview.';
 }
 function bind(p,d){
  const used=p&&d?.timeline?new Set(d.clips(p.name).map(c=>c.take_id)):new Set(),key=p?p.name+':'+[...used].sort().join(','):null;
  if(owner===key)return;
  restore();owner=key;binding=p&&used.size?createTurnPreview({THREE,gltf,performer:{...p,takes:p.takes.filter(t=>used.has(t.id))},performers:d.audit.performers}):null;
  if(binding?.available){
   model.updateMatrixWorld(true);const bounds=new THREE.Box3();for(const root of binding.roots)bounds.expandByObject(root,true);
   const size=bounds.getSize(new THREE.Vector3());radius=Math.max(.12,Math.min(10000,Math.max(size.x,size.z,size.y*.65)*.65));
  }
 }
 function targetPose(){
  const {d,c,p}=state();if(!c||!canEdit())return false;
  bind(p,d);const reason=blocker(d,c,p);if(reason){failure=reason;return false;}
  // A turn edits the NEXT animation's orientation. Show that pose while dragging,
  // rather than pretending to evaluate an unsaved blended transition in WebGL.
  restore();seekFrame(c.start);
  const baseline=savedHeadingAt(p.timeline,currentFrame());
  if(!Number.isFinite(baseline)){failure='Save or inspect this motion before previewing its orientation.';return false;}
  if(!binding.apply(turnAngle(baseline,c.heading_deg||0))){failure=binding.reason;return false;}
  preview=d.dirty;if(preview)host.dataset.turnPreview='orientation-only';failure='';return true;
 }
 function draw(){
  if(disposed)return;const {d,c,p}=state();toolbar.hidden=!c;group.visible=!!c&&!!binding?.available;handle.hidden=!group.visible;
  if(!c)return;
  const reason=blocker(d,c,p);heading.textContent=Number((c.heading_deg||0).toFixed(1))+'°';heading.dataset.degrees=String(c.heading_deg||0);
  handle.disabled=!canEdit()||!!reason;group.visible=group.visible&&!reason;
  if(reason){handle.hidden=true;status.textContent=reason;invalidate();return;}
  if(failure)status.textContent=failure;
  else if(preview)status.textContent='Unsaved orientation preview · frame '+currentFrame()+'. Save changes, then Play to review the turn.';
  else status.textContent=isPlaying()?'Playing saved motion · drag the ring to pause and edit.':'Drag the amber ring to turn this animation. Degrees update automatically.';
  const position=binding.pivot();if(!position){handle.hidden=true;group.visible=false;status.textContent='Preview ownership changed; reopen the saved preview.';invalidate();return;}
  pivot.copy(position);group.position.copy(pivot);group.scale.setScalar(radius);group.updateMatrixWorld(true);
  const angle=(c.heading_deg||0)*Math.PI/180,point=new THREE.Vector3(Math.cos(angle)*radius,0,-Math.sin(angle)*radius).add(pivot).project(camera);
  handle.hidden=!group.visible||point.z>1||point.z< -1||Math.abs(point.x)>1||Math.abs(point.y)>1;
  handle.style.left=((point.x+1)/2*canvas.clientWidth)+'px';handle.style.top=((-point.y+1)/2*canvas.clientHeight)+'px';
  if(handle.hidden&&!reason)status.textContent+=' Reset view if the ring is outside the view.';
  invalidate();
 }
 function update(){
  if(updating||disposed)return;updating=true;
  try{const {d,c,p}=state(),key=c?[p.name,c.id,d.selectedPart].join(':'):null;
   if(key!==selection){restore();selection=key;lastHeading=c?.heading_deg||0;failure='';if(gesture)endGesture();}
   bind(p,d);
   // The workbench briefly locks controls during Undo/render. Do not consume
   // that changed heading until its final unlocked sync can display the pose.
   if(c&&lastHeading!==(c.heading_deg||0)&&canEdit()){lastHeading=c.heading_deg||0;if(!isPlaying())targetPose();}
   draw();
  }catch(error){restore();failure=error.message;status.textContent=failure;handle.hidden=true;group.visible=false;invalidate();}
  finally{updating=false;}
 }
 function aim(e){const r=canvas.getBoundingClientRect();mouse.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);ray.setFromCamera(mouse,camera);}
 function groundAngle(e){aim(e);plane.constant=-pivot.y;if(!ray.ray.intersectPlane(plane,hit)||hit.distanceTo(pivot)<radius*.03)return null;return Math.atan2(-(hit.z-pivot.z),hit.x-pivot.x)*180/Math.PI;}
 function change(value){
  const {d,c}=state();if(!canEdit()||!c)return;
  const priorMode=c.transition?.mode;d.rotateHeading(value);lastHeading=d.selectedClip.heading_deg||0;targetPose();
  onChange({controls:priorMode!==d.selectedClip.transition?.mode});update();
 }
 function endGesture(){if(!gesture)return;const old=gesture;gesture=null;orbit.enabled=old.orbitEnabled;if(canvas.hasPointerCapture(old.pointerId))canvas.releasePointerCapture(old.pointerId);getDraft()?.finishEdit();}
 function cancel(){if(!gesture)return;const {d}=state(),changed=gesture.changed;endGesture();if(changed)d.undo();lastHeading=null;onChange({controls:true});update();}
 const down=e=>{
  if(e.button!==0||handle.disabled||!binding?.available||!state().c)return;
  aim(e);group.updateMatrixWorld(true);if(e.target!==handle&&!ray.intersectObject(ring).length)return;
  e.preventDefault();e.stopImmediatePropagation();getDraft().finishEdit();
  if(!targetPose()){draw();return;}draw();const angle=groundAngle(e);if(angle===null)return;
  gesture={pointerId:e.pointerId,angle,heading:state().c.heading_deg||0,changed:false,orbitEnabled:orbit.enabled};orbit.enabled=false;canvas.setPointerCapture(e.pointerId);
 };
 const move=e=>{if(!gesture||e.pointerId!==gesture.pointerId)return;e.preventDefault();e.stopImmediatePropagation();if(!canEdit()){cancel();return;}const angle=groundAngle(e);if(angle===null)return;
  try{let value=gesture.heading+turnAngle(gesture.angle,angle);if(e.shiftKey)value=Math.round(value/5)*5;const before=state().c.heading_deg||0;change(value);gesture.changed ||= before!==(state().c.heading_deg||0);}catch(error){failure=error.message;draw();}
 };
 const up=e=>{if(!gesture||e.pointerId!==gesture.pointerId)return;e.preventDefault();e.stopImmediatePropagation();endGesture();draw();};
 for(const node of [canvas,handle]){listen(node,'pointerdown',down,true);listen(node,'pointermove',move,true);listen(node,'pointerup',up,true);listen(node,'pointercancel',()=>cancel(),true);}
 listen(handle,'keydown',e=>{
  if(e.key==='Escape'){e.preventDefault();cancel();return;}
  if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)||handle.disabled)return;
  e.preventDefault();e.stopPropagation();getDraft().finishEdit();
  try{change((state().c.heading_deg||0)+(['ArrowLeft','ArrowDown'].includes(e.key)?-1:1)*(e.shiftKey?15:5));}
  catch(error){failure=error.message;draw();}finally{getDraft().finishEdit();}
 });
 listen(canvas,'keydown',e=>{if(e.key==='Escape'&&gesture){e.preventDefault();e.stopPropagation();cancel();}},true);
 listen(orbit,'change',draw);update();
 return {update,frameChanged:draw,clear:pausePreview,dispose(){endGesture();restore();disposed=true;for(const fn of listeners)fn();ring.geometry.dispose();material.dispose();group.removeFromParent();toolbar.remove();handle.remove();}};
}
