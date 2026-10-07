import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

// Execute the actual client reconciliation function, without starting a browser.
// Native WebView2 acceptance separately covers viewer refresh and real jobs.
const source=await fs.readFile(new URL('../public/workbench.mjs',import.meta.url),'utf8');
const body=source.slice(source.indexOf('function acceptSnapshot(value){'),source.indexOf('\nasync function load()'));
const snapshot=stage=>({project:{workbench:{scenes:[{id:'scene',stage,current:'accepted'}]}},runs:[]});
function context(next){return {projectId:'project',sceneId:'scene',state:snapshot('action'),next,
 layerDrafts:new Map(),actionDrafts:new Map(),layerKey:()=> 'project:scene',sceneViewer:null,actionSave:null,
 reconcileWorldSave(){},reconcileLayerSave(){},
 currentActionDraft(){throw Error('Do not reconstruct the old persisted working request during refresh');},
 currentLayerDraft(){throw Error('Do not lazily build a draft while applying a new snapshot');}};}
const apply=c=>vm.runInNewContext(body+'\nacceptSnapshot(next);state;',c);

test('accepted or restored checkpoint refresh cannot recreate a discarded working draft',()=>{
 const c=context(snapshot('action'));
 assert.equal(apply(c),c.next);assert.equal(c.actionDrafts.size,0);
});
test('snapshot refresh still protects real cached edits when the activity changes',()=>{
 const c=context(snapshot('shots')),draft={dirty:true};c.actionDrafts.set('project:scene',draft);
 const before=c.state;assert.throws(()=>apply(c),/Action draft is retained/);assert.equal(c.state,before);assert.equal(c.actionDrafts.get('project:scene'),draft);
 c.actionDrafts.clear();c.layerDrafts.set('project:scene',{dirty:true,layer:'light'});
 assert.throws(()=>apply(c),/camera\/light draft is retained/);assert.equal(c.state,before);
});
test('ordinary same-activity refresh preserves cached unsaved choices',()=>{
 const c=context(snapshot('action')),draft={dirty:true};c.actionDrafts.set('project:scene',draft);
 assert.equal(apply(c),c.next);assert.equal(c.actionDrafts.get('project:scene'),draft);
});

test('a restored working draft cannot retain an empty viewer placeholder',()=>{
 const body=source.slice(source.indexOf('function retainedSceneHost(){'),source.indexOf('\nconst sceneViewKey='));
 const host={},c={sceneViewer:null,tab:'scenes',s:()=>({stage:'action'}),sceneViewerKey:null,sceneViewKey:()=> 'accepted',
  currentActionDraft:()=>({dirty:true}),currentLayerDraft:()=>null,document:{querySelector:()=>host}};
 const retained=()=>vm.runInNewContext(body+'\nretainedSceneHost();',c);
 assert.equal(retained(),null);
 c.sceneViewer={dirty:false};assert.equal(retained(),host);
 c.currentActionDraft=()=>({dirty:false});assert.equal(retained(),null);
 c.sceneViewerKey='accepted';assert.equal(retained(),host);
 c.tab='film';assert.equal(retained(),null);
});
