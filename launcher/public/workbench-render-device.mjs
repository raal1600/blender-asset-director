// Explicit per-render device selection. Old readiness remains CPU-only.
export function renderDevices(ready,cap){
 const result=[{backend:'CPU',id:'CPU',name:'CPU (2 threads)'}];
 if(cap?.gpu_render)for(const d of ready?.render_devices||[]){
  if(d.backend==='OPTIX'&&typeof d.id==='string'&&d.id&&typeof d.name==='string'&&!result.some(x=>x.backend===d.backend&&x.id===d.id))result.push(d);
 }
 return result;
}
export function deviceControl(ready,cap,esc){
 const devices=renderDevices(ready,cap);
 return '<label class="full">Render device<select id="render-device">'+devices.map((d,i)=>'<option value="'+i+'">'+esc(d.backend==='CPU'?d.name:d.name+' · OptiX GPU')+'</option>').join('')+'</select></label><p class="full muted">GPU uses the selected card for OptiX rendering and denoising when enabled. No automatic CPU fallback; a failed GPU render keeps its evidence. Choose CPU explicitly to retry.</p>'+(ready?.device_warnings||[]).map(x=>'<p class="full warn">'+esc(x)+'</p>').join('');
}
export function selectedDevice(ready,cap,index){
 const d=renderDevices(ready,cap)[Number(index)];
 if(!d||!Number.isInteger(Number(index)))throw Error('Choose an observed render device.');
 return d.backend==='CPU'?{backend:'CPU'}:{backend:'OPTIX',id:d.id};
}
export function deviceLabel(device,ready,cap){
 if(!device||device.backend==='CPU')return 'CPU';
 const d=renderDevices(ready,cap).find(x=>x.backend===device.backend&&x.id===device.id);
 if(!d)throw Error('Selected GPU is not in current readiness. Check readiness again.');
 return d.name+' · OptiX GPU (render + enabled denoising)';
}
export function outputDevice(render){
 const d=render?.data?.render_device;
 return d?d.name+' · '+d.backend:(render?.data?.engine||'Device not recorded');
}
