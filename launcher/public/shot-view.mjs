/** Read-only Blender camera samples. Orbit never writes or substitutes a shot. */
export function shotFrame(view,seconds){
 return Math.max(view.shot.start,Math.min(view.shot.end,view.shot.start+Math.floor(seconds*view.fps+1e-6)));
}
export function shotViewport(width,height,aspect){
 const w=Math.min(width,height*aspect),h=w/aspect;return {x:(width-w)/2,y:(height-h)/2,width:w,height:h};
}
export function sampledCamera(THREE,view){
 const camera=new THREE.Camera();camera.matrixAutoUpdate=false;
 const conversion=new THREE.Matrix4().makeRotationX(-Math.PI/2);
 return {camera,frame(frame){
   const sample=view.samples[frame-view.shot.start];if(!sample||sample.frame!==frame)throw Error('Missing observed camera frame.');
   camera.isPerspectiveCamera=sample.projection==='PERSP';camera.isOrthographicCamera=sample.projection==='ORTHO';
   camera.matrix.copy(conversion).multiply(new THREE.Matrix4().set(...sample.matrix_world));
   camera.projectionMatrix.set(...sample.projection_matrix);camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
   camera.updateMatrixWorld(true);return camera;
 }};
}
