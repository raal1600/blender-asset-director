import {atomicRename} from './atomic-rename.mjs';
import fs from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';

export class Fault extends Error { constructor(message, status = 400) { super(message); this.status = status; } }
export const assert = (ok, message, status) => { if (!ok) throw new Fault(message, status); };
export const exists = async p => fs.access(p).then(() => true, () => false);
export const json = async p => JSON.parse((await fs.readFile(p, 'utf8')).replace(/^\uFEFF/, ''));
export const digest = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
export const now = () => new Date().toISOString();
export const slash = p => p.split(path.sep).join('/');
export function relativeName(name) {
  assert(typeof name === 'string' && name.length > 0 && !name.includes('\\') && !name.includes(':') && !name.includes('\0') && !path.isAbsolute(name), 'Expected a relative file path.');
  assert(name.split('/').every(p => p && p !== '.' && p !== '..'), 'Path traversal is not allowed.');
  return name;
}
export function inside(root, candidate) {
  const rel = path.relative(root, candidate);
  return rel === '' || (!rel.startsWith('..' + path.sep) && rel !== '..' && !path.isAbsolute(rel));
}
export async function safe(root, relative = '') {
  const base = await fs.realpath(root);
  const target = path.resolve(base, relative ? relativeName(relative) : '');
  assert(inside(base, target), 'Path leaves its storage root.');
  // Check every existing component, including junctions and linked parents.
  let cursor = target;
  while (!await exists(cursor)) {
    const parent = path.dirname(cursor);
    assert(parent !== cursor, 'Missing storage root.');
    cursor = parent;
  }
  assert(inside(base, await fs.realpath(cursor)), 'Linked path leaves its storage root.');
  return target;
}
export async function writeJson(filename, value) {
  await fs.mkdir(path.dirname(filename), { recursive: true });
  const tmp = `${filename}.${randomUUID()}.tmp`;
  let prepared=false;
  try {
    const handle = await fs.open(tmp, 'wx');
    try { await handle.writeFile(JSON.stringify(value, null, 2) + '\n'); await handle.sync(); } finally { await handle.close(); }
    prepared=true;
    await atomicRename(tmp, filename);
  } catch(error) {
    // A complete but unpublished snapshot is recovery evidence, not committed
    // state. Preserve the prior destination and report failure honestly.
    if(prepared)error.message+='; uncommitted JSON snapshot retained at '+tmp;
    else await fs.rm(tmp,{force:true}).catch(()=>{});
    throw error;
  }
}
export async function fileHash(filename) {
  const h = createHash('sha256');
  const before = await fs.stat(filename);
  for await (const chunk of createReadStream(filename)) h.update(chunk);
  const after = await fs.stat(filename);
  assert(before.size === after.size && before.mtimeMs === after.mtimeMs, 'File changed during verification; retry.');
  return { sha256: h.digest('hex'), size: after.size };
}
export async function walk(root, max = 20000) {
  const result = [];
  async function visit(dir) {
    for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
      assert(result.length < max, 'Folder exceeds the scan limit.');
      const full = path.join(dir, entry.name);
      assert(!entry.isSymbolicLink(), `Linked source files are not scanned: ${entry.name}`);
      if (entry.isDirectory()) { await safe(root, slash(path.relative(root, full))); await visit(full); }
      else if (entry.isFile()) result.push(slash(path.relative(root, full)));
    }
  }
  await visit(root);
  return result.sort();
}
export async function snapshot(root) {
  const info = await fs.stat(root);
  const names = info.isDirectory() ? await walk(root) : [path.basename(root)];
  const files = [];
  for (const name of names) files.push({ path: name, ...await fileHash(info.isDirectory() ? await safe(root, name) : root) });
  return { version: digest(files), files, bytes: files.reduce((s, f) => s + f.size, 0) };
}
