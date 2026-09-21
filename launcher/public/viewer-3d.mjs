/** Local WebGL inspection. No project writes and no connection to live Blender. */
export function viewerPlaceholder() {
  return '<section class="viewer-3d" data-viewer-host aria-label="Interactive 3D preview"><div class="viewer-message"><strong>Explore in 3D</strong><p>Orbit, zoom and pan the actual saved geometry. Native takes can be played when present.</p><p class="muted">Read-only inspection, not a final render or a live link to Blender.</p></div></section>';
}

export function animationEntries(animations) {
  return animations.filter(a=>a.tracks.length).map(clip=>{
    if(!Number.isFinite(clip.duration)||clip.duration<0)throw Error('Invalid animation duration.');
    return {clip,staticPose:clip.duration===0};
  });
}

function releaseTree(root) {
  const geometries=new Set(),materials=new Set(),textures=new Set(),skeletons=new Set();
  for(const tree of Array.isArray(root)?root:[root])tree?.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.skeleton)skeletons.add(o.skeleton);for(const m of Array.isArray(o.material)?o.material:o.material?[o.material]:[])materials.add(m);});
  for(const m of materials){for(const v of Object.values(m))if(v?.isTexture)textures.add(v);m.dispose();}
  for(const t of textures){t.source?.data?.close?.();t.dispose();}for(const g of geometries)g.dispose();for(const s of skeletons)s.dispose();
}

export function openViewer({host,prepare,fetchModel}) {
  let disposed=false,renderer,controls,world,mixer,frame=0,observer,model,action,playing=false,last=0,dirty=true,resize,loadedScenes=[];
  const abort=new AbortController(),cleanups=[];
  host.dataset.viewerState='loading';delete host.dataset.previewId;
  host.innerHTML='<div class="viewer-message" role="status" aria-live="polite">Verifying this exact source and preparing 3D geometry… Native files may need up to three minutes. No scene changes or render.</div>';
  const status=()=>host.querySelector('[data-viewer-status]');
  const listen=(node,type,fn,options)=>{node.addEventListener(type,fn,options);cleanups.push(()=>node.removeEventListener(type,fn,options));};
  const dispose=()=>{if(disposed)return;disposed=true;abort.abort();cancelAnimationFrame(frame);observer?.disconnect();for(const f of cleanups)f();controls?.dispose();mixer?.stopAllAction();if(model)mixer?.uncacheRoot(model);releaseTree([world,...loadedScenes]);renderer?.dispose();renderer?.forceContextLoss();host.replaceChildren();delete host.dataset.viewerState;delete host.dataset.previewId;};
  const ready=(async()=>{
    try {
      const [record,THREE,{GLTFLoader},{OrbitControls}]=await Promise.all([prepare(),import('./vendor/three/build/three.module.js'),import('./vendor/three/examples/jsm/loaders/GLTFLoader.js'),import('./vendor/three/examples/jsm/controls/OrbitControls.js')]);
      if(disposed)return;
      const bytes=await fetchModel(record,abort.signal);if(disposed)return;
      const manager=new THREE.LoadingManager();
      manager.setURLModifier(url=>{if(!url.startsWith('blob:'+location.origin+'/'))throw Error('External 3D resources are blocked.');return url;});
      const gltf=await new GLTFLoader(manager).parseAsync(bytes,'');
      model=gltf.scene;loadedScenes=gltf.scenes;if(disposed){releaseTree(loadedScenes);return;}
      host.innerHTML='<div class="viewer-toolbar"><strong data-viewer-title></strong><span class="grow"></span><button type="button" data-view="reset">Reset view</button><button type="button" data-view="grid" aria-pressed="true">Grid</button><button type="button" data-view="wire" aria-pressed="false">Wireframe</button></div><div class="viewer-canvas"></div><div class="viewer-animation"><label>Animation <select data-view="take" aria-label="Animation take"></select></label><button type="button" data-view="play">Play</button><input data-view="time" aria-label="Animation time" type="range" min="0" max="1" step="0.001" value="0"><output data-view="clock">0.00 s</output></div><p class="viewer-help">Drag to orbit · scroll to zoom · right-drag / Shift-drag to pan · focus view and use arrow keys to pan; F to reset.</p><p class="viewer-status" data-viewer-status role="status" aria-live="polite"></p><p class="viewer-disclaimer">Saved geometry with inspection lighting. Materials may differ from Blender. No import, edit, render or approval.</p>';
      host.querySelector('[data-viewer-title]').textContent=record.title;
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
      const box=new THREE.Box3().setFromObject(model,true),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3());
      let radius=Math.max(size.length()/2,0.01);if(!Number.isFinite(radius)||radius>1e9)throw Error('Invalid model dimensions.');
      const camera=new THREE.PerspectiveCamera(40,1,Math.max(radius/10000,.00001),radius*1000);
      controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=.12;controls.target.copy(center);controls.minDistance=radius*.02;controls.maxDistance=radius*100;
      controls.listenToKeyEvents(canvas);controls.addEventListener('change',()=>{dirty=true;});
      const grid=new THREE.GridHelper(radius*4,20,0x748195,0x394455);grid.position.set(center.x,box.min.y-.002*radius,center.z);world.add(grid);
      const gridRadius=radius;
      const reset=()=>{
        // Fit the evaluated pose, not the bind pose cached before animation.
        model.updateMatrixWorld(true);model.traverse(o=>o.skeleton?.update());
        box.setFromObject(model,true);box.getCenter(center);box.getSize(size);radius=Math.max(size.length()/2,.01);
        if(!Number.isFinite(radius)||radius>1e9)throw Error('Invalid animated dimensions.');
        camera.near=Math.max(radius/10000,.00001);camera.far=radius*1000;camera.updateProjectionMatrix();
        const limitingFov=Math.min(THREE.MathUtils.degToRad(camera.fov/2),Math.atan(Math.tan(THREE.MathUtils.degToRad(camera.fov/2))*camera.aspect));
        camera.position.copy(center).add(new THREE.Vector3(1,.5,1.4).normalize().multiplyScalar(radius/Math.sin(limitingFov)*1.12));
        grid.scale.setScalar(radius/gridRadius);grid.position.set(center.x,box.min.y-.002*radius,center.z);
        controls.minDistance=radius*.02;controls.maxDistance=radius*100;controls.target.copy(center);controls.update();dirty=true;
      };
      reset();resize=()=>{if(disposed)return;const width=surface.clientWidth,height=surface.clientHeight;if(width>0&&height>0){renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();dirty=true;}};
      observer=new ResizeObserver(resize);observer.observe(surface);resize();
      listen(node('reset'),'click',reset);listen(canvas,'keydown',e=>{if(e.key.toLowerCase()==='f'){e.preventDefault();reset();}});
      listen(node('grid'),'click',()=>{grid.visible=!grid.visible;node('grid').setAttribute('aria-pressed',String(grid.visible));dirty=true;});
      listen(node('wire'),'click',()=>{const on=node('wire').getAttribute('aria-pressed')!=='true';node('wire').setAttribute('aria-pressed',String(on));model.traverse(o=>{for(const m of Array.isArray(o.material)?o.material:o.material?[o.material]:[])if('wireframe' in m)m.wireframe=on;});dirty=true;});
      const entries=animationEntries(gltf.animations),takes=entries.map(e=>e.clip);
      mixer=new THREE.AnimationMixer(model);
      for(const [i,clip] of takes.entries()){const option=document.createElement('option');option.value=String(i);option.textContent=(clip.name||'Take '+(i+1))+' · '+(clip.duration===0?'Static pose':clip.duration.toFixed(2)+' s');node('take').append(option);}
      const clock=()=>{node('clock').textContent=(action?.time||0).toFixed(2)+' s';node('time').value=String(action?.time||0);};
      const select=()=>{mixer.stopAllAction();playing=false;node('play').textContent='Play';const clip=takes[Number(node('take').value)],staticPose=clip.duration===0;action=mixer.clipAction(clip);action.reset().setLoop(staticPose?THREE.LoopOnce:THREE.LoopRepeat,Infinity);action.clampWhenFinished=staticPose;action.play();mixer.update(0);node('time').max=String(clip.duration);node('play').disabled=staticPose;node('time').disabled=staticPose;clock();reset();dirty=true;};
      if(takes.length)select();else{host.querySelector('.viewer-animation').hidden=true;}
      listen(node('take'),'change',select);
      listen(node('play'),'click',()=>{playing=!playing;node('play').textContent=playing?'Pause':'Play';last=performance.now();});
      listen(node('time'),'input',()=>{playing=false;node('play').textContent='Play';action.time=Number(node('time').value);mixer.update(0);clock();dirty=true;});
      listen(document,'visibilitychange',()=>{last=performance.now();});
      listen(canvas,'webglcontextlost',e=>{e.preventDefault();playing=false;cancelAnimationFrame(frame);host.dataset.viewerState='failed';status().textContent='The 3D graphics context was lost. Close and reopen this preview, or inspect in Blender.';});
      const poseCount=entries.filter(e=>e.staticPose).length,playable=takes.length-poseCount;
      status().textContent=`${record.observed.vertices.toLocaleString()} vertices · ${playable} playable take${playable===1?'':'s'}${poseCount?' · '+poseCount+' static pose'+(poseCount===1?'':'s'):''} · source ${record.version.slice(0,12)} · ${record.cached?'verified cached copy':'verified preview copy'}`;
      host.dataset.viewerState='ready';host.dataset.previewId=record.previewId;
      function animate(now){if(disposed)return;frame=requestAnimationFrame(animate);if(document.hidden||(!host.closest('dialog')&&document.querySelector('dialog[open]'))){last=now;return;}const dt=Math.min((now-(last||now))/1000,.1);last=now;if(playing){mixer.update(dt);clock();dirty=true;}controls.update();if(dirty){renderer.render(world,camera);dirty=false;}}
      frame=requestAnimationFrame(animate);
      return record;
    }catch(error){if(disposed)return;cancelAnimationFrame(frame);observer?.disconnect();controls?.dispose();releaseTree([world,...loadedScenes]);renderer?.dispose();world=null;loadedScenes=[];model=null;renderer=null;controls=null;host.replaceChildren();const message=document.createElement('p');message.className='viewer-message warn';message.setAttribute('role','alert');message.textContent='3D preview unavailable: '+error.message+' Use the separate Blender preview for inspection.';host.append(message);host.dataset.viewerState='failed';}
  })();
  return {dispose,ready};
}
