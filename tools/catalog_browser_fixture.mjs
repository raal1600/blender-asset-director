/** Synthetic HTTP/browser fixture only. Never runs Blender or claims native execution. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createApp} from '../launcher/server.mjs';
import {writeJson} from '../launcher/lib/storage.mjs';
export async function fixture(root,count=10000) {
  if(!Number.isSafeInteger(count)||count<0||count>10000)throw Error('Synthetic count must be 0..10000');
  // This runner is intentionally new-only, like the installer.
  await fs.mkdir(root);
  const assets=Array.from({length:count},(_,i)=>({id:'a_'+i.toString(16).padStart(24,'0'),version:'b'.repeat(64),title:(i%4?'Motion clip ':'Synthetic model ')+String(i).padStart(5,'0'),kind:i%4?'animation':'model',provider:'synthetic',policy:{eligible:false,reasons:['Synthetic browser fixture; not licensed-input approval']},package_images:[],models:[],files:[],metadata:{},license_id:'UNKNOWN'}));
  const runtime={health:null,harness:async args=>{
    if(args[0]==='workbench-capabilities')return {schema:1,catalog:true,task_workspace:true};
    if(args[0]==='workbench-verify')return {ok:true};
    if(args[0]!=='workbench-catalog')throw Error('Fixture refuses native operations: '+args[0]);
    const get=(key,otherwise)=>args.includes(key)?args[args.indexOf(key)+1]:otherwise;
    if(args.includes('--asset')){const a=assets.find(a=>a.id===get('--asset'));if(!a)throw Error('Unknown synthetic asset');return a;}
    const query=get('--query','').toLowerCase(),kind=get('--kind',null),offset=Number(get('--offset',0));
    const matched=assets.filter(a=>(!kind||a.kind===kind)&&a.title.toLowerCase().includes(query));
    return {schema:1,items:matched.slice(offset,offset+24),offset,total:matched.length,next_offset:offset+24<matched.length?offset+24:null};
  }};
  const app=await createApp({root,config:{},runtime,port:0});
  const project=await app.store.create('Synthetic large library','Disposable UI regression only; no Blender or human approval.');
  const created=await app.workbench.create(project.id,project.revision,'Library browser test');
  const sources=Array.from({length:count},(_,i)=>({id:'src_00000000-0000-4000-8000-'+String(i).padStart(12,'0'),name:'Source package '+String(i).padStart(5,'0'),kind:i%3===0?'Animations':i%3===1?'Characters':'Meshes',available:i!==3,review:'UNREVIEWED',version:'a'.repeat(64),fileCount:100,bytes:50000,relative:'Synthetic/'+i,entrypoints:['Synthetic/'+i+'/model.obj']}));
  await writeJson(path.join(root,'Database/Registry/sources.json'),{schema:1,sources});
  app.workbench.sourcePreview=async()=>null;app.workbench.catalogImage=async()=>null;
  const session={fixture:'synthetic-catalog-browser',origin:app.origin,token:app.token,root,projectId:project.id,sceneId:created.sceneId};
  await writeJson(path.join(root,'browser-session.json'),session);
  return app;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
  const app=await fixture(path.resolve(process.argv[2]),Number(process.argv[3]||10000));
  console.log('Synthetic library browser listening at '+app.origin+'; private session saved inside fixture root.');
}
