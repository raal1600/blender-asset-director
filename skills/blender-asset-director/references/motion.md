# Motion selection, transfer and honest limits

**Search -> inspect source -> compare rigs -> preview -> retarget flat -> validate -> terrain -> human review.**

The local catalog stores each actual action/slot/owner binding, source file hash, FPS, frame range, measured motion, inferred filename tags and provenance. A filename tag is not a verified semantic description. The lexical ranking score is not an artistic-quality score. Re-evaluate an apparently relevant walk for pace, arm posture, held weapon, loop quality and genre.

The Mwni backend is pinned by upstream commit and per-file Git object hash. It is acquired separately, remains GPL-3.0-or-later, and is not vendored into the MIT core. The adapter registers only its data schema in a disposable process and calls matrix-transfer functions directly. It does not install the add-on globally or enable scripted drivers. New uniquely named actions preserve old actions.

Automatic mapping uses limited anatomical aliases. Unknown/control rigs, missing skinning, nonuniform/negative scales, active constraints, substantial rest-pose differences, ambiguous slots or object-level source travel require explicit review. A matching bone name alone is not proof of compatibility. Rest direction checks are conservative, not a complete skeleton-equivalence proof.

NLA accepts actions baked for the exact target fingerprint. A root that returns to its origin can still contain travel: use range, not only net displacement. Do not repeat a traveling root without handling continuity. In-place cycles can repeat and receive **one** external controller with a calibrated speed; do not simultaneously add that controller to an already traveling action.

Numerical QA measures sampled root/hip/ankle paths, relative limb movement, heuristic stance drift, endpoint seams and discontinuities. Foot motion relative to the root helps catch a static character translated through space. It does not establish biologically natural gait. Static feet can be legitimate during an idle. In-place source clips often show apparent world-space foot sliding until locomotion travel is applied.

Terrain following in this version adjusts only controller root height on a gentle, sampled route. There is no full foot-IK/contact solver, ragdoll, cloth simulation, procedural combat synthesis or automatic equipment-grip repair. Report remaining defects rather than obscuring them with camera motion or fog. A good source can still fail on a different character's proportions.

Blender actions from 4.4 onward can use slots/channel bags. Do not assume legacy `action.fcurves` or take the first slot from a multi-object action. Source ownership and duration must come from actual channels/bindings.

Primary references:
- https://github.com/Mwni/blender-animation-retargeting/tree/424f08bd7e675619adf539209a1e8816c242c386
- https://developer.blender.org/docs/release_notes/5.0/python_api/
- https://docs.blender.org/manual/en/latest/animation/actions.html
