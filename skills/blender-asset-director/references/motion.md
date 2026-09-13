# Motion selection, transfer and honest limits

**Search -> inspect source -> compare rigs -> preview -> retarget flat -> validate -> terrain -> human review.**

The local catalog stores each actual action/slot/owner binding, source file hash, FPS, frame range, measured motion, inferred filename tags and provenance. A filename tag is not a verified semantic description. The lexical ranking score is not an artistic-quality score. Re-evaluate an apparently relevant walk for pace, arm posture, held weapon, loop quality and genre.

The Mwni backend is pinned by upstream commit and per-file Git object hash. It is acquired separately, remains GPL-3.0-or-later, and is not vendored into the MIT core. The adapter registers only its data schema in a disposable process and calls matrix-transfer functions directly. It does not install the add-on globally or enable scripted drivers. New uniquely named actions preserve old actions.

### Explicit evaluated-pose transfer

For unlike rest poses/parent frames, local-delta transfer can distort motion even
when every bone name is mapped. `retarget` may explicitly select `pose_space`:
`{"rotation":[1,0,0,0,1,0,0,0,1],"translation_bone":"observed target pelvis","translation_scale":1.0,"target_origin":[0,0,1]}`.
These numbers are schema examples, not a ready-made alignment. Supply a reviewed
one-to-one `mapping` and target pose-basis `alignment` as well. `rotation` is a
proper row-major 3x3 world rotation mapping source anatomical facing to target
facing. `target_origin` is the selected target anchor's world position at the
first sampled source frame. Only that anchor receives source world displacement,
scaled by the explicit positive ratio; target segment lengths are preserved.

This mode transfers evaluated world-rotation deltas and reconstructs target local
bases in parent order. It is opt-in, never an automatic backend switch. Source and
target object transforms must stay fixed; all chains must be unconstrained;
animated non-anchor local translations and non-unit pose scales are rejected.
The pinned backend remains verified by the job runner, but this mode does not
invoke its local-delta transfer math. Other calls retain the existing behavior.

Compare source and target in the **same world coordinate system** and at matched
times. An imported glTF's frame coordinates depend on import FPS; confirm its
actual action range/timebase rather than assuming indexed coordinates remain
unchanged in a differently timed scene. Match a short cycle, then measure limb
directions, preserved lengths and anchor displacement after saving/reopening.
Different proportions can still cause contact errors: this mode is not a foot-IK
solver. Travel on either root or hips disqualifies automatic cycle repetition.

Automatic mapping uses limited anatomical aliases. Unknown/control rigs, missing skinning, nonuniform/negative scales, active constraints, substantial rest-pose differences, ambiguous slots or object-level source travel require explicit review. A matching bone name alone is not proof of compatibility. Rest direction checks are conservative, not a complete skeleton-equivalence proof.

NLA accepts actions baked for the exact target fingerprint. A root that returns to its origin can still contain travel: use range, not only net displacement. Do not repeat a traveling root without handling continuity. In-place cycles can repeat and receive **one** external controller with a calibrated speed; do not simultaneously add that controller to an already traveling action.

Numerical QA measures sampled root/hip/ankle paths, relative limb movement, heuristic stance drift, endpoint seams and discontinuities. Foot motion relative to the root helps catch a static character translated through space. It does not establish biologically natural gait. Static feet can be legitimate during an idle. In-place source clips often show apparent world-space foot sliding until locomotion travel is applied.

Terrain following in this version adjusts only controller root height on a gentle, sampled route. There is no full foot-IK/contact solver, ragdoll, cloth simulation, procedural combat synthesis or automatic equipment-grip repair. Report remaining defects rather than obscuring them with camera motion or fog. A good source can still fail on a different character's proportions.

Blender actions from 4.4 onward can use slots/channel bags. Do not assume legacy `action.fcurves` or take the first slot from a multi-object action. Source ownership and duration must come from actual channels/bindings.

Primary references:
- https://github.com/Mwni/blender-animation-retargeting/tree/424f08bd7e675619adf539209a1e8816c242c386
- https://developer.blender.org/docs/release_notes/5.0/python_api/
- https://docs.blender.org/manual/en/latest/animation/actions.html
