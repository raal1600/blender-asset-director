/** Session-local, bounded thumbnail loading. Never caches approvals or scene evidence. */
export function imageLoader({fetchImage,limit=4,maxEntries=96,maxBytes=32*1024*1024}) {
  const cache=new Map(),pending=new Map(),queue=[];
  let active=0,bytes=0,generation=0;
  function pump() {
    while(active<limit&&queue.length) {
      const task=queue.shift();
      if(task.generation!==generation||!task.wanted.some(fn=>fn())){if(pending.get(task.key)===task)pending.delete(task.key);task.resolve(null);continue;}
      active++;
      Promise.resolve().then(()=>fetchImage(task.url)).then(blob=>{
        if(task.generation===generation&&(!blob||blob.size<=maxBytes)) {
          cache.set(task.key,blob);bytes+=blob?.size||0;
          while(cache.size>maxEntries||bytes>maxBytes){const key=cache.keys().next().value;bytes-=cache.get(key)?.size||0;cache.delete(key);}
        }
        task.resolve(blob);
      },task.reject).finally(()=>{active--;if(pending.get(task.key)===task)pending.delete(task.key);pump();});
    }
  }
  return {
    load(key,url,wanted=()=>true) {
      if(cache.has(key)){const blob=cache.get(key);cache.delete(key);cache.set(key,blob);return Promise.resolve(blob);}
      if(pending.has(key)){const task=pending.get(key);task.wanted.push(wanted);return task.promise;}
      let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});
      const task={key,url,wanted:[wanted],resolve,reject,promise,generation};pending.set(key,task);queue.push(task);pump();return promise;
    },
    clear(){generation++;cache.clear();bytes=0;pending.clear();pump();}
  };
}
