import test from 'node:test';
import assert from 'node:assert/strict';
import {candidateState,qualityAdvice,transitionReviewView} from '../public/transition-review-view.mjs';

test('saved generated motion offers explicit regeneration before any clip edit',()=>{
 const scene={transitionReview:{candidates:[],acceptances:[]}},draft={changes:[],hasGeneratedTransitions:true};
 const html=transitionReviewView(scene,draft,[],String,label=>label,false);
 assert.match(html,/Generate alternatives \(3\)/);
 draft.hasGeneratedTransitions=false;
 assert.doesNotMatch(transitionReviewView(scene,draft,[],String,label=>label,false),/Generate alternatives/);
});

test('missing quality evidence is a failure, while an unverified build requires preparation',()=>{
 const scene={current:'base',transitionReview:{working:{fingerprint:'f'},acceptances:[]}},candidate={baseCheckpointId:'base',fingerprint:'f'};
 assert.equal(candidateState(scene,candidate),'Failed quality checks');
 candidate.validation={status:'PASS'};assert.equal(candidateState(scene,candidate),'Needs preparation');
 candidate.applicationIdentity={status:'VERIFIED'};assert.equal(candidateState(scene,candidate),'Ready for review');
 scene.transitionReview.working.fingerprint='changed';assert.equal(candidateState(scene,candidate),'Stale');
});

test('failed measurements have actionable advice without suggesting ineffective provider knobs',()=>{
 const advice=qualityAdvice({status:'FAIL',joins:[{failures:[{metric:'joint_acceleration_deg_s2'},{metric:'planted_drift_m'},{metric:'rotation_correction_max_deg'}]}]});
 assert.equal(advice.length,3);assert.match(advice.join(' '),/contact intervals/);assert.match(advice.join(' '),/new request/);
 assert.deepEqual(qualityAdvice({status:'PASS'}),[]);assert.match(qualityAdvice(null)[0],/evidence is missing/);
});
