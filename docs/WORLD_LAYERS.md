# Layered scene workflow: safe World foundation

This is the first implementation slice, not the whole layered-editor plan.
World is static arrangement; Action retains motion inspection. Existing project
schemas, source-use gates, approvals and explicit Save/return semantics remain.

## Whole-asset placement

Workbench model imports request the bounded `placement: world-v1` option. Plain
harness imports retain their previous behavior unless they explicitly opt in.
Preparation uses observed `bad_asset` + `bad_job` ownership, not guessed object
names or a character-specific hierarchy. New groups receive an unanimated EMPTY
above their independent roots and a UUID `bad_placement_instance` on the control
and its members. Source versions and exact input bytes remain bound by the import
job specification and the project's catalog pins; audit rows expose instance and
control identity in addition to the existing asset/job references.

Two imports of one source retain distinct instances. Multiple roots can share a
control without altering local animation channels, actions, armature modifiers,
mesh data or bind/rest state. Parent-plus-child selection resolves to one control.
Linked/overridden/shared-scene objects, constraints/drivers, cross-owned hierarchy,
missing controls and inconsistent instance bindings are not guessed into support.
They remain unchanged and appear in the preparation report/manual task panel.

Existing imports are prepared only in the dedicated World task working copy.
Opening a project or requesting a preview never migrates its checkpoints. Task
initialization is not an explicit Save. Don't Save keeps the input; Save publishes
the separate result through the existing unapproved Save/return protocol.

The dedicated World workspace has a whole-asset selector and Move/Rotate/Scale
commands. G/R/S route selected imported members to their placement control only
inside this task's World workspace. Untagged user-created objects retain normal
Blender transforms. No global keymap or preference is saved. Uniform positive
scale is the verified rig path; nonuniform/negative scale and arbitrary detailed
editing remain manual, unverified operations. Native toolbar/property edits are
not reinterpreted as whole-instance operations. This is not a restricted Blender
editor or a universal rig adapter.

## Static World preview

The authenticated server chooses `world-static-v1` from the actual scene stage;
the client cannot override it. Other stages retain `inspection-v1` in this slice.
The profile enters source/cache identity and scene-view reuse identity. Cached
bytes and originals are still verified before serving. Derivatives do not import,
save scene changes, assign motion or approve work.

For Blender-converted World sources, the worker makes temporary evaluated mesh
copies at the saved/observed reference frame. This preserves current deformation:
turning off animation export alone can incorrectly export the bind pose. The
derivative carries no animation tracks and records its frame and source-to-node
mapping. Temporary geometry, image bindings and visibility are restored even if
export fails; no original file is saved. World's controls do not play animation.
Direct verified glTF assets use their default pose without applying a clip. Such
asset inspections have no invented Blender frame or custom-shape classification.

World suppresses bone overlays in its dedicated Blender view and hides only
objects actually referenced as bone custom shapes, never mesh names that merely
look like controls. Skinned/ambiguous custom-shape objects refuse automatic hiding.
Viewport hiding is task-local and recorded for restoration in later tasks; master
render visibility is not changed. Action restores recorded widget visibility.
User geometry resembling a skeleton is not automatically removed.

Existing limits remain: 2 million source/evaluated mesh vertices, 128 MiB GLB,
512 MiB copied inputs/dependencies and 100 GiB private derivative storage.
Unsupported simulations/procedural geometry retain explicit Blender fallback.
Materials and neutral viewer lighting remain approximations, not delivery proof.

## Verification and rollout

Run the usual offline and launcher suites. The following generated fixtures test
actual Blender separately, using new unused evidence directories:

```text
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/world_layers_fixture.py -- <new-output>
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/import_visibility_fixture.py -- <new-import-output>
node tools/task_save_native.mjs <new-save-output> <blender-executable> <world-fixture-output>
```

The World fixture preserves the original keyed-transform failure, verifies
Save/reopen/frame evaluation, independent rigged instances, static/multiple roots,
shared data, safe refusals, interrupted derivative restoration, real skin motion
and Blender-to-GLB evaluated placement. The import fixture checks the actual
opt-in worker and unchanged older imports. Save/return optionally adds imported
keyed-rig Save and Don't Save cases to its five existing native-file cases.

`embedded_viewer_suite.py` retains its existing CI journey names and runs this
foundation before real browser checks. World controls/static pixels and Action
playback/pixel changes are separate assertions; animation coverage is not removed.
`world_layers_check.mjs` is an additional real-browser check for an existing
JavaScript Playwright installation. It accepts only `synthetic-embedded-viewer`
fixtures and explicit existing module/Chrome paths; it installs nothing.

Background Blender and browser success do not certify native Windows keymaps,
close dialogs, human creative acceptance, every licensed rig or a live cutover.
Those remain separately recorded gates. Deployment requires exact-commit CI,
private-input checks, packaged staging, backups and reversible coherent replacement
of launcher plus harness. Do not patch an installed runtime under its old identity.

Not implemented in this slice: in-app picking/transform gizmos, transform-draft
undo/Save batching, performer-first motion assignment, new shot/light controls,
live unsaved Blender streaming, or automatic recovery of earlier lost placement.
Earlier checkpoints are not repaired merely by switching to a static viewer.
