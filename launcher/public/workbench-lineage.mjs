/** Pure lineage rules shared by the local server and browser. No inferred approval. */
export const shotFor = (scene, id=scene.selectedShot) => (scene.shots||[]).find(s=>s.id===id)||null;
export function renderIsCurrent(scene, render) {
  if(!render || render.checkpointId!==scene.current)return false;
  if(!render.shotId)return true; // Historical explicit-camera renders retain their original contract.
  const shot=shotFor(scene,render.shotId);
  return !!shot&&shot.revision===render.shotRevision&&shot.camera===render.options?.camera&&
    shot.start===render.options?.start&&shot.end===render.options?.end;
}
export function previewIsCurrent(scene, checkpointId=scene.current) {
  const preview=scene.preview,shot=['world','action'].includes(scene.stage)?null:shotFor(scene);
  if(!preview||preview.checkpointId!==checkpointId)return false;
  return shot?preview.shotId===shot.id&&preview.shotRevision===shot.revision&&preview.camera===shot.camera:!preview.shotId;
}
export function cutIsCurrent(workbench,cut) {
  if(!cut||JSON.stringify(cut.refs)!==JSON.stringify(workbench.film.clips))return false;
  return cut.refs.every(ref=>{
    const scene=workbench.scenes.find(s=>s.id===ref.sceneId);
    const render=scene?.renders.find(r=>r.id===ref.renderId);
    return !!render&&render.approved===true&&renderIsCurrent(scene,render);
  });
}
