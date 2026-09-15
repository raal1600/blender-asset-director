# Reviewed full-clip sequences (development)

Runtime `0.6.0-dev.4`, branch `feature/reviewed-sequence-integration-20260915`.
Identify builds by commit. This is not a release or an installed-skill update.
Read SEQUENCE_ACCEPTANCE.md for executed evidence and SEQUENCE_LOCAL_ACCEPTANCE.md
for the bounded workstation procedure. Automated development tests run in Actions.

## Design and tradeoffs

Complete target action A -> explicit derived bridge -> complete aligned action B.
Both original actions remain unchanged. A copy of B changes only its target-anchor
location/quaternion channels for a constant planar translation and explicit Z yaw.
A separate bridge action connects the endpoints. Full-channel NLA REPLACE tracks
reference A, the bridge and aligned B. No overlap conceals B's opening, no crop,
repeat, speed-up or added object controller. Duration is sum(clip durations) plus
sum(bridge durations) in seconds, not the count of inclusive frame labels.

The bridge uses quintic Hermite position interpolation with measured endpoint
velocities, quaternion-log interpolation and the SO(3) right Jacobian for angular
velocity tangents. Tangent-aware Bezier curves approximate this in Blender.
This is NOT a full inertialization implementation, IK, physics, pose matching or
proof of natural choreography. A mismatch can still overshoot or penetrate.
Near-180-degree local rotation differences require an intermediate-pose review.

A plain NLA crossfade cannot align travelling clips. An added animated object/root
layer could double-own travel when hips already move beneath a stationary root.
Instead the reviewed target pose-bone anchor owns trajectory; its ancestors stay
stationary and all keyed bones belong to its subtree. Existing root controls are
preserved, not interpreted as stray geometry. No source or target body is rebuilt.

## Identity and review

Use two to four distinct completed REVIEWED RETARGET JOB IDs from the originating
private library and a saved copy of the same target. Required: recorded QA roles,
immutable approved transfer proposals, matching complete keyed-bone coverage,
slots, fixed target world placement and compatible target units. Historical jobs
are verified DATA, not rerun with new code; output hashes and current license
validity still apply. Unreviewed legacy jobs need a new review, not forged receipts.

Descriptors bind result bytes, job, action, slot, owner, source asset, roles, rest
fingerprint, world transform, units, target anchor, full range, FPS and duration.
Identical generic Mixamo action labels are not identity. Only actions are appended
from verified results; no second character mesh is imported. Current sequence jobs
retain implementation-bound stale checks and license revocation/derivative rules.

Use this checkout's CLI with explicit private library and observed paths/IDs:

```text
python -m asset_director --library LIB job-prepare sequence-plan --input TARGET_COPY.blend --options REQUEST.json
python -m asset_director --library LIB job-run PLAN_JOB --blender BLENDER
python -m asset_director --library LIB sequence-prepare --review REVIEW.json
python -m asset_director --library LIB job-run EXECUTION_JOB --blender BLENDER
python -m asset_director --library LIB job-prepare sequence-check --input EXACT_RESULT.blend --options CHECK.json
python -m asset_director --library LIB job-run CHECK_JOB --blender BLENDER
```

Plan fields: target_object, clips=[{job_id},...], fps, meters_per_unit, joins,
budget, contact (explicit calibration or null). Exactly one join per boundary:

- duration_seconds: 0.05..2, additional bridge time, never source retiming.
- yaw_degrees: -180..180, reviewed world-Z yaw; never inferred from backslide travel.
- placement: match_endpoint or continue_velocity. The former matches planar anchor
  positions; the latter adds average measured boundary velocity times bridge time.
  Neither adjusts vertical placement.
- subdivisions: integer 1..8 for bridge sampling.

There is no universal duration, yaw, floor or bone-name preset. The read-only plan
returns sq_... identity, endpoint poses, spatial transform, pose RMS, angular and
velocity differences, work estimates and limitations. Inspect these before an
explicit host review: actual plan_job_id, plan_id, reviewer, offset-aware reviewed_at,
approved=true. This is host execution approval, not invented human artistic consent.
Changed inputs, units, actions, role maps, options, timing or code require replanning.

Contact calibration, when supplied, contains mesh, feet.left/right vertex-group
lists, ground_z, tolerance_m, near_ground_m and glide_speed_m_s. Use measured units
and soles. Null means NOT_MEASURED, not contact success. Sequence contact is
DIAGNOSE_ONLY; deliberate horizontal gliding is never automatically locked.

## Full length with bounded work

Default retarget stays at 360 output intervals. transfer-plan can explicitly
request max_output_intervals up to 7200, with absolute duration <=180 seconds.
Execution above 360 requires an approved transfer binding. The 500,000 scalar-key
per-action bound remains. A 1113-frame 30 FPS take needs 1112 intervals at 30 FPS;
at 24 FPS it ends at frame 890.6 (891 samples, 890 intervals including the partial
last one). The seconds remain 1112/30. Do not crop or reduce FPS to evade a budget.

All sequence budget fields are explicit, with these hard ceilings:

| Field | Maximum |
| --- | ---: |
| max_duration_seconds | 180 |
| max_pose_samples | 12000 |
| max_created_keys | 3500000 |
| max_contact_samples | 2049 |
| max_mesh_evaluations | 50000000 |

Choose tighter bounds from inspected work. The existing worker deadlines, log caps
and 10,000-frame global sampling span remain. Long retargets use one bounded worker,
not a new chunked bake system. Expensive contact sampling is sparse globally and
dense around joins, in batches of at most 257 with boundary accounting.

Ground correction is separate. Even for long clips it retains 2,881 checkpoint
and 50-million mesh-work caps. Do not blindly ground jumps/lifts across a long dance.
The new sequence path does not remove the old assemble path's conservative limits.

## Numerical representation and import failures

Receipts retain intended double-precision time and duration. Blender key/NLA frame
fields store binary32. Appended action ranges are checked against exact binary32
representation, not a blanket epsilon. Reports show intended/stored ranges, frame
errors and NLA operation-rounding bounds in seconds. One stored-step action change
is not accepted. Native source FPS is never adjusted to hide rounding.

Later complete REPLACE tracks own the pose when they begin. HOLD_FORWARD prevents
microscopic frame-storage gaps from exposing the rest pose and retains the final
fractional pose through the integer playback endpoint. That last held fraction is
reported as presentation coverage, not extra source performance or a seamless loop.

Reviewed source checks use a fixed 10-micrometre/component non-anchor translation
precision converted by source units and fixed uniform object scale. Centimetre and
metre sources face the same physical check; source keys are not flattened. Real
extra-bone translations remain unsupported. The legacy no-unit path is unchanged.

A connected source anchor with meaningful location keys is rejected explicitly:
Blender can ignore those channels after FBX tail reconstruction connects a child.
Do not disconnect a production bone or alter importer settings to force acceptance.
The synthetic regression retains both a collinear-root failure and a horizontal
floor-control travelling source, with independent pre/post-export travel checks.

## QA, preservation and remaining limits

The manifest/check verifies original action signatures, target rest/world/skin/
weights/material slots/display, object inventory, source identities, reviewed roles,
NLA settings, native timing and evaluated endpoint poses. It reports finite seam
linear/angular velocity differences, sparse full-clip poses and optional calibrated
integer/subframe sole measurements. These do not prove all continuous extrema.

Run sequence-check on exact result bytes BEFORE camera/light/display derivatives.
Then preserve the checked result and make separate presentation copies with the
originating library/grants. Restrictions follow all sources and the independent
character; renamed derived actions are not CC0. Never upload private source assets.

Original input is the rollback artifact. No automatic sequence-revert or live
multi-window control service is implemented. Preserve unsaved sessions/configuration.
An advancing timeline, playable project or CI PASS is not proof someone watched.

The near-term method uses Blender Actions/NLA plus a small CPU-only bridge. No new
addon, model, GPU, SDK or third-party code is installed or vendored. Primary design
references (concepts, not copied code):

- https://docs.blender.org/manual/en/latest/editors/nla/strips.html
- https://docs.blender.org/manual/en/latest/editors/nla/sidebar.html
- https://docs.blender.org/api/current/bpy.types.NlaStrip.html
- https://docs.blender.org/api/current/bpy.types.Scene.html
- https://graphics.cs.wisc.edu/Papers/2003/KG03/
- https://www.gdcvault.com/play/1025165/Inertialization

TECHNICAL, contact/continuity diagnostics, PERFORMANCE and HUMAN decisions remain
separate. A smooth formula does not establish a natural Moonwalk-to-Thriller join.
