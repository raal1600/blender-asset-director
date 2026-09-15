> **Historical session record.** For the current branch, contributor workflow and
> acceptance gates, read [the current handoff](CONSOLIDATION.md). The dated
> instructions below are preserved as evidence, not current merge restrictions.

# Current motion harness handoff — 2026-09-15

## Read this first: current state and user request

This section supersedes the dated 2026-09-14 implementation recommendations
below. Those historical findings remain evidence, not instructions to redo work.
The user now wants the SAME existing Adventurer character to perform the acquired
Moonwalk and then transition smoothly into the newly downloaded Thriller dance.

The user explicitly requested that the receiving agent review the code, investigate
the best solution, and perform all further automated testing in GitHub Actions.
Do not request access to the Windows desktop to run your development tests. Do not
claim CI establishes artistic/temporal quality of private assets it cannot access.

Repository: `raal1600/blender-asset-director`.
Pull branch: `feature/reviewed-bone-display-20260915` (NOT main).
Runtime remains `0.6.0-dev.3`; identify builds by exact commit, not version alone.
This handoff's commit sits above these completed implementation commits:

| Commit | Change |
| --- | --- |
| `5b7a4bb4117daadb39567f27125639ce1f6e4068` | Bounded subframe ground-contact correction and independent diagnostics |
| `4ed2397beb0fd12bec4d8f6802d875c5a43730f4` | Carry exact reviewed semantic roles through transfer execution and QA |
| `fd21202708cf53ae1bbe80e2951e997f2e3c26f0` | Reviewed bone-display audit, standard styling and explicit widget hiding |

All three are ancestors of this branch; do not cherry-pick duplicates. They were
developed in separate clean worktrees. Discover remote/current worktree state
before editing: other agents may be active. Preserve all uncommitted work.
No installed skill, configuration, production project or existing live session
was replaced by these changes. No merge or release is authorized by this handoff.

Read `AGENTS.md`, `docs/REVIEWED_TRANSFER_PLANNING.md`,
`docs/REVIEWED_ROLE_QA_FIX.md`, `docs/BONE_DISPLAY_ACCEPTANCE.md`, and the skill
references `transfer-planning.md`, `bone-display.md`, `local-motion-library.md`.

## Completed changes and evidence

### Grounding

The independent half-frame defect was addressed using bounded subframe correction,
not horizontal foot locking. `ground_contact.subdivisions` is explicit and bounded.
The real mannequin check sampled 249 eighth-frame points; maximum remaining
penetration was approximately 0.0983 mm, below the 1 mm test tolerance. Corrections
preserved rotation curves, horizontal travel, rig/skin and timing. Do not reuse the
case's correction cap or infer perfect continuous contact from bounded samples.
Read the source/fixture and corresponding local report for scope.

### Another character: actual acquisition and transfer

The user asked to transfer to a different Sketchfab character. A first acquired
Bulky Knight package advertised rigging but its downloaded glTF contained no rig
or skin weights; it was rejected and preserved as failed-candidate evidence.

The selected replacement is **Male Adventurer**, author
`manoeldarochadeoliveira`, Sketchfab ID `3f5f7d12c07445fe9b8c4958935970e2`.
Official API detail supplied CC BY 4.0 evidence. No model bytes accompany this
handoff. The source has rig `Rig`, skinned mesh `corpo_0`, 69 bones, 2014 weighted
vertices, and 21 pre-existing actions. Names are actual observations, not defaults.

The proposal mapped 50 joints: 22 body roles and 28 finger roles. The target has
two thumb segments per side; a third was not invented. Stationary root and facial
controls remained unmapped. World-facing alignment was nearly zero yaw, not the
mannequin's previous 180-degree choice. The measured root scale was approximately
0.92479756. Source duration was 31/30 seconds, frames 1–32 at 30 FPS.

Execution originally crashed because post-transfer QA discarded explicit roles,
re-inferred names, and passed `None` anatomical height into `quality()`. Commit
4ed2397 passes roles ONLY after immutable proposal/world/fingerprint/action checks,
uses them in preflight and evaluated QA, and records the actual QA roles/height.
Unreviewed missing anatomy is refused before action creation; invalid QA scale
inputs now produce a structured error. No bone rename or semantic-property write
was used to get a pass.

The real retry preserved mesh vertices, skin weights/groups, rest fingerprint,
all 21 previous action curves and object inventory; it added one Moonwalk action.
Pose scales remained one and the final key was covered. This is technical transfer
evidence, not full IK, skin fitting or a performance-quality guarantee.

### Bone display: fix the cause, not the explanation

The rig used an **Icosphere custom shape** on its pose bones. Armature OCTAHEDRAL
alone did not suppress that override. The host initially described spheres as
joint markers without inspecting those references; that explanation was wrong.
The same widget object also appeared as a large mesh obstructing the render.

Commit fd21202 adds `bone-display-audit` and `bone-display`. Normal inspect includes
display evidence. The new operation toggles custom-shape drawing OFF while
preserving all shape references, resets per-bone styles, and supports explicitly
named visible bones and widget hiding. It refuses stale, linked, shared, unrelated
or skinned targets where applicable before mutation. It does NOT delete a root,
reshape bones, rewrite materials/actions, or provide a generic object-delete API.

The saved real result has 23 body/root bones visible and the reviewed widget hidden
in the viewport and render. Independent reopen checks preserved references,
rest/skin/actions/transforms/scales and evaluated mesh coordinates at three times.
A CPU still actually showed an unobstructed Adventurer. Beauty renders do not show
bone overlays, so that is not automatic viewport-bone visual acceptance.

Interactive presentation used a separate, hash-bound, one-shot no-save launcher.
The latest launcher only set viewport/selection/pose mode and playback; the bone
display changes came from the saved harness result. Native computer control failed
with `Computer Use native pipe is unavailable ... os error 2`; MCP also failed to
connect when tried. No ports/configuration were changed or command service added.
The user gave positive informal feedback after the corrected pointed-bone view.
Keep this scoped to that view; no generalized PERFORMANCE PASS was established.

## Existing validation — do not represent as new CI results

- Grounding revision: 420 offline tests, one skipped; installer checks PASS;
  relevant Blender fixture/real checks passed locally.
- Reviewed-role revision: 421 offline tests, one skipped; installer checks PASS;
  Blender 5.2.1 normal transfer fixture 11 groups and custom-name variant 12 groups
  PASS. The first new custom-name test compared the wrong frame in its oracle;
  it was corrected to compare evaluated frame one, with failed evidence retained.
- Bone-display revision: 427 offline tests, one skipped; temporary installer checks
  PASS; Blender 5.2.1 bone-display fixture five gate groups PASS, plus real reopen
  verification. One non-fatal fixture thumbnail-write warning was recorded.

These are local observations from the prior session. The next agent must review
the changes and establish fresh GitHub Actions results, including older Blender
compatibility. A push triggers existing CI but is not a green test result.

## New Thriller intake and concrete blockers

Found the user's `Thriller Part 4.fbx` in their configured Mixamo folder. Read-only
sync and controlled-copy index observed ONE original action with 67 bones, 7825
weighted vertices, 30 FPS, frames 1–1113, duration 37.0666666667 seconds. The actual
skeleton fingerprint differs from the 65-bone Moonwalk source: re-audit and review
the new source mapping rather than reuse the previous source fingerprint blindly.
Its action label happens to match the Moonwalk's generic Mixamo action label;
identity must be asset/hash/slot-bound, not based on that name alone.

No Thriller retarget, sequence, render or motion-quality acceptance was performed.
Original hash/mtime were unchanged. The user has now explicitly confirmed this
download came from official Adobe Mixamo, in response to the question about
downloading it using their account: "Yes, from official Mixamo". This is actual
user attestation for this file, not independent provider verification. Record its
file-specific review through the existing policy/evidence workflow before project
use; the grant has NOT yet been created for Thriller. Do not extend a previous
current-files-only review or approve future downloads implicitly. The filename/
folder is not a license or observed choreography judgment.

The existing code has basic `assemble` NLA blending, but cannot yet be called a
complete smooth-transition solution for this case:

1. `assemble` re-runs `rig_report` without the reviewed semantic roles. The explicit
   role repair currently covers retarget QA, not standalone sequence QA. The new
   character still lacks auto-inferred anatomy; do not bypass the check or rename
   its bones. Establish a provenance/fingerprint-bound role route for sequencing.
2. `blend_in` does not align root placement between clips. Moonwalk moves roughly
   0.93 m on this target. Both independently transferred clips start at their own
   reference origin; a naive blend can visibly pull the character back. Need
   reviewed spatial alignment and transition diagnostics, not blind cross-fading.
3. `bake_samples` caps transfer at 360 output intervals; `retained_range`/assemble
   cap at frame 361. Full Thriller alone lasts over 37 seconds. Do not falsify FPS,
   silently crop, speed up, or just delete bounds to fit it into a 12-second path.

## Receiving agent: review, investigate, then implement and test in Actions

Investigate the best bounded sequence design before choosing an implementation.
Use actual code and primary Blender documentation when researching; distinguish
NLA influence blending, clip placement, root ownership and actual contact quality.
Do not assume a blend duration, pivot, yaw or floor height from this local scene.

Recommended questions/acceptance requirements:

- Bind each source/derived action by immutable identity, owner/slot, exact timebase,
  target fingerprint and reviewed semantic context; preserve license lineage for
  BOTH sources and the independent character. Avoid same-name action collisions.
- Propose a reviewed sequence plan: ordered clips, source ranges, desired native
  speed, blend interval, world/root anchor, origin/yaw alignment and bounded work.
  Show changes requiring review. Do not mutate source actions to place a clip.
- Compare feasible clip-placement strategies (e.g. derived root-offset action,
  explicit trajectory composition, or constrained NLA composition) against the
  actual solver and serialization. Select and explain the smallest robust method.
- Account for translated/rotated/non-origin rigs, a stationary root with traveling
  hips, differing units/FPS, turns and non-looping takes. Do not add a second root
  owner or flatten intentional Moonwalk gliding.
- Support the full requested take through explicit bounded duration/sample/work
  budgets or chunking with exact boundary continuity. Preserve fractional last
  keys and covered playback endpoints. No unbounded evaluation or hidden retiming.
- Check position/orientation continuity, velocity changes, pose discontinuities,
  mesh penetration and foot/toe behavior at integer and subframe transition times.
  Numeric smoothness is not artistic acceptance; full IK is not implied.
- Preserve original files/actions, all target geometry/weights/rest proportions,
  bone scales, existing display settings and previous result lineage. Provide
  separate results and repeat-job reuse. No production/live-window inputs.

All NEW automated tests should run in GitHub Actions. Existing `.github/workflows/ci.yml`
triggers on feature/fix pushes and has offline/installer/bootstrap jobs plus Blender
4.5.3, 5.0.0 and 5.2.1. Review the workflow itself, especially API compatibility of
new display fields across that matrix. The currently committed CI already invokes
ground_contact_fixture.py and the normal transfer_planning_fixture.py, but **does
not yet invoke** these new cases: wire them in before claiming full coverage:

- `tools/transfer_planning_fixture.py -- NEW_OUTPUT NEW_LIBRARY custom`
  (existing verified pinned backend, isolated outputs; see normal fixture usage).
- `tools/bone_display_fixture.py -- NEW_OUTPUT NEW_LIBRARY` (no backend required).
- New synthetic sequence tests for translated clip joins, rotation/turns, custom
  roles, different FPS/units, long duration/chunk boundaries, fractional endpoints,
  stale review rejection, duplicate action names, idempotence and preservation.

Keep controlled public smoke tests distinct from offline gates and private-asset
acceptance. Do not put Mixamo/Sketchfab originals, restricted motion, tokens or
private logs into commits or Actions artifacts. CI should generate its own fixtures;
it cannot inspect this Windows library. Upload bounded diagnostic reports, and
state exact commit/run URLs and which gates actually ran. User-specific continuous
Moonwalk-to-Thriller evaluation remains a later local acceptance, not a CI fiction.

Do not merge, publish a release, replace the user's installed skill, change
Codex/DeepSeek/MCP/Blender settings, start GPU/full-IK work, or send external messages.
Return the code review, selected design with tradeoffs, exact implementation commits,
Actions results, remaining gaps and a concrete bounded local acceptance procedure.

## Current private evidence pointers

Relative to configured CGI-Library; do not upload these directories to GitHub:

- `reports/subframe-ground-fix-20260915-01/REPORT.md`
- `reports/sketchfab-character-transfer-20260915-004214/REPORT.md` (original failure)
- `reports/reviewed-role-fix-20260915-01/REPORT.md` and `BONE_DISPLAY_FOLLOWUP.md`
- `reports/bone-display-harness-20260915-01/REPORT.md`, `working-output.json`,
  `real-verification.json`, `harness-show-01/playback.json`
- `reports/thriller-intake-20260915-01/FEASIBILITY.md`, `inspection.json`,
  `source-before.json`, `index-job.json`, `USER_SOURCE_ATTESTATION.md`
  (no sequence has been produced; attestation arrived after the feasibility report)

Recent protected-file comparisons checked 1397 paths. Original assets, previous
results, installed skill and protected production file matched the retained baseline.
Two shared-state differences persist relative to that older baseline: Codex config
and Blender recent-files history. Their cause was not attributed; no restoration
was attempted. Preserve the earlier unresolved finding. Historical unsaved live
state remains UNVERIFIED. Do not replace missing historical evidence with new tests.

---

## Archived 2026-09-14 handoff — historical context only

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
