# Director harness improvement handoff

## Starting point

Continue from branch `fix/evaluated-pose-retarget`. This is development work, not
a published release or an installed-runtime update. The parent implementation
commit `52b8ab3` adds opt-in evaluated world-pose retargeting for different rig
reference frames. The follow-up adds bounded vertical sole correction and a
bounded additive floor operation. Legacy retargeting remains the default.

The user's goal is a genuinely animated person performing a convincing moonwalk
in a visible environment. The latest user review found the motion insufficiently
smooth and the floor missing. A floor and vertical-drift repair now work, but a
polished moonwalk has NOT been established. Improve the Director's decisions and
verification harness, rather than hardcoding this character, action or scene.

## What was implemented and measured

- `pose_contract.py` / `pose_transfer.py`: explicit reference-frame conversion,
  translation anchor, scale and origin. Evaluated world rotation transfer avoids
  the erroneous local-delta assumption for unlike rigs. Source/target constraints,
  animated scale and changing object transforms have bounded rejection paths.
- `ground_contact.py`: optional `pose_space.ground_contact`, using explicitly
  selected weighted sole vertices. Corrects the anchor vertically within a cap;
  preserves rotations and horizontal travel. No horizontal foot lock or IK.
- `floor_contract.py` / `floor_stage.py`: `stage-floor` creates one bounded
  horizontal tiled mesh and two new matte materials, preserving existing ones.
  Registered in job preparation, mutation/input policy and worker save dispatch.
- Full source clip retimed to 80% playback speed; tracking camera; existing lights
  broadened along travel. These scene-specific choices remain local evidence,
  not runtime defaults.
- Initial tilted world alignment mapped horizontal travel upward. A level yaw
  alignment removed the drift. Optional contact correction then applied at most
  0.067669 scene units; after retiming, measured sole height stayed within about
  -0.002032 to +0.000802 scene units.
- The first final-frame camera check failed: ceil of a fractional NLA strip end
  included a frame outside the strip and exposed the rest pose. Trimming the
  retained range to frame187 fixed this instance. The general assembly endpoint
  issue has NOT been fixed in the runtime.
- Final sampled camera framing passes. Eight small CPU preview frames were used,
  including four after the endpoint repair. Preview settings restored; the
  retained working file is not a PREVIEW_ARTIFACT.
- Rendered inspection confirms floor, shadows and visible foot poses. It cannot
  certify temporal smoothness. The source still looks like a backward walking
  glide, not an accepted Michael Jackson-style performance. Playback was observed
  advancing in a new window; its final observation was paused. Do not claim it
  is still playing or automatically reload that window.

## Prioritized harness work

1. Separate semantic action suitability from technical transfer success. A file
   titled Moonwalk, moving joints, or low retarget error is insufficient evidence
   of the requested footwork. Add an explicit performance acceptance gate.
2. Verify source timing at import. The glTF catalog was indexed at24 FPS while
   loading into a30 FPS scene produced a proportionately different action range.
   Record seconds/native sampling/playback speed separately; do not overload
   `source_fps` to express intentional speed changes as the local assembly did.
3. Test fractional strip endpoints, last-frame pose continuity and scene range
   selection. Distinguish a traveling clip from a seamless loop. Do not fix a
   short visible reset by presenting a one-second repeated slice as finished.
4. Improve world-up/travel alignment contracts and measured trajectory checks.
   Never derive ground direction from a leaning character's spine without
   evidence. Ground contact must remain opt-in and unsuitable for jumps/steps.
5. Add temporal visual evidence and contact analysis: alternating support,
   planted versus sliding foot velocity, toe/heel phase and root travel. Keep
   these separate from bone-length, pose, clipping and static render checks.
6. Connect the new floor capability to role/capability discovery and production
   planning contracts where appropriate. Current work registers the executor
   operation, not complete semantic routing. Audit packaging/docs/CI coverage.
7. Add synthetic job-level regressions for retarget + optional grounding + NLA
   assembly + floor + camera + preview. Existing component tests and the local
   scene demonstrate only limited cases. Contact index stability currently checks
   vertex count; equal counts alone do not prove topology/index identity.
8. Keep transport/live presentation health separate from background job success.
   Avoid opening more windows blindly. Preserve existing unsaved work and ask for
   scene-specific authorization when the live target is uncertain.

## Validation available

`python tools/run_checks.py --offline`: 205 unit tests and installer checks pass.
Use a real Python installation, not a Windows Store alias.

Run these in separate factory/background Blender processes:

```text
blender --background --factory-startup --disable-autoexec --python tools/test_pose_transfer_blender.py
blender --background --factory-startup --disable-autoexec --python tools/test_floor_blender.py
```

Both passed locally on Blender5.2.1 LTS. Pose regression:25 poses,max cross error
4.66e-7 (naive local transfer comparison about0.2875). These are synthetic tests,
not claims of natural dancing. No new remote CI/version-matrix result is claimed.

## Local evidence (not included in Git)

Relative to the configured asset library:

- `reports/retarget-development-20260914-01/`: initial pose-space development.
- `reports/moonwalk-floor-20260914-01/REPORT.md`: floor/contact follow-up.
- Same directory: `production-jobs.jsonl`, operation options/result receipts,
  `preservation.json`, `final-comparison.jpg`, `playback-receipt.json`, and
  `Moonwalk-Studio-Review.blend`.

The final working result hash is
`a5881c325c7f27d93d71e59140cab62b48f8eecf5da3d84692b3c75855e7af61`.
Original target and three acquired source files passed hash preservation.
Assets/evidence are library-local and another machine cannot assume they exist.
Resolve runtime/library paths from actual configuration without dumping secrets.

Source motion: Sketchfab Moonwalk by TADC FAN Anass Official,
https://sketchfab.com/3d-models/moonwalk-2346d9e8314645009a1f335d441de0fc,
recorded CC-BY4.0. Target mannequin: Quaternius, recorded CC0. No asset bytes are
committed. Recheck provenance before any new distribution/acquisition.

## Boundaries

Do not touch Desert Warrior, old production files, existing unsaved Blender
sessions, model/MCP configuration, preferences or installed runtime. Do not
download again merely to rerun tests. No credentials or local reports in Git.
Historical unsaved-state preservation for the earlier unrelated import test
remains UNVERIFIED. Human acceptance of the moonwalk remains NOT ESTABLISHED.
Read AGENTS.md and the relevant skill contracts before implementation. Keep
technical, temporal visual and human acceptance separate throughout the harness.
