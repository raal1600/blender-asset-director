/** Scene-only visual draft. The Save owner supplies the authenticated job boundary. */
import {worldDraft,instanceObjects} from './world-draft.mjs';
import {TransformControls} from './vendor/three/examples/jsm/controls/TransformControls.js';

export function attachWorldEditor({THREE,host,model,gltf,world,camera,orbit,canvas,record,labels={},changed=()=>{},invalidate=()=>{}}){
  const instances=record.placement?.instances||[];
  if(!instances.length)return null;
  const listeners=[],groups=new Map(),selected=new Set(),ray=new THREE.Raycaster(),pointer=new THREE.Vector2();
  const conversion=new THREE.Matrix4().makeRotationX(-Math.PI/2),inverseConversion=conversion.clone().invert();
  const fromRows=rows=>new THREE.Matrix4().set(...rows);
  const rows=matrix=>{const e=matrix.elements;return [0,1,2,3].flatMap(r=>[0,1,2,3].map(c=>e[c*4+r]));};
  const toViewer=value=>conversion.clone().multiply(fromRows(value)).multiply(inverseConversion);
  const toBlender=value=>rows(inverseConversion.clone().multiply(value).multiply(conversion));
  const listen=(node,type,fn,options)=>{node.addEventListener(type,fn,options);listeners.push(()=>node.removeEventListener(type,fn,options));};
  let enabled=true,gesture=null,down=null,disposed=false,mode='translate';
  const toolbar=document.createElement('div');toolbar.className='world-editor-toolbar';toolbar.setAttribute('aria-label','Arrange whole assets');
  toolbar.innerHTML='<label class="world-instance-picker">Asset<select data-world-pick aria-label="Asset instance"><option value="">Click an asset</option></select></label><div role="group" aria-label="Placement tool"><button type="button" data-world-mode="translate" aria-pressed="true">Move</button><button type="button" data-world-mode="rotate" aria-pressed="false">Rotate</button><button type="button" data-world-mode="scale" aria-pressed="false" title="Positive uniform scale">Scale</button></div><button type="button" data-world-focus>Focus selected</button><span data-world-selection role="status">Choose an asset</span>';
  host.querySelector('.viewer-canvas').before(toolbar);
  const details=document.createElement('details');details.className='world-transform-details';details.innerHTML='<summary>Exact placement</summary><div class="world-transform-fields">'+['X','Y','Z','Heading','Scale'].map((name,i)=>'<label>'+name+'<input type="number" step="'+(i===4?'0.1':'0.25')+'" aria-label="Placement '+name+'" data-world-value="'+name+'"></label>').join('')+'<button type="button" data-world-apply>Apply to draft</button></div><p>Blender world coordinates; heading in degrees. Uniform scale changes the whole instance. Save changes to keep this draft.</p>';
  toolbar.after(details);
  const error=document.createElement('p');error.className='world-editor-error';error.setAttribute('role','alert');error.hidden=true;details.after(error);
  const say=message=>{error.textContent=message;error.hidden=!message;};
  const picker=toolbar.querySelector('[data-world-pick]');
  const draft=worldDraft({checkpointId:record.sourceId,sha256:record.version,instances},state=>{syncGeometry();changed(state);});
  model.updateMatrixWorld(true);
  for(const item of instances){
    const group=new THREE.Group();group.name='Director instance '+item.instance;model.add(group);
    const local=model.matrixWorld.clone().invert().multiply(toViewer(item.matrix));local.decompose(group.position,group.quaternion,group.scale);group.updateMatrixWorld(true);
    for(const index of item.nodes){
      const objects=instanceObjects(gltf.parser.associations,index);
      const object=objects[0];group.attach(object);
      object.traverse(o=>{o.userData.directorInstance=item.instance;});
    }
    groups.set(item.instance,{group,item});
    const option=document.createElement('option');option.value=item.instance;option.textContent=labels[item.assetId]||item.control;picker.append(option);
  }
  const pivot=new THREE.Object3D();world.add(pivot);
  const gizmo=new TransformControls(camera,canvas);world.add(gizmo.getHelper());gizmo.setSize(.85);
  const handle=document.createElement('span');handle.dataset.worldHandle='';handle.setAttribute('aria-live','polite');toolbar.append(handle);
  listen(gizmo,'axis-changed',()=>{handle.textContent=gizmo.axis?mode+' · '+gizmo.axis:'';});
  const selectionBox=new THREE.Box3(),outline=new THREE.Box3Helper(selectionBox,0x90bfff);outline.visible=false;outline.material.depthTest=false;outline.renderOrder=1000;world.add(outline);
  function syncGeometry(){
    if(disposed)return;
    for(const [id,{group}] of groups){
      const local=model.matrixWorld.clone().invert().multiply(toViewer(draft.get(id)));
      local.decompose(group.position,group.quaternion,group.scale);group.updateMatrixWorld(true);
    }
    updateBox();invalidate();
  }
  function updateBox(){
    selectionBox.makeEmpty();for(const id of selected)selectionBox.expandByObject(groups.get(id).group,true);
    outline.visible=selected.size>0;outline.updateMatrixWorld(true);
  }
  function selectionUI(){
    updateBox();pivot.position.copy(selectionBox.isEmpty()?new THREE.Vector3():selectionBox.getCenter(new THREE.Vector3()));
    pivot.quaternion.identity();pivot.scale.setScalar(1);pivot.updateMatrixWorld(true);
    if(selected.size&&enabled)gizmo.attach(pivot);else gizmo.detach();
    picker.value=selected.size===1?[...selected][0]:'';
    toolbar.querySelector('[data-world-selection]').textContent=selected.size?selected.size+' asset'+(selected.size===1?'':'s')+' selected':'Choose an asset';
    host.dataset.selectedInstances=String(selected.size);
    for(const button of toolbar.querySelectorAll('[data-world-mode],[data-world-focus]'))button.disabled=!enabled||!selected.size;
    const one=selected.size===1,fields=details.querySelectorAll('input');
    details.querySelector('button').disabled=!enabled||!one;for(const field of fields)field.disabled=!enabled||!one;
    if(one){const m=fromRows(draft.get([...selected][0])),p=new THREE.Vector3(),q=new THREE.Quaternion(),s=new THREE.Vector3();m.decompose(p,q,s);const values=[p.x,p.y,p.z,THREE.MathUtils.radToDeg(new THREE.Euler().setFromQuaternion(q,'XYZ').z),s.x];fields.forEach((field,i)=>{field.value=String(Number(values[i].toFixed(5)));});}
    invalidate();
  }
  function select(id,add=false){
    if(!enabled||gesture)return;
    if(id&&!groups.has(id))return;
    if(!add)selected.clear();
    if(id){if(add&&selected.has(id))selected.delete(id);else if(selected.size<64)selected.add(id);else say('Select up to 64 assets for one placement batch.');}
    selectionUI();
  }
  listen(picker,'change',()=>select(picker.value));
  for(const button of toolbar.querySelectorAll('[data-world-mode]'))listen(button,'click',()=>{
    mode=button.dataset.worldMode;gizmo.setMode(mode);gizmo.setSpace(mode==='scale'?'local':'world');
    toolbar.querySelectorAll('[data-world-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));say('');invalidate();
  });
  listen(toolbar.querySelector('[data-world-focus]'),'click',()=>{
    if(!selected.size)return;updateBox();const center=selectionBox.getCenter(new THREE.Vector3()),radius=Math.max(selectionBox.getSize(new THREE.Vector3()).length()/2,.01);
    const direction=camera.position.clone().sub(orbit.target).normalize();
    const fov=Math.min(THREE.MathUtils.degToRad(camera.fov/2),Math.atan(Math.tan(THREE.MathUtils.degToRad(camera.fov/2))*camera.aspect));
    camera.position.copy(center).addScaledVector(direction,radius/Math.sin(fov)*1.2);orbit.target.copy(center);orbit.update();invalidate();
  });
  listen(details.querySelector('[data-world-apply]'),'click',()=>{
    if(!enabled||selected.size!==1)return;
    try{const id=[...selected][0],values=[...details.querySelectorAll('input')].map(i=>i.value===''?NaN:Number(i.value));
      const m=fromRows(draft.get(id)),p=new THREE.Vector3(),q=new THREE.Quaternion(),s=new THREE.Vector3();m.decompose(p,q,s);
      const e=new THREE.Euler().setFromQuaternion(q,'XYZ');e.z=THREE.MathUtils.degToRad(values[3]);q.setFromEuler(e);
      draft.apply([{instance:id,matrix:rows(m.compose(p.set(...values.slice(0,3)),q,s.setScalar(values[4])))}]);say('');selectionUI();
    }catch(e){say(e.message);}
  });
  // Capture before OrbitControls sees a handle, so one gesture cannot also orbit.
  listen(canvas,'pointerdown',event=>{if(event.button!==0)return;down={x:event.clientX,y:event.clientY};if(enabled&&gizmo.axis)orbit.enabled=false;},true);
  listen(canvas,'pointerup',event=>{
    const wasGesture=gesture!==null||gizmo.dragging;
    if(down&&!wasGesture&&event.button===0&&Math.hypot(event.clientX-down.x,event.clientY-down.y)<4){
      const rect=canvas.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(pointer,camera);
      const hit=ray.intersectObject(model,true).find(h=>h.object.isMesh);
      select(hit?.object.userData.directorInstance||null,event.shiftKey||event.ctrlKey||event.metaKey);
    }
    down=null;orbit.enabled=true;
  },true);
  listen(gizmo,'mouseDown',()=>{if(!enabled)return;draft.begin();gesture={pivot:pivot.matrixWorld.clone(),matrices:new Map([...selected].map(id=>[id,toViewer(draft.get(id))]))};orbit.enabled=false;say('');});
  listen(gizmo,'objectChange',()=>{
    if(!gesture)return;
    try{
      if(mode==='scale'){const axis=gizmo.axis||'XYZ';const factor=axis==='Y'?pivot.scale.y:axis==='Z'?pivot.scale.z:pivot.scale.x;if(!Number.isFinite(factor)||factor<=0)throw Error('Use positive uniform scale.');pivot.scale.setScalar(factor);}
      pivot.updateMatrixWorld(true);const delta=pivot.matrixWorld.clone().multiply(gesture.pivot.clone().invert());
      draft.preview([...gesture.matrices].map(([instance,m])=>({instance,matrix:toBlender(delta.clone().multiply(m))})));
    }catch(e){say(e.message);}
  });
  listen(gizmo,'mouseUp',()=>{if(gesture){draft.commit();gesture=null;selectionUI();}orbit.enabled=true;});
  listen(gizmo,'change',invalidate);
  const cancel=()=>{if(!gesture)return;gizmo.reset();draft.cancel();gesture=null;gizmo.dragging=false;orbit.enabled=true;selectionUI();};
  listen(canvas,'pointercancel',cancel);
  listen(canvas,'keydown',event=>{
    if(event.key==='Escape'){cancel();return;}
    if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='a'&&enabled){event.preventDefault();cancel();if(groups.size>64){say('Choose up to 64 assets for one placement batch.');return;}selected.clear();for(const id of groups.keys())selected.add(id);selectionUI();return;}
    if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'&&enabled){event.preventDefault();cancel();draft.undo();selectionUI();}
  });
  host.querySelector('.viewer-help').textContent='Click an asset · Shift-click to select more · Ctrl+A selects all · drag handles to arrange · drag empty space to orbit. Save changes to keep your draft.';
  selectionUI();
  return {get dirty(){return draft.state().dirty;},get state(){return draft.state();},
    request:id=>draft.request(id),targets:()=>[...selected].map(id=>groups.get(id).item.control),
    undo(){cancel();draft.undo();selectionUI();},discard(){cancel();draft.discard();selectionUI();},
    setEnabled(value){if(enabled===value)return;enabled=value;picker.disabled=!value;gizmo.enabled=value;if(!value)cancel();selectionUI();},
    dispose(){disposed=true;for(const f of listeners)f();gizmo.dispose();world.remove(gizmo.getHelper(),pivot,outline);outline.geometry.dispose();outline.material.dispose();toolbar.remove();details.remove();error.remove();delete host.dataset.selectedInstances;}
  };
}
