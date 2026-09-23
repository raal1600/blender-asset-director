import {assert} from './storage.mjs';
export function validateRenderDevice(value,ready,cap){
 if(value===undefined)return; // Historical CPU jobs stay compatible.
 assert(value&&typeof value==='object'&&!Array.isArray(value),'Invalid render device.');
 assert(Object.keys(value).every(k=>['backend','id'].includes(k))&&['CPU','OPTIX'].includes(value.backend),'Invalid render device.');
 if(value.backend==='CPU'){assert(Object.keys(value).length===1,'CPU selection must not identify a GPU.');return;}
 assert(cap?.gpu_render,'Configured harness does not support GPU rendering. Update the coherent runtime first.',409);
 assert(typeof value.id==='string'&&value.id.length>0&&value.id.length<=512&&!/[\x00-\x1f]/.test(value.id),'Choose an exact GPU identity.');
 assert((ready?.render_devices||[]).filter(d=>d.backend==='OPTIX'&&d.id===value.id).length===1,'GPU not observed in readiness. Check readiness again or explicitly choose CPU.',409);
}
