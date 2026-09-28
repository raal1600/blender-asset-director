# Bounded camera and shared-light transactions

Development contract: `scene-layer-v1`. This slice adds native operations and
authenticated launcher transactions. Selected-shot viewing is described below;
the contextual camera/light authoring controls and native desktop acceptance
remain separate unfinished work.
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
They do not substitute for browser camera/light authoring,
rendered before/after comparison, Windows manual handoff, licensed
inputs, exact-commit CI or local deployment acceptance. Those remain separate
required gates in the layered-workflow enhancement.

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
