/** One explicit Save -> one bounded job -> verified, unapproved checkpoint.
 * Browser drafts never own a writer lease. This module acquires it only on Save.
 */
import {assert,digest} from './storage.mjs';
import {checkpointJob} from './checkpoint-job.mjs';
import {validHash,validId} from './workbench-model.mjs';

export function validateWorldSave(request) {
  assert(request&&typeof request==='object'&&!Array.isArray(request)&&
    Object.keys(request).every(k=>['version','requestId','checkpointId','sha256','transforms'].includes(k)), 'Invalid World save request.');
  assert(request.version==='world-transform-v1'&&validId(request.requestId,'run_')&&validId(request.checkpointId,'cp_')&&validHash(request.sha256), 'Invalid World save identity.');
  assert(Array.isArray(request.transforms)&&request.transforms.length>0&&request.transforms.length<=64, 'Save one to 64 whole assets.');
  const seen=new Set();
  for(const change of request.transforms){
    assert(change&&typeof change==='object'&&!Array.isArray(change)&&Object.keys(change).length===3&&
      Object.keys(change).every(k=>['instance','expected_matrix','matrix'].includes(k))&&validId(change.instance,'instance_')&&!seen.has(change.instance), 'Choose distinct observed asset instances.');
    seen.add(change.instance);
    for(const matrix of [change.expected_matrix,change.matrix])assert(Array.isArray(matrix)&&matrix.length===16&&matrix.every(x=>typeof x==='number'&&Number.isFinite(x)), 'Invalid placement matrix.');
  }
  return request;
}

export async function saveWorld(work,id,sceneId,revision,request) {
  validateWorldSave(request);
  const options={version:request.version,transforms:request.transforms};
  return checkpointJob(work,id,sceneId,revision,request,{
    stage:'world',operation:'world-transform',options,
    check:({cp})=>{
      // Saved-file imports intentionally have no cached scene audit. Their
      // preview can still expose native-verified instances. The bounded worker
      // resolves every identity/owner/expected matrix again before ANY mutation;
      // absence of this optional cache must not make those controls unsaveable.
      // A present audit still supplies the early unknown-target refusal below.
      if(cp.audit===null||cp.audit===undefined)return;
      const observed=cp.audit?.objects||[];
      for(const change of request.transforms){
        const control=observed.filter(o=>o.placement_control&&o.placement_instance===change.instance);
        assert(control.length===1&&control[0].type==='EMPTY','This instance has no verified placement control. Arrange it in Blender first.',409);
      }
    },
    verify:data=>assert(data.version===request.version&&data.reopened===true&&data.scene_audit&&Array.isArray(data.transforms)&&
      digest(data.transforms.map(x=>({instance:x.instance,expected_matrix:x.before,matrix:x.after})))===digest(options.transforms),'Native Save did not verify the exact placement batch.')
  });
}
