/** Viewer navigation only: selecting a clip never authors motion or starts a job. */
const validFrame=value=>Number.isInteger(value)&&value>=-100000&&value<=100000;
export function actionSelectionFrame(draft){
 const clip=draft?.timeline?draft.selectedClip:null;
 if(!clip||!validFrame(clip.start))return null;
 if(draft.selectedPart==='transition'){
  const duration=clip.transition?.frames;
  if(!Number.isInteger(duration)||duration<2||duration>120||!validFrame(clip.start-duration))return null;
  // Seek the visible amber block, not the preceding take's fractional end.
  return clip.start-duration;
 }
 return clip.start;
}

/** Heading/distance changes are edits, not a new navigation target. */
export function actionSelectionStamp(draft){
 const frame=actionSelectionFrame(draft);
 return frame===null?null:JSON.stringify([draft.selected,draft.selectedClip.id,draft.selectedPart,frame]);
}

export function actionSelectionSeeking(current){
 let intent=0;
 return {
  cancel(){intent++;},
  async seek(viewer,context,frame,applied){
   const mine=++intent;
   if(!viewer||!context||!validFrame(frame))return false;
   try{
    const record=await viewer.ready,now=current();
    if(!record||mine!==intent||now.viewer!==viewer||now.context!==context)return false;
    // seekFrame pauses playback and clamps to this immutable saved preview.
    // A not-yet-saved appended clip can lie beyond its available frame range.
    viewer.seekFrame(frame);viewer.updateActionPath?.();applied?.();return true;
   }catch{return false;} // Failed/disposed previews already show their own error.
  }
 };
}
