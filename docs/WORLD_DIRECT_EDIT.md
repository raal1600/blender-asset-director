# World direct editing: visual draft and bounded Save

This is an incremental implementation of the layered-editor plan. Prepared World
instances support picking, Shift-click multi-selection, Ctrl+A, move/rotate/uniform
scale handles, optional exact placement, local undo/discard and one explicit Save.
Orbiting or dragging never starts Blender; Save submits one authenticated batch.
Source assets remain inspection-only. Older/unsupported scenes retain the Blender
route; explicit in-app preparation and the remaining layers are still outstanding.

The converter binds native instance membership to exact exported GLB node indices.
The client never guesses ownership from similar names or treats separate skin
parts as independent characters. Blender Z-up matrices are transformed into the
viewer coordinate system and back. Local changes do not approve World or write
project metadata. Navigation and new mutations offer Save/Discard/Stay only when
needed; failed saves and stale checkpoint refreshes preserve the local draft.

`world-transform` is an isolated mutation on an exact saved `.blend` input. Its
versioned options contain 1–64 distinct observed instance IDs with the expected
and requested row-major Blender-coordinate 4x4 control matrices. It refuses
nonfinite/unbounded values, shear, reflected or nonuniform scale, stale matrices,
ambiguous/missing identities, foreign descendants, linked/shared objects and
constrained/driven ownership. It validates every target before moving any of them.
Only the unanimated instance controls change; native rig channels stay intact.

The worker saves a separate `result.blend`, reopens it with scripts disabled,
checks the requested matrices and retained local hierarchy/animation/unrelated
state, then emits the actual scene audit. Failed results are never published as
current checkpoints. `world-placement-audit` is a read-only companion operation.

`POST /api/workbench/world-save` uses the existing authentication and serialized
command surface. It binds project revision, scene, exact checkpoint ID/hash,
versioned matrix batch and a request UUID. The same request returns its retained
receipt; reusing that UUID for another request refuses. Project source-use and
byte checks plus the shared writer lease gate execution. Manual tasks cannot race
with Save. Sources and baseline are rechecked before publishing the verified
output as a new current **unapproved** checkpoint. Saving is not World completion,
render approval or a replacement for source rights. Previous files are retained.

## Regression coverage

Portable contract tests and launcher synthetic persistence tests cover schema,
bounds, source-use refusal, writer exclusion, stale/foreign identities, exact
result binding, failure retention and idempotency. The generated real Blender
fixture exercises two keyed rigs and a multi-root static asset through isolated
job preparation, execution, Save/reopen and frame evaluation:

```text
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/world_layers_fixture.py -- <new-world-fixture>
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/world_transform_fixture.py -- <world-fixture>/placed.blend <new-transform-output>
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/world_append_fixture.py -- <new-append-output>
```

Collection append differs from glTF import: linking a collection leaves transforms
unevaluated until the view layer updates. World preparation now evaluates that
baseline before checking identity-parent preservation. The preservation guard is
not weakened. The append fixture uses the same generated animated collection as
the installed-studio journey and tests two independent imports plus original
byte preservation. The journey also reports failed retained jobs immediately
instead of hiding the worker error behind an eventual generic add timeout.

These tests run through the existing embedded-viewer suite; workflow names and
historical evidence are unchanged. Synthetic confirmations are not human review.
`tools/world_edit_check.mjs` exercises real Chrome picking and a group gizmo,
undo/discard, unsaved-navigation protection, one Save through actual Blender,
rotation/scale persistence, original preservation, transport failure and stale
draft handling. It reuses the installed Playwright driver and Chrome, not a CDN.
Native desktop gestures, private licensed inputs and packaged/live deployment
remain separate acceptance gates.

## Explicit interrupted-save recovery

A failed native Save leaves the local placement draft and previous checkpoint
intact. Inspect / recover attempt exposes the retained failure. Declining reset
changes nothing. An explicitly confirmed reset archives the native attempt and
returns that bounded, project-owned job to PLANNED; it never launches a worker.
The retry allowlist includes World, Action and scene-layer audit/edit operations
alongside existing preview/render jobs. Running/successful jobs, unrelated native
operations, foreign ownership, stale revisions and active writers still refuse.

Reset and stopped-task resolution change recovery metadata only, so they do not
require discarding or resaving the failed local draft first. Execution is a new
explicit Save, rechecking all ordinary source/checkpoint/writer guards. Resolve
does not terminate processes, adopt unsaved work or approve a stage.

`world_recovery_check.mjs` exercises the real browser and native harness after
deliberately stopping its exact owned background Blender child during startup.
The test-only helper uses the captured Popen handle, never process-name/PID scans
or manual receipt edits. It verifies actual failure, a scripted decline, archived
failure hashes, preserved draft, explicit resolve, a new native Save/reopen and
viewer agreement. This startup interruption is not proof of a native close dialog,
mid-render recovery or genuine human approval; those remain distinct gates.

## Windows path compatibility

New manual tasks retain the existing filenames when bounded; deeper Windows
projects use full task-ID-only working/checkpoint filenames. Reconciliation accepts
both exact formats, never arbitrary names. Preflight checks working files and
save/return receipts before taking a writer lease. Too-deep paths refuse without
moving files or changing Windows policy. New immutable save observations use the
unique save ID in their filename; their contents still bind the task/project/scene.
Existing task files, receipts and checkpoints are not renamed or rewritten.
