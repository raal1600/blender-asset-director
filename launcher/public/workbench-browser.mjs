/** Contextual, bounded library browser. Navigation is never an approval. */
export const PAGE_SIZE=24;
export function pinnedPage(project,scene,{query='',kind='',offset=0}={}) {
  const ids=new Set(scene.catalog||[]),words=query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const rows=(project.workbench.catalogPins||[]).filter(a=>ids.has(a.id)&&(!kind||a.kind===kind)&&words.every(w=>a.title.toLowerCase().includes(w)))
    .sort((a,b)=>a.title.localeCompare(b.title)||a.id.localeCompare(b.id));
  const start=rows.length?Math.min(offset,Math.floor((rows.length-1)/PAGE_SIZE)*PAGE_SIZE):0;
  return {items:rows.slice(start,start+PAGE_SIZE).map(({files,...a})=>({...a,pinnedOnly:true})),
    total:rows.length,offset:start,next_offset:start+PAGE_SIZE<rows.length?start+PAGE_SIZE:null};
}
export function ingredientStatus(scene,id) {
  const checkpoint=scene.checkpoints.find(c=>c.id===(scene.candidate||scene.current));
  return (checkpoint?.audit?.objects||[]).some(o=>o.asset_id===id)
    ?scene.candidate?'In candidate':'In checkpoint':'Selected · not imported';
}
export function ingredientsView({project,scene,inventory,esc,b}) {
  const ids=new Set(scene.catalog||[]),sources=new Set(scene.sources);
  const rows=[...(project.workbench.catalogPins||[]).filter(a=>ids.has(a.id)).map(a=>({id:a.id,name:a.title,status:ingredientStatus(scene,a.id),action:'catalog-detail'})),
    ...inventory.sources.filter(a=>sources.has(a.id)).map(a=>({id:a.id,name:a.name,status:'Package selected · not imported',action:'source-detail'}))];
  const count=ids.size+sources.size;
  return `<section class="ingredients" aria-label="Scene ingredients"><div class="ingredients-heading"><div class="grow"><h3>Ingredients <span class="count">${count}</span></h3><p>${count?'Selected for this scene. Import and review remain separate.':'Start with your library. Choose ingredients, then assemble the world in Blender.'}</p></div>${b('Browse assets','browse-assets',{},'primary')}</div>${rows.length?`<div class="ingredient-list">${rows.slice(0,4).map(a=>`<button class="ingredient" data-action="${a.action}" data-id="${esc(a.id)}"><span title="${esc(a.name)}">${esc(a.name)}</span><small>${esc(a.status)}</small></button>`).join('')}</div>${b('View all selected ('+count+')','browse-assets',{selected:'true'},'ghost small')}`:''}</section>`;
}
function itemView(a,{source,scene,locked,esc,b}) {
  const selected=source?scene.sources.includes(a.id):(scene.catalog||[]).includes(a.id);
  const name=source?a.name:a.title,motion=['animation','Animations'].includes(a.kind);
  const status=source?(selected?'Package selected · not imported':a.available?'Available package':'Unavailable'):selected?ingredientStatus(scene,a.id):'Not selected';
  const image=!motion&&(source||a.package_images?.length);
  return `<article class="browser-asset ${selected?'selected':''} ${motion?'motion':''}" data-item-id="${esc(a.id)}"><div class="browser-thumb"><div class="glyph" aria-hidden="true">${motion?'∿':'◇'}</div>${image?`<img data-${source?'source':'catalog'}-image="${esc(a.id)}" data-version="${esc(a.version)}" alt="Source image: ${esc(name)}" hidden>`:''}<small>${motion?'Motion':'No preview'}</small></div><div class="copy"><h3 title="${esc(name)}">${esc(name)}</h3><small>${esc(a.kind)}${source?'':' · '+esc(a.provider)}</small><small class="${status.startsWith('In ')?'good':''}">${esc(status)}</small><small>${source?'Source use: '+esc(a.review||'UNREVIEWED'):a.pinnedOnly?'Pinned version · inspect current evidence':a.policy?.eligible?'Native policy eligible':'Source-use evidence required'}</small></div><div class="asset-actions">${b('Inspect',source?'source-detail':'catalog-detail',{id:a.id},'small')}${b(selected?'Deselect':'Select',source?'source':'catalog-select',{id:a.id},'small',locked||!!scene.candidate||(source&&!a.available&&!selected))}</div></article>`;
}
export function browserView({ui,page,project,scene,locked,esc,b}) {
  const source=ui.tab==='sources',kinds=source?[['Meshes','Meshes'],['Characters','Characters'],['Animations','Animations']]:[['model','Models'],['pack','Packs'],['animation','Motion'],['material','Materials'],['hdri','HDRIs']];
  const count=(scene.catalog||[]).length+scene.sources.length;
  return `<header class="browser-heading"><div><div class="eyebrow">Ingredients for ${esc(scene.name)}</div><h2 id="library-title">Browse assets</h2></div>${b('Done','browser-close',{},'ghost')}</header><nav class="browser-tabs" aria-label="Library source">${b('Catalog assets','browser-tab',{tab:'catalog'},!source?'active':'').replace('<button','<button aria-pressed="'+!source+'"')}${b('Source packages','browser-tab',{tab:'sources'},source?'active':'').replace('<button','<button aria-pressed="'+source+'"')}<span class="grow"></span><small>${count} selected for this scene</small></nav><form id="browser-search" class="browser-toolbar"><label class="browser-query"><span class="sr-only">Search ${source?'source packages':'catalog assets'}</span><input id="browser-query" maxlength="2000" placeholder="Search ${source?'source packages':'catalog assets'}…" value="${esc(ui.query)}"></label><button type="submit">Search</button><label><span class="sr-only">Asset type</span><select id="browser-kind"><option value="">All types</option>${kinds.map(([v,label])=>`<option value="${v}" ${ui.kind[ui.tab]===v?'selected':''}>${label}</option>`).join('')}</select></label><label><span class="sr-only">Selection filter</span><select id="browser-scope"><option value="all">All items</option><option value="selected" ${ui.selected?'selected':''}>Selected only</option></select></label><div class="view-switch" aria-label="Result layout"><button type="button" data-action="browser-layout" data-layout="grid" aria-pressed="${ui.layout==='grid'}">Grid</button><button type="button" data-action="browser-layout" data-layout="list" aria-pressed="${ui.layout==='list'}">List</button></div></form><p class="browser-description">${source?'Original database packages · kept separate from the indexed catalog. Selection does not import or grant rights.':'Installed harness catalog · inspect exact members, rights and versions before importing.'}</p><p id="browser-notice" class="note warn" role="alert" hidden></p><div class="browser-results ${ui.layout==='list'||ui.kind[ui.tab]==='animation'||ui.kind[ui.tab]==='Animations'?'list':''}" tabindex="0" aria-label="Asset results" aria-busy="${!page}">${!page?'<p class="empty">Loading assets…</p>':page.error?`<div class="empty"><p class="warn">${esc(page.error)}</p>${b('Retry','browser-retry')}</div>`:page.items.map(a=>itemView(a,{source,scene,locked,esc,b})).join('')||'<div class="empty"><h3>No matching assets</h3><p>Try another search, type or selection filter. Sources have not been removed.</p></div>'}</div><footer class="browser-footer"><div><span role="status">${page?.error?'Library unavailable':page?`${page.total? page.offset+1:0}–${Math.min((page.offset||0)+page.items.length,page.total)} of ${page.total} ${source?'packages':'assets'}`:'Loading library'}</span><small>Source images are not generated model or motion previews.</small></div><div class="row">${source?b('Refresh library','scan',{},'ghost small',locked):''}${b('Previous','browser-page',{offset:Math.max(0,(page?.offset||0)-PAGE_SIZE)},'small',!page||!!page.error||!page.offset)}${b('Next','browser-page',{offset:page?.next_offset},'small',!page||!!page.error||page.next_offset===null)}</div></footer>`;
}
export function sourceDialog({source,scene,locked,esc,b}) {
  const selected=scene.sources.includes(source.id);
  return {body:`<p>${esc(source.kind)} · ${source.available?'Available':'Unavailable'} · Source use: ${esc(source.review||'UNREVIEWED')}</p><p>This is an original database package, not proof of catalog intake, rights or Blender import. Inspect and intake it through the existing reviewed specialist workflow.</p><p>${source.fileCount} files · ${Number(source.bytes||0).toLocaleString()} bytes</p><details><summary>Source identity and package members</summary><pre>${esc(JSON.stringify({id:source.id,version:source.version,relative:source.relative,entrypoints:source.entrypoints},null,2))}</pre></details>`,buttons:b(selected?'Deselect package':'Select package','source',{id:source.id},'primary',locked||!!scene.candidate||(!source.available&&!selected))};
}

/** Keeps tab/query/page/scroll per scene without persisting creative state. */
export function assetBrowser({dialog,context,api,esc,b,loadImages,releaseImages=()=>{},onError}) {
  const contexts=new Map();let ui,page,key,request=0;
  const currentKey=()=>context().scene?context().project.id+':'+context().scene.id:null;
  const remember=()=>{if(ui)ui.scroll[ui.tab]=dialog.querySelector('.browser-results')?.scrollTop||0;};
  function paint(focus=null) {
    if(!dialog.open)return;
    releaseImages(dialog);
    dialog.innerHTML=browserView({...context(),ui,page,esc,b});
    dialog.querySelector('.browser-results').scrollTop=ui.scroll[ui.tab]||0;
    loadImages(dialog);
    if(focus)dialog.querySelector(focus)?.focus();
  }
  async function refresh({reset=false,focus=null,capture=true}={}) {
    if(!dialog.open)return;
    if(key!==currentKey()){close();return;}
    if(!focus&&dialog.contains(document.activeElement)){
      const el=document.activeElement;
      focus=el.id?'#'+el.id:el.dataset?.action?'[data-action="'+el.dataset.action+'"]'+(el.dataset.id?'[data-id="'+el.dataset.id+'"]':''):null;
    }
    if(capture)remember();if(reset){ui.offset[ui.tab]=0;ui.scroll[ui.tab]=0;}
    const serial=++request;page=null;paint();
    try {
      const {project,scene}=context();
      const params={projectId:project.id,query:ui.query,offset:ui.offset[ui.tab],kind:ui.kind[ui.tab]};
      const result=ui.tab==='catalog'?(ui.selected?pinnedPage(project,scene,params):await api('workbench/catalog?'+new URLSearchParams(params))):
        await api('workbench/sources?'+new URLSearchParams({...params,sceneId:scene.id,selected:ui.selected}));
      if(serial!==request||!dialog.open||key!==currentKey())return;
      page=result;ui.offset[ui.tab]=result.offset;paint(focus);
    }catch(e){if(serial===request&&dialog.open){page={error:e.message};paint(focus);}}
  }
  async function open({selected}={}) {
    key=currentKey();ui=contexts.get(key);
    if(!ui){ui={tab:'catalog',query:'',kind:{catalog:'',sources:''},offset:{catalog:0,sources:0},scroll:{catalog:0,sources:0},selected:false,layout:'grid'};contexts.set(key,ui);}
    if(selected!==undefined){ui.selected=selected;ui.offset={catalog:0,sources:0};ui.scroll={catalog:0,sources:0};if(selected&&!(context().scene.catalog||[]).length)ui.tab='sources';}
    if(!dialog.open){dialog.showModal();document.body.classList.add('library-open');}
    await refresh({capture:false,focus:'#browser-query'});
  }
  function close() {remember();request++;dialog.close();}
  dialog.addEventListener('close',()=>{request++;releaseImages(dialog);dialog.innerHTML='';document.body.classList.remove('library-open');document.querySelector('[data-action="browse-assets"]')?.focus();});
  dialog.addEventListener('cancel',remember);
  dialog.addEventListener('keydown',event=>{
    if(event.key!=='Tab')return;
    const stops=[...dialog.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),[tabindex="0"]')].filter(e=>e.getClientRects().length);
    const first=stops[0],last=stops.at(-1);
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
  });
  return {open,close,refresh,get isOpen(){return dialog.open;},
    async dispatch(action,data={}) {
      if(action==='browser-close'){close();return true;}
      if(!action.startsWith('browser-'))return false;
      remember();
      // Save unsubmitted text too; switching source never loses the search.
      const query=dialog.querySelector('#browser-query')?.value??ui.query;
      if(query!==ui.query){ui.offset={catalog:0,sources:0};ui.scroll={catalog:0,sources:0};}
      ui.query=query;
      if(action==='browser-tab'){ui.tab=data.tab;await refresh({capture:false,focus:'[data-action="browser-tab"][data-tab="'+ui.tab+'"]'});}
      else if(action==='browser-layout'){ui.layout=data.layout;paint('[data-action="browser-layout"][data-layout="'+ui.layout+'"]');}
      else if(action==='browser-page'){ui.offset[ui.tab]=Number(data.offset);ui.scroll[ui.tab]=0;await refresh({capture:false,focus:'.browser-results'});}
      else if(action==='browser-search'){await refresh({reset:true,focus:'#browser-query'});}
      else if(action==='browser-kind'){ui.kind[ui.tab]=data.value;await refresh({reset:true,focus:'#browser-kind'});}
      else if(action==='browser-scope'){ui.selected=data.value==='selected';await refresh({reset:true,focus:'#browser-scope'});}
      else if(action==='browser-retry')await refresh();
      else onError('Unknown library action.');
      return true;
    }};
}
