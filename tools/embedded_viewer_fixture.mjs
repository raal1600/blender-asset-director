/** Real catalog/server + generated Blender inputs. Never connect to a live studio. */
import fs from 'node:fs/promises';
import {constants} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';
import {createApp} from '../launcher/server.mjs';
import {fileHash,writeJson} from '../launcher/lib/storage.mjs';
const repository=fileURLToPath(new URL('../',import.meta.url));
const [root,generated,python,blender]=process.argv.slice(2);
if(!root||!generated||!python||!blender)throw Error('Expected new studio, generated fixture, Python and Blender paths');
const prior=JSON.parse(await fs.readFile(path.join(generated,'asset_preview_report.json'),'utf8'));
if(prior.status!=='PASS')throw Error('Native synthetic fixture has not passed');
await fs.mkdir(root);const input=path.join(root,'SyntheticInputs');await fs.mkdir(input);
for(const name of ['scene.blend','scene.glb'])await fs.copyFile(path.join(generated,'originals',name),path.join(input,name),constants.COPYFILE_EXCL);
const library=path.join(root,'Database/AssetDirector');
const app=await createApp({root,config:{library,python,blender,skill:path.join(repository,'skills/blender-asset-director')},port:0});
const evidence=path.join(root,'synthetic-intake.json');await writeJson(evidence,{title:'Synthetic animated 3D subject',kind:'model',source_url:'https://example.invalid/generated-fixture',attested:false});
const intake=await app.runtime.harness(['intake',input,'--evidence',evidence]);
let project=await app.store.create('Synthetic interactive viewer','Generated fixture only; no creative approval.');
const created=await app.workbench.create(project.id,project.revision,'Camera-free saved scene');project=await app.store.get(project.id);
const scene=project.workbench.scenes[0],checkpointId='cp_'+randomUUID(),relative='Scenes/'+checkpointId+'.blend';
await fs.copyFile(path.join(input,'scene.blend'),path.join(project.directory,relative),constants.COPYFILE_EXCL);
scene.checkpoints.push({id:checkpointId,path:relative,...await fileHash(path.join(project.directory,relative)),parent:null,stage:'world',createdAt:new Date().toISOString(),source:'synthetic-generated-native-file',audit:null});scene.candidate=checkpointId;
await app.store.save(project,project.revision);
const asset=await app.workbench.catalogDetail(project.id,intake.asset_id);
await writeJson(path.join(root,'browser-session.json'),{fixture:'synthetic-embedded-viewer',origin:app.origin,token:app.token,root,projectId:project.id,sceneId:created.sceneId,assetId:asset.id,version:asset.version,checkpointId,
  projectManifest:path.join(project.directory,'project.json'),catalog:path.join(library,'catalog.sqlite'),sourceFiles:asset.files.map(f=>({path:path.join(library,f.path),sha256:f.sha256}))});
console.log('Synthetic embedded viewer ready; session stays in its private fixture.');
