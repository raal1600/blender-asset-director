# Local animation library and cross-character retarget: development handoff

This is a sanitized summary of local Windows validation and subsequent production
work on 2026-09-14. It is development input, not a release announcement or a claim
that the public installer includes these capabilities. No user assets, images,
logs, configuration contents, credentials or private working files accompany it.

## Start here

- Repository: `raal1600/blender-asset-director`.
- Tested branch: `feature/local-motion-library`.
- Tested implementation: `c11248c7ff83e1dc48aef949fdb50d97cac5336b`.
- Tested runtime: `0.6.0-dev.2`.
- Blender: 5.2.1 LTS, build `9e2066aef7ef`.
- No harness code was changed during the local tests or retarget production work.

Discover current checkout/worktree state and read `AGENTS.md` before development.
Other agents may have advanced the implementation: compare newer commits and
avoid duplicating improvements. Preserve uncommitted work and use an isolated
development worktree. Do not replace the installed skill, change agent/MCP/Blender
configuration, merge or publish a release automatically.

Read `docs/LOCAL_MOTION_LIBRARY.md` and the skill references for local motion,
motion foundations, grounded motion and studio contracts. Use the registered
working Python and Blender executables; a plain Windows Store `python` alias is
not a valid fallback on the tested machine.

## What the session actually established

The workflow transferred a real animation from a Mixamo Beta character to an
existing Quaternius mannequin. It preserved the target mesh, skin weights,
material slots, bone lengths and rest fingerprint. Target-specific alignment,
measured root-displacement scaling and bounded vertical grounding were applied.

This was not mesh merging, realistic skin fitting, motion reconstruction or full
proportion-aware foot IK. The user initially associated the earlier mannequin
with Sketchfab; catalog evidence showed that Quaternius supplied the mannequin
and Sketchfab had supplied the earlier motion. Character provenance and motion
provenance must remain separate.

The executed sequence was:

```text
read-only folder discovery -> verified private copy -> actual clip index
-> evidence-backed project-use review -> local search
-> original character/action preview -> target rig and body audit
-> explicit mapping and reference alignment -> retarget
-> measured contact repair -> floor/camera/light review -> CPU stills
-> separate interactive playback
```

## Existing features that passed

Do not reimplement these as though they were absent:

- Bounded provider-folder registration, read-only scanning, hashing and copying.
- Actual FBX owner/action/slot, hierarchy, FPS and range indexing.
- Distinct Mixamo `Hips -> Spine -> Spine1 -> Spine2` recognition.
- The narrow `LicenseRef-Adobe-Mixamo` project-use policy, retained evidence,
  current-file grants, derivative restrictions and revocation.
- Native playback before retargeting, preserving the source character and timing.
- Second-sync reuse without another source copy, asset record or indexing worker;
  catalog manifests and job receipts/logs remained unchanged.
- Joint-head anatomical body profiles and a reviewed root-scale proposal.
- Evaluated-pose retargeting, target-side anchor validation, vertical
  `ground_contact`, camera/light operations and preview-settings restoration.

Validation on the tested commit:

- Offline suite: 360 tests ran, one skipped; PASS.
- Installer self-tests and isolated temporary packaging: PASS.
- Local-motion Blender fixture: nine gates PASS, including rejection of a
  source-named translation anchor when the target uses different names.

## Real-source observations

The user-acquired `Moonwalk.fbx` contained an original `Armature` rig with 65
bones, `Beta_Joints` and `Beta_Surface`, and 24,746 skinned vertices. Its action was
`Armature|mixamo.com|Layer0`, observed at 30 FPS over exact frames 1 through 32:
31 intervals, or 1.033333333333 seconds. The native capture rate/method remained
unknown. Native reimport preserved the action curves, mesh inventory and rig
transforms; all 32 indexed pose samples matched. Root travel was about 1.00753 m.

The target was the previously acquired CC0 Quaternius mannequin, with rig `Rig`,
mesh `Mannequin` and 53 bones. Its actual torso hierarchy was:

```text
root -> DEF-hips -> DEF-spine.001 -> DEF-spine.002 -> DEF-spine.003
     -> neck/head and shoulder branches beneath the appropriate torso joints
```

Automatic discovery reported a missing spine despite the available numbered
chain. The host inspected it and supplied distinct roles without patching code.

### Transfer and alignment

- 52 explicit mappings: 22 body joints and 30 finger joints. The stationary target
  root remained unmapped.
- `mixamorig:Hips -> DEF-hips`; the translation anchor was the target `DEF-hips`.
- `Spine`, `Spine1`, `Spine2` mapped to `DEF-spine.001`, `.002`, `.003`.
- Three joints of each index, middle, ring, pinky and thumb chain were mapped on
  both sides after checking actual parent relationships.
- Target/source leg ratios were approximately 0.933405; arm ratios approximately
  0.973967. Root displacement used the existing body-profile proposal,
  0.9334045618, based on bilateral hip-knee-ankle reach.
- A world-Z-preserving yaw of approximately -180 degrees followed the actual
  armature orientations. It is not a generic Mixamo preset.
- The host derived explicit target reference matrices from anatomical directions.
  This planning still required a task-specific script; execution used the
  reviewed runtime operation.
- Source timing and the final key were preserved. Target pose scales remained
  one and the rest fingerprint stayed stable.

### Contact repair

The first transfer was technically valid but the target soles penetrated the
existing floor by approximately 10.17 to 32.44 mm. A separate, justified repair
used the existing vertical pelvis correction with 252 measured foot/toe-weighted
vertices and topology verification. The cap was 40 mm, derived for this observed
case; maximum correction was 32.4375 mm.

There was no horizontal foot locking or grounding-induced joint rotation change.
Integer frames met the runtime contact tolerance. Independent half-frame samples
still ranged from -1.4133 to +0.4219 mm. Do not call this perfect continuous contact.
All 52 mapped world rotations agreed with the reviewed reference relation at the
32 sampled frame times, to reported Blender precision.

### Presentation

The existing floor, character materials and three area lights were reused. Light
placement/aim was adapted. A new static 55 mm side/three-quarter camera passed five
framing checks with no sampled external occlusion. These are scene choices, not
runtime defaults.

Four CPU stills at 640x360 and 16 samples showed readable feet/body and no obvious
explosive deformation. Preview settings and artifact labeling were verified.
The saved result retained EEVEE, 1920x1080, AgX, exposure zero and 30 FPS.

Playback and bone display used task-local no-save presentation scripts in newly
launched Blender processes. They were host actions, not a new harness feature.
No reliably bound control route to those new windows was established, so a second
bones-visible window was opened instead of controlling an unrelated live scene.

The floor-level bone is the target's existing root control. It is not a surface
capsule or retarget defect. Showing all bones exposes it; hiding its display must
not delete or reparent it.

## Recommended first implementation milestone

Make planning a source-to-existing-character transfer reusable and reviewable.
Keep the successful scene constants out of runtime code.

### 1. Better skeleton discovery and mapping proposals

- Recognize numbered `DEF-spine` families only after verifying direct parent order.
  Retain distinct spine, middle-spine and chest roles.
- Propose bilateral finger mappings from actual side, hierarchy and joint order.
  Report ambiguity, missing joints and unmapped helpers explicitly.
- Present source character/action and target character/provider separately in
  preflight, together with their respective project-use readiness.
- Test duplicate aliases, namespace variants, broken chains, absent joints and
  asymmetry. Do not infer universal Rigify support from one exported DEF-only rig.

### 2. A bounded, read-only alignment proposal

The runtime already accepts reviewed alignment/profile data; the host currently
has to construct much of the proposal manually.

- Bind fingerprints, action/slot, timing, mapping, units, world alignment,
  reference matrices, target-side anchor, target origin and root-scale policy.
- Derive facing from reviewed anatomical evidence with ambiguity checks. Do not
  assume -180 degrees, identity alignment, identical names or a universal scale.
- Expose the measured proportions and the rationale for root scaling. Preserve
  target geometry, skinning, rest lengths and unit pose scales.
- Refuse stale bindings, duplicate target mappings, unsupported constraints,
  animated object transforms/scales and unreviewed alignment before execution.
- A proposal requires host review; it must not silently mutate a scene or claim
  anatomical/foot IK that the solver does not implement.

### 3. Reviewable contact diagnostics and repair

- Distinguish penetration, floating, possible planting and intentional glide.
  A filename or low ankle is not authority to lock a foot.
- Reuse actual evaluated sole/topology checks. Keep the unmodified transfer and
  its measured failure separate from a proposed repair.
- Report units, body-scale context, correction bounds and affected channels.
  The observed 40 mm cap is not a default for every character.
- Add bounded subframe checks and report their extrema separately from keyframe
  checks. Do not present integer-frame contact as continuous contact acceptance.
- Preserve timing, rotations and horizontal travel during vertical correction;
  do not flatten heel/toe phases or ground jumping motion automatically.

### 4. Earlier request validation

Two host-authored camera-check requests were correctly rejected during local
acceptance: missing camera, then mutually exclusive `frames` and `sample`.
These were caller errors. Move portable required-field and mutual-exclusion
validation before job creation/Blender startup where practical, while retaining
Blender-side verification of actual scene facts. Add focused regression tests.

## Following priority: safely bound presentation

Use available, approved UI/MCP capabilities without installing a helper or
starting a service by default.

- Bind the intended process/window/file explicitly; multiple agents/windows are
  normal. Never switch an unrelated unsaved Blender session.
- Label native versus retargeted playback with character, source, action, FPS,
  range and pending/accepted review status.
- Support bounded play/pause, framing, in-front armature display, anatomical-bone
  filtering and display restoration. Root visibility is a display choice.
- Keep viewport/selection/mode changes separate from animation edits, project
  saves and preference saves.
- Reuse a safely bound review window when possible. Report unavailable control
  honestly; do not restart Blender/MCP or change ports to obtain it.
- Do not add arbitrary-code endpoints or file-watching command channels merely
  to control playback. A frame-advance receipt is not proof somebody watched.

## Limits and evidence attribution

Local `moonwalk` search matched filename/title tags. `backslide` and `backward
glide` normalized to that label; `dance` did not match. Any broader lexical recall
must retain `FILENAME_CLAIM_ONLY` provenance rather than fabricate observed motion
semantics.

The approximately one-second source travels, so replaying its range visibly
resets the root. Do not blindly repeat traveling clips or add another motion
controller. Longer seamless choreography requires separate design and validation.

No full-video renderer, new dataset converter, GPU reconstruction, mesh fitting,
realistic skin or full foot IK was implemented. Provider folders remain provenance
hints; the reviewed Mixamo scope does not grant raw standalone redistribution or
blanket permission for other providers/future files.

Saved formal reports retained performance PENDING and human acceptance NOT
ESTABLISHED because the image-capable host inspected stills, not temporal video.
Subsequent user feedback after interactive retarget playback and bone display was
positive (including "looks good"). Record that as informal feedback on this
particular result; do not backdate or generalize acceptance. A review mechanism
should bind an explicit decision to an output hash and viewing scope.

The earlier local-library acceptance had 716/717 protected files unchanged. A
shared agent configuration changed while multiple agents were active; attribution
was unresolved and no acceptance command wrote it. Keep that preservation failure
recorded. Do not blame the harness, restore another agent's configuration or
retroactively declare full preservation without causal evidence. The later
mannequin transfer preserved all seven explicitly protected source/prior files;
that narrower check did not re-audit shared configuration.

## Private evidence index

The following are relative to the user's configured CGI-Library and are not
included in Git:

- `reports/local-motion-acceptance-20260914-201358/REPORT.md`: native/library test.
- In that directory: `clip-record.json`, `review-request.json`,
  `idempotence-verification.json`, `configuration-preservation-gap.json`, and
  `fixture-output/local_motion_report.json`.
- `reports/mixamo-on-mannequin-20260914-204736/REPORT.md`: production transfer.
- In that directory: `reviewed-roles.json`, `body-profile.json`,
  `derive_alignment.py`, `retarget-options.json`, `alignment-evidence.json`,
  `initial-motion-audit.json`, `grounded-options.json`,
  `grounded-motion-audit.json`, `final-verification.json`, `jobs.jsonl`,
  `director-brief.json`, `production-contract.json`, `delivery.json`,
  `preservation-final.json`, and the compact `mannequin-preview.jpg`.
- `playback/` and `bones-playback-*/` contain host presentation scripts/receipts.

Read selected sections, not entire histories. The private alignment script is a
method/evidence reference, not a source of hardcoded runtime constants. An agent
without local evidence access must mark those checks NOT RUN; it must not pretend
to have inspected the assets or download protected sources to compensate.

## Expected developer validation and handoff

1. Identify newer existing fixes and select a focused implementation scope.
2. Add meaningful synthetic tests for numbered torso and finger chains, unlike
   namespaces, stale bindings, unit/facing differences, deliberate glide,
   bounded contact checks, request validation and preservation/idempotence.
3. Run `tools/run_checks.py --offline` and relevant Blender fixtures using
   disposable outputs and the already verified pinned backend. Never use a
   production blend as a synthetic fixture.
4. If authorized local sources are available, repeat a bounded real-source check
   from verified copies with retained license evidence. Preserve old outputs.
   Default budget: at most eight CPU stills, 640x360/16 samples; temporal evidence
   remains a separate requirement.
5. Return code changes, exact commits, tests, limitations and compatibility notes.
   Commit only sanitized code/docs/tests and synthetic fixture generators.
   Do not publish user assets, replace the installed skill, merge or release
   automatically, or start deferred GPU/IK/choreography work.
