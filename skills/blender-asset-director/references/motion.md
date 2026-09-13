# Motion selection, transfer and honest limits

Search -> inspect source -> compare rigs -> retarget flat -> validate timing and
contacts -> temporal review -> optional terrain adaptation -> human review.

The catalog stores each actual action/slot/owner binding, file hash, imported FPS,
frame range, measured motion, inferred tags and provenance. A filename is not a
verified action description, and lexical rank is not a realism score. Review pace,
support exchange, arm posture, props and transitions before selecting a source.

The Mwni backend is pinned by upstream commit and per-file Git object hash. It is
acquired separately, remains GPL-3.0-or-later and is not vendored into the MIT
core. The adapter registers its data schema only in a disposable process and
uses matrix-transfer functions without globally installed handlers or drivers.
Legacy local transfer remains default.

## Opt-in evaluated world-pose transfer

Use retarget `pose_space` only with an explicit one-to-one mapping, reviewed target
pose-basis alignment, proper source-to-target row-major 3x3 rotation, one mapped
translation_bone, positive translation_scale and target_origin. Origin is the
target anchor's world position at the first sampled source frame. Only the anchor
receives converted source displacement; target segment lengths are preserved.

Evaluated world rotations are converted into local target bases in parent order.
Unmapped reference bases are retained. Armature world transforms must stay fixed,
chains must be unconstrained, source non-anchor local translations must not vary,
and source/target reference pose scales must be unit. The pinned backend is still
verified, but its local-delta math is not invoked for this explicit mode.
Unknown/control rigs and substantial rest-pose differences remain review gates,
not reasons to guess a mapping. Matching names alone do not prove compatibility.

Compare in the same world coordinate system at matched times. Imported frame
coordinates, native capture rate (possibly unknown), destination FPS and artistic
playback_speed are distinct. Retargeted glTF imports use the catalog timebase;
assembly rejects a conflicting source_fps override instead of treating it as speed.
See [grounded motion and timing](grounded-motion.md) for supported contracts.

Travel in either root or hips prevents automatic repetition and conflicts with a
second path controller. An action returning to its starting position can still
travel. In-place clips may repeat only after appropriate loop/contact review.
The fingerprint confirms a target rig, not the naturalness of the transferred motion.

Numerical QA measures sampled root/hip/ankle paths and heuristic stance drift,
seams and discontinuities. It does not prove biologically natural gait, support
pressure or correct toe/heel phases. Grounding is not horizontal foot IK. A good
source can still fail on a different character's proportions. Do not hide defects
with cropping, camera movement or fog.

Retarget/NLA reports leave performance_acceptance NOT_EVALUATED and require
separate temporal visual review. A source tagged Moonwalk may still be a backward
walk. Contact sheets supplement continuous-motion evidence; they do not replace
it. Keep technical, source-performance, temporal and human acceptance distinct.

Blender layered actions require slot/channel-bag handling; do not assume legacy
action.fcurves or choose the first slot when ownership is ambiguous.

Primary references:
- https://github.com/Mwni/blender-animation-retargeting/tree/424f08bd7e675619adf539209a1e8816c242c386
- https://developer.blender.org/docs/release_notes/5.0/python_api/
- https://docs.blender.org/manual/en/latest/animation/actions.html
