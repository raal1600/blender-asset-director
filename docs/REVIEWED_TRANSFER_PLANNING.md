# Reviewed source-to-existing-character transfer

Development branch: `feature/reviewed-transfer-planning`; runtime `0.6.0-dev.3`.
This is not a published release or an installed-runtime update. Read
[the real-session handoff](LOCAL_MOTION_SESSION_HANDOFF.md) and AGENTS.md first.
The local-library/native-source workflow already exists; do not replace it.

## Workflow

```text
eligible indexed source clip + saved existing target copy
  -> transfer-plan: read-only background proposal
  -> inspect mapping, units, proportions, facing and reference matrices
  -> explicit host review bound to exact proposal/job identifiers
  -> transfer-prepare: prepare the existing retarget operation
  -> job-run: new retargeted working file
  -> contact-check: read-only integer/subframe sole diagnostics
  -> separately authorized presentation and temporal/human review
```

Motion provenance and character provenance are distinct. The session used Mixamo
motion on a Quaternius character; this is not merging bodies or fitting skin.
Planning never saves a result blend or edits either input. Retargeting retains
its existing controlled worker and writes a new result. No source asset, rig,
installed skill, live Blender window, agent configuration or preference is edited.

## Hierarchy-based mapping proposals

Numbered torso candidates are accepted only as one direct three-joint chain below
hips, with indices 0/1/2 or 1/2/3. `Spine/Spine1/Spine2` and
`DEF-spine.001/.002/.003` stay distinct spine, spine_mid and chest roles. A fourth
segment, duplicate aliases, numbering gaps or broken chain require review rather
than truncation or arbitrary first-match selection.

Finger proposals require a side and numbered direct three-joint chain below that
side's hand. Mixamo-style and exported DEF naming are supported. Missing fingers,
asymmetry, unmapped helpers and ambiguous chains remain visible in evidence. This
is not universal Rigify/control-rig support. The root is not mapped as anatomy;
a floor-level root control remains part of the target rig, not stray geometry.
Explicit source_roles/target_roles may supply reviewed observed names, one-to-one.

## Read-only plan contract

Use the NEW checkout's CLI and a working Python with an explicit test library,
not the old globally installed runtime. Substitute observed paths/identifiers:

```text
python -m asset_director --library <library> job-prepare transfer-plan --input <saved-target-copy.blend> --asset <indexed-clip-id> --options <request.json>
python -m asset_director --library <library> job-run <plan-job-id> --blender <actual-executable>
```

A request requires target_object, source_meters_per_unit, target_meters_per_unit,
target_fps (1..120), root_mode (preserve_world or morphology_scaled), and facing.
Optional: source_roles, target_roles, check_count (2..257, default 65), paired
start/end excerpt inside the indexed action, and the existing explicit
`ground_contact` contract. A proposal is not permission to perform grounding.

Anatomical facing is `{"mode":"anatomical"}`. It checks bilateral ankle-to-toe
directions, foot agreement, upright torso and hip lateral evidence. Ambiguity
requires explicit horizontal source_forward/target_forward vectors, mode explicit,
and a nonempty evidence explanation. Never infer facing from travel; backslides
travel opposite the body direction. No previous scene yaw is a runtime default.

The proposal includes source and target body measurements. Morphology-scaled root
travel uses bilateral hip-knee-ankle reach; preserve_world keeps physical travel.
Meters conversion is separate from anatomy scaling. These do not change target
limb lengths, resize skin, perform IK, or change playback speed.

Reference alignment uses semantic head-to-head directions where available,
minimal swing and nearest target-rest twist, then reconstructs target local bases
through the actual hierarchy. Unmapped helpers retain reference poses. Terminal
rest directions are explicitly less certain. Antiparallel directions require
review instead of inventing a twist axis. Inspect the proposed matrices; this is
not a guarantee of universal anatomical correctness.

The result is `asset-director.transfer-proposal/1`, `status: REVIEW_REQUIRED`,
and `id: tp_...`. It binds source action/slot/range/FPS and curve signature, rig
fingerprints, object world transforms, exact mappings/reference bases, target-side
translation anchor and origin, unit conversion, proportions, facing and any
explicit grounding request. Target provenance/rights remain unknown when no
linked evidence exists; the source license is not attributed to the target.

## Approval and execution

After inspecting result.json, the host creates a review containing the actual
returned plan_job_id, plan_id, reviewer, offset-aware ISO reviewed_at, and
approved=true. Never invent a human decision. Then:

```text
python -m asset_director --library <library> transfer-prepare --review <review.json>
python -m asset_director --library <library> job-run <returned-retarget-job-id> --blender <actual-executable>
```

The review is an explicit host attestation, not a cryptographic identity or a
performance verdict. It applies only to the exact proposal and inputs. Changes to
options, rig/world placement, target bytes, source action, implementation or
license evidence require replanning/review. Execution rechecks observed
fingerprint, world and action facts. Existing license revocation/lineage gates
continue to apply. Legacy explicit retarget options remain supported.

Constraints, drivers, varying object transforms, unsupported scales and
non-anchor translations are refused. Planning examines source curves and bounded
evaluated samples; execution also performs its per-bake checks. Neither is a
mathematical proof over every continuous-time extremum. A changing or constrained
control rig needs a separately reviewed baked path, not a silent approximation.

## Contact diagnostics

```text
python -m asset_director --library <library> job-prepare contact-check --input <retarget-result.blend> --options <contact.json>
python -m asset_director --library <library> job-run <contact-job-id> --blender <actual-executable>
```

Required: target_object, mesh, feet with separate left/right lists of actual
foot/toe vertex groups, ground_z in scene units, meters_per_unit, tolerance_m,
near_ground_m, glide_speed_m_s, and exactly one of frames or
sample={start,end,count}. Explicit fractional frames are supported. Maximum 257
checkpoints and 50 million full-mesh vertex evaluations. No broad scene scan.

The worker reuses weighted sole selection and verifies base/evaluated topology.
It requires one active target Armature modifier and disjoint foot selections.
Selected vertices are evidence to review, not proof they represent true soles.

Reports separate integer and subframe clearance/penetration extrema and per-foot
horizontal centroid speed. Raw measurement inputs remain unchanged. Nonfinite
coordinates, invalid calibration and nonmonotonic time are refused. States are
PENETRATING, ABOVE_GROUND_UNCLASSIFIED, UNKNOWN_INITIAL_SAMPLE, GLIDE_CANDIDATE or
PLANT_CANDIDATE. They do not establish pressure, support, jump intent or heel/toe
phase. Initial motion direction/speed is unknown, not a planted-foot assertion.

No repair is applied: channels_changed is empty and performance remains PENDING.
Absent subframe checks do not count as PASS. A separate, justified vertical
repair can use an explicit observed cap, retaining the uncorrected result. Never
lock intentional sliding or flatten jumping simply to remove warnings. No swept
collision, COM, full IK, body-volume fitting or continuous-contact guarantee.

## Portable rejection

camera-check now checks required camera/subjects, frames-versus-sample exclusivity,
bounds/types, targets and ray budget before creating a job or launching Blender.
Transfer excerpt, target anchor and rigid reference-matrix validation likewise
run portably where possible. Actual scene/rig facts stay Blender-side checks.

## Validation and local acceptance

Use an isolated worktree and disposable library with the already verified pinned
backend. Do not use production blends as synthetic fixtures. Commands:

```text
python tools/run_checks.py --offline
python tools/bootstrap_smoke.py --shell sh
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/transfer_planning_fixture.py -- <unused-output> <disposable-library>
```

Select the actual executable and appropriate bootstrap shell on Windows; do not
use the Microsoft Store placeholder Python. Bootstrap tests bind the locally
built archive's version explicitly, without relaxing archive integrity checks or
changing which published release users install.

The generated fixture exercises 52 mappings, unrelated object names, a measured
67-degree facing difference, 1.18 proportions, imported start-frame offset, changed
output FPS, stale approvals and independent mapped-world-rotation comparisons at
matched elapsed times. Its contact probe independently verifies actual world-Z
penetration between clear integer keys; local bone Z is not assumed to be world Z.
A source fixture's motion is not real Mixamo data or performance acceptance.

For the workstation: reuse the already authorized Mixamo clip and a new copy of
the Quaternius target. Run transfer-plan, inspect/approve, transfer once and
contact-check integer/half frames against independently inspected sole groups.
Compare with prior manual-planning evidence without hardcoding its values.
Preserve prior outputs and licensing grants. Budget at most eight CPU stills,
640x360/16 samples; temporal evidence is a separate requirement.

## Deliberately deferred presentation control

Safely bound multi-window play/pause and bone-display control are NOT implemented
here. The live worker remains read-only. Use only actually available approved
host UI tools with explicit process/window/file binding, or report control
unavailable. Do not create services, file-watching command channels or arbitrary
Python endpoints to obtain UI control. Never switch an unrelated unsaved session.
Root visibility is a display choice, never a reason to delete/reparent a control.

A later controller must verify process/session/window/file/scene/armature identity,
reject stale/ambiguous targets, restore its display changes and never save project
or preferences implicitly. A frame-advance receipt is not proof anyone watched.
The user's informal positive playback feedback applies only to that exact result;
do not backdate formal performance acceptance. The previous shared-config
preservation failure remains causally unresolved and is not erased or blamed on
this harness. Private workstation assets/reports were not inspected by CI.
