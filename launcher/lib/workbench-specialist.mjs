/** Existing Codex terminal, but exact scene/native catalog context. No extra model call. */
import fs from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
import {buildSessionContext} from './onboarding.mjs';
import {checkpointFor,stages,stageIndex} from './workbench-model.mjs';
import {assert,now,safe,writeJson} from './storage.mjs';
export async function startSpecialist(work,p,sceneId) {
  const scene=work.scene(p,sceneId);await work.unlocked(p);
  assert(!scene.candidate,'Review the current candidate before starting another writer.',409);
  assert((await work.store.verify(p.id)).ok,'Pinned sources changed.',409);
  assert(p.brief.trim(),'Add the production intent before asking a specialist to propose work.');
  if(scene.current)await work.verify(p,scene);
  const context=await buildSessionContext(work.store,work.config,p.id);
  const task={projectId:p.id,sceneId,activity:scene.stage,checkpoint:checkpointFor(scene),
    selectedSources:p.assets.filter(a=>scene.sources.includes(a.sourceId)),
    nativeCatalog:(p.workbench.catalogPins||[]).filter(a=>(scene.catalog||[]).includes(a.id)),
    selectedMotion:scene.selectedMotion||null,role:stages[stageIndex(scene.stage)].role};
  context.prompt+='\n\n## Scene-scoped workbench task\n'+JSON.stringify(task,null,2)+'\n\n'+
    'This exact scene is the target, not the legacy scene pointer. Native catalog IDs and pinned versions are selected ingredients, not imported objects, rig compatibility or license grants. Search existing sources first. For animation, inspect source motion and target rig, propose transfer-plan, then request its explicit review before transfer-prepare and mediated execution. Do not guess mappings. '+
    'Use the installed specialist and its existing bounded operations. Call prepare_project; bind prepared jobs before run_project_job. Respect the shared project writer semaphore. Never overwrite checkpoints, originals or live Blender edits. A dedicated manual Blender window does not establish ownership of the existing MCP socket. '+
    'Save a NEW candidate under project Scenes with external asset references remapped. Return its exact path, hash, operation/job IDs, observed objects/actions and unresolved checks. The user collects and approves it in this scene. Do not approve your own output or mark stages complete. Full renders need separate authorization. No new providers, MCP configurations, paid services or automatic model calls are introduced by launcher navigation.';
  const sessionId=randomUUID(),directory=await safe(p.directory,'Docs/Codex');await fs.mkdir(directory,{recursive:true});
  const promptFile=await safe(p.directory,`Docs/Codex/${sessionId}.md`);await fs.writeFile(promptFile,context.prompt,{flag:'wx'});
  await writeJson(await safe(p.directory,`Docs/Codex/${sessionId}.json`),{...context,sessionId,promptFile,createdAt:now(),task});
  const terminal=await work.runtime.launchTerminal(p.id,sessionId);
  return {sessionId,processId:terminal.processId,message:'Scene specialist terminal requested. Existing Codex sign-in, trust, costs and source/job approvals still apply.'};
}
