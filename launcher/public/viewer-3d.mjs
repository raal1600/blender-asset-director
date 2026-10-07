/** Local WebGL inspection. No project writes and no connection to live Blender. */
import {shotFrame,shotViewport,sampledCamera} from './shot-view.mjs';
import {performerMeshes} from './performer-framing.mjs';
export function viewerPlaceholder() {
  return '<section class="viewer-3d" data-viewer-host aria-label="Interactive 3D preview"><div class="viewer-message"><strong>Explore in 3D</strong><p>Orbit, zoom and pan the actual saved geometry. World focuses on arrangement; Action exposes motion.</p><p class="muted">Read-only inspection, not a final render or a live link to Blender.</p></div></section>';
}

export function animationEntries(animations,profile='inspection-v1',staticScene=false) {
  if(profile==='world-static-v1')return [];
  if(['action-playback-v1','shot-framing-v1','look-inspection-v1'].includes(profile)&&animations.length!==(staticScene?0:1))throw Error('Expected one combined saved-scene animation or verified static scene.');
  return animations.filter(a=>a.tracks.length).map(clip=>{
    if(!Number.isFinite(clip.duration)||clip.duration<0)throw Error('Invalid animation duration.');
    return {clip,staticPose:clip.duration===0};
  });
}

/** Explicit Reset view includes the selected draft path, not just saved geometry. */
export function actionPathPoints(path){
  if(!path||!Number.isFinite(path.meters_per_unit)||path.meters_per_unit<=0||
     !Array.isArray(path.origin_m)||path.origin_m.length!==3||!path.origin_m.every(Number.isFinite)||
     !Array.isArray(path.delta_m)||path.delta_m.length!==2||!path.delta_m.every(Number.isFinite))return [];
  const [x,y,z]=path.origin_m,u=path.meters_per_unit,[dx,dy]=path.delta_m;
  return [[x/u,z/u,-y/u],[(x+dx)/u,z/u,-(y+dy)/u]];
}

function releaseTree(root) {
  const geometries=new Set(),materials=new Set(),textures=new Set(),skeletons=new Set();
  for(const tree of Array.isArray(root)?root:[root])tree?.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.skeleton)skeletons.add(o.skeleton);for(const m of Array.isArray(o.material)?o.material:o.material?[o.material]:[])materials.add(m);});
  for(const m of materials){for(const v of Object.values(m))if(v?.isTexture)textures.add(v);m.dispose();}
  for(const t of textures){t.source?.data?.close?.();t.dispose();}for(const g of geometries)g.dispose();for(const s of skeletons)s.dispose();
}

export function previewFailure(error) {
  const detail=String(error?.message||error||'Unknown preview error');
  const textures=/texture|image dimensions/i.test(detail)&&/budget|limit|exceed|width|height/i.test(detail);
  return {title:'3D preview unavailable',message:textures?'This asset exceeds the in-app texture conversion limits. You can inspect the full-resolution asset in Blender.':'Director could not prepare this in-app preview. You can inspect the asset separately in Blender.',detail};
}

export function openViewer({host,prepare,fetchModel,inspectInBlender,worldEdit,actionEdit,release,focusPerformer}) {
  let actionPath=null,actionRotation=null;
  let seekActionFrame=null,resetCamera=null;
  let disposed=false,renderer,controls,world,mixer,editor,frame=0,observer,model,action,playing=false,last=0,dirty=true,resize,loadedScenes=[],playback=null;
  let shotView=null,shotTime=0,shotFixed=true,staticFrame=null;
  const abort=new AbortController(),cleanups=[];
  let preparedRecord,releaseWanted=false,released=false;
  const relinquish=()=>{releaseWanted=true;if(preparedRecord&&!released){released=true;Promise.resolve().then(()=>release?.(preparedRecord)).catch(()=>{});}};
  host.dataset.viewerState='loading';delete host.dataset.previewId;
  host.innerHTML='<div class="viewer-message" role="status" aria-live="polite">Verifying this exact source and preparing 3D geometry… Native files may need up to three minutes. No scene changes or render.</div>';
  const status=()=>host.querySelector('[data-viewer-status]');
  const listen=(node,type,fn,options)=>{node.addEventListener(type,fn,options);cleanups.push(()=>node.removeEventListener(type,fn,options));};
  const dispose=()=>{if(disposed)return;disposed=true;relinquish();abort.abort();cancelAnimationFrame(frame);observer?.disconnect();for(const f of cleanups)f();editor?.dispose();controls?.dispose();mixer?.stopAllAction();if(model)mixer?.uncacheRoot(model);releaseTree([world,...loadedScenes]);renderer?.dispose();renderer?.forceContextLoss();host.replaceChildren();delete host.dataset.viewerState;delete host.dataset.previewId;};
  const ready=(async()=>{
    try {
      const [record,THREE,{GLTFLoader},{OrbitControls}]=await Promise.all([Promise.resolve().then(()=>prepare(abort.signal)).then(value=>{preparedRecord=value;if(releaseWanted)relinquish();return value;}),import('./vendor/three/build/three.module.js'),import('./vendor/three/examples/jsm/loaders/GLTFLoader.js'),import('./vendor/three/examples/jsm/controls/OrbitControls.js')]);
      if(disposed)return;
      const bytes=await fetchModel(record,abort.signal);if(disposed)return;
      const manager=new THREE.LoadingManager();
      manager.setURLModifier(url=>{if(!url.startsWith('blob:'+location.origin+'/'))throw Error('External 3D resources are blocked.');return url;});
      const gltf=await new GLTFLoader(manager).parseAsync(bytes,'');
      model=gltf.scene;loadedScenes=gltf.scenes;if(disposed){releaseTree(loadedScenes);return;}
      host.innerHTML='<div class="viewer-toolbar"><strong data-viewer-title></strong><span class="grow"></span><button type="button" data-view="reset">Reset view</button><button type="button" data-view="grid" aria-pressed="true">Grid</button><button type="button" data-view="wire" aria-pressed="false">Wireframe</button></div><div class="viewer-canvas"></div><div class="viewer-animation"><label>Animation <select data-view="take" aria-label="Animation take"></select></label><button type="button" data-view="play">Play</button><input data-view="time" aria-label="Animation time" type="range" min="0" max="1" step="0.001" value="0"><output data-view="clock">0.00 s</output></div><p class="viewer-help">Drag to orbit · scroll to zoom · right-drag / Shift-drag to pan · focus view and use arrow keys to pan; F to reset.</p><p class="viewer-status" data-viewer-status role="status" aria-live="polite"></p><p class="viewer-disclaimer">Saved geometry with inspection lighting. Materials may differ from Blender. No import, edit, render or approval.</p>';
      host.querySelector('[data-viewer-title]').textContent=record.title;
      if(record.texturePreview?.reducedImages>0){const label=document.createElement('p');label.className='viewer-texture-note viewer-disclaimer';label.textContent='Optimized 3D preview · '+record.texturePreview.reducedImages+' lighter texture'+(record.texturePreview.reducedImages===1?'':'s')+'. Full-resolution originals and Blender copies are unchanged.';host.querySelector('.viewer-disclaimer').before(label);}
      const node=k=>host.querySelector('[data-view="'+k+'"]'),surface=host.querySelector('.viewer-canvas');
      renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'});
      renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));renderer.outputColorSpace=THREE.SRGBColorSpace;
      renderer.setClearColor(0x161c25);renderer.toneMapping=THREE.ACESFilmicToneMapping;
      const canvas=renderer.domElement;canvas.tabIndex=0;canvas.setAttribute('aria-label','3D model: drag to orbit, scroll to zoom; arrow keys pan; F resets');surface.append(canvas);
      world=new THREE.Scene();world.add(model);
      // Model lights cannot silently substitute for our inspection setup.
      model.traverse(o=>{if(o.isLight)o.visible=false;});
      world.add(new THREE.HemisphereLight(0xeaf3ff,0x6a7385,2.5));
      const key=new THREE.DirectionalLight(0xffffff,3);key.position.set(3,5,4);world.add(key);
      const fill=new THREE.DirectionalLight(0xbed6ff,2);fill.position.set(-3,2,-2);world.add(fill);
      model.updateMatrixWorld(true);
      const focusedMeshes=performerMeshes(gltf,focusPerformer);
      host.dataset.framing=focusedMeshes.length?'performer':'scene';
      const bounds=box=>{box.makeEmpty();if(focusedMeshes.length){for(const mesh of focusedMeshes)box.expandByObject(mesh,true);}else box.setFromObject(model,true);return box;};
      const box=bounds(new THREE.Box3()),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3());
      let radius=Math.max(size.length()/2,0.01);if(!Number.isFinite(radius)||radius>1e9)throw Error('Invalid model dimensions.');
      const camera=new THREE.PerspectiveCamera(40,1,Math.max(radius/10000,.00001),radius*1000);
      shotView=record.shotView;const shotRig=shotView?sampledCamera(THREE,shotView):null;
      controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=.12;controls.target.copy(center);controls.minDistance=radius*.02;controls.maxDistance=radius*100;
      controls.listenToKeyEvents(canvas);controls.addEventListener('change',()=>{dirty=true;});
      const grid=new THREE.GridHelper(radius*4,20,0x748195,0x394455);grid.position.set(center.x,box.min.y-.002*radius,center.z);world.add(grid);
      const shotMode=fixed=>{shotFixed=fixed;controls.enabled=!fixed;host.dataset.cameraMode=fixed?'saved-shot':'orbit-inspection';const button=node('orbit');if(button)button.setAttribute('aria-pressed',String(!fixed));dirty=true;};
      if(shotRig){
        controls.enabled=false;grid.visible=false;node('grid').setAttribute('aria-pressed','false');
        node('reset').textContent='Return to shot camera';
        const orbit=document.createElement('button');orbit.type='button';orbit.dataset.view='orbit';orbit.textContent='Orbit inspection';orbit.setAttribute('aria-pressed','false');node('reset').before(orbit);
        listen(orbit,'click',()=>{shotMode(!shotFixed);if(!shotFixed)reset();});shotMode(true);
        canvas.setAttribute('aria-label','Saved shot camera. Use Orbit inspection to look around without changing the camera.');
        host.querySelector('.viewer-help').textContent='Saved Blender camera · scrub or play this shot. Orbit inspection never changes the camera. F returns to the shot camera.';
      }
      const gridRadius=radius;
      const reset=()=>{
        // Fit the evaluated pose, not the bind pose cached before animation.
        model.updateMatrixWorld(true);model.traverse(o=>o.skeleton?.update());
        bounds(box);
        if(!shotRig)for(const point of actionPathPoints(actionEdit?.getDraft?.()?.arrow?.()))box.expandByPoint(new THREE.Vector3(...point));
        box.getCenter(center);box.getSize(size);radius=Math.max(size.length()/2,.01);
        if(!Number.isFinite(radius)||radius>1e9)throw Error('Invalid animated dimensions.');
        camera.near=Math.max(radius/10000,.00001);camera.far=radius*1000;camera.updateProjectionMatrix();
        const limitingFov=Math.min(THREE.MathUtils.degToRad(camera.fov/2),Math.atan(Math.tan(THREE.MathUtils.degToRad(camera.fov/2))*camera.aspect));
        camera.position.copy(center).add(new THREE.Vector3(1,.5,1.4).normalize().multiplyScalar(radius/Math.sin(limitingFov)*1.12));
        grid.scale.setScalar(radius/gridRadius);grid.position.set(center.x,box.min.y-.002*radius,center.z);
        controls.minDistance=radius*.02;controls.maxDistance=radius*100;controls.target.copy(center);controls.update();dirty=true;
      };
      reset();resize=()=>{if(disposed)return;const width=surface.clientWidth,height=surface.clientHeight;if(width>0&&height>0){renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();actionPath?.update();actionRotation?.update();dirty=true;}};
      observer=new ResizeObserver(resize);observer.observe(surface);resize();
      const resetView=()=>{if(shotRig)shotMode(true);else reset();};
      resetCamera=resetView;
      listen(node('reset'),'click',resetView);listen(canvas,'keydown',e=>{if(e.key.toLowerCase()==='f'){e.preventDefault();resetView();}});
      listen(node('grid'),'click',()=>{grid.visible=!grid.visible;node('grid').setAttribute('aria-pressed',String(grid.visible));dirty=true;});
      listen(node('wire'),'click',()=>{const on=node('wire').getAttribute('aria-pressed')!=='true';node('wire').setAttribute('aria-pressed',String(on));model.traverse(o=>{for(const m of Array.isArray(o.material)?o.material:o.material?[o.material]:[])if('wireframe' in m)m.wireframe=on;});dirty=true;});
      const entries=animationEntries(gltf.animations,record.profile,record.playback?.static===true),takes=entries.map(e=>e.clip);
      playback=record.playback;staticFrame=playback?.start??null;
      mixer=new THREE.AnimationMixer(model);
      for(const [i,clip] of takes.entries()){const option=document.createElement('option');option.value=String(i);option.textContent=(clip.name||'Take '+(i+1))+' · '+(clip.duration===0?'Static pose':clip.duration.toFixed(2)+' s');node('take').append(option);}
      const clock=()=>{const time=shotView?shotTime:playback?.static?(staticFrame-playback.start)/playback.fps:action?.time||0,current=shotView?shotFrame(shotView,time):playback?Math.min(playback.end,Math.round(playback.start+time*playback.fps)):null;
        if(shotRig){shotRig.frame(current);if(action){action.paused=false;action.time=(current-playback.start)/playback.fps;mixer.update(0);}host.dataset.shotFrame=String(current);}
        node('clock').textContent=playback?'Frame '+current+' · '+time.toFixed(2)+' s':time.toFixed(2)+' s';node('time').value=String(shotView?current:time);};
      const select=()=>{mixer.stopAllAction();playing=false;node('play').textContent='Play';const clip=takes[Number(node('take').value)],staticPose=clip.duration===0;action=mixer.clipAction(clip);action.reset().setLoop(staticPose||shotRig?THREE.LoopOnce:THREE.LoopRepeat,Infinity);action.clampWhenFinished=staticPose||!!shotRig;action.play();mixer.update(0);node('time').max=String(clip.duration);node('play').disabled=staticPose;node('time').disabled=staticPose;clock();reset();dirty=true;};
      if(takes.length)select();else{host.querySelector('.viewer-animation').hidden=true;}
      const seekNote=document.createElement('p');seekNote.className='viewer-seek-note';seekNote.dataset.viewSeekNote='';seekNote.hidden=true;surface.after(seekNote);
      seekActionFrame=(value,turnTarget=false,exact=false)=>{
        if(!playback||shotView||(!action&&!playback.static)||!Number.isFinite(value))return;
        if(!turnTarget)actionRotation?.clear();playing=false;node('play').textContent='Play';
        const requested=exact?value:Math.round(value),actual=Math.max(playback.start,Math.min(playback.end,requested));
        if(action){action.setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;action.paused=false;action.enabled=true;action.time=(actual-playback.start)/playback.fps;mixer.update(0);}else staticFrame=actual;
        clock();seekNote.hidden=requested===actual&&!playback.static;
        seekNote.textContent=playback.static?'Static saved pose at frame '+actual+'. Save changes to preview this animation.':'Draft starts at frame '+requested+'; saved playback covers '+playback.start+'–'+playback.end+'. Showing saved frame '+actual+'. Save changes to preview the new timing.';
        actionPath?.update();actionRotation?.frameChanged();dirty=true;
      };
      if(record.profile==='action-playback-v1'){
        if(playback.static===true){host.querySelector('.viewer-animation').hidden=false;node('play').disabled=true;node('time').disabled=true;clock();}
        node('take').closest('label').hidden=true;
        const label=document.createElement('strong');label.className='scene-playback-label';label.textContent=(playback.static?'Static scene':'Whole scene')+' · '+playback.fps+' fps';host.querySelector('.viewer-animation').prepend(label);
        host.querySelector('.viewer-disclaimer:not(.viewer-texture-note)').textContent=(playback.static?'Static saved scene':'Combined saved performance')+' · frames '+playback.start+'–'+playback.end+'. No rig editing or motion-quality approval. Materials and lighting remain inspection approximations.';
      }
      if(shotView){
        host.querySelector('.viewer-animation').hidden=false;node('take').closest('label').hidden=true;
        node('time').min=String(shotView.shot.start);node('time').max=String(shotView.shot.end);node('time').step='1';node('time').setAttribute('aria-label','Shot frame');
        node('play').disabled=node('time').disabled=shotView.shot.start===shotView.shot.end;
        const label=document.createElement('strong');label.className='scene-playback-label';label.textContent=shotView.shot.name+' · '+shotView.shot.camera+' · '+Number(shotView.fps.toFixed(3))+' fps';host.querySelector('.viewer-animation').prepend(label);
        host.querySelector('.viewer-disclaimer:not(.viewer-texture-note)').textContent='Saved shot · frames '+shotView.shot.start+'–'+shotView.shot.end+'. Exact sampled Blender camera; materials and lighting are inspection approximations. Depth of field is not simulated. Use rendered previews to review lighting.';
        clock();
      }
      if(record.profile==='world-static-v1')host.querySelector('.viewer-disclaimer:not(.viewer-texture-note)').textContent='Static World preview'+(Number.isInteger(record.referenceFrame)?' at frame '+record.referenceFrame:'')+'. Animation and rig editing belong in Action. Original materials and motion are preserved.';
      listen(node('take'),'change',select);
      listen(node('play'),'click',()=>{actionRotation?.clear();seekNote.hidden=true;playing=!playing;if(playing&&action&&!shotView){action.setLoop(THREE.LoopRepeat,Infinity);action.clampWhenFinished=false;action.paused=false;action.enabled=true;}node('play').textContent=playing?'Pause':'Play';last=performance.now();});
      listen(node('time'),'input',()=>{actionRotation?.clear();seekNote.hidden=true;playing=false;node('play').textContent='Play';if(shotView)shotTime=(Number(node('time').value)-shotView.shot.start)/shotView.fps;else if(action){action.paused=false;action.time=Number(node('time').value);mixer.update(0);}clock();actionRotation?.frameChanged();dirty=true;});
      listen(document,'visibilitychange',()=>{last=performance.now();});
      listen(canvas,'webglcontextlost',e=>{e.preventDefault();playing=false;cancelAnimationFrame(frame);host.dataset.viewerState='failed';status().textContent='The 3D graphics context was lost. Close and reopen this preview, or inspect in Blender.';});
      const poseCount=entries.filter(e=>e.staticPose).length,playable=takes.length-poseCount;
      const motionStatus=shotView?'saved shot camera and range':record.profile==='world-static-v1'?'static World':record.profile==='action-playback-v1'?(playback.static?'static saved scene':'combined saved scene'):`${playable} playable take${playable===1?'':'s'}${poseCount?' · '+poseCount+' static pose'+(poseCount===1?'':'s'):''}`;
      status().textContent=`${record.observed.vertices.toLocaleString()} vertices · ${motionStatus} · source ${record.version.slice(0,12)} · ${record.cached?'verified cached copy':'verified preview copy'}`;
      if(worldEdit&&record.kind==='checkpoint'&&record.profile==='world-static-v1'&&record.placement?.instances.length){
        const {attachWorldEditor}=await import('./world-editor.mjs');if(disposed)return;
        editor=attachWorldEditor({THREE,host,model,gltf,world,camera,orbit:controls,canvas,record,...worldEdit,invalidate:()=>{dirty=true;}});
        worldEdit.changed?.(editor.state);
      }
      if(actionEdit&&record.profile==='action-playback-v1'){
        const {attachActionPath}=await import('./action-path-editor.mjs');if(disposed)return;
        actionPath=attachActionPath({THREE,host,world,camera,canvas,orbit:controls,...actionEdit,invalidate:()=>{dirty=true;}});
        cleanups.push(()=>actionPath?.dispose());
        const {attachActionRotation}=await import('./action-rotation-editor.mjs');if(disposed)return;
        actionRotation=attachActionRotation({THREE,host,model,gltf,world,camera,canvas,orbit:controls,...actionEdit,
          currentFrame:()=>playback.static?staticFrame:Math.min(playback.end,Math.round(playback.start+(action?.time||0)*playback.fps)),
          seekFrame:value=>seekActionFrame(value,true),isPlaying:()=>playing,invalidate:()=>{dirty=true;}});
        cleanups.push(()=>actionRotation?.dispose());
      }
      host.dataset.viewerState='ready';host.dataset.previewId=record.previewId;
      function animate(now){if(disposed)return;frame=requestAnimationFrame(animate);if(document.hidden||(!host.closest('dialog')&&document.querySelector('dialog[open]'))){last=now;return;}const dt=Math.min((now-(last||now))/1000,.1);last=now;if(playing){if(shotView){const duration=(shotView.shot.end-shotView.shot.start+1)/shotView.fps;shotTime=(shotTime+dt)%duration;}else mixer.update(dt);clock();actionRotation?.frameChanged();dirty=true;}if(controls.enabled)controls.update();if(dirty){
        if(shotRig&&shotFixed){const width=surface.clientWidth,height=surface.clientHeight,v=shotViewport(width,height,shotView.aspect);renderer.setScissorTest(false);renderer.setViewport(0,0,width,height);renderer.setClearColor(0x080b10);renderer.clear();renderer.setViewport(v.x,v.y,v.width,v.height);renderer.setScissor(v.x,v.y,v.width,v.height);renderer.setScissorTest(true);renderer.setClearColor(0x161c25);renderer.render(world,shotRig.camera);renderer.setScissorTest(false);}
        else{renderer.setViewport(0,0,surface.clientWidth,surface.clientHeight);renderer.render(world,camera);}dirty=false;}}
      frame=requestAnimationFrame(animate);
      return record;
    }catch(error){
      relinquish();
      if(disposed)return;cancelAnimationFrame(frame);observer?.disconnect();actionRotation?.dispose();actionRotation=null;actionPath?.dispose();actionPath=null;editor?.dispose();editor=null;controls?.dispose();releaseTree([world,...loadedScenes]);renderer?.dispose();world=null;loadedScenes=[];model=null;renderer=null;controls=null;host.replaceChildren();
      const failure=previewFailure(error),box=document.createElement('div');box.className='viewer-message warn';box.setAttribute('role','alert');
      const title=document.createElement('strong');title.textContent=failure.title;box.append(title);
      for(const text of [failure.message,'Nothing was imported or changed in your scene.']){const p=document.createElement('p');p.textContent=text;box.append(p);}
      if(inspectInBlender){const button=document.createElement('button');button.type='button';button.textContent='Preview in Blender';button.dataset.viewerFallback='';listen(button,'click',async()=>{button.disabled=true;try{await inspectInBlender();}finally{if(!disposed)button.disabled=false;}});box.append(button);}
      const details=document.createElement('details'),summary=document.createElement('summary'),reason=document.createElement('p');summary.textContent='Technical details';reason.textContent=failure.detail;details.append(summary,reason);box.append(details);host.append(box);host.dataset.viewerState='failed';
    }
  })();
  return {dispose,ready,framePerformer:()=>resetCamera?.(),seekFrame:value=>seekActionFrame?.(value),seekFrameExact:value=>seekActionFrame?.(value,false,true),updateActionPath:()=>{actionPath?.update();actionRotation?.update();},get dirty(){return !!editor?.dirty;},get draft(){return editor?.state;},
    get currentFrame(){return shotView?shotFrame(shotView,shotTime):playback?.static?staticFrame:playback?Math.min(playback.end,Math.round(playback.start+(action?.time||0)*playback.fps)):null;},
    request:id=>{if(!editor)throw Error('This saved scene needs placement preparation in Blender.');return editor.request(id);},
    targets:()=>editor?.targets()||[],undo:()=>editor?.undo(),discard:()=>editor?.discard(),setEnabled:value=>editor?.setEnabled(value)};
}
