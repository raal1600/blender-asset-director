/** Package-local glTF -> embedded GLB. No network requests, decoders or Blender writes. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {assert,safe,fileHash} from './storage.mjs';

export const MAX_VIEWER_BYTES=128*1024*1024;
const JSON_CHUNK=0x4e4f534a,BIN_CHUNK=0x004e4942;
const limited=(value,max,label)=>assert(Number.isSafeInteger(value)&&value>=0&&value<=max,`${label} exceeds the interactive preview limit; inspect in Blender instead.`);
function imagePixels(bytes,type) {
  let width=0,height=0;
  if(type==='image/png') {
    assert(bytes.length>=24&&bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))&&bytes.toString('ascii',12,16)==='IHDR','Invalid PNG texture.');
    width=bytes.readUInt32BE(16);height=bytes.readUInt32BE(20);
  } else {
    assert(bytes.length>=4&&bytes[0]===255&&bytes[1]===216,'Invalid JPEG texture.');
    for(let at=2;at+4<=bytes.length;) {
      assert(bytes[at]===255,'Invalid JPEG marker.');const marker=bytes[at+1];if(marker===255){at++;continue;}
      if(marker===217||marker===218)break;const size=bytes.readUInt16BE(at+2);assert(size>=2&&at+2+size<=bytes.length,'Invalid JPEG segment.');
      if([192,193,194].includes(marker)){assert(size>=8,'Invalid JPEG dimensions.');height=bytes.readUInt16BE(at+5);width=bytes.readUInt16BE(at+7);break;}at+=size+2;
    }
  }
  assert(width>0&&height>0,'Unknown texture dimensions.');limited(width,8192,'Texture width');limited(height,8192,'Texture height');return width*height;
}
export function unpackGLB(bytes) {
  assert(bytes.length>=20&&bytes.readUInt32LE(0)===0x46546c67&&bytes.readUInt32LE(4)===2&&bytes.readUInt32LE(8)===bytes.length,'Invalid GLB envelope.');
  limited(bytes.length,MAX_VIEWER_BYTES,'Model');let document=null,binary=Buffer.alloc(0);
  for(let at=12;at<bytes.length;) {
    assert(at+8<=bytes.length,'Truncated GLB chunk.');const length=bytes.readUInt32LE(at),type=bytes.readUInt32LE(at+4);at+=8;
    assert(length%4===0&&at+length<=bytes.length,'Invalid GLB chunk length.');
    if(type===JSON_CHUNK){assert(document===null&&at===20&&length<=8*1024*1024,'Invalid GLB JSON.');document=JSON.parse(bytes.subarray(at,at+length).toString('utf8'));}
    else {assert(type===BIN_CHUNK&&document&&!binary.length,'Unsupported GLB chunk.');binary=bytes.subarray(at,at+length);}
    at+=length;
  }
  assert(document?.asset?.version==='2.0','Only glTF 2.0 is supported.');return {document,binary};
}
export function validateGLB(bytes) {
  const {document:d,binary}=unpackGLB(bytes);
  limited(d.nodes?.length||0,10000,'Object count');limited(d.animations?.length||0,256,'Animation count');
  limited(d.images?.length||0,128,'Texture count');
  assert(!(d.extensionsUsed||[]).includes('EXT_mesh_gpu_instancing'),'GPU-instanced packages need Blender inspection.');
  assert(!JSON.stringify([d.extensionsRequired||[],d.extensionsUsed||[]]).match(/draco|meshopt|basisu/i),'Compressed geometry/textures need an offline adapter; use Blender preview.');
  function noURI(v,depth=0){assert(depth<100,'Model nesting is too deep.');if(v&&typeof v==='object')for(const [k,x] of Object.entries(v)){assert(k!=='uri','3D preview must be fully embedded; external/data URLs are refused.');noURI(x,depth+1);}}
  noURI(d);
  assert((d.buffers||[]).length===1&&d.buffers[0].byteLength<=binary.length,'Model must have one embedded buffer.');
  limited(d.buffers[0].byteLength,binary.length,'Embedded buffer');
  for(const v of d.bufferViews||[]){limited(v.byteLength,binary.length,'Buffer view');limited(v.byteOffset||0,binary.length,'Buffer offset');assert(v.buffer===0&&(v.byteOffset||0)+v.byteLength<=binary.length,'Invalid buffer view.');}
  let elements=0;for(const a of d.accessors||[]){limited(a.count,6000000,'Accessor');elements+=a.count;}
  limited(elements,16000000,'Geometry/animation data');
  // Bound expanded draw calls, not only file bytes; repeated instances count.
  let vertices=0;
  for(const n of d.nodes||[])if(n.mesh!==undefined){const mesh=d.meshes?.[n.mesh];assert(mesh,'Invalid mesh reference.');for(const p of mesh.primitives||[]){const a=d.accessors?.[p.attributes?.POSITION];assert(a,'Missing positions.');vertices+=a.count;}}
  limited(vertices,2000000,'Displayed vertices');assert(vertices>0,'This source has no displayable mesh; inspect its rig in Blender.');
  const visited=new Set(),active=new Set();
  function visit(index,depth=0){assert(Number.isInteger(index)&&d.nodes?.[index]&&depth<256&&!active.has(index),'Invalid/cyclic node hierarchy.');if(visited.has(index))return;active.add(index);for(const child of d.nodes[index].children||[])visit(child,depth+1);active.delete(index);visited.add(index);}
  for(let i=0;i<(d.nodes||[]).length;i++)visit(i);
  let pixels=0;
  for(const im of d.images||[]){assert(['image/png','image/jpeg'].includes(im.mimeType)&&Number.isInteger(im.bufferView),'Only embedded PNG/JPEG textures are supported.');const v=d.bufferViews?.[im.bufferView];assert(v,'Missing texture buffer.');pixels+=imagePixels(binary.subarray(v.byteOffset||0,(v.byteOffset||0)+v.byteLength),im.mimeType);limited(pixels,64*1024*1024,'Decoded textures');}
  return {objects:d.nodes?.length||0,vertices,animations:(d.animations||[]).map((a,i)=>a.name||`Take ${i+1}`)};
}

export async function verifiedPackage(source) {
  const seen=new Set();let total=0;
  assert(Array.isArray(source.files)&&source.files.length>0&&source.files.length<=4096,'Invalid preview package.');
  for(const f of source.files){assert(typeof f.path==='string'&&!seen.has(f.path.toLowerCase()),'Duplicate package member.');seen.add(f.path.toLowerCase());limited(f.size,512*1024*1024,'Source file');total+=f.size;limited(total,512*1024*1024,'Source package');const actual=await fileHash(await safe(source.root,f.path));assert(actual.sha256===f.sha256&&actual.size===f.size,'Preview source changed; refresh its version.',409);}
}

export async function packageGLTF(source) {
  const selected=source.files.find(f=>f.path===source.file);assert(selected,'Unknown model member.');limited(selected.size,MAX_VIEWER_BYTES,'Model');
  const bytes=await fs.readFile(await safe(source.root,source.file));
  if(/\.glb$/i.test(source.file)){validateGLB(bytes);return bytes;}
  limited(bytes.length,8*1024*1024,'glTF JSON');const d=JSON.parse(bytes.toString('utf8'));
  assert(d.asset?.version==='2.0','Only glTF 2.0 is supported.');
  const chunks=[];let size=0;
  const append=bytes=>{const at=size,pad=(4-bytes.length%4)%4;size+=bytes.length+pad;limited(size,MAX_VIEWER_BYTES,'Embedded model');chunks.push(bytes,Buffer.alloc(pad));return at;};
  async function member(uri) {
    assert(typeof uri==='string'&&!/[:\\?#\0]/.test(uri)&&!uri.startsWith('/')&&!uri.split('/').includes('..'),'Only package-local resource URIs are supported.');
    const decoded=decodeURIComponent(uri);assert(!/[:\\?#\0]/.test(decoded)&&!decoded.startsWith('/')&&!decoded.split('/').includes('..'),'Unsafe resource URI.');
    const name=path.posix.join(path.posix.dirname(source.file),decoded),record=source.files.find(f=>f.path===name);
    assert(record,'glTF resource is not in the verified package.');limited(record.size,MAX_VIEWER_BYTES,'Resource');return fs.readFile(await safe(source.root,name));
  }
  const offsets=[];
  for(const buffer of d.buffers||[]){const bytes=await member(buffer.uri);assert(bytes.length===buffer.byteLength,'Buffer size differs from glTF.');offsets.push(append(bytes));}
  for(const view of d.bufferViews||[]){assert(offsets[view.buffer]!==undefined,'Missing buffer.');view.byteOffset=(view.byteOffset||0)+offsets[view.buffer];view.buffer=0;}
  d.bufferViews||=[];
  for(const im of d.images||[])if(im.uri){const uri=im.uri,bytes=await member(uri);im.bufferView=d.bufferViews.length;im.mimeType=im.mimeType||(/\.png$/i.test(uri)?'image/png':/\.jpe?g$/i.test(uri)?'image/jpeg':null);delete im.uri;d.bufferViews.push({buffer:0,byteOffset:append(bytes),byteLength:bytes.length});}
  d.buffers=[{byteLength:size}];const json=Buffer.from(JSON.stringify(d));const padded=Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,32)]),binary=Buffer.concat(chunks);
  const result=Buffer.alloc(12+8+padded.length+8+binary.length);result.writeUInt32LE(0x46546c67,0);result.writeUInt32LE(2,4);result.writeUInt32LE(result.length,8);result.writeUInt32LE(padded.length,12);result.writeUInt32LE(JSON_CHUNK,16);padded.copy(result,20);const at=20+padded.length;result.writeUInt32LE(binary.length,at);result.writeUInt32LE(BIN_CHUNK,at+4);binary.copy(result,at+8);validateGLB(result);return result;
}
