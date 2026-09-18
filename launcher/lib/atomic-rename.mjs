/** Preserve atomic replacement when Windows temporarily holds a read handle.
 * Never unlink the destination or fall back to copying over it. The caller's
 * serialized writer still owns revision checks; these retries only handle
 * short-lived sharing/permission conflicts. Persistent errors remain errors.
 */
import fs from 'node:fs/promises';
import {setTimeout as delay} from 'node:timers/promises';
const waits=Object.freeze([10,20,40,80,160,320,640,1000]);
export async function atomicRename(source,destination,{platform=process.platform,rename=fs.rename,wait=delay}={}) {
  for(let attempt=0;;attempt++) {
    try{return await rename(source,destination);}
    catch(error) {
      if(platform!=='win32'||!['EPERM','EACCES','EBUSY'].includes(error.code)||attempt>=waits.length)throw error;
      await wait(waits[attempt]);
    }
  }
}
