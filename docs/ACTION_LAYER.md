# Performer-first Action layer

This source slice adds performer-first browser controls and bounded saved-scene
operations, not a retargeting system or motion-quality approval. The compact
Action view automatically inspects the exact saved checkpoint, offers performer-
owned native takes or a held pose, and keeps timing choices in a local draft.
Undo, Discard and navigation protection do not run Blender. Explicit Save runs
one bounded batch, refreshes the saved scene and does not complete the activity.
The preview is labelled as saved performance while a timing draft is unsaved.
The visible planned playback range expands when needed to include complete takes;
Save includes that exact range, within the existing 3600-interval bound. It never
silently trims a later-starting or slowed take to the previous playback window.

The server-derived `action-playback-v1` profile exports one combined scene clip
with the actual FPS/range and a verified zero-time origin. Blender's default
per-object scene-animation splitting is explicitly disabled. Performer choices
are not a global GLB take selector; play/scrub shows all assigned performance
together. Confirmed rig widgets are hidden only in the disposable derivative;
skin, native keys, original helper visibility and source files remain intact.
Returning to World produces its separate frozen-frame profile without removing
motion from the scene. Materials and viewer lighting remain approximations.

`action-audit` observes actual object/action/slot bindings from active actions and
NLA strips. Unbound lookalike actions are reported separately, never offered by
guessing bone names. Each take ID binds performer, action, slot, range and native
channel hash. Placement controls and confirmed rig widgets are not performers.

`action-edit` accepts `action-layer-v1`, the exact audit hash and one to 32 distinct
performers. A native clip edit selects a take ID, start frame and speed 0.1–4.
The complete take is assigned once through an NLA strip; there is no silent trim,
repeat, FPS change or keyframe rewrite. A hold edit samples one explicit frame
inside the observed scene range and retains that object/pose state. Previous
active motion is retained as a muted binding and prior tracks are kept muted,
not deleted. An optional bounded scene playback range is explicit.

Linked/shared ownership, constrained/driven performance, animated attachments,
shape-key motion and NLA tweak/solo contexts require detailed Blender editing.
These refusals protect a limited supported subset; they are not assertions that
the source assets are broken. Retargeting still requires the existing exact
source/target inspection and reviewed transfer plan. No normal control launches
a model, acquires a new asset or invents a permission decision.

The worker starts from an immutable checkpoint in a separate process, validates
the whole batch before changing it, saves separately and reopens its result.
Verification checks native channels, rig rest/skin identity, placement controls,
unselected bindings and selected clip/hold state. Original bytes and earlier
results are retained. This is structural/numeric evidence, not proof of contacts,
deformation quality, natural movement or transitions. Temporal review is required.

## Authenticated app boundary

`POST /api/workbench/action-inspect` records a real native inspection receipt.
`POST /api/workbench/action-save` binds its inspection, project, scene, expected
revision/checkpoint/hash, exact bounded changes and idempotency UUID. The server
refuses foreign performers/takes, stale inspection, changed source bytes, missing
source-use review and concurrent writers. The native worker independently checks
the observed binding again. A replay returns the existing receipt, not a new job.

World and Action reuse the same checkpoint-job lease and publication boundary.
Successful Action Save creates a new current **unapproved** checkpoint. World
completion remains; Action and later completion/readiness are invalidated by the
existing dependency rules. Previous movies and checkpoints remain historical.
Inspection itself does not replace the current checkpoint or approve a layer.
Failed jobs retain their evidence. Explicit existing recovery verifies native
jobs are stopped before releasing the owned lease; it never removes saved files.

## Tests and remaining acceptance

Portable contract and launcher tests cover bounds, refusal, writer exclusion,
idempotency, exact result verification and preservation. Generated native tests:

```text
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/action_layer_fixture.py -- <world-fixture>/placed.blend <new-action-output>
node tools/action_layer_check.mjs <new-http-output> <action-output> <python> <blender>
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/action_preview_fixture.py -- <action-output>/source.blend <new-preview-output>
node tools/action_browser_check.mjs <new-browser-output> <action-output> <preview-output> <python> <blender> <installed-playwright-module> [installed-chrome]
```

The existing embedded-viewer CI journey runs these fixtures without changing its
workflow names or replacing earlier evidence. Tests use two generated rigs plus
object motion, independent timing/hold samples, actual deformation and original
hash checks. HTTP tests call the authenticated server and actual native worker,
then independently inspect the new checkpoint. They are not browser or native
desktop tests and contain no genuine human approvals.

Browser tests compare both generated skins and a moving prop against evaluated
Blender samples, then exercise timing/hold, Undo, Save, Discard and return to World.
Legacy preview-only tests precompute performer inspection before their unchanged-
manifest baseline; they still forbid scene mutations and approvals.

Intentional manual rig access, private licensed inputs, interruption/stale-draft
edge cases, exact-commit CI, full-film acceptance, packaging and live rollout must
still be recorded separately. No native Windows UI proof follows from Playwright.
No installed runtime is changed merely by committing this source slice.
