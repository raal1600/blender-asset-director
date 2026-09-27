# Explicit Save and return

New matched launcher/harness tasks negotiate `explicit_save_handoff` and record
`handoff: explicit-save-v1`. Older tasks keep their checkpoint/collect protocol;
their files are never retrospectively interpreted as a user Save.

## User experience

Arrange in Blender opens a dedicated working copy. The existing Director scene
stays unchanged while editing. Save normally (including Save in Blender's close
dialog), then close Blender. Director automatically returns the last successfully
saved version without a checkpoint collection or another keep/save step.

Closing without any explicit Save retains the pre-edit scene. Saving, editing
again and choosing Don't Save retains the earlier saved edits, not the later
unsaved changes. Cancel leaves Blender open and the writer lease held. The
dedicated Save & return to Director command saves and closes only its own process.

Saving updates the working draft, not human approval. It does not advance a
stage. Changed drafts invalidate downstream completion/readiness through the
existing checkpoint model, while old checkpoints, movies and reviews remain.

## Evidence and refusal behavior

Initialization's save happens before handlers are installed. `save_pre` and
`save_post` accept only the exact task working path, with lineage checks. Saves
to different paths, startup files, and recovery copies are not handoffs. Opening
another file disconnects automatic return. No timer performs a Save.

The session record distinguishes READY, SAVING, SAVED, SAVE_FAILED and DISCONNECTED.
A successful Save produces an atomic latest-save pointer and an immutable small
observation with task/project/scene/process identity, hash, size and scene audit.
It does not create another large scene snapshot on every Ctrl+S. Once the exact
owned process is confirmed stopped, the serialized authenticated `task-sync`
POST verifies the receipt and saved bytes, freezes a separate checkpoint and
adopts it as the unapproved current draft. GET remains read-only. The active
scene UI polls for return; reopening Director can complete a pending handoff.

No-save return requires the working bytes to equal the initialized baseline.
Unknown/reused process identity, failed/incomplete saves, file drift, changed
sources, corrupted receipts or changed project context refuse automatic return
and retain the files and lease for inspection. Recovery cannot silently discard
an explicit saved receipt. Partial persistence can be retried without duplicate
checkpoints or invented approvals. No credentials, preference changes, new
service, asset upload or global automatic script execution are involved.

The save callback distinction is consistent with Blender's native file-writing
implementation: [normal save and autosave code](https://github.com/blender/blender/blob/main/source/blender/windowmanager/intern/wm_files.cc).
Actual installed-version tests remain required; upstream source is not local
acceptance evidence.

## Validation

- `node --test launcher/test/task-save.test.mjs`: synthetic state, identity,
  refusal, preservation and crash-retry contracts, not native GUI proof.
- `python -B tools/run_checks.py --offline`: portable and installer checks.
- `node tools/task_save_native.mjs NEW_OUTPUT ABSOLUTE_BLENDER`: real background
  Blender saves and authenticated HTTP return for no-save, save, save then
  unsaved edits, repeated saves and separate recovery-copy cases.
- Browser acceptance must verify Arrange -> task-sync -> saved/no-save scene,
  automatic preview refresh, no collection button and no generated approval.
- Native acceptance separately tests X -> Save, X -> Don't Save, Cancel and
  Save & return in a disposable dedicated GUI. Never run unbound keyboard
  automation over user windows. Headless operator tests do not certify dialogs.

Production rollout still requires the exact-source gates and verified reversible
staging. This document does not claim a release, CI pass or human acceptance.
