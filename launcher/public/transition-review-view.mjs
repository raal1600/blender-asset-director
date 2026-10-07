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
export function transitionReviewView(scene,draft,runs,esc,b,active){
 const review=scene.transitionReview,generated=draft?.changes?.some(c=>c.clips?.some(x=>x.transition?.mode==='generated'));
 if(!review&&!generated)return '';
 const candidates=review?.candidates||[],run=runs.find(r=>r.id===scene.run);
 const failures=runs.filter(r=>r.sceneId===scene.id&&r.publication==='TRANSITION_REVIEW_ONLY'&&['FAILED','CANCELLED','INTERRUPTED'].includes(r.state)).slice(-5).reverse();
 const state=run?run.state==='RUNNING'?'Generating':'Queued':candidates.length?'Review candidates':draft?.invalid?'Needs preparation':'Ready';
 return '<section class="transition-review" aria-label="Transition review"><h2>Review generated movement</h2><p role="status">'+esc(state)+'. The accepted scene remains available during generation and review.</p>'+
 (generated?b('Generate alternatives (3)','transition-alternatives',{},'primary',active||draft.invalid):'')+
 '<p>Each candidate contains the complete working timeline. Changing an earlier join can move or retime every later join. Accept a complete consistent revision after review.</p>'+
 '<ol>'+[...candidates].reverse().map((c,i)=>{const state=candidateState(scene,c),advice=state==='Stale'?['Inputs changed. Generate a candidate for the current working request.']:state==='Needs preparation'?['The application build needs verification. Inspect the technical details and rebuild an isolated installation before regenerating.']:qualityAdvice(c.validation);return '<li><strong>Candidate '+(candidates.length-i)+' · '+esc(state)+'</strong> '+b('Inspect / compare','transition-review',{id:c.id},'ghost',active)+b('Accept candidate','transition-accept',{id:c.id},'primary',active||draft?.invalid||state!=='Ready for review')+advice.map(text=>'<p>'+esc(text)+'</p>').join('')+'<details><summary>Validation and provider details</summary><pre>'+esc(JSON.stringify({id:c.id,request:c.requestId,sha256:c.sha256,applicationIdentity:c.applicationIdentity,traceSource:c.traceSource,validation:c.validation,transitions:c.transitions},null,2))+'</pre></details></li>';}).join('')+'</ol>'+
 failures.map(r=>'<p class="warn">'+esc(r.state==='FAILED'?'Failed execution':r.state==='CANCELLED'?'Cancelled':'Interrupted')+': '+esc(r.error||'Inspect the retained attempt. Previous accepted scene retained.')+'</p>').join('')+
 (review?.acceptances.length?'<details><summary>Accepted history / restore</summary>'+[...new Set(review.acceptances.flatMap(e=>[e.previousCheckpointId,e.checkpointId]))].map(id=>b('Restore '+id.slice(0,11),'transition-restore',{id},'ghost',active||id===scene.current)).join('')+'</details>':'')+'</section>';
}
