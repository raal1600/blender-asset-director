/** Inspection reuse is bound to native code, not just unchanged scene bytes. */
export const actionInspectionRefresh='Performer inspection predates this runtime. Use Inspect performers again before continuing.';
export function currentActionInspection(run,cap){
  return /^[a-f0-9]{64}$/.test(cap?.implementation)&&run?.implementation===cap.implementation&&
    run.inspection?.version==='action-layer-v1'&&Array.isArray(run.inspection.performers)&&
    (!cap.action_timeline||run.inspection.performers.every(p=>p.timeline?.version===cap.action_timeline));
}
export function actionInspectionAttempt(run,scene,checkpoint,cap){
  return /^[a-f0-9]{64}$/.test(cap?.implementation)&&run.action==='action-audit'&&run.sceneId===scene.id&&
    run.checkpointId===checkpoint?.id&&run.checkpointSha256===checkpoint?.sha256&&run.implementation===cap.implementation&&
    (run.state!=='SUCCEEDED'||currentActionInspection(run,cap));
}
