import test from 'node:test';
import assert from 'node:assert/strict';
import {candidateState,candidateRankings,qualityAdvice,transitionReviewView} from '../public/transition-review-view.mjs';

test('saved generated motion offers explicit regeneration before any clip edit',()=>{
 const scene={transitionReview:{candidates:[],acceptances:[]}},draft={changes:[],hasGeneratedTransitions:true};
 const html=transitionReviewView(scene,draft,[],String,label=>label,false);
 assert.match(html,/Generate alternatives \(3\)/);
 draft.hasGeneratedTransitions=false;
 assert.doesNotMatch(transitionReviewView(scene,draft,[],String,label=>label,false),/Generate alternatives/);
});

test('review identifies the downstream joins and preserves complete-revision acceptance semantics',()=>{
 const scene={transitionReview:{candidates:[],acceptances:[]}},draft={hasGeneratedTransitions:true,dependencyImpact:[{performer:'Rig',changedClip:'Source',joins:[{label:'Middle',targetFrame:43},{label:'Last',targetFrame:85}]}]};
 const html=transitionReviewView(scene,draft,[],String,label=>label,false);
 assert.match(html,/into Middle \(target frame 43\).*into Last \(target frame 85\)/);
 assert.match(html,/accepted revision stays available/);assert.match(html,/complete replacement/);
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

const rankedCandidate=(id,scores)=>({id,checkpointId:id,baseCheckpointId:'base',fingerprint:'f',applicationIdentity:{status:'VERIFIED'},
 transitions:scores.map(()=>({provider:'motion-bricks.cpp'})),validation:{status:'PASS',joins:scores.map(score=>({status:'PASS',failures:[],preset:'upright-grounded-kinematic-v2',rank_score:score}))}});
const rankingScene=()=>({current:'base',transitionReview:{working:{fingerprint:'f'},candidates:[],acceptances:[]}});
test('quality ranking excludes failed, stale, duplicate and incomplete evidence regardless of attractive scores',()=>{
 const scene=rankingScene(),a=rankedCandidate('a',[4,6]),b=rankedCandidate('b',[2,4]);
 const rejected=rankedCandidate('failed',[0]);rejected.validation.status='FAIL';
 const failedJoin=rankedCandidate('failed-join',[0]);failedJoin.validation.joins[0].failures=[{metric:'penetration_m'}];
 const stale={...rankedCandidate('stale',[0]),fingerprint:'old'};
 const duplicate={...rankedCandidate('duplicate',[0]),diversity:{near_duplicate_of:['b']}};
 const incomplete=rankedCandidate('incomplete',[0,0]);incomplete.validation.joins.pop();
 const missing=rankedCandidate('missing',[NaN]);
 const unverified={...rankedCandidate('unverified',[0]),applicationIdentity:{status:'UNVERIFIED'}};
 const wrongPreset=rankedCandidate('wrong-preset',[0]);wrongPreset.validation.joins[0].preset='unknown';
 const candidates=[a,rejected,failedJoin,stale,duplicate,incomplete,missing,unverified,wrongPreset,b],before=structuredClone(candidates);
 assert.deepEqual(candidateRankings(scene,candidates),[{id:'b',number:10,score:3,rank:1,count:2},{id:'a',number:1,score:5,rank:2,count:2}]);
 assert.deepEqual(candidates,before,'Ranking never edits or accepts candidates');
});
test('quality ranks preserve ties and cannot survive a dependency change or acceptance',()=>{
 const scene=rankingScene(),candidates=[rankedCandidate('a',[2]),rankedCandidate('b',[2]),rankedCandidate('c',[3])];
 assert.deepEqual(candidateRankings(scene,candidates).map(v=>v.rank),[1,1,3]);
 scene.transitionReview.working.fingerprint='changed';assert.deepEqual(candidateRankings(scene,candidates),[]);
 scene.transitionReview.working.fingerprint='f';scene.current='a';scene.transitionReview.acceptances=[{checkpointId:'a'}];assert.deepEqual(candidateRankings(scene,candidates),[]);
});
test('review displays a quality order for eligible alternatives without changing acceptance controls',()=>{
 const scene=rankingScene();scene.transitionReview.candidates=[rankedCandidate('a',[5]),rankedCandidate('b',[3])];
 const html=transitionReviewView(scene,{hasGeneratedTransitions:true},[],String,label=>label,false);
 assert.match(html,/data-quality-ranking/);assert.match(html,/Candidate 2 \(rank 1\).*Candidate 1 \(rank 2\)/);assert.match(html,/not a naturalness or physics guarantee/);
 assert.equal((html.match(/Accept candidate/g)||[]).length,2);
});
