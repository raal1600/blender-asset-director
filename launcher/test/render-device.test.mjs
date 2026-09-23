// Synthetic policy/UI tests; real GPU evidence is a separate local gate.
import test from 'node:test';
import assert from 'node:assert/strict';
import {validateRenderDevice} from '../lib/render-device.mjs';
import {renderDevices,deviceControl,selectedDevice,deviceLabel,outputDevice} from '../public/workbench-render-device.mjs';
const gpu={backend:'OPTIX',id:'test-gpu',name:'Synthetic <GPU>'},ready={render_devices:[gpu]},cap={gpu_render:true};
test('CPU default and historical readiness remain usable',()=>{
 validateRenderDevice(undefined,{},{});validateRenderDevice({backend:'CPU'},{},{});
 assert.equal(renderDevices({},cap).length,1);assert.deepEqual(selectedDevice({},cap,0),{backend:'CPU'});
 assert.equal(deviceLabel({backend:'CPU'},{},{}),'CPU');
});
test('GPU requires matching capability and exact observed identity',()=>{
 validateRenderDevice({backend:'OPTIX',id:gpu.id},ready,cap);
 for(const [v,r,c] of [[gpu,ready,cap],[{backend:'OPTIX',id:'missing'},ready,cap],[{backend:'OPTIX',id:gpu.id},ready,{}],[{backend:'OPTIX',id:gpu.id},{render_devices:[gpu,gpu]},cap],[{backend:'AUTO'},ready,cap],[{backend:'CPU',id:'x'},ready,cap]])
  assert.throws(()=>validateRenderDevice(v,r,c));
});
test('UI uses escaped detected devices, explicit selection and honest evidence',()=>{
 const esc=s=>String(s).replaceAll('<','&lt;').replaceAll('>','&gt;');
 const html=deviceControl(ready,cap,esc);
 assert.match(html,/Synthetic &lt;GPU&gt;/);assert.match(html,/No automatic CPU fallback/);
 assert.deepEqual(selectedDevice(ready,cap,1),{backend:'OPTIX',id:gpu.id});
 assert.match(deviceLabel(selectedDevice(ready,cap,1),ready,cap),/OptiX GPU/);
 assert.throws(()=>selectedDevice(ready,cap,99));assert.throws(()=>selectedDevice(ready,cap,0.5));
 assert.equal(renderDevices(ready,{}).length,1);
 assert.equal(outputDevice({data:{engine:'CYCLES_CPU'}}),'CYCLES_CPU');
 assert.match(outputDevice({data:{render_device:gpu}}),/OPTIX/);
});
