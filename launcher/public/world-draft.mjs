/** Local, unsaved instance transforms. No storage, network, approval or Blender calls. */
// Read-only inspection is safe. New mutations/navigation resolve the draft first.
const safeActions=new Set(['save-world','world-undo','refresh','close','dismiss','history','world-details','world-ingredients','browse-assets','catalog-detail','source-detail','viewer-open','catalog-preview-detail','source-preview-detail','library-scene','asset-preview-open','inspect-candidate','settings','diagnostics','verify-sources','recover','focus-task','browser-search','browser-kind','browser-scope','browser-activity','browser-subcategory','browser-view','browser-page','browser-close']);
// Retry only archives a stopped failure; resolve only releases its receipt.
// Neither executes work nor changes the scene, so keep the failed-save draft.
safeActions.add('retry');safeActions.add('resolve');
safeActions.add('preview-storage');safeActions.add('preview-storage-apply');
export const worldActionNeedsSave=action=>!safeActions.has(action);
export function instanceObjects(associations,index){
 const objects=[...associations].filter(([object,ref])=>object.isObject3D&&ref?.nodes===index).map(([object])=>object);
 if(objects.length!==1)throw Error('The saved instance geometry cannot be selected unambiguously. Inspect it in Blender.');return objects;
}
export const sameMatrix=(a,b)=>a.length===b.length&&a.every((v,i)=>Math.abs(v-b[i])<=1e-7*Math.max(1,Math.abs(b[i])));
export function placementMatrix(value){
  if(!Array.isArray(value)||value.length!==16||!value.every(v=>typeof v==='number'&&Number.isFinite(v)))throw Error('Placement needs a finite 4x4 matrix.');
  if([0,0,0,1].some((v,i)=>Math.abs(value[12+i]-v)>1e-7)||[3,7,11].some(i=>Math.abs(value[i])>1e6))throw Error('Placement is outside the supported world range.');
  const columns=[0,1,2].map(c=>[0,1,2].map(r=>value[r*4+c]));
  const lengths=columns.map(c=>Math.hypot(...c)),scale=lengths.reduce((a,b)=>a+b)/3;
  if(lengths.some(s=>s<1e-4||s>1e4)||Math.max(...lengths)-Math.min(...lengths)>scale*1e-5)throw Error('Use positive uniform scale for whole assets.');
  if([[0,1],[0,2],[1,2]].some(([i,j])=>Math.abs(columns[i].reduce((s,v,k)=>s+v*columns[j][k],0))>scale**2*1e-5))throw Error('Sheared placement needs detailed Blender editing.');
  const [a,b,c]=columns,det=a[0]*(b[1]*c[2]-b[2]*c[1])-b[0]*(a[1]*c[2]-a[2]*c[1])+c[0]*(a[1]*b[2]-a[2]*b[1]);
  if(det<=0)throw Error('Mirrored placement needs detailed Blender editing.');return value;
}

export function worldDraft({checkpointId,sha256,instances},changed=()=>{}){
  if(!/^cp_[0-9a-f-]{36}$/.test(checkpointId)||!/^[0-9a-f]{64}$/.test(sha256)||!Array.isArray(instances))throw Error('Invalid saved World context.');
  const base=new Map();
  for(const item of instances){if(!/^instance_[0-9a-f-]{36}$/.test(item.instance)||base.has(item.instance))throw Error('Ambiguous placement identity.');base.set(item.instance,placementMatrix(item.matrix).slice());}
  let current=new Map([...base].map(([id,m])=>[id,m.slice()])),transaction=null;
  const history=[],copy=()=>new Map([...current].map(([id,m])=>[id,m.slice()]));
  const transforms=()=>[...current].filter(([id,m])=>!sameMatrix(m,base.get(id))).map(([instance,matrix])=>({instance,expected_matrix:base.get(instance).slice(),matrix:matrix.slice()}));
  const state=()=>({dirty:transforms().length>0,count:transforms().length,canUndo:history.length>0,editing:!!transaction});
  const emit=()=>changed(state());
  const api={state,get:id=>current.get(id)?.slice(),ids:()=>[...base.keys()],
    begin(){if(transaction)throw Error('Finish the current placement gesture.');transaction=copy();},
    preview(batch){
      if(!transaction)throw Error('Begin a placement gesture first.');
      if(!Array.isArray(batch)||!batch.length||batch.length>64||new Set(batch.map(x=>x.instance)).size!==batch.length)throw Error('Select one to 64 whole assets.');
      const next=copy();
      for(const item of batch){if(!base.has(item.instance))throw Error('Unknown asset instance.');next.set(item.instance,placementMatrix(item.matrix).slice());}
      if([...next].filter(([id,m])=>!sameMatrix(m,base.get(id))).length>64)throw Error('Save this batch before arranging more than 64 assets.');
      current=next;emit();
    },
    commit(){if(!transaction)return;const prior=transaction;transaction=null;if([...prior].some(([id,m])=>!sameMatrix(m,current.get(id)))){history.push(prior);if(history.length>100)history.shift();}emit();},
    cancel(){if(transaction){current=transaction;transaction=null;emit();}},
    apply(batch){api.begin();try{api.preview(batch);api.commit();}catch(error){api.cancel();throw error;}},
    undo(){if(transaction)api.cancel();if(history.length){current=history.pop();emit();}},
    discard(){transaction=null;history.length=0;current=new Map([...base].map(([id,m])=>[id,m.slice()]));emit();},
    request(requestId){if(transaction)throw Error('Finish the placement gesture before saving.');if(!state().dirty)throw Error('No placement changes to save.');return {version:'world-transform-v1',requestId,checkpointId,sha256,transforms:transforms()};}
  };
  return api;
}
