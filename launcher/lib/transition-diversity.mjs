/** Numerical motion comparison; filenames, seeds and job metadata are irrelevant. */
import {assert,fileHash,json,safe} from './storage.mjs';
export const limits=Object.freeze({root_rms_height:1e-4,rotation_rms_degrees:.1});
const schema='motion-bricks.comparison.v1';
const finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);
export function motionDifference(a,b,height,secondsA,secondsB){
 assert(Number.isFinite(height)&&height>0&&Number.isFinite(secondsA)&&secondsA>0&&Number.isFinite(secondsB)&&secondsB>0,'Invalid motion comparison units.');
 if(Math.abs(secondsA-secondsB)>1e-7)return {status:'DIFFERENT_DURATIONS',near_duplicate:false};
 assert(Array.isArray(a.roots_m)&&a.roots_m.length>=3&&a.roots_m.length<=4096&&a.roots_m.length===a.rotations_wxyz?.length,'Invalid comparison samples.');
 assert(a.roots_m.length===b.roots_m?.length&&b.roots_m.length===b.rotations_wxyz?.length,'Comparison sampling differs.');
 let rootSquare=0,angleSquare=0,rootMax=0,angleMax=0,joints=0;
 // Endpoints are native pins. Compare only the independently generated interior.
 for(let i=1;i<a.roots_m.length-1;i++){
  assert(finite(a.roots_m[i],3)&&finite(b.roots_m[i],3),'Nonfinite root motion.');
  const distance=Math.hypot(...a.roots_m[i].map((v,j)=>v-b.roots_m[i][j]));rootSquare+=(distance/height)**2;rootMax=Math.max(rootMax,distance);
  const left=a.rotations_wxyz[i],right=b.rotations_wxyz[i],names=Object.keys(left).sort();
  assert(names.length>0&&names.length<=256&&JSON.stringify(names)===JSON.stringify(Object.keys(right).sort()),'Comparison skeletons differ.');
  for(const name of names){
   const q=left[name],r=right[name];assert(finite(q,4)&&finite(r,4),'Nonfinite joint motion.');
   const norm=Math.hypot(...q)*Math.hypot(...r);assert(norm>1e-12,'Invalid comparison quaternion.');
   const dot=Math.min(1,Math.abs(q.reduce((v,x,j)=>v+x*r[j],0)/norm)),angle=2*Math.acos(dot)*180/Math.PI;
   angleSquare+=angle*angle;angleMax=Math.max(angleMax,angle);joints++;
  }
 }
 const root=Math.sqrt(rootSquare/(a.roots_m.length-2)),angle=Math.sqrt(angleSquare/joints);
 return {status:'COMPARED_INTERIOR',root_rms_height:root,rotation_rms_degrees:angle,root_max_m:rootMax,rotation_max_degrees:angleMax,
  thresholds:limits,near_duplicate:root<=limits.root_rms_height&&angle<=limits.rotation_rms_degrees};
}
async function descriptor(library,candidate,join){
 const evidence=join.provenance?.evidence_file;if(!evidence)return null;
 const name=evidence.replace(/\.json$/,'-corrected.json');
 const member=candidate.artifacts.find(f=>f.path===`jobs/${candidate.nativeJobId}/${name}`);if(!member)return null;
 assert(member.size<=16*1024*1024,'Candidate comparison artifact exceeds its bound.');
 const file=await safe(library,member.path),actual=await fileHash(file);
 assert(actual.sha256===member.sha256&&actual.size===member.size,'Candidate motion evidence changed before comparison.');
 const value=(await json(file)).comparison;
 return value?.schema===schema?value:null;
}
export async function compareCandidates(library,candidate,history){
 const joins=candidate.transitions.filter(j=>j.provider==='motion-bricks.cpp');
 const result={schema,status:'FIRST_CANDIDATE',comparisons:[],near_duplicate_of:[],
  scope:'Raw neural and corrected pre-bake motion, matching physical duration and dependency fingerprint; not a quality or physics pass.'};
 const current=await Promise.all(joins.map(j=>descriptor(library,candidate,j)));
 if(!joins.length||current.some(v=>!v)){result.status='UNAVAILABLE';result.reason='Required numerical motion evidence is unavailable.';return result;}
 for(const prior of history.filter(c=>c.fingerprint===candidate.fingerprint)){
  const rows=[];
  for(let i=0;i<joins.length;i++){
   const join=joins[i],other=prior.transitions.find(j=>j.performer===join.performer&&j.clip_id===join.clip_id),a=current[i],b=other&&await descriptor(library,prior,other);
   if(!b){rows.push({clip_id:join.clip_id,status:'UNAVAILABLE',near_duplicate:false});continue;}
   assert(a.height_m===b.height_m,'Reviewed character height differs between comparable candidates.');
   rows.push({clip_id:join.clip_id,raw:motionDifference(a.raw,b.raw,a.height_m,a.seconds,b.seconds),
    corrected:motionDifference(a.corrected,b.corrected,a.height_m,a.seconds,b.seconds)});
  }
  result.comparisons.push({candidate_id:prior.id,joins:rows});
  if(rows.every(r=>r.corrected?.near_duplicate))result.near_duplicate_of.push(prior.id);
 }
 if(result.comparisons.length)result.status='COMPARED';
 return result;
}
