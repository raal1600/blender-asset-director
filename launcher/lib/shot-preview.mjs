/** Server-owned selected shot, and validation of native evaluated projections. */
import {isDeepStrictEqual} from 'node:util';
import {assert} from './storage.mjs';
import {assertObservedShot} from './workbench-shots.mjs';
export const shotProfiles=['shot-framing-v1','look-inspection-v1'];
export function selectedShotPreview(scene,checkpoint){
 if(!['shots','light','render'].includes(scene.stage)||!scene.selectedShot)return null;
 const shot=scene.shots.find(s=>s.id===scene.selectedShot);assert(shot,'Selected shot is missing.',409);
 assertObservedShot(scene,checkpoint,shot);
 const {id,revision,name,camera,start,end}=shot;return {version:'shot-view-v1',id,revision,name,camera,start,end};
}
export function validateShotCamera(view,expected,playback){
 assert(view?.version==='shot-camera-samples-v1'&&isDeepStrictEqual(view.shot,expected)&&
   view.sampling==='INTEGER_FRAMES'&&view.lighting==='INSPECTION_APPROXIMATION'&&
   view.depth_of_field==='NOT_SIMULATED'&&view.human_acceptance==='NOT_EVALUATED'&&
   Number.isFinite(view.aspect)&&view.aspect>0&&Number.isFinite(view.fps)&&view.fps===playback?.fps,
   'Saved-shot camera evidence differs from this request.',409);
 assert(expected.start>=playback.start&&expected.end<=playback.end&&Array.isArray(view.samples)&&
   view.samples.length===expected.end-expected.start+1&&view.samples.length<=360,'Shot samples differ from the saved range.',409);
 for(const [i,row] of view.samples.entries())assert(row.frame===expected.start+i&&['PERSP','ORTHO'].includes(row.projection)&&
   ['matrix_world','projection_matrix'].every(key=>Array.isArray(row[key])&&row[key].length===16&&row[key].every(Number.isFinite)),
   'Invalid sampled Blender camera projection.',409);
}
