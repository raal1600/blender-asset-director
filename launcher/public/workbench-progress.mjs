// Phases report work actually entered, never an invented percentage or ETA.
const labels=Object.freeze({
  'verify-sources':'Checking source files and rights',
  'verify-checkpoint':'Checking the saved scene',
  'prepare-job':'Preparing the bounded Blender job',
  'bind-job':'Saving the job ownership',
  'blender-worker':'Blender is loading and processing the selected asset',
  'verify-result':'Verifying the Blender output',
  'reverify-sources':'Rechecking source integrity',
  'save-checkpoint':'Saving and verifying the new checkpoint'
});
const nativeLabels=Object.freeze({evaluating_boundary_support:'Evaluating native boundary support',sampling_native_contexts:'Sampling the selected native motion',provider_start:'Starting the isolated motion provider',queued:'Waiting for local generation resources',verifying_model:'Verifying model files',model_verified:'Model files verified',loading_and_inference:'Loading the model and generating motion',running:'Generating motion in the isolated provider',validated_candidate:'Raw model output checked; retargeting remains',retargeting_generated_interval:'Retargeting generated movement',seam_processing:'Correcting the bridge boundaries',contact_processing:'Refining bridge contacts within correction limits',baking_generated_connection:'Baking the candidate motion',fresh_reopen_quality_validation:'Validating the reopened candidate and native preservation',quality_validation_complete:'Quality measurements complete; checking candidate artifacts'});
export const transitionPhase=run=>run?.state==='RUNNING'?(run.nativeProgress?.stage==='queued'?'Queued':['fresh_reopen_quality_validation','quality_validation_complete'].includes(run.nativeProgress?.stage)||['verify-result','reverify-sources','save-checkpoint'].includes(run.phase)?'Validating':'Generating'):'Queued';
export const progressLabel=run=>(run?.state==='RUNNING'&&(!run.phase||run.phase==='blender-worker')?nativeLabels[run.nativeProgress?.stage]:null)||labels[run?.phase]||({'source-prepare':'Checking source files, dependencies and the shared catalog copy','world-prepare-audit':'Checking saved asset ownership and animation; your scene is unchanged','world-prepare':'Preparing and reopening a separate placement copy; your current scene is unchanged'}[run?.action])||'Working from the frozen checkpoint';
export const progressKey=runs=>JSON.stringify((runs||[]).map(r=>[r.id,r.state,r.phase,r.nativeProgress?.stage]));
export function statusPoller(){
  let inFlight=false,last=-Infinity;
  return async(active,at,read)=>{
    if(inFlight||at-last<(active?500:2500))return;
    inFlight=true;last=at;
    try{return await read();}finally{inFlight=false;}
  };
}
