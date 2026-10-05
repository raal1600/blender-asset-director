# Authored planted-foot cleanup

Native transitions can preserve explicitly authored planted feet on a verified
connected two-bone leg plus foot. This is a deterministic local solve. It uses
no model, no name-based anatomical inference and no retargeting. Unannotated
clips remain available as pose transitions, with contact quality unverified.

## Preparing a supported rig

Prepare metadata in Blender on the intended armature. Each chain identifies its
upper bone, connected lower bone and connected end-effector bone. These must be
three distinct existing bones, use ordinary inherited rotation/scale and have
unit pose scale. Chains cannot share bones. A rig supports at most four chains.
The world transform must have a positive uniform scale. Constraints, drivers,
nonstandard inheritance and arbitrary rig controls must be baked/prepared first.

An explicit knee-pole direction is expressed in rig-local coordinates. Choose it
from the authored bend plane; the application never guesses a left/right knee.
Every chain bone must have all native rotation components keyed in both Actions.
A rest hash binds the mapping to the actual names, hierarchy, rest matrices, ancestor rest transforms and
bone lengths. Changing rest geometry invalidates the annotation.

The armature string custom property `bad_contact_rig_v1` contains JSON:

```json
{
  "version": "native-contact-rig-v1",
  "chains": [
    {"id": "left-support", "upper": "ReviewedUpper", "lower": "ReviewedLower",
     "end": "ReviewedFoot", "pole_local": [0, -1, 0]}
  ],
  "rest_sha256": "computed from the observed rest hierarchy",
  "ground_z_m": 0.0,
  "height_m": 2.0
}
```

Use `asset_director.motion_contacts.rest_identity(armature, chains)` to compute
`rest_sha256` in the Blender Python environment. The generated fixtures show a
complete executable example. Ground elevation and character reference height
are in metres, independent of Blender scene-unit scale.

## Authoring source contacts

Each selected native Action can contain the string property
`bad_contact_intervals_v1`:

```json
{
  "version": "native-contact-intervals-v1",
  "rig_sha256": "asset_director.core.digest(the decoded rig JSON)",
  "intervals": [
    {"chain": "left-support", "start": 13.0, "end": 25.0}
  ]
}
```

Intervals are closed source-frame intervals, ordered per chain, non-overlapping
and nonempty. They are an author's statement that the end-effector is planted,
not an automated classifier output. Confirm them against the evaluated source
motion and declared ground. FPS conversion is the normal explicit clip speed.
Do not label airborne, sliding or pivoting feet as stationary planted contacts.

Select the two Actions in the normal client and configure the transition. At
least one chain must be planted at both selected endpoints. Their placed world
contact positions must agree within 0.001 times the declared height. Orientation
must agree within 1 degree; source foot velocity must be below 0.05 times height
per second, and source foot angular velocity below 5 degrees per second. An
explicit whole-body heading turn requires an authored turning step. A supported
native body-pose turn can be solved while preserving the planted foot.

The fixture covers four positive cases and nine refusal cases, including stale
ancestor rest transforms, constraints, drivers and NLA solo state. Bad metadata
or incompatible endpoints produce a structured, actionable error
before modifying the performer. Use a compatible stance, change clip phase/trim,
or author an intermediate step. The application does not silently drop a failed
contact constraint or label an unannotated bridge as foot-locked.

## What gets saved

For accepted contacts, a disposable evaluated rig solves the measured two-bone
geometry at each quarter-frame bridge sample. It retains planted foot world
orientation, preserves the source endpoint rotations, and prevents annotated
foot head/toe penetration by constrained cleanup. Singular poles, unreachable
foot targets and nonuniform or animated chain scales are rejected. The source
Actions and native tracks remain intact. The resulting local rotations are baked
to a new connection Action in the rig's existing rotation modes.

The saved connection contains `contact_cleanup` with its method, exact rig hash,
source provenance, constrained chains, interval, nonzero sample count, endpoint
mismatch, sampled drift and sampled penetration. Its status is
`SAMPLED_AUTHORED_CLEANUP`, not human or universal natural-motion approval.
Changing the source contact metadata changes the audit identity and invalidates
managed native defaults, preventing stale result reuse.

This solver is bounded to 4096 sampled pose/chain operations per request. Split
long sequences when the client reports its resource limit. Full-body balance,
hand contacts, arbitrary retargeting, terrain following, moving platforms,
sliding/pivot contacts and general humanoid motion synthesis are outside scope.

## Reproducing acceptance

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python-exit-code 1 --python tools/contact_transition_fixture.py -- OUTPUT
```

The legal generated fixture set includes idle-to-walk, walk-to-idle,
walk-to-run and a body turn with a planted support foot. They are analytic
reference steps for numerical validation, not claims of natural running style.
Each saved case has actual source and result `.blend` files, provenance,
preservation hashes, 129 evaluated stance samples, foot head/toe measurements,
and both same-timestamp boundary derivatives. A separate fresh Blender process
in the acceptance runner reopens, renders and exports the accepted result.

For the failing contact comparison, add `--unannotated` and use a different output
directory. This removes the contact metadata while preserving the same source
motion. The body-turn case then fails the fixed drift/penetration thresholds;
that nonzero process exit is the expected negative reference, not a passing gate.
