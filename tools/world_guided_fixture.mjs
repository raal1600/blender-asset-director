/** Disposable real-harness World fixture. Never opens an existing studio. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {constants} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {createApp} from '../launcher/server.mjs';
import {fileHash,writeJson} from '../launcher/lib/storage.mjs';
const repository=fileURLToPath(new URL('../',import.meta.url));
const [root,generated,python,blender]=process.argv.slice(2);
if(!root||!generated||!python||!blender)throw Error('Expected NEW fixture directory, generated synthetic input, Python and Blender');
const prior=JSON.parse(await fs.readFile(path.join(generated,'asset_preview_report.json'),'utf8'));
if(prior.status!=='PASS')throw Error('Synthetic native source fixture must pass first');
await fs.mkdir(root);
const input=path.join(root,'SyntheticInputs');await fs.mkdir(input);
await fs.copyFile(path.join(generated,'originals/scene.glb'),path.join(input,'scene.glb'),constants.COPYFILE_EXCL);
const library=path.join(root,'Database/AssetDirector');
const app=await createApp({root,config:{library,python,blender,skill:path.join(repository,'skills/blender-asset-director')},port:0});
const evidence=path.join(root,'synthetic-intake.json');
await writeJson(evidence,{title:'Synthetic animated prop',kind:'model',source_url:'https://example.invalid/generated-ci-fixture',license_id:'CC0-1.0',license_url:'https://example.invalid/synthetic-license',author:'Synthetic fixture generator',price:0,attested:true});
const asset=await app.runtime.harness(['intake',input,'--evidence',evidence,'--preserve-existing']);
// A distinct generated asset, positioned beside the first by its own source data.
// The application does not invent placement or merge selected preview models.
const secondInput=path.join(root,'SecondSyntheticInputs');await fs.mkdir(secondInput);
const positions=Buffer.alloc(36);[-.5,0,0,.5,0,0,0,1,0].forEach((v,i)=>positions.writeFloatLE(v,i*4));
const gltf={asset:{version:'2.0',generator:'Synthetic guided World test'},scene:0,scenes:[{nodes:[0]}],
  nodes:[{name:'SecondSyntheticTriangle',mesh:0,translation:[3,0,0]}],
  meshes:[{primitives:[{attributes:{POSITION:0},material:0}]}],
  materials:[{doubleSided:true,pbrMetallicRoughness:{baseColorFactor:[.2,.8,.3,1],metallicFactor:0,roughnessFactor:1}}],
  buffers:[{byteLength:36,uri:'second.bin'}],
  bufferViews:[{buffer:0,byteOffset:0,byteLength:36,target:34962}],
  accessors:[{bufferView:0,componentType:5126,count:3,type:'VEC3',min:[-.5,0,0],max:[.5,1,0]}]};
const secondFile=path.join(secondInput,'second.gltf');await writeJson(secondFile,gltf);
const secondBinary=path.join(secondInput,'second.bin');await fs.writeFile(secondBinary,positions,{flag:'wx'});
const secondEvidence=path.join(root,'second-synthetic-intake.json');
await writeJson(secondEvidence,{title:'Second synthetic prop',kind:'model',source_url:'https://example.invalid/generated-second-fixture',license_id:'CC0-1.0',license_url:'https://example.invalid/synthetic-license',author:'Synthetic fixture generator',price:0,attested:true});
const secondAsset=await app.runtime.harness(['intake',secondInput,'--evidence',secondEvidence,'--preserve-existing']);
if(secondAsset.asset_id===asset.asset_id)throw Error('Distinct synthetic asset identity required');
let project=await app.store.create('Guided World · synthetic test','Disposable generated inputs. Scripted test decisions are not human creative approval.');
const created=await app.workbench.create(project.id,project.revision,'Build a world');project=await app.store.get(project.id);
await writeJson(path.join(root,'browser-session.json'),{fixture:'synthetic-guided-world',origin:app.origin,token:app.token,pid:process.pid,root,projectId:project.id,sceneId:created.sceneId,assetId:asset.asset_id,secondAssetId:secondAsset.asset_id,secondInput:secondFile,secondOriginal:await fileHash(secondFile),secondBinary,secondBinaryOriginal:await fileHash(secondBinary),projectManifest:path.join(project.directory,'project.json'),catalog:path.join(library,'catalog.sqlite'),input:path.join(input,'scene.glb'),original:await fileHash(path.join(input,'scene.glb'))});
console.log('Disposable guided World server ready. Authentication stays in the private fixture.');
