import test from 'node:test';
import assert from 'node:assert/strict';
import {preparationHint,preparationInspection,preparationDialog,preparationSelection} from '../public/workbench-world-prepare.mjs';
const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const b=(label,action,data={},style='',disabled=false)=>`<button data-action="${action}" ${disabled?'disabled':''}>${esc(label)}</button>`;
const checkpoint={id:'cp_test',sha256:'a'.repeat(64),audit:{objects:[{asset_id:'asset',import_job:'import'}]}};
const scene={id:'sc_test'},run={id:'run_test',sceneId:scene.id,action:'world-prepare-audit',state:'SUCCEEDED',checkpointId:checkpoint.id,checkpointSha256:checkpoint.sha256,inspection:{version:'world-prepare-v1',groups:[
 {asset_id:'asset',import_job:'import',status:'PREPARABLE',members:['<skin>','Rig']},
 {asset_id:'asset',import_job:'second',status:'UNSUPPORTED',reason:'<linked>',members:['SecondRig']},
 {asset_id:'prop',import_job:'third',status:'ALREADY_PREPARED',members:['Prop']}
]}};
const project={workbench:{catalogPins:[{id:'asset',title:'<Character>'}]}};
test('compatibility hint is optional, read-only and bound to the exact saved scene',()=>{
 const context={scene,checkpoint,runs:[],cap:{world_prepare:'world-prepare-v1'},blocked:false,esc,b};
 assert.match(preparationHint(context),/Check asset placement/);
 for(const patch of [{checkpoint:null},{cap:{}},{scene:{...scene,candidate:'draft'}}])assert.equal(preparationHint({...context,...patch}),'');
 assert.match(preparationHint({...context,blocked:true}),/disabled/);
 assert.equal(preparationInspection([run],scene,checkpoint),run);
 for(const patch of [{sceneId:'other'},{state:'FAILED'},{checkpointSha256:'b'.repeat(64)},{checkpointId:'other'}])assert.equal(preparationInspection([{...run,...patch}],scene,checkpoint),undefined);
 assert.match(preparationHint({...context,runs:[run]}),/Review placement check/);
 assert.equal(preparationHint({...context,runs:[{...run,inspection:{...run.inspection,groups:[run.inspection.groups[2]]}}]}),'');
});
test('review escapes labels, offers only observed supported groups and does not preselect consent',()=>{
 const view=preparationDialog({project,run,esc,b});assert.match(view.body,/&lt;Character>/);assert.match(view.body,/&lt;skin>/);assert.match(view.body,/&lt;linked>/);assert.doesNotMatch(view.body,/checked|<Character>|<skin>|<linked>/);
 assert.equal((view.body.match(/ disabled/g)||[]).length,2);assert.match(view.buttons,/disabled/);assert.match(view.body,/Save changes/);assert.match(view.body,/Undo/);assert.match(view.body,/does not mark World ready/);
 assert.deepEqual(preparationSelection(run,['0']),[{asset_id:'asset',import_job:'import'}]);
 for(const values of [[],['0','0'],['1'],['2'],['-1'],['NaN'],['3'],Array(65).fill('0')])assert.throws(()=>preparationSelection(run,values));
 const empty=preparationDialog({project,run:{inspection:{groups:[]}},esc,b});assert.match(empty.body,/will not guess/);assert.equal(empty.buttons,'');
});
