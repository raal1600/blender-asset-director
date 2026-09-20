/** File envelopes are hints only. Blender, not this header check, validates scene data. */
import fs from 'node:fs/promises';
import {assert} from './storage.mjs';

export function blendEnvelope(header) {
  if(header.length >= 12 && header.subarray(0,7).toString('ascii') === 'BLENDER') return 'blend';
  if(header.length >= 4 && header.subarray(0,4).equals(Buffer.from([0x28,0xb5,0x2f,0xfd]))) return 'zstd';
  if(header.length >= 3 && header[0] === 0x1f && header[1] === 0x8b && header[2] === 8) return 'gzip';
  return null;
}

export async function assertBlendEnvelope(filename) {
  const handle=await fs.open(filename);
  try {
    const header=Buffer.alloc(17);
    const {bytesRead}=await handle.read(header,0,header.length,0);
    const envelope=blendEnvelope(header.subarray(0,bytesRead));
    assert(envelope,'This file has no recognized Blender or compressed Blender header. Select a saved .blend file.');
    return envelope;
  } finally {await handle.close();}
}
