import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {motionDifference,compareCandidates} from '../lib/transition-diversity.mjs';
import {fileHash,writeJson} from '../lib/storage.mjs';
const motion=()=>({roots_m:Array.from({length:12},(_,i)=>[i*.02,0,0]),rotations_wxyz:Array.from({length:12},()=>({joint:[1,0,0,0]}))});
test('diversity compares numerical interior motion, ignores quaternion sign/noise and never warps duration',()=>{
 const a=motion(),b=motion();b.rotations_wxyz.forEach(p=>p.joint=[-1,0,0,0]);b.roots_m[4][1]=1e-7;
 assert(motionDifference(a,b,2,.55,.55).near_duplicate);
 b.rotations_wxyz[5].joint=[Math.cos(.1),0,Math.sin(.1),0];
 const varied=motionDifference(a,b,2,.55,.55);assert(!varied.near_duplicate);assert(varied.rotation_rms_degrees>1);
 assert.equal(motionDifference(a,b,2,.55,.8).status,'DIFFERENT_DURATIONS');
 b.roots_m[3][1]=NaN;assert.throws(()=>motionDifference(a,b,2,.55,.55),/Nonfinite/);
});
test('publication compares hash-verified raw/corrected artifacts and labels duplicate candidates',async t=>{
 const library=await fs.mkdtemp(path.join(os.tmpdir(),'motion-diversity-'));t.after(()=>fs.rm(library,{recursive:true,force:true}));
 async function candidate(id,raw,corrected){
  const member=`jobs/${id}/motion-bricks-clip_b-corrected.json`,file=path.join(library,member);
  await writeJson(file,{comparison:{schema:'motion-bricks.comparison.v1',height_m:2,seconds:.55,raw,corrected}});
  return {id,nativeJobId:id,fingerprint:'same',artifacts:[{path:member,...await fileHash(file)}],
   transitions:[{provider:'motion-bricks.cpp',performer:'Rig',clip_id:'clip_b',provenance:{evidence_file:'motion-bricks-clip_b.json'}}]};
 }
 const a=await candidate('first',motion(),motion()),changed=motion();changed.rotations_wxyz[4].joint=[Math.cos(.2),0,0,Math.sin(.2)];
 const b=await candidate('second',changed,motion());const result=await compareCandidates(library,b,[a]);
 assert.deepEqual(result.near_duplicate_of,['first']);assert(!result.comparisons[0].joins[0].raw.near_duplicate);
 assert(result.comparisons[0].joins[0].corrected.near_duplicate,'Correction can erase raw diversity and must report it');
 await fs.appendFile(path.join(library,a.artifacts[0].path),' ');
 await assert.rejects(compareCandidates(library,b,[a]),/evidence changed/);
});
