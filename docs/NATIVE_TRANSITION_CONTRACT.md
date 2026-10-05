# Native transition data and acceptance contract

The native provider is deterministic interpolation (`native-stitch-c1-v2`), not
AI-generated choreography. The saved connection records identify the provider,
implementation, generation mode and root owner. Motion generation providers are
separate integrations and cannot silently stand in for this operation.

## Supported motion

Transitions join Actions on the same observed Blender performer and action slot.
The rig identity includes hierarchy, bone rest matrices, inheritance settings,
source channels, unkeyed defaults, object placement, parent transform and scene
units. Equal bone names in two different rigs do not establish compatibility.
Direct cross-rig transitions are rejected. The existing reviewed retarget pipeline
can first bake Actions to the intended rig; those exact bound Actions can then
be transitioned. Retargeting is not inferred during native transition planning. Constraints, drivers, procedural keys,
singular/reflected scales, mismatched native channel ownership and ambiguous
near-180-degree pose changes require an authored intermediate clip or Blender
preparation. Source Actions, rest geometry, weights and other performers stay
unchanged. Each accepted connection creates a new Action and NLA strip.

The disposable sampler restores verified native defaults and reads the evaluated
Blender dependency graph. Its input is native Action context, not an isolated raw
keyframe value. Because constraints and drivers are excluded, evaluated local
transform components are representable in the preserved native rotation mode.
Pose rotations use normalized **WXYZ** quaternions internally, shortest relative
logarithms, and body-space angular velocity. Quaternion signs are made consistent
when baking. Euler and axis-angle component representations retain their native
mode; an identity axis-angle boundary uses its angular tangent to resolve the
otherwise undefined axis. Zero angle does not erase incoming angular velocity.

All pose coordinates are local to the owner in Blender's right-handed, Z-up
transform system. Ground tests use the authored fixture world XY plane. Units are
Blender scene units for native channels and metres for explicit added travel;
scene `scale_length` converts between them. Parent transforms are applied once.

## Timing and stitching

The native source range is a closed interval `[source_start, source_end]`. A clip
occupies `frames` displayed samples but contains `frames - 1` time intervals.
Source time advances by `speed` source frames per scene frame. Actions do not
carry independent FPS metadata: imported source FPS must be represented by the
explicit speed ratio `source_fps / (scene_fps / fps_base)`; it is never guessed.
The scene rational frame rate is `fps / fps_base`.

Connections add the explicitly chosen gap. Their exact start is the outgoing
native end (possibly fractional), and their end is the incoming clip start. A
request for 2 added displayed frames normally spans 3 frame intervals from the
outgoing boundary to the incoming boundary. There is no duplicated source
boundary frame. Rounded occupancy after a fractional native endpoint is a hold.
Phase matching requires a reviewed closed cycle; trimmed clips cannot inherit
full-cycle phase matching or automatic full-cycle travel calibration.

Native source endpoint derivatives are sampled over at most 1/64 scene frame.
Location and scale use quintic Hermite interpolation. Rotation uses a quaternion
logarithm and the SO(3) right Jacobian. The generated poses are sampled at quarter
scene frames. Crucially, generated F-curves have explicit Bezier endpoint
handles derived from the native tangents. Linear interpolation of these samples
would turn the first baked secant into the boundary velocity and break C1
continuity, particularly for short connections. Interior handles use centered
slopes; no automatic Blender overshoot is enabled. Original curves are untouched.

## Root ownership and contacts

Supported native object-location root motion is preserved in the source Actions.
A separate delta-location channel aligns each incoming clip's origin with the
outgoing placed endpoint, carrying mean endpoint velocity through the connection.
The alignment correction has zero endpoint velocity, so it does not replace or
double the native root velocity. Different starting offsets and cumulative
multi-clip placement are supported. An additional explicit travel path cannot
own the same native root motion. Bone-driven planar root travel and inferred root
retargeting remain unsupported and are rejected with an actionable message.
Heading changes for in-place clips use the existing explicit turn mode; it
brakes the added path, turns in place, then accelerates. Native object-root
heading changes remain authored source motion rather than inferred facing.

Contact cleanup is optional and requires explicit authored metadata, described in
[Authored contact setup](AUTHORED_CONTACTS.md). It validates two-bone chains and
rest identity, matching planted endpoint targets, ground height, near-zero foot
velocity and stable foot orientation before solving on the disposable rig.
It never infers anatomical roles from names. Corrected rotations are baked into
the accepted native connection Action; source clips stay unchanged. The saved
connection reports `SAMPLED_AUTHORED_CLEANUP` and quantitative sampled diagnostics.

Unannotated results retain `contact_acceptance=NOT_EVALUATED`. The acceptance
suite never turns an empty contact mask into a pass. The original travelling
pose-only figures without authored planted intervals are `NOT_APPLICABLE` for
that metric. Separate locomotion fixtures use genuine planted source intervals,
measure all stance samples and verify cleanup through both boundaries. These are
controlled reference steps, not certification of arbitrary natural locomotion.

## Numerical regression and evidence

Run in an isolated output directory:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python-exit-code 1 --python tools/stitch_continuity_fixture.py -- OUTPUT
```

The 15-case generated CC0 fixture has a 2 m reference skeleton, skinned visible segments,
an authored ground plane, a camera and lighting. It checks 24/30/60 FPS, short
and long gaps, explicit travelling turns, actual native object-root motion with
a 10 m source offset, mixed 24/60 FPS source timing at 30 FPS, a three-clip native
root sequence, quaternion sign changes, an axis-angle identity endpoint, Euler pitch beyond
90 degrees and fractional NLA starts.
Each case saves `result.blend`, `acceptance-report.json`, source channel hashes,
exact evaluated samples and strict thresholds in `RESULTS.json`.

Boundary limits are fixed before evaluating candidates: position 0.002 m,
orientation 1 degree, root velocity 0.1 m/s and angular velocity 5 degrees/s.
Derivatives use second-order one-sided differences at the **same** stitch time
with h=1/64 scene frame, and quaternion logarithms anchored to the boundary body
orientation. Boundary positions/orientations are extrapolated to the same time;
consecutive moving frames are not required to be identical. Grounded foot
intervals have 65 actual samples per bridge; drift limit is 0.02 m and penetration
limit is 0.01 m. Native Action channel hashes must remain identical.

Before the C1 fix the controlled 60 FPS short bridge had about 49.75 degrees/s
angular-velocity mismatch, and the short travelling turn had about 0.2315 m/s
root-velocity mismatch. The corrected implementation measured below 0.62
degrees/s and 0.0022 m/s respectively on Blender 5.2.1. This is controlled
numerical evidence, not natural gait, retargeting or arbitrary contact approval.
Fresh-process persistence, preview parity and render/playback are separate
acceptance stages run by `tools/run_transition_acceptance.py`.


The separate `tools/contact_transition_fixture.py -- OUTPUT` fixture covers
idle-to-walk, walk-to-idle, walk-to-run and a body turn while one authored foot
remains planted. Each has 129 measured stance samples spanning both boundaries,
including foot head and toe rather than an empty mask. Invalid rest identity,
one-sided metadata, empty masks, false planting and disconnected chains are
rejected without scene mutation. The final contact suite also rejects changed
ancestor rest transforms, constraints, drivers and NLA solo state (nine failure
cases total), alongside its four positive cases. The body-turn case without cleanup reproduces
0.04627 m horizontal drift and 0.02560 m penetration (both fail). Authored cleanup
reduces these to about 0.000071 m drift and 0.00379 m evaluated skin penetration on Blender
5.2.1. `--unannotated` deliberately generates the negative reference and returns
failure when its fixed quality thresholds are exceeded.


## Fractional ranges and retargeted Actions

`tools/retarget_transition_fixture.py -- OUTPUT LIBRARY` runs the application's
actual pinned Mwni matrix-transfer backend, with an explicit mapping to renamed
bones on a target scaled by 1.2. It converts two generated 24 FPS source Actions
to 30 FPS target Actions, then transitions those same-target Actions. Install the
already-pinned dependency in an isolated library with the normal
`asset-director --library LIBRARY backend-install` command first. This downloads
verified upstream source at `424f08bd7e675619adf539209a1e8816c242c386` under its
GPL-3.0-or-later license; no upstream code or generated assets are vendored here.

That real integration exposed an independent fractional NLA defect. Blender's
strip constructor accepts an integer start. Setting `frame_start` to 29.75 after
construction moved only the left edge, so the planned 29.75-to-37 bridge actually
ended at 36.25. Endpoint-only verification passed because the incoming native
strip supplied the expected pose at exactly 37; the preceding 0.75-frame hole
fell back to the outgoing held pose. The shared strip helper now sets its planned
right edge explicitly, and bridge baking verifies full interval coverage.
The retarget regression measures all joints on both sides of the fractional
boundary and rejects a source-rig Action offered directly to the target.
A separate native speed-1.1 fixture guards the same fractional-start behavior
without requiring an external backend. All accepted result rows record the
saved `.blend` SHA-256 before independent reopen/render/export checks.
