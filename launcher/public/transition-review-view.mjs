export function candidateState(scene,c){
 const review=scene.transitionReview;
 if(scene.current===c.checkpointId&&review?.acceptances.some(e=>e.checkpointId===c.checkpointId))return 'Accepted';
 if(!review?.working||review.working.fingerprint!==c.fingerprint||scene.current!==c.baseCheckpointId)return 'Stale';
 return c.validation?.status==='PASS'?(c.applicationIdentity?.status==='VERIFIED'?'Ready for review':'Needs preparation'):'Failed quality checks';
}
export function qualityAdvice(validation){
 const metrics=new Set((validation?.joins||[]).flatMap(j=>(j.failures||[]).map(f=>f.metric)));
 const advice=[];
 if([...metrics].some(m=>/acceleration|speed/.test(m)))advice.push('Motion changes too sharply. Try another supported transition duration or compare another model sample.');
 if([...metrics].some(m=>/planted|penetration|support|contact/.test(m)))advice.push('Foot support did not pass. Review the source and target contact intervals and ground calibration, then regenerate.');
 if([...metrics].some(m=>/correction/.test(m)))advice.push('This prediction needs too much correction. Try another duration or explicitly select a different native boundary in a new request.');
 if([...metrics].some(m=>/position_m|orientation_deg|velocity/.test(m)))advice.push('The bridge does not match the selected native boundary closely enough. Compare another sample or duration.');
 if(validation?.status!=='PASS'&&!advice.length)advice.push('Required quality evidence is missing or failed. Inspect the validation details before regenerating.');
 return advice;
}
export function candidateRankings(scene,candidates){
 // Compare only the current complete request after every hard gate passes.
 // A normalized score is a review aid, never evidence of physical feasibility.
 const eligible=candidates.flatMap((c,index)=>{
  const joins=c.validation?.joins;
  if(candidateState(scene,c)!=='Ready for review'||c.diversity?.near_duplicate_of?.length||!joins?.length)return [];
  const generated=c.transitions?.filter(j=>j.provider==='motion-bricks.cpp');
  if(!generated?.length||generated.length!==joins.length||joins.some(j=>j.status!=='PASS'||j.failures?.length||j.preset!=='upright-grounded-kinematic-v2'||!Number.isFinite(j.rank_score)||j.rank_score<0))return [];
  return [{id:c.id,number:index+1,score:joins.reduce((sum,j)=>sum+j.rank_score,0)/joins.length}];
 });
 eligible.sort((a,b)=>a.score-b.score||a.number-b.number);
 return eligible.map(v=>({...v,rank:eligible.findIndex(p=>p.score===v.score)+1,count:eligible.length}));
}
export function transitionReviewView(scene,draft,runs,esc,b,active){
 const review=scene.transitionReview,generated=draft?.hasGeneratedTransitions||draft?.changes?.some(c=>c.clips?.some(x=>x.transition?.mode==='generated'));
 if(!review&&!generated)return '';
 const candidates=review?.candidates||[],run=runs.find(r=>r.id===scene.run);
 const failures=runs.filter(r=>r.sceneId===scene.id&&r.publication==='TRANSITION_REVIEW_ONLY'&&['FAILED','CANCELLED','INTERRUPTED'].includes(r.state)).slice(-5).reverse();
 const state=run?transitionPhase(run):candidates.length?'Review candidates':draft?.invalid?'Needs preparation':'Ready';
 const impact=draft?.dependencyImpact||[];
 const ranking=candidateRankings(scene,candidates);
 return '<section class="transition-review" aria-label="Transition review"><h2>Review generated movement</h2><p role="status">'+esc(state)+'. The accepted scene remains available during generation and review.</p>'+
 (generated?b('Generate alternatives (3)','transition-alternatives',{},'primary',active||draft.invalid):'')+
 '<p>Each candidate contains the complete working timeline. Changing an earlier join can move or retime every later join. Accept a complete consistent revision after review.</p>'+
 (ranking.length?'<div data-quality-ranking><strong>Quality review order</strong><p>'+ranking.map(v=>'Candidate '+v.number+' (rank '+v.rank+')').join(' → ')+'.</p><p>Only current candidates that pass every quality check are ranked. Near duplicates are omitted. Lower normalized seam, support, motion and correction errors rank first; tied scores share a rank. This is a review aid, not a naturalness or physics guarantee.</p></div>':'')+
 (impact.length?'<div data-transition-dependencies><strong>Working timeline dependencies</strong>'+impact.map(row=>'<p>'+esc(row.performer)+' · change at '+esc(row.changedClip)+'. '+(row.joins.length?'Review these affected joins in order: '+row.joins.map(j=>'into '+esc(j.label)+' (target frame '+esc(j.targetFrame)+')').join(' → ')+'.':'No later joins remain in this track.')+'</p>').join('')+'<p>Generation bakes the complete requested timeline. The accepted revision stays available until you accept the complete replacement.</p></div>':'')+
 '<ol>'+[...candidates].reverse().map((c,i)=>{const state=candidateState(scene,c),advice=state==='Stale'?['Inputs changed. Generate a candidate for the current working request.']:state==='Needs preparation'?['The application build needs verification. Inspect the technical details and rebuild an isolated installation before regenerating.']:qualityAdvice(c.validation);return '<li><strong>Candidate '+(candidates.length-i)+' · '+esc(state)+'</strong> '+b('Inspect / compare','transition-review',{id:c.id},'ghost',active)+b('Accept candidate','transition-accept',{id:c.id},'primary',active||draft?.invalid||state!=='Ready for review')+(c.diversity?.near_duplicate_of?.length?'<p>Near duplicate of an earlier candidate: '+esc(c.diversity.near_duplicate_of.join(', '))+'. No useful corrected-motion variation was measured.</p>':'')+advice.map(text=>'<p>'+esc(text)+'</p>').join('')+'<details><summary>Validation and provider details</summary><pre>'+esc(JSON.stringify({id:c.id,request:c.requestId,sha256:c.sha256,applicationIdentity:c.applicationIdentity,traceSource:c.traceSource,diversity:c.diversity,validation:c.validation,transitions:c.transitions},null,2))+'</pre></details></li>';}).join('')+'</ol>'+
 failures.map(r=>'<p class="warn">'+esc(r.state==='FAILED'?'Failed execution':r.state==='CANCELLED'?'Cancelled':'Interrupted')+': '+esc(r.error||'Inspect the retained attempt. Previous accepted scene retained.')+'</p>').join('')+
 (review?.acceptances.length?'<details><summary>Accepted history / restore</summary>'+[...new Set(review.acceptances.flatMap(e=>[e.previousCheckpointId,e.checkpointId]))].map(id=>b('Restore '+id.slice(0,11),'transition-restore',{id},'ghost',active||id===scene.current)).join('')+'</details>':'')+'</section>';
}
import {transitionPhase} from './workbench-progress.mjs';
