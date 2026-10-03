/** A local red path handle. It never changes the saved GLB or publishes a job. */
export function attachActionPath({THREE,host,world,camera,canvas,orbit,getDraft,onChange,invalidate,canEdit=()=>true}){
 const group=new THREE.Group();world.add(group);
 const arrow=new THREE.ArrowHelper(new THREE.Vector3(0,0,1),new THREE.Vector3(),1,0xff4040,.18,.1);group.add(arrow);
 const handle=new THREE.Mesh(new THREE.SphereGeometry(1,16,10),new THREE.MeshBasicMaterial({color:0xff4040,depthTest:false}));handle.renderOrder=1000;group.add(handle);
 const label=document.createElement('p');label.className='motion-path-label';label.dataset.motionPath='';host.querySelector('.viewer-canvas').after(label);
 const endpoint=document.createElement('button');endpoint.type='button';endpoint.className='motion-endpoint';endpoint.setAttribute('aria-label','Move path endpoint');endpoint.title='Drag endpoint; arrow keys move 0.1 m, Shift moves 1 m';host.querySelector('.viewer-canvas').append(endpoint);
 const ray=new THREE.Raycaster(),point=new THREE.Vector2(),plane=new THREE.Plane(),hit=new THREE.Vector3();let dragging=false,current=null;
 const listeners=[];const listen=(type,fn)=>{for(const node of [canvas,endpoint]){node.addEventListener(type,fn,true);listeners.push(()=>node.removeEventListener(type,fn,true));}};
 function update(){const d=getDraft();current=d?.timeline?d.arrow():null;group.visible=!!current;label.hidden=!current;endpoint.hidden=!current;if(!current){invalidate();return;}
  const unit=current.meters_per_unit,origin=new THREE.Vector3(current.origin_m[0]/unit,current.origin_m[2]/unit,-current.origin_m[1]/unit),delta=new THREE.Vector3(current.delta_m[0]/unit,0,-current.delta_m[1]/unit),length=delta.length();
  arrow.position.copy(origin);arrow.setDirection(delta.clone().normalize());arrow.setLength(length,Math.min(length*.2,.3/unit),Math.min(length*.12,.16/unit));handle.position.copy(origin).add(delta);handle.scale.setScalar(Math.max(.03/unit,Math.min(.12/unit,length*.12)));plane.set(new THREE.Vector3(0,1,0),-origin.y);label.textContent=(d.dirty?'Unsaved':'Saved')+' path · '+Math.hypot(...current.delta_m).toFixed(2)+' m · drag the red endpoint; facing stays unchanged.';
  if(d.selectedClip?.travel?.gait_id){label.textContent=(d.dirty?'Unsaved':'Saved')+' path · '+Math.hypot(...current.delta_m).toFixed(2)+' m · drag to change distance along the observed gait; facing stays unchanged.';endpoint.title='Drag along path; Up/Right lengthen, Down/Left shorten (0.1 m, Shift 1 m)';}
  else endpoint.title='Drag endpoint; arrow keys move 0.1 m, Shift moves 1 m';
  const screen=handle.position.clone().project(camera);endpoint.hidden=screen.z>1||screen.z< -1||Math.abs(screen.x)>1||Math.abs(screen.y)>1;endpoint.style.left=((screen.x+1)/2*canvas.clientWidth)+'px';endpoint.style.top=((-screen.y+1)/2*canvas.clientHeight)+'px';endpoint.disabled=!canEdit();invalidate();
 }
 function aim(e){const r=canvas.getBoundingClientRect();point.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);ray.setFromCamera(point,camera);}
 listen('pointerdown',e=>{if(e.button!==0||!current||!canEdit())return;aim(e);group.updateMatrixWorld(true);if(e.target!==endpoint&&!ray.intersectObject(handle).length)return;e.preventDefault();e.stopImmediatePropagation();dragging=true;orbit.enabled=false;canvas.setPointerCapture(e.pointerId);getDraft().finishEdit();});
 listen('pointermove',e=>{if(!dragging||!canEdit())return;e.preventDefault();e.stopImmediatePropagation();aim(e);if(!ray.ray.intersectPlane(plane,hit))return;getDraft().moveEndpoint([hit.x*current.meters_per_unit-current.origin_m[0],-hit.z*current.meters_per_unit-current.origin_m[1]]);update();onChange();});
 const end=e=>{if(!dragging)return;e.stopImmediatePropagation();dragging=false;orbit.enabled=true;if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);getDraft()?.finishEdit();};
 listen('pointerup',end);listen('pointercancel',end);
 const keyboard=e=>{if(!current||!canEdit()||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();e.stopPropagation();let delta=[...current.delta_m];const axis=['ArrowLeft','ArrowRight'].includes(e.key)?0:1,step=(['ArrowLeft','ArrowDown'].includes(e.key)?-1:1)*(e.shiftKey?1:.1);if(getDraft().selectedClip?.travel?.gait_id){const length=Math.hypot(...delta);delta=delta.map(v=>v/length*Math.max(.001,length+step));}else delta[axis]+=step;getDraft().finishEdit();getDraft().moveEndpoint(delta);getDraft().finishEdit();update();onChange();};
 endpoint.addEventListener('keydown',keyboard);orbit.addEventListener('change',update);update();
 return {update,dispose(){for(const fn of listeners)fn();orbit.removeEventListener('change',update);endpoint.removeEventListener('keydown',keyboard);if(dragging)orbit.enabled=true;group.removeFromParent();group.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});label.remove();endpoint.remove();}};
}
