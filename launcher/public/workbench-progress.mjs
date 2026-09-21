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
export const progressLabel=run=>labels[run?.phase]||(run?.action==='source-prepare'?'Checking source files, dependencies and the shared catalog copy':'Working from the frozen checkpoint');
export const progressKey=runs=>JSON.stringify((runs||[]).map(r=>[r.id,r.state,r.phase]));
export function statusPoller(){
  let inFlight=false,last=-Infinity;
  return async(active,at,read)=>{
    if(inFlight||at-last<(active?500:2500))return;
    inFlight=true;last=at;
    try{return await read();}finally{inFlight=false;}
  };
}
