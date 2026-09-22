/** Explicit user add intents, serialized in this window; never creative approvals. */
export function worldAddQueue({context,run,changed=()=>{},failed=()=>{},limit=12}) {
  const items=[];let active=null;
  const state=()=>({active,waiting:items.map(x=>({...x})),count:items.length+(active?1:0)});
  const same=(a,b)=>a.projectId===b.projectId&&a.sceneId===b.sceneId;
  async function pump(){
    if(active||!items.length)return;
    active=items.shift();changed(state());
    try {
      const check=()=>{if(!same(context(),active))throw Error('Scene changed. Remaining additions were cancelled; completed drafts are preserved.');};
      check();if(await run(active,check)==='cancelled')items.length=0;check();
    }catch(error){items.length=0;failed(error);}
    finally{active=null;changed(state());void pump();}
  }
  return {state,add(intent){
    if(state().count>=limit)throw Error('Finish the current additions before queuing more.');
    const item={...structuredClone(intent),...context()};
    if([active,...items].some(x=>x&&same(x,item)&&x.kind===item.kind&&x.id===item.id&&x.file===item.file))return false;
    items.push(item);changed(state());void pump();return true;
  },cancelWaiting(){items.length=0;changed(state());}};
}

/** Only observed single-collection files can proceed without a collection decision. */
export async function addCatalogFlow(intent,{read,asset,command,wait,permission,collections,check}) {
  check();let state=await read();check();
  const current=await asset(intent.id);check();
  if(current.version!==intent.version||!current.models.includes(intent.file))throw Error('Asset changed. Reopen it before adding.');
  if(!current.policy?.eligible)throw Error('Source policy blocks this asset. Review its rights first.');
  if(!state.scene.catalog?.includes(intent.id)){
    await command('catalog-select',{assetId:intent.id,selected:true});state=await read();check();
  }
  if(!state.sourceUse?.ready){if(!await permission(state))return 'cancelled';state=await read();check();if(!state.sourceUse?.ready)throw Error('Source-use confirmation is still required.');}
  let selection;
  if(intent.file.toLowerCase().endsWith('.blend')){
    let observed=state.scene.assetContents?.[intent.id];
    if(observed?.version!==intent.version||observed?.file!==intent.file){
      check();const started=await command('catalog-job',{request:{assetId:intent.id,version:intent.version,file:intent.file,operation:'asset-contents'}});
      await wait(started.run.id);state=await read();check();observed=state.scene.assetContents?.[intent.id];
    }
    if(observed?.version!==intent.version||observed?.file!==intent.file||!observed.collections?.length)throw Error('No verified appendable collection was found in this file.');
    selection=intent.selection?.length?intent.selection:observed.collections.length===1?[observed.collections[0]]:await collections(observed.collections);
    check();if(!selection)return 'cancelled';
    if(!selection.length||!selection.every(n=>observed.collections.includes(n)))throw Error('Choose the observed collections to add.');
  }
  check();const started=await command('catalog-job',{request:{assetId:intent.id,version:intent.version,file:intent.file,operation:'import',confirmed:true,...(selection?{selection}:{})}});
  await wait(started.run.id);check();return 'added';
}
