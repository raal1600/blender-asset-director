export function candidateState(scene,c){
 const review=scene.transitionReview;
 if(scene.current===c.checkpointId&&review?.acceptances.some(e=>e.checkpointId===c.checkpointId))return 'Accepted';
 if(!review?.working||review.working.fingerprint!==c.fingerprint||scene.current!==c.baseCheckpointId)return 'Stale';
 return c.validation?.status==='PASS'?'Ready for review':c.validation?.status==='FAIL'?'Failed quality checks':'Validating';
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
 '<ol>'+[...candidates].reverse().map((c,i)=>{const state=candidateState(scene,c);return '<li><strong>Candidate '+(candidates.length-i)+' · '+esc(state)+'</strong> '+b('Inspect / compare','transition-review',{id:c.id},'ghost',active)+b('Accept candidate','transition-accept',{id:c.id},'primary',active||draft?.invalid||state!=='Ready for review')+'<details><summary>Validation and provider details</summary><pre>'+esc(JSON.stringify({id:c.id,request:c.requestId,sha256:c.sha256,validation:c.validation,transitions:c.transitions},null,2))+'</pre></details></li>';}).join('')+'</ol>'+
 failures.map(r=>'<p class="warn">'+esc(r.state==='FAILED'?'Failed execution':r.state==='CANCELLED'?'Cancelled':'Interrupted')+': '+esc(r.error||'Inspect the retained attempt. Previous accepted scene retained.')+'</p>').join('')+
 (review?.acceptances.length?'<details><summary>Accepted history / restore</summary>'+[...new Set(review.acceptances.flatMap(e=>[e.previousCheckpointId,e.checkpointId]))].map(id=>b('Restore '+id.slice(0,11),'transition-restore',{id},'ghost',active||id===scene.current)).join('')+'</details>':'')+'</section>';
}
