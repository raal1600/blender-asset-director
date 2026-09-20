/** Local, additive diagnostics. Never an approval, progress percentage or ETA. */
export function operationTiming(record,clock=()=>performance.now()) {
  record.timings=[];
  return async(name,operation)=>{
    record.phase=name;
    const start=clock();let outcome='SUCCEEDED';
    try{return await operation();}
    catch(error){outcome='FAILED';throw error;}
    finally{record.timings.push({phase:name,milliseconds:Math.max(0,Math.round(clock()-start)),outcome});}
  };
}
