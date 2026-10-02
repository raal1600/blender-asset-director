# Bounded camera and shared-light transactions

Development contract: `scene-layer-v1`. Native operations, authenticated launcher
transactions and progressive camera/shared-light controls are implemented.
Selected-shot viewing is described below. Complete rendered lighting comparison,
native desktop acceptance and local deployment remain separate required work.
It builds on [World placement](WORLD_LAYERS.md) and [Action](ACTION_LAYER.md).

## Inspect, propose, explicitly save

`scene-layer-audit` reads one saved `.blend`, with options `{ "layer": "shots" }`
or `{ "layer": "light" }`. Its hash binds observed cameras, scene geometry,
actual timebase, shared look and the preservation fingerprint. Inspection is not
approval and does not save a changed scene.

`scene-layer-edit` requires that exact audit hash, contract version, layer and
an explicit list of operations. The existing bounded native helpers execute in
a separate Blender worker. Shots permits one `camera-fit` or `camera-plan`;
Light permits up to four distinct operations from `light-adjust`, `world-adjust`,
`look-adjust` and additive `light-rig`. There is no script or arbitrary job field.

Camera names and subjects are explicit. New names must fit 63 UTF-8 bytes and
must not collide; no silent rename. Camera keys stay in the saved Action range.
FPS, scene frame range, original geometry, instance placement, native actions,
skin/rest state and unrelated objects must survive. Adapting supported camera
animation retains earlier object and lens actions in muted NLA tracks, binding
the observed action slot rather than guessing among a layered action's slots.
Original camera actions are not overwritten. Orbiting a viewer is not a Save.

Unsupported linked/shared/parented/constrained camera or light state, drivers,
active NLA and animated lights require detailed Blender editing. Camera data
animation outside the supported lens/focus fields also refuses. Complex or
animated world graphs are not simplified. Material/HDRI authoring remains in
the existing reviewed specialist/manual workflow.

The worker verifies the changed scene, saves a separate result, reopens it and
compares its audit and preservation fingerprint. Camera changes must not alter
lighting; light changes must not alter cameras. Requested edits never certify
framing, lighting quality or motion: `visual_acceptance` stays `NOT_EVALUATED`.

## Launcher boundaries

Authenticated POST routes `/api/workbench/scene-layer-inspect` and
`/api/workbench/scene-layer-save` bind the production, scene, project revision,
checkpoint ID/hash, request ID, layer and inspection receipt. Foreign cameras,
lights or subjects, stale inspections and cross-layer operations refuse.
Native portable validation checks the complete options before preparing a job.

The shared checkpoint transaction enforces source-use readiness, writer
ownership, idempotent request identity and unchanged source context. Success
publishes a separately hashed **unapproved** checkpoint. Failure retains its
receipt and does not replace the current scene. No empty catalog or automatic
project rewrite is involved.

Lighting is shared scene state, not a per-shot override. Each saved transaction
records all affected shot IDs/revisions, camera names and ranges from server
state. Clients cannot manufacture this list. Shot definitions and the selected
shot are retained; dependent completion and output validity follow existing
checkpoint rules. Actual rendered previews and deliberate review of all affected
shots are still required. WebGL appearance is not Blender lighting evidence.

## Evidence and remaining scope

Portable and launcher tests cover strict contracts and rejection paths.
`tools/scene_layer_fixture.py` generates real Blender camera creation/refinement,
retained camera actions, shared-light edits, save/reopen and preservation checks.
`tools/scene_layer_check.mjs` exercises authenticated HTTP through actual Blender,
two named shots, idempotency, refusal, checkpoint publication and shared-shot
context. Both run in the existing embedded-viewer acceptance journey.

Their generated test decisions are explicitly scripted, not human approvals.
They do not substitute for rendered before/after comparison, Windows manual handoff, licensed
inputs, exact-commit CI or local deployment acceptance. Those remain separate
required gates in the layered-workflow enhancement.

## Progressive authoring controls

Shots and Light share the large saved-scene viewer, scene picker, activity strip,
compact shot selector and explicit Save/Ready separation. The former general
asset shelf and three-column controls are not shown in these layers. History and
specialist/import tools remain under More. Light's More menu includes **Find
materials / HDRIs**, preserving the reviewed library route without restoring a
permanent asset shelf. Imported candidates retain explicit inspect, keep-working
and reject controls; normal native Save/return does not gain
an extra Collect/Keep step.

Shots can create a separate fitted camera from explicitly selected observed
geometry, a named new camera, frame, direction and lens. Starting values are
visible and editable, not an automatic artistic prescription. Naming a shot then
binds its real saved camera and range. Detailed camera refinement/motion remains
available through Blender; orbiting never edits a camera.

Light exposes the selected observed light's supported energy, size/radius/angle,
linear color and position, plus supported world strength and scene exposure.
Unrelated properties are omitted from the bounded batch. Local values have Undo,
Discard and one explicit Save; a typed field is one Undo gesture. Typing does not
remount the controls or steal the Save click. The selected light survives Save.
No approximate WebGL lighting is presented as these unsaved values or as a render.
All named affected shots are listed; Preview lighting explicitly authorizes the
existing bounded real still. Saving or previewing does not approve Light.

Inspection scheduling reuses exact layer/checkpoint receipts, refreshes a stale
read revision once and never automatically retries a failed mutation. Stale local
drafts remain visible and cannot save. Navigation resolves a dirty draft before
changing context. Separately verified native results publish new checkpoints.

`tools/scene_layer_browser_check.mjs` drives real browser camera creation, named
shot viewing, light editing, undo/navigation, invalid-input refusal, one-click
Save, a competing native Save/stale draft and explicit discard. Independent
native inspections check saved values, unchanged cameras, affected-shot identities
and preserved original/checkpoint hashes. Its scripted Shots-ready decision is
synthetic test setup, never human approval. It runs in the existing embedded-viewer
browser partition; native Windows handoff and artistic lighting review are not
inferred from this browser result.

## Rendered shared-light comparisons

Light's **Compare rendered stills** opens a read-only, shot-scoped comparison of
retained Blender PNGs. It does not render, save or approve anything. The current
checkpoint and historical checkpoint are labelled separately; matching camera,
frame, shot revision and preview settings do not prove that only lighting changed.
Users review every affected shot before deliberately marking Light ready.

The authenticated evidence endpoint verifies project/scene ownership, the retained
successful run and native job, exact options, checkpoint bytes/path, saved shot
definition, native result and exact PNG hash/size. Named-camera previews now retain
the verified external dependency identities in their native result. Changed or
missing dependencies make a still historical; older results with no dependency
identity cannot establish current lighting. No historical receipt is rewritten.
The browser additionally checks the PNG bytes against the returned SHA-256 before
display. Unavailable evidence is reported, never silently replaced or approved.

History reads the retained run directory rather than the small recent-run window.
It is bounded to 10,000 receipt names, 64 KiB per scanned receipt, 32 MiB total
receipt bytes and 20 previews per page. Larger non-preview receipts are not read.
No asset/database schema migration, asset copy, deletion or new service is needed.
Scenes without optional shot metadata remain readable without rewriting them.

`tools/lighting_evidence_check.mjs` generates four real CPU previews: two named
cameras before and after one explicit shared exposure Save. It verifies the
actual browser images, old/current identities, ownership, mobile comparison and
shot-revision invalidation. It runs in the existing embedded-viewer partition.
`tools/lighting_retained_check.mjs` can continue the specific synthetic selector
failure using the retained four renders without rendering them again; its report
does not replace the original failure. Synthetic checks and image inspection are
not native desktop or human artistic acceptance.

## Saved-shot viewing

For a selected checkpoint shot, the server derives `shot-framing-v1` (Shots or
Render) or `look-inspection-v1` (Light) from the actual activity. The source and
cache identity include the selected shot ID, revision, name, camera and range.
Client-supplied profile or camera overrides are refused. Native copies validate
the identity, observed camera and 1..360-frame range before sampling.

The native worker records the evaluated camera world matrix and Blender's real
projection matrix for every integer shot frame, including animated lens/shift,
orthographic projection and pixel aspect. Unsupported panorama, render-border
and multiview cases refuse rather than approximate. Sampling restores the
original frame/subframe and active camera. Original scene files stay unchanged.

The browser uses the same combined saved-scene motion as Action, restricted to
the named shot's range. Camera and geometry advance together at integer frames;
the scrubber uses integer frame values, avoiding floating-point endpoint errors.
The fixed view is letterboxed to the saved pixel aspect. **Orbit inspection** is
a separate local mode; **Return to shot camera** or F restores the exact sampled
view. Neither mode, playback nor navigation changes a camera or creates approval.
Manual handoff includes the viewed frame; the existing server shot contract still
enforces the exact named camera and range. Native window acceptance is separate.

Native task setup enables Blender's preview range before assigning its bounds.
It widens the lower endpoint before moving the upper one, then verifies both
requested endpoints. This handles an unused preview range, a shot earlier than a
previously saved preview, and a one-frame shot without changing the scene's Action
range or FPS. The real `workbench_film_fixture.py` covers these three cases as
part of the existing film journey; headless success is not a native-window pass.

Light uses these same camera samples, but WebGL lighting/materials remain
explicit inspection approximations. Depth of field is not simulated. Actual
Blender-rendered stills remain the authority for shared-light review.

### Fractional frame rates

Installed exporters can use `fps * fps_base` or `fps` for GLB timestamps instead
of Blender's actual `fps / fps_base`. Preview conversion validates the full
integer-frame sample interval against those known rates before correcting only
the derivative's timestamp accessors. Unknown/partial timing refuses; native
animation values, source keys, FPS and scene properties are never retimed.
The receipt retains the correction evidence. The exporter also loses subframes
when restoring its frame; the wrapper restores both values even on failure.

`tools/shot_view_fixture.py` generates moving perspective/lens, orthographic,
single-frame and static-geometry/moving-camera cases at fractional FPS. It checks
projection against independent Blender camera-space calculations and preserves
source hashes. `tools/shot_view_check.mjs` drives actual scene/shot controls,
compares GLB geometry and projected coordinates against those native samples,
checks real pixels/playback/orbit return, revises a shot and verifies cache
invalidation plus preserved old bytes, and enters Light under its distinct
profile. Its generated stage decisions are scripted, not human acceptance.

### Windows checkpoint paths and inspection failures

New native layer/World/Action checkpoints retain the full checkpoint UUID but
omit the redundant scene UUID from the filename when the longer Windows path
would exceed 250 characters. Node and standalone Python can read some paths that
Blender's embedded Python cannot. If even the compact path exceeds that bound,
Save refuses before taking the writer lease or starting a native job. Existing
files, manifests and checkpoint identities are never renamed or truncated.

Failed/interrupted layer inspection appears in the viewer with the retained
operation and technical details. Native retry remains an explicit evidence-
preserving reset; it neither reruns a job nor approves a saved scene.
