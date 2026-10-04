import test from 'node:test';
import assert from 'node:assert/strict';
import {actionSelectionFrame,actionSelectionStamp,actionSelectionSeeking} from '../public/action-selection.mjs';
import {timelineDraft} from '../public/action-timeline-draft.mjs';

const take='take_'+'a'.repeat(64),checkpoint={id:'cp_synthetic',sha256:'b'.repeat(64)};
function savedDraft(){
 const clip={id:'clip_one',take_id:take,start:1,frames:25,speed:1,repeat_reviewed:false,travel:null};
 return timelineDraft(checkpoint,{id:'run_synthetic',inspection:{frame_range:[1,80],fps:24,reference_frame:1,performers:[{name:'Synthetic rig',takes:[{id:take,range:[1,25]}],timeline:{version:'action-timeline-v1',edit_version:'native-motion-edit-v1',clips:[clip,{...clip,id:'clip_two',start:38,transition:{frames:12,match_phase:false}}]}}]}});
}
function delayedViewer(){
 let resolve,reject;const calls=[];
 const ready=new Promise((a,b)=>{resolve=a;reject=b;});
 return {ready,resolve,reject,calls,seekFrame:frame=>calls.push(['seek-paused',frame]),updateActionPath:()=>calls.push(['overlay'])};
}

test('clip and transition selection resolve visible start frames without dirtying saved motion',()=>{
 const draft=savedDraft(),before=structuredClone(draft.run);
 draft.select('Synthetic rig','clip_two');assert.equal(actionSelectionFrame(draft),38);
 draft.select('Synthetic rig','clip_two','transition');assert.equal(actionSelectionFrame(draft),26);
 draft.select('Synthetic rig','clip_two','clip');assert.equal(actionSelectionFrame(draft),38);
 assert.equal(draft.dirty,false);assert.equal(draft.canUndo,false);assert.deepEqual(draft.run,before);
});
test('displayed draft start stays authoritative, including a new clip beyond the saved range',()=>{
 const draft=savedDraft();draft.select('Synthetic rig','clip_one');draft.edit('start','4');
 assert.equal(actionSelectionFrame(draft),4);assert.equal(draft.run.inspection.performers[0].timeline.clips[0].start,1);
 draft.add(take,'clip_new');draft.edit('start','100');assert.equal(actionSelectionFrame(draft),100);
 // Clamping belongs to the loaded saved viewer, never to the authored timeline.
 assert.equal(draft.selectedClip.start,100);
});
test('absent, invalid and legacy selections do not invent a preview frame',()=>{
 for(const draft of [null,{}, {timeline:true}, {timeline:false,selectedClip:{start:5}}, {timeline:true,selectedClip:{start:NaN}}, {timeline:true,selectedClip:{start:2.5}}, {timeline:true,selectedPart:'transition',selectedClip:{start:38}}, {timeline:true,selectedPart:'transition',selectedClip:{start:38,transition:{frames:121}}}])assert.equal(actionSelectionFrame(draft),null);
 assert.equal(actionSelectionFrame({timeline:true,selectedClip:{start:-10}}),-10);
 assert.equal(actionSelectionFrame({timeline:true,selectedPart:'transition',selectedClip:{start:0,transition:{frames:6}}}),-6);
});
test('seek waits for the real viewer, then pauses at the chosen frame and refreshes overlays',async()=>{
 const viewer=delayedViewer(),context='project:scene:action:checkpoint:hash',coordinator=actionSelectionSeeking(()=>({viewer,context}));
 let applied=0;const pending=coordinator.seek(viewer,context,38,()=>applied++);
 assert.deepEqual(viewer.calls,[]);viewer.resolve({playback:{start:1,end:80}});
 assert.equal(await pending,true);assert.deepEqual(viewer.calls,[['seek-paused',38],['overlay']]);assert.equal(applied,1);
});
test('newer clip selection wins when several requests await the same preview',async()=>{
 const viewer=delayedViewer(),context='same',coordinator=actionSelectionSeeking(()=>({viewer,context}));
 let oldApplied=false;const old=coordinator.seek(viewer,context,26,()=>oldApplied=true),latest=coordinator.seek(viewer,context,38);
 viewer.resolve({});assert.equal(await old,false);assert.equal(await latest,true);assert.equal(oldApplied,false);assert.deepEqual(viewer.calls,[['seek-paused',38],['overlay']]);
});
test('a delayed save-return frame cannot override a newer selected clip',async()=>{
 const viewer=delayedViewer(),context='same',coordinator=actionSelectionSeeking(()=>({viewer,context}));
 let returned=false;const saved=coordinator.seek(viewer,context,63,()=>returned=true),selected=coordinator.seek(viewer,context,1);
 viewer.resolve({});assert.equal(await saved,false);assert.equal(await selected,true);assert.equal(returned,false);assert.equal(viewer.calls[0][1],1);
});
test('project, scene, activity, checkpoint and preview replacement prevent stale seeks',async()=>{
 for(const changed of ['another-project','another-scene','shots','another-checkpoint','another-hash',null]){
  const viewer=delayedViewer();let current={viewer,context:'original'};const coordinator=actionSelectionSeeking(()=>current),pending=coordinator.seek(viewer,'original',38);
  current={viewer,context:changed};viewer.resolve({});assert.equal(await pending,false);assert.deepEqual(viewer.calls,[]);
 }
 const viewer=delayedViewer();let current={viewer,context:'same'};const coordinator=actionSelectionSeeking(()=>current),pending=coordinator.seek(viewer,'same',38);
 current={viewer:delayedViewer(),context:'same'};viewer.resolve({});assert.equal(await pending,false);assert.deepEqual(viewer.calls,[]);
});
test('clearing selection or a direct scrub cancels earlier pending navigation',async()=>{
 for(const cancel of [(c,v)=>c.cancel(),(c,v)=>c.seek(v,'same',null)]){
  const viewer=delayedViewer(),coordinator=actionSelectionSeeking(()=>({viewer,context:'same'})),pending=coordinator.seek(viewer,'same',38);
  await cancel(coordinator,viewer);viewer.resolve({});assert.equal(await pending,false);assert.deepEqual(viewer.calls,[]);
 }
});
test('failed or disposed previews do not seek, refresh overlays or consume return receipts',async()=>{
 for(const fail of [v=>v.reject(Error('synthetic load failure')),v=>v.resolve(undefined)]){
  const viewer=delayedViewer(),coordinator=actionSelectionSeeking(()=>({viewer,context:'same'}));let applied=false;
  const pending=coordinator.seek(viewer,'same',38,()=>applied=true);fail(viewer);assert.equal(await pending,false);assert.equal(applied,false);assert.deepEqual(viewer.calls,[]);
 }
});
test('a ready viewer still obeys newer same-turn click intent and supports native negative frames',async()=>{
 const viewer=delayedViewer();viewer.resolve({});const coordinator=actionSelectionSeeking(()=>({viewer,context:'same'}));
 const a=coordinator.seek(viewer,'same',1),b=coordinator.seek(viewer,'same',-6);
 assert.equal(await a,false);assert.equal(await b,true);assert.deepEqual(viewer.calls,[['seek-paused',-6],['overlay']]);
});
test('Undo of orientation retains its target; only changed selection or timing needs a new seek',()=>{
 const draft=savedDraft();draft.select('Synthetic rig','clip_two');const selected=actionSelectionStamp(draft);
 draft.edit('heading_deg','10');draft.finishEdit();draft.edit('heading_deg','20');draft.finishEdit();draft.undo();
 assert.equal(draft.selectedClip.heading_deg,10);assert.equal(actionSelectionStamp(draft),selected);
 const sameTarget={timeline:true,selected:draft.selected,selectedPart:draft.selectedPart,selectedClip:{...draft.selectedClip,heading_deg:10}};
 assert.equal(actionSelectionStamp(sameTarget),selected);
 assert.equal(actionSelectionStamp({...sameTarget,selectedClip:{...sameTarget.selectedClip,heading_deg:20}}),selected);
 assert.notEqual(actionSelectionStamp({...sameTarget,selectedPart:'transition'}),selected);
 assert.notEqual(actionSelectionStamp({...sameTarget,selected:'Another performer'}),selected);
 assert.notEqual(actionSelectionStamp({...sameTarget,selectedClip:{...sameTarget.selectedClip,id:'clip_replacement'}}),selected);
 assert.notEqual(actionSelectionStamp({...sameTarget,selectedClip:{...sameTarget.selectedClip,start:40}}),selected);
 assert.equal(actionSelectionStamp(null),null);assert.equal(actionSelectionStamp({timeline:true}),null);
});
