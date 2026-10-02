# Action motion timeline — development

This adds an opt-in **Build a motion timeline** route inside the existing Action
layer. It is source development, not an installed or production-approved release.
World, Action, Shots, Light, Render and Final film remain the existing workflow.

Each observed performer owns up to 64 non-overlapping clips. Clip identities,
native action/slot/hash, inclusive start and occupied frames, speed, explicit loop
review and optional planar travel are saved in the separate checkpoint. A clip
occupying 1–50 leaves 51 as the next append position. Other performers have
independent tracks. Earlier clips remain editable; moving following clips is an
explicit operation, not an implicit overwrite. Emptying a track holds its first
pose rather than reviving a previously muted animation. Undo/Discard are local.

The red endpoint can be dragged in the viewer or moved with arrow keys (0.1 m,
Shift 1 m). Distance and world direction also have numeric controls. Name-based
direction is only an editable world-axis suggestion: it does not establish the
character's facing or animation semantics. The arrow does not turn the character.
Saved scene playback remains labelled separately from the unsaved path overlay.

In-place animation has no measured travel speed. The user supplies metres per
native cycle; further clips using that take can reuse the authored value. Duration
is ceil(distance / metres-per-cycle * native-frame-span / speed) + one inclusive
endpoint frame. The final fractional interval is an endpoint hold. Repetition
requires an explicit repeatable-cycle review. This review is not final Action,
foot-contact, transition, source-license or film approval. Distance cannot by
itself determine a physically correct pace.

The limited travel adapter animates only the performer's delta_location, converted
from world metres through its static parent transform. World controls remain
unanimated. Original actions/rest/skin, previous tracks and unselected performance
are preserved and verified after reopening. It requires native rigged characters,
skin under that rig, static unconstrained parents and no existing delta channels.
Conservative native-channel bounds refuse planar travel (including out-and-back),
procedural curves, conflicting object rotation/scale and unsupported ownership.
Such sources need reviewed Blender editing, not automatic root-motion cancellation.
Mixed travelling-native clips plus a new path are refused. This is not retargeting,
foot IK, terrain following, collision avoidance, curved paths or automatic blends.
Changing the World parent transform or scene units after authoring travel makes
the saved path context require Blender review; it is never silently reinterpreted.

Wire `action-layer-v1` remains backward-compatible for legacy clip/hold operations;
new `mode: timeline` needs observed `action-timeline-v1` capability and inspection.
Legacy edits cannot silently replace a managed timeline. The existing authenticated
Save endpoint, source-use checks, revision/checkpoint/hash binding, job lease,
idempotency, separate outputs and downstream invalidation apply unchanged.

## Verification

Portable tests: `tests/test_action_timeline.py` and launcher timeline/asset tests.
Real generated native fixture: `tools/action_timeline_fixture.py -- <new-output>`
under background Blender with auto-execution disabled. It checks two rigs, scaled
rotated parent/unit conversion, exact travel, deformation, occupancy, revision,
clearing, preservation and root-motion refusal. The browser journey in
`tools/action_timeline_browser_check.mjs` uses an isolated authenticated studio,
real Blender and saved GLB; no user project, credentials or creative approval.

Browser acceptance, licensed-character temporal/contact review, exact-commit CI,
packaging, staging and reversible live deployment are distinct required gates.
Passing portable/native fixtures alone does not authorize live replacement.
