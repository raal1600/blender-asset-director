/** Scene workbench facade: native file/catalog adapters over the shared job lifecycle. */
import fs from 'node:fs/promises';
import {constants} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {assert, fileHash, now, safe, writeJson} from './storage.mjs';
import {Workbench as WorkbenchCore} from './workbench-core.mjs';
import {assertBlendEnvelope} from './workbench-files.mjs';

export class Workbench extends WorkbenchCore {
  async importCheckpoint(id,sceneId,revision,sourceScene) {
    const p=await this.project(id,revision),s=this.scene(p,sceneId);await this.unlocked(p);
    assert(!s.candidate,'Review or discard the existing candidate first.',409);
    assert((await this.store.scenes(id)).includes(sourceScene),'Choose an existing saved file from this project.');
    const source=await safe(p.directory,sourceScene),before=await fileHash(source),cpId='cp_'+randomUUID();
    const envelope=await assertBlendEnvelope(source);
    const relative=`Scenes/${s.id}--${cpId}.blend`,destination=await safe(p.directory,relative);
    // Sibling copy preserves relative asset paths for both compressed and raw files.
    // Recognizing a compression envelope is not a scene audit or a user approval.
    await fs.copyFile(source,destination,constants.COPYFILE_EXCL);
    const after=await fileHash(source),saved=await fileHash(destination);
    assert(before.sha256===after.sha256&&saved.sha256===before.sha256,'File changed while checkpointing. Candidate was not registered.',409);
    const cp={id:cpId,path:relative,...saved,parent:s.current,stage:s.stage,createdAt:now(),source:'saved-project-file',audit:null,envelope};
    await writeJson(await safe(p.directory,`Docs/Workbench/${cp.id}.json`),cp);
    s.checkpoints.push(cp);s.candidate=cp.id;
    return this.store.save(p,p.revision);
  }
}
