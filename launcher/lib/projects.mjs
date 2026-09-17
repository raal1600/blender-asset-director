import {isDeepStrictEqual} from 'node:util';
import fs from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { assert, exists, json, now, relativeName, safe, slash, snapshot, writeJson } from './storage.mjs';

import {validateOnboarding} from './onboarding.mjs';

export const projectId = id => assert(/^prj_[0-9a-f-]{36}$/.test(id), 'Invalid project ID.');
const formats = new Set(['.fbx', '.bvh', '.blend', '.gltf', '.glb', '.obj', '.usd', '.usdz', '.abc']);
const sourceId = id => assert(/^src_[0-9a-f-]{36}$/.test(id), 'Invalid source ID.');
export class Store {
  constructor(root) { this.root = path.resolve(root); this.projects = path.join(this.root, 'Workspace', 'Projects'); this.database = path.join(this.root, 'Database'); this.registry = path.join(this.database, 'Registry'); }
  async init() {
    for (const p of [this.projects, this.registry]) await fs.mkdir(p, { recursive: true });
    if (!await exists(path.join(this.registry, 'sources.json'))) await writeJson(path.join(this.registry, 'sources.json'), { schema: 1, scannedAt: null, sources: [] });
  }
  validate(p) {
    assert(p.schema === 1 && p.owner === 'asset-director-launcher', 'Unsupported project manifest.'); projectId(p.id);
    assert(typeof p.name === 'string' && p.name.length <= 100 && typeof p.brief === 'string', 'Invalid project description.');
    assert(Number.isInteger(p.revision) && p.revision >= 1 && Array.isArray(p.assets) && Array.isArray(p.jobs), 'Invalid project record.');
    if (p.scene) { relativeName(p.scene); assert(p.scene.startsWith('Scenes/') && p.scene.endsWith('.blend'), 'Scene must belong to Scenes.'); }
    for (const a of p.assets) { sourceId(a.sourceId); assert(/^[0-9a-f]{64}$/.test(a.version), 'Invalid asset version.'); }
    for (const j of p.jobs) assert(/^j_[0-9a-f]{24}$/.test(j.id), 'Invalid job reference.');
    validateOnboarding(p);
    return p;
  }
  async list() {
    const projects = [], errors = [];
    for (const entry of await fs.readdir(this.projects, { withFileTypes: true })) {
      if (!entry.isDirectory() || entry.name.startsWith('.')) continue;
      try {
        const directory = await safe(this.projects, entry.name);
        if (!await exists(path.join(directory, 'project.json'))) continue;
        const p = this.validate(await json(path.join(directory, 'project.json')));
        assert(!projects.some(x => x.id === p.id), 'Duplicate project ID; resolve before making changes.');
        projects.push({ ...p, folder: entry.name, directory });
      } catch (e) { errors.push({ folder: entry.name, message: e.message }); }
    }
    return { projects: projects.sort((a,b) => b.updatedAt.localeCompare(a.updatedAt)), errors };
  }
  async get(id) {
    projectId(id);
    const { projects, errors } = await this.list();
    assert(errors.length === 0, 'A project manifest is invalid. Resolve the issue shown in Projects before making changes.', 409);
    const p = projects.find(p => p.id === id); assert(p, 'Project not found.', 404); return p;
  }
  async save(project, expected) {
    const current = await this.get(project.id);
    assert(current.revision === expected, 'This project changed in another window. Refresh and try again.', 409);
    const { folder, directory, ...p } = project;
    const content=({folder,directory,revision,updatedAt,onboarding,...data})=>({...data,libraryReviewed:!!onboarding?.libraryReviewed});
    p.revision = expected + (isDeepStrictEqual(content(current),content(p)) ? 0 : 1); p.updatedAt = now(); this.validate(p);
    await writeJson(await safe(current.directory, 'project.json'), p);
    return this.get(p.id);
  }
  async create(name, brief = '') {
    assert(typeof name === 'string' && name.trim().length >= 2 && name.trim().length <= 100 && !/[\r\n\0]/.test(name), 'Use a project name of 2–100 characters.');
    assert(typeof brief === 'string' && brief.length <= 10000, 'Brief is too long.');
    const id = `prj_${randomUUID()}`;
    const slug = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0,55) || 'project';
    const folder = `${slug}--${id.slice(4,12)}`;
    const directory = await safe(this.projects, folder);
    await fs.mkdir(directory);
    for (const dir of ['Scenes', 'Renders', 'Deliverables', 'Docs', 'Runs']) await fs.mkdir(path.join(directory, dir));
    const p = { schema: 1, owner: 'asset-director-launcher', id, name: name.trim(), brief, revision: 1, createdAt: now(), updatedAt: now(), scene: null, assets: [], jobs: [], capabilities: [], capabilityMode: 'auto', onboarding: {step:2,libraryReviewed:false} };
    await writeJson(path.join(directory, 'project.json'), p);
    await fs.writeFile(path.join(directory, 'AGENTS.md'), this.instructions(id));
    return this.get(id);
  }
  instructions(id) {
    return `# Asset Director project\n\nProject ID: ${id}. Read project.json before any operation. This manifest is the authoritative project context; a selection in the launcher UI is not global session state.\n\nUse the blender-asset-director skill at ${path.join(this.root, 'SystemRuntime/Harness/Installed')}. Read its SKILL.md and only the relevant operation contracts.\n\nShared sources and the managed library are under ${this.database}. Never edit source originals or harness receipts. Asset references in project.json are launcher source IDs and pinned hashes, not harness catalog IDs, license grants, or proof of scene provenance. Verify them before production with the launcher. Intake/review and harness catalog IDs remain separate.\n\nSave editable scenes under Scenes/, renders under Renders/, approved exports under Deliverables/, and notes under Docs/. Use relative render paths //../Renders/ for scenes saved directly in Scenes/. Never put required assets solely in Cache or Temp.\n\nUse node "${path.join(this.root, 'SystemRuntime/Launcher/cli.mjs')}" verify ${id} before work. Use the launcher audit command for a read-only scene audit. After any other harness job is prepared, bind its ID before execution with: node "${path.join(this.root, 'SystemRuntime/Launcher/cli.mjs')}" bind-job ${id} JOB_ID. The launcher enforces one owning project per job; shared prerequisites may be referenced as dependencies, not claimed as new project jobs. Do not edit job receipts to insert project IDs.\n\nInspect the existing Blender scene before touching it; never load over unsaved work. Starting Blender, checking health, and reading a scene are setup. Creative changes still require a user brief and the skill's bounded review workflow. Opening this workspace alone does not authorize rendering or production.\n`;
  }
  async update(id, { revision, name, brief, scene, capabilities, capabilityMode, onboarding }) {
    const p = await this.get(id);
    if (name !== undefined) { assert(typeof name === 'string' && name.trim().length >= 2 && name.length <= 100, 'Invalid project name.'); p.name = name.trim(); }
    if (brief !== undefined) { assert(typeof brief === 'string' && brief.length <= 10000, 'Invalid brief.'); p.brief = brief; }
    if (scene !== undefined) { assert(p.scene !== scene || scene === null, 'This scene is already selected.'); p.scene = scene; if (scene) assert(await exists(await safe(p.directory, relativeName(scene))), 'Scene does not exist.'); }
    if(capabilities!==undefined)p.capabilities=capabilities;
    if(capabilityMode!==undefined)p.capabilityMode=capabilityMode;
    if(onboarding!==undefined)p.onboarding=onboarding;
    return this.save(p, revision);
  }
  async inventory() { return json(await safe(this.registry, 'sources.json')); }
  async scan() {
    const old = await this.inventory(); const candidates = [];
    async function visit(base, dir, kind) {
      for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
        assert(!entry.isSymbolicLink(), 'Linked source packages are not supported.');
        const full = await safe(base, slash(path.relative(base, path.join(dir, entry.name))));
        if (entry.isDirectory()) await visit(base, full, kind);
        else if (formats.has(path.extname(entry.name).toLowerCase())) candidates.push({ kind, file: slash(path.relative(base, full)) });
      }
    }
    for (const kind of ['Animations','Characters','Meshes']) await visit(this.database, await safe(this.database, kind), kind);
    const packages = new Map();
    for (const c of candidates) {
      const parts = c.file.split('/');
      // Animations are individual clips. Character folders are complete packages;
      // meshes have a category level (Terrain/Buildings/etc.) before the package.
      const n = c.kind === 'Characters' ? 2 : 3;
      const rel = c.kind === 'Animations' || parts.length <= n ? c.file : parts.slice(0,n).join('/');
      const value = packages.get(rel) || { kind: c.kind, relative: rel, entrypoints: [] };
      value.entrypoints.push(c.file); packages.set(rel,value);
    }
    const sources = [];
    for (const pkg of packages.values()) {
      const previous = old.sources.find(x => x.relative === pkg.relative);
      const snap = await snapshot(await safe(this.database, pkg.relative));
      const source = { ...pkg, id: previous?.id || `src_${randomUUID()}`, name: path.basename(pkg.relative, path.extname(pkg.relative)), version: snap.version, bytes: snap.bytes, fileCount: snap.files.length, available: true, scannedAt: now(), review: 'UNREVIEWED' };
      const versionPath = await safe(this.registry, `versions/${source.id}/${snap.version}.json`);
      if (!await exists(versionPath)) await writeJson(versionPath, { schema: 1, sourceId: source.id, relative: source.relative, ...snap });
      sources.push(source);
    }
    for (const previous of old.sources) if (!sources.some(s => s.id === previous.id)) sources.push({ ...previous, available: false });
    const registry = { schema: 1, scannedAt: now(), sources: sources.sort((a,b) => a.name.localeCompare(b.name)) };
    await writeJson(await safe(this.registry,'sources.json'), registry); return registry;
  }
  async attach(id, sid, revision) {
    sourceId(sid); const p = await this.get(id); const registry = await this.inventory();
    const s = registry.sources.find(s => s.id === sid); assert(s?.available, 'Source missing; refresh the library first.');
    const current = await snapshot(await safe(this.database, s.relative));
    assert(current.version === s.version, 'Source changed since refresh. Refresh the library before linking it.', 409);
    assert(!p.assets.some(a => a.sourceId === sid), 'Source already linked. Remove its reference before deliberately choosing a new version.', 409);
    p.assets.push({ sourceId: sid, version: s.version, linkedAt: now() }); return this.save(p, revision);
  }
  async detach(id, sid, revision) { const p = await this.get(id); sourceId(sid); p.assets = p.assets.filter(a => a.sourceId !== sid); return this.save(p, revision); }
  async verify(id) {
    const p = await this.get(id); const results = [];
    for (const ref of p.assets) {
      try {
        const v = await json(await safe(this.registry, `versions/${ref.sourceId}/${ref.version}.json`));
        const current = await snapshot(await safe(this.database, v.relative));
        results.push({ ...ref, relative: v.relative, status: current.version === ref.version ? 'VERIFIED' : 'CHANGED' });
      } catch (e) { results.push({ ...ref, status: 'UNAVAILABLE', message: e.message }); }
    }
    return { projectId: id, checkedAt: now(), ok: results.every(r => r.status === 'VERIFIED'), assets: results };
  }
  async scenes(id) {
    const p = await this.get(id); const entries = await fs.readdir(await safe(p.directory,'Scenes'), { withFileTypes: true });
    return entries.filter(x => x.isFile() && x.name.endsWith('.blend')).map(x => `Scenes/${x.name}`);
  }
  async runs(id) {
    const p = await this.get(id), records = [];
    for (const name of (await fs.readdir(await safe(p.directory,'Runs'))).filter(n=>n.endsWith('.json')).sort().reverse().slice(0,30)) {
      try { const r=await json(await safe(p.directory,`Runs/${name}`)); assert(r.projectId===id,'Operation belongs to a different project.'); records.push(r); }
      catch(e) {records.push({state:'UNAVAILABLE',action:name,error:e.message});}
    }
    return records;
  }
  async trashList() {
    const trashRoot=await safe(this.root,'Archive/Trash');
    if(!await exists(trashRoot))return {projects:[],errors:[]};
    const projects=[],errors=[];
    for(const entry of await fs.readdir(trashRoot,{withFileTypes:true})) {
      if(!entry.isDirectory())continue;
      try {
        const container=await safe(trashRoot,entry.name);
        const receipt=await json(await safe(container,'trash.json'));
        projectId(receipt.projectId); relativeName(receipt.folder);
        assert(!receipt.folder.includes('/'),'Invalid original folder.');
        const p=this.validate(await json(await safe(container,receipt.folder+'/project.json')));
        assert(p.id===receipt.projectId && entry.name===p.id,'Trash identity mismatch.');
        projects.push({...p,trashedAt:receipt.trashedAt,folder:receipt.folder,container});
      }catch(e){errors.push({folder:entry.name,message:e.message});}
    }
    return {projects,errors};
  }
  async trash(id,revision) {
    const p=await this.get(id);
    assert(p.revision===revision,'Project changed. Refresh before moving it to Trash.',409);
    assert(!(await fs.lstat(p.directory)).isSymbolicLink(),'Linked project folders cannot be moved to Trash.');
    const runs=await this.runs(id);
    assert(!runs.some(r=>['RUNNING','PREPARING'].includes(r.state)),'An operation is unfinished. Resolve it before moving the project.',409);
    for(const ref of p.jobs) {
      const record=await safe(this.database,'AssetDirector/jobs/'+ref.id+'/job.json');
      if(await exists(record))assert((await json(record)).state!=='RUNNING','A harness job is running for this project.',409);
    }
    const trashRoot=await safe(this.root,'Archive/Trash');await fs.mkdir(trashRoot,{recursive:true});
    const container=await safe(trashRoot,id);assert(!await exists(container),'A trash entry with this ID already exists.',409);
    await fs.mkdir(container);
    await writeJson(path.join(container,'trash.json'),{schema:1,projectId:id,folder:p.folder,trashedAt:now()});
    try {await fs.rename(await safe(this.projects,p.folder),await safe(container,p.folder));}
    catch(e){await fs.unlink(path.join(container,'trash.json'));await fs.rmdir(container);if(['EBUSY','EPERM','EACCES'].includes(e.code))assert(false,'Windows could not move this project. Close its Codex terminal window (including PowerShell), and any Blender or Explorer window using the project folder, then retry. The project is still in place. If it remains blocked, check folder permissions.',409);throw e;}
    return {projectId:id,name:p.name,message:'Project moved to Trash. Shared sources and harness evidence were preserved.'};
  }
  async restore(id) {
    projectId(id);const trash=await this.trashList();
    assert(!trash.errors.length,'A trash record is invalid. Resolve it before restoring.',409);
    const p=trash.projects.find(p=>p.id===id);assert(p,'Project not found in Trash.',404);
    const live=await this.list();assert(!live.errors.length,'An active project manifest is invalid.',409);
    assert(!live.projects.some(x=>x.id===id),'This project ID is already active.',409);
    const destination=await safe(this.projects,p.folder);assert(!await exists(destination),'Original project folder is occupied; restore will not overwrite it.',409);
    await fs.rename(await safe(p.container,p.folder),destination);
    await fs.unlink(await safe(p.container,'trash.json'));await fs.rmdir(p.container);
    return this.get(id);
  }
  async bindJob(id, job) {
    assert(/^j_[0-9a-f]{24}$/.test(job.id), 'Invalid harness job.');
    const p = await this.get(id); const all = await this.list(); const trash = await this.trashList();
    assert(!trash.errors.length, 'A trash record is invalid; job ownership cannot be verified.',409); all.projects.push(...trash.projects);
    assert(!all.projects.some(x => x.id !== id && x.jobs.some(j => j.id === job.id)), 'This job already belongs to another project.', 409);
    if (p.jobs.some(j => j.id === job.id)) return p;
    // A job with target files must target this project. Shared source-only jobs
    // can be explicitly associated but never silently inferred from UI selection.
    for (const f of job.specification.inputs) {
      const rel = slash(path.relative(p.directory, f.path)); await safe(p.directory, rel);
    }
    p.jobs.push({ id: job.id, operation: job.specification.operation, linkedAt: now() });
    return this.save(p,p.revision);
  }
}
