# Motion foundation — 0.6.0-dev.1

This branch implements the first vertical slice of the research's prioritized
foundation: immutable canonical records, rights-aware discovery, body profiles,
a basic clay proxy, and a canonical-to-v0.5 retarget bridge. It is not a complete
implementation of the research roadmap and is not a published release.

The complete installed operation/CLI contracts are in
[the motion reference](../skills/blender-asset-director/references/motion-foundation.md).
The [local acceptance handoff](LOCAL_MOTION_ACCEPTANCE.md) describes how to test
without replacing the user's installed skill or touching production scenes.

## Modules

| Module | Responsibility |
|---|---|
| motion_assets.py | Immutable manifests and bounded numeric arrays, hashes, rights/use gates, collection and reuse |
| motion_scout.py | Deterministic metadata retrieval, explicit source states and pending external discovery tasks |
| motion_body.py | Stable rest anatomy and cached, review-required rig-pair mapping/scale proposals |
| motion_contract.py | Portable operation schemas; reject malformed or unsupported input before Blender |
| motion_blender.py | Evaluated-action export, reconstructed source, source-shaped proxy, v0.5 retarget bridge |
| motion_review.py | Timestamp-aware kinematics, calibrated contact candidates and temporal-review receipts |
| motion_cli.py | CLI integration without importing bpy into ordinary Python |

The existing jobs/worker retain their normal hash checks, rights gates, isolated
background execution and new output files. The legacy retarget path stays default.
The new pose_space.translation_scale_xyz is optional, requires scalar scale=1 and
world-Z-preserving alignment. Proxy generation never edits an existing user mesh.

## Implemented, scoped honestly

- Local canonical and existing-asset searches; optional live queries through the
  **existing** Sketchfab/Quaternius routes. No new source-download API is claimed.
- Immutable canonical world positions/quaternions with explicit seconds, units,
  hierarchy, rest transforms, roles, source hashes, capture-method evidence,
  licensing evidence and optional contact annotations/parent record IDs.
- Blender source action export and source-only reconstruction; no arbitrary
  provider pickle/deserialization or hidden inference dependency.
- Stable head-to-head leg/arm profiles and root-scale proposals keyed by source
  and target fingerprints. Rest anatomy, not a one-frame pose, defines proportions.
- A newly generated segmented capsule mannequin with rigid per-bone skin weights.
  Selected rest lengths may be changed once within bounds. It is a diagnostic
  body, not a continuous sculpted human skin or automatic production mesh warp.
- An explicit bridge from canonical meters into declared target scene units and
  the existing evaluated-world-pose solver. Morphology and unit conversion differ.
- Numerical root/angular diagnostics and hysteretic contact **candidates**. No
  kinematic statistic certifies that gliding is deliberate rather than an error.
- Evidence-backed performance-review receipts. Still images/metrics cannot earn a
  temporal ACCEPT. These are caller attestations, not proof the reviewer watched.

## Deferred

Native CMU ASF/AMC conversion, AIST/AMASS body-model formats, learned motion
embeddings, per-limb IK, reach optimization, automatic anatomy/alignment solving,
seamless human proxy skin, temporal video rendering, GVHMR/GPU inference, paid APIs
and live capture are **not implemented**. Provider stubs return pending host-search
or acquisition/conversion blockers, not invented completed requests. The Director
can use its actual web tools to locate exact candidates and supported authorized
interchange files. It must not describe those host tasks as automated adapters.

Current CMU/AIST/AMASS/other discovery entries do not fetch whole datasets, crawl
sites, bypass login, or reinterpret software licenses as data/media permissions.
Research providers are blocked for commercial execution in this milestone. A
separate reviewed commercial-license override is not yet implemented.

## Record layout / binary contract

`motions/m_<64hex>/record.json` + `motion.bin`. ID hashes the manifest without id,
including numeric-payload hash. Store is staged/atomic and repeat collection reuses
verified files. Modified payload, manifest, or retained rights evidence fails.
Existing v0.5 SQLite catalog schema is not changed.

`asset-director.motion/1` coordinates: right-handed meters, +Z up. A complete
source rotation and meters-per-source-unit are recorded; forward facing is not
inferred. Joints: rest head/tail, world-rest quaternion, parent, semantic roles and
source fingerprint. Samples: seconds from zero, world head position, world wxyz
rotation. Native capture FPS may be null; scene frame-coordinate FPS is separate.

Binary layout (little endian): header `<8sII` containing `BADMOT1\0`, sample count,
joint count; each sample then stores `<d` timestamp and `<7f` per joint (xyz,wxyz).
Limits: 10,000 samples, 256 joints, 600,000 joint-samples, 600 seconds. All numeric
values finite/bounded, quaternions normalized, timestamps strictly increasing, rest
orientation consistent with head/tail, hierarchy parent-first with one root. No
pickle or object loading, and numeric arrays are not dumped into CLI/context.

Rights include source terms URL, retained local evidence hash/size, attribution,
and separate commercial/adaptation/raw-redistribution allowed/denied/unknown
assertions. Project use must be commercial/noncommercial rather than unknown.
Assertions are host-reviewed evidence, not automatic legal clearance. Raw media,
performer likeness, music, model weights, source code and motion data may each have
different rights. Raw redistribution is recorded, not automatically authorized.

The first exporter hashes a selected saved action source as a new raw record. It
supports parent IDs in the schema but does not infer a complete external
capture/cleanup lineage. Preserve original provider files and receipts separately.

## Tests

Offline tests cover records, timing, payload corruption, evidence paths, rights,
source states, profiles, contacts, review rules, new job hashes and source-only
isolation. Existing installer tests still bundle all Python modules/references.
`tools/motion_foundation_fixture.py` exercises actual background jobs: export,
collect/reuse, reimport at another FPS, two proxy proportions, body profile,
retarget, stale-profile refusal, camera/light/preview, and preserved source hashes.
All geometry/motion and terms evidence in this fixture are explicitly synthetic.
No artistic fidelity, arbitrary rigs or GPU compatibility follows from that test.

Do not treat a CI fixture as workstation or real-performer acceptance. Record the
exact code revision, Blender version, tested cases and unresolved failures.

## Source/design basis

The completed project research recommends canonical records and explicit rights
before optional capture backends. Its clay proxy is diagnostic, with rest anatomy
fitted once before animation. This implementation follows that separation and
uses newly authored proxy geometry/code; it vendors no SMPL body or model weights.
Provider verification remains source-specific. Primary sources to review when
implementing the deferred adapters:
- https://mocap.cs.cmu.edu/
- https://google.github.io/aistplusplus_dataset/
- https://amass.is.tue.mpg.de/license.html
- https://github.com/zju3dv/GVHMR
- https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html
- https://sketchfab.com/developers
