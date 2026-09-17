import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {Store} from '../lib/projects.mjs';
import {Runtime} from '../lib/runtime.mjs';
import {buildSessionContext} from '../lib/onboarding.mjs';
async function fixture(t){const root=await fs.mkdtemp(path.join(os.tmpdir(),'ad-wizard-test-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));for(const kind of ['Animations','Characters','Meshes'])await fs.mkdir(path.join(root,'Database',kind),{recursive:true});const store=new Store(root);await store.init();const runtime=new Runtime(store,{skill:'installed-skill'});return {root,store,runtime};}
test('wizard choices persist independently and legacy projects remain readable',async t=>{
 const {store}=await fixture(t);let a=await store.create('Project A'),b=await store.create('Project B');
 a=await store.update(a.id,{revision:a.revision,brief:'A character dance',capabilityMode:'selected',capabilities:['character-motion','camera'],onboarding:{step:4,libraryReviewed:false}});
 assert.deepEqual((await store.get(a.id)).capabilities,['character-motion','camera']);assert.equal((await store.get(a.id)).onboarding.step,4);assert.deepEqual((await store.get(b.id)).capabilities,[]);
 await assert.rejects(store.update(a.id,{revision:a.revision,capabilities:['unsupported']}),/Invalid harness/);
 await assert.rejects(store.update(a.id,{revision:a.revision,capabilities:[]}),/at least one/);
 await assert.rejects(store.update(a.id,{revision:a.revision,onboarding:{step:7,libraryReviewed:true}}),/wizard/);
 const legacy=JSON.parse(await fs.readFile(path.join(b.directory,'project.json'),'utf8'));delete legacy.capabilities;delete legacy.capabilityMode;delete legacy.onboarding;await fs.writeFile(path.join(b.directory,'project.json'),JSON.stringify(legacy));assert.equal((await store.get(b.id)).id,b.id);
});
test('Codex snapshots the reviewed brief, scope and pinned sources; stale or changed inputs block launch',async t=>{
 const {root,store,runtime}=await fixture(t);let p=await store.create('Prompt project');let launched=0;
 runtime.startBlender=async()=>({started:true,connected:true,message:'Fixture connected.'});runtime.launchTerminal=async()=>{launched++;return {processId:42};};
 await assert.rejects(runtime.openCodex(p.id,p.revision),/Describe/);
 const source=path.join(root,'Database/Characters/hero.glb');await fs.writeFile(source,'synthetic');const registry=await store.scan();p=await store.attach(p.id,registry.sources[0].id,p.revision);
 p=await store.update(p.id,{revision:p.revision,brief:'Dance in a moonlit courtyard',capabilityMode:'selected',capabilities:['character-motion','lighting'],onboarding:{step:5,libraryReviewed:true}});
 const preview=await buildSessionContext(store,runtime.config,p.id);assert.match(preview.prompt,/Dance in a moonlit courtyard/);assert.match(preview.prompt,/character-motion/);assert.ok(preview.prompt.includes(registry.sources[0].version));assert.ok(preview.prompt.includes('Characters/hero.glb'));
 await assert.rejects(runtime.openCodex(p.id,p.revision-1),/changed/);assert.equal(launched,0);
 const result=await runtime.openCodex(p.id,p.revision);assert.equal(launched,1);assert.equal(await fs.readFile(path.join(p.directory,'Docs/Codex',result.sessionId+'.md'),'utf8'),preview.prompt);
 await fs.writeFile(source,'changed');await assert.rejects(runtime.openCodex(p.id,p.revision),/sources changed/);assert.equal(launched,1);
});
test('scene review launches the exact project file without querying or replacing a live scene',async t=>{
 const {store,runtime}=await fixture(t);let p=await store.create('Review project');const filename=path.join(p.directory,'Scenes/working.blend');await fs.writeFile(filename,'untouched scene');p=await store.update(p.id,{revision:p.revision,scene:'Scenes/working.blend'});
 runtime.blender=async()=>{throw Error('Review must not depend on live scene');};runtime.showBlender=async()=>({visible:true,focused:true});let actual;
 runtime.launchReview=async(project,file)=>{actual={id:project.id,file};return 99;};const result=await runtime.startBlender(p.id,true);
 assert.equal(result.scene,'Scenes/working.blend');assert.deepEqual(actual,{id:p.id,file:filename});assert.equal(await fs.readFile(filename,'utf8'),'untouched scene');await fs.unlink(filename);await assert.rejects(runtime.startBlender(p.id,true));
});


test('Windows session helper forwards the exact project directory and saved prompt path', {skip:process.platform!=='win32'}, async t=>{
 const {root,store}=await fixture(t);const p=await store.create('Unicode project');const sessionId='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
 const tools=path.join(root,'SystemRuntime/Launcher/tools');await fs.mkdir(tools,{recursive:true});
 await fs.copyFile(new URL('../tools/project-session.ps1',import.meta.url),path.join(tools,'project-session.ps1'));
 const fake=path.join(root,'unused-codex.exe');await fs.writeFile(path.join(tools,'codex-session.mjs'),"import fs from 'node:fs';fs.writeFileSync('invocation.json',JSON.stringify({arguments:process.argv.slice(2),directory:process.cwd()}));");
 await fs.mkdir(path.join(root,'SystemRuntime/UserData/Launcher'),{recursive:true});await fs.writeFile(path.join(root,'SystemRuntime/UserData/Launcher/config.json'),JSON.stringify({codex:fake,skill:'test-skill'}));
 await fs.mkdir(path.join(p.directory,'Docs/Codex'));await fs.writeFile(path.join(p.directory,'Docs/Codex',sessionId+'.json'),JSON.stringify({projectId:p.id,directory:p.directory}));
 const {promisify}=await import('node:util');const {execFile}=await import('node:child_process');
 await promisify(execFile)('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(tools,'project-session.ps1'),'-ProjectId',p.id,'-SessionId',sessionId],{windowsHide:true});
 const actual=JSON.parse((await fs.readFile(path.join(p.directory,'invocation.json'),'utf8')).replace(/^\uFEFF/,''));assert.equal(actual.directory,p.directory);assert.deepEqual(actual.arguments,[p.id,sessionId]);
});


test('wizard navigation does not invalidate the reviewed production context',async t=>{
 const {store}=await fixture(t);let p=await store.create('Navigation project','A still');p=await store.update(p.id,{revision:p.revision,onboarding:{step:5,libraryReviewed:true}});const revision=p.revision;
 p=await store.update(p.id,{revision,onboarding:{step:6,libraryReviewed:true}});assert.equal(p.revision,revision);assert.equal(p.onboarding.step,6);
 p=await store.update(p.id,{revision,brief:'An animation'});assert.equal(p.revision,revision+1);await assert.rejects(store.update(p.id,{revision,brief:'Stale edit'}),/another window/);
});

test('Codex launch attempts Blender setup before terminal and reports a setup failure honestly',async t=>{
 const {store,runtime}=await fixture(t);let p=await store.create('Startup project','Inspect my linked character');p=await store.update(p.id,{revision:p.revision,onboarding:{step:5,libraryReviewed:true}});const calls=[];
 runtime.startBlender=async(id,openScene)=>{calls.push(['blender',id,openScene]);throw Error('Fixture server unavailable');};runtime.launchTerminal=async()=>{calls.push(['terminal']);return {processId:42};};
 const result=await runtime.openCodex(p.id,p.revision);assert.deepEqual(calls,[['blender',p.id,false],['terminal']]);assert.equal(result.blenderSetup.connected,false);assert.match(result.message,/Fixture server unavailable/);
});


test('locked project returns a useful error and rolls back Trash so retry succeeds',async t=>{
 const {store}=await fixture(t);const p=await store.create('Locked project');const rename=fs.rename;
 fs.rename=async(from,to)=>{if(from===p.directory){const error=new Error('fixture lock');error.code='EBUSY';throw error;}return rename(from,to);};
 try {await assert.rejects(store.trash(p.id,p.revision),e=>e.status===409&&e.message.includes('Codex terminal window'));} finally {fs.rename=rename;}
 assert.equal((await store.get(p.id)).id,p.id);assert.equal((await store.trashList()).projects.length,0);assert.equal((await store.trashList()).errors.length,0);
 await store.trash(p.id,p.revision);assert.equal((await store.trashList()).projects[0].id,p.id);
});


test('live scene inspection uses only the read-only addon query and marks ownership unverified',async t=>{
 const {store,runtime}=await fixture(t);const p=await store.create('Inspect project');const net=await import('node:net');let query;
 const server=net.createServer(socket=>{socket.once('data',data=>{query=JSON.parse(data.toString());socket.end(JSON.stringify({status:'success',result:{name:'Existing scene',object_count:3}}));});});await new Promise(r=>server.listen(0,'127.0.0.1',r));t.after(()=>new Promise(r=>server.close(r)));runtime.config.mcpPort=server.address().port;
 const result=await runtime.liveScene(p.id);assert.deepEqual(query,{type:'get_scene_info',params:{}});assert.equal(result.scene.object_count,3);assert.match(result.ownership,/Not established/);assert.match(result.review,/not a visual review/);
 const context=await buildSessionContext(store,{skill:'test-skill'},p.id);assert.ok(context.prompt.includes('scene-info '+p.id));assert.match(context.prompt,/No selected .blend is normal/);assert.match(context.prompt,/exact question/);
});
