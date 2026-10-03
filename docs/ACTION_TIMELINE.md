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
Turning off travel restores the clip's local pre-travel duration; after reloading
a saved path it defaults to one native cycle at the selected speed. Explicit
non-travel trims remain available under Timing and path.

The red endpoint can be dragged in the viewer or moved with arrow keys (0.1 m,
Shift 1 m). Automatic pace constrains the endpoint to the inspected gait direction;
Up/Right lengthen and Down/Left shorten the path. Distance has a numeric control.
Manual calibration retains editable world direction. Its name-based hint does
not establish facing or animation semantics. The arrow does not turn the character.
Saved scene playback remains labelled separately from the unsaved path overlay.

In-place animation has no recorded root travel speed. When two independent low
support landmarks can be identified geometrically, the inspector samples 65 poses
of the actual bound action/slot on a disposable unskinned rig copy. The original
static parent space, scene units and world orientation are respected; original
objects, frame, actions, rest/skin and bindings are restored/preserved. Names never
classify gait or infer a retarget mapping. At most 48 takes / 3,120 sampled poses
are analyzed per inspection, with 1–120 native frame intervals per take;
ambiguous/large rigs or undersampled long takes get an explicit fallback.

`stance-pace-v1` estimates displacement per cycle from the opposite of horizontal
support velocity during low, vertically stable stance. It requires bilateral
agreement, alternating support, sufficient coverage, bounded velocity residual,
lift and endpoint closure. A squat, jump, static pose, nonclosing take or conflicting
native travel is not silently treated as a walk. The result remains an estimate,
not proof of ground contact, smooth transitions or an actual sole-based IK solve.

Selecting a supported gait automatically supplies pace and heading at normal
speed. The primary input is distance: longer paths add native cycles and duration,
not longer strides. Unsupported takes stay as valid native clips instead of
opening an invalid travel form. Explicit manual calibration remains available in
Timing and path, including for existing saved clips; values are never silently
replaced. Automatic profiles carry an exact inspection identity, and Blender
revalidates profile, pace and direction before mutation. Overrides must explicitly
leave automatic mode. Uncertain native samples do not manufacture a speed.

Duration
is ceil(distance / metres-per-cycle * native-frame-span / speed) + one inclusive
endpoint frame. Translation stops at the fractional native endpoint; the rounded
occupied tail is a hold. Repetition requires an explicit repeatable-cycle review,
shown beside the distance/duration rather than hidden in advanced controls. The
Save bar explains the exact blocker. This review is not final Action,
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

Portable tests: `tests/test_action_timeline.py`, `tests/test_gait_profile.py` and
launcher timeline/asset tests. `tools/gait_profile_fixture.py` checks an actual
generated alternating-support rig, preservation, deterministic inspection,
forged-calibration and unreviewed-repeat refusal, exact endpoint, saved identity
and observed support-drift reduction. Its optional private-copy mode only executes
one cycle; it never creates human loop approval for a licensed asset.
`tools/gait_browser_check.mjs` exercises distance-first UI, constrained pointer and
keyboard edits, inline validation, explicit manual overrides, real Save/reload,
occupied frames and actual saved GLB playback in an isolated authenticated studio.
Real generated native fixture: `tools/action_timeline_fixture.py -- <new-output>`
under background Blender with auto-execution disabled. It checks two rigs, scaled
rotated parent/unit conversion, exact travel, deformation, occupancy, revision,
clearing, preservation and root-motion refusal. The browser journey in
`tools/action_timeline_browser_check.mjs` uses an isolated authenticated studio,
real Blender and saved GLB; no user project, credentials or creative approval.

Browser acceptance, licensed-character temporal/contact review, exact-commit CI,
packaging, staging and reversible live deployment are distinct required gates.
Passing portable/native fixtures alone does not authorize live replacement.
