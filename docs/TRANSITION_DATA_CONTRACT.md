# Native transition data contract

The existing Action layer creates versioned Blender checkpoints. `native-stitch-c1-v2`
is deterministic interpolation of observed native Actions, not model-generated
motion. The client must identify that provider/mode explicitly. Model inference
has a separate capability contract and may not be substituted silently.

## Identity and compatibility

The performer is an observed object from the exact saved checkpoint/audit hash.
Every take binds its owning object, Action and Action slot; bone names alone are
not a retargeting contract. The sampler uses a temporary copy of the same rig and
its captured native defaults. Original Actions, rest geometry, skin weights,
World placement and unrelated objects remain protected by preservation hashes.

The native stitch supports a bounded, matching set of native transform channels
on that rig. Constraints, drivers, procedural/sample-only F-curves, animated
parents, unsupported transforms and mismatched channel ownership are refused
with an actionable error. Those inputs need a separately reviewed evaluated bake
or retarget operation; this bridge does not pretend to evaluate arbitrary rigs.
Application retargeting remains a distinct reviewed operation before sequencing.

## Spaces and rotations

Blender uses right-handed coordinates and Z up. World-space distances are metres
after applying `scene.unit_settings.scale_length`. Pose transforms use the
observed native owner/bone local space; evaluated world transforms are used for
acceptance measurements. Existing placement/parent transforms remain intact.

Portable quaternion math and Blender use WXYZ components, unit quaternions,
shortest-path sign alignment and body-space angular velocities. Native Euler,
quaternion and axis-angle ownership is retained. A generated bridge may not
acquire previously unkeyed components to conceal an incompatible pose.
Provider XYZW/Y-up output requires explicit conversion before Blender use.

## Root ownership

Added user-authored paths use the existing `delta_location` owner and scene unit
conversion. Native root displacement must not also receive that path. Native
object-root clip placement uses explicit alignment; bone-root travelling motion
is unsupported until its ownership can be verified. Refusal is not a successful
travelling-root test. Heading changes retain the existing heading transform
contract and its uniform-scale/parent limitations.

## Time and endpoints

Effective scene FPS is `render.fps / render.fps_base`. Native Actions already
belong to that saved scene timebase; importing external 24/30/60 FPS material
must preserve seconds through an explicit source/scene FPS speed ratio before it is offered as a native take. A clip's source
range, speed, start, occupancy and repeat review are explicit. No filename or
matching keyframe numbers imply equal external FPS.

The source end and incoming start are stitch timestamps. A transition with N
extra occupied frames spans N+1 frame intervals between those endpoints. Both
source clips retain their requested timing; the extra bridge is not a hidden
overlap or slowed source. Fractional final intervals have explicit held tails.
An unreviewed loop cannot be used solely to improve phase matching.

Generated pose/path keys retain endpoint derivatives with explicit Bezier handles.
Testing compares the two curves at the **same** stitch time, not consecutive
moving frames. The reference acceptance fixture estimates one-sided derivatives
with the three-point formula at h=1/64 scene frame; angular differences use
shortest quaternion logarithms anchored in the boundary body's coordinate frame.

## Contacts and artifacts

Contacts require explicit provenance and nonempty planted intervals. Authored two-bone chains can receive constrained cleanup after rest, hierarchy,
endpoint, velocity and ground validation; see [contact setup](AUTHORED_CONTACTS.md).
The controlled locomotion fixture measures real planted intervals across both
boundaries. A travelling fixture without stance annotations must report contacts
unverified, never pass an empty contact mask. The native bridge does not promise
full-body IK or terrain adaptation.

Every accepted .blend contains actual native and generated Actions/NLA data plus
timeline metadata, source binding, settings and generated channel hashes.
Worker implementation hashes invalidate stale requests. Checkpoint hashes bind
preview and render inputs; changing clips, timing, root placement or provider
requires a new checkpoint and derivative identity. Preview GLB is a sampled
derivative of that checkpoint, with separately measured frame/subframe parity.
Fresh-process reopening is required independently of the in-process save check.
