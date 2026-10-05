# Generated repositioning between intact native clips (development)

The Action layer's **MotionBricks repositioning** connection samples the end of
one native Action and the beginning of the next, generates a separate interval,
and starts the second Action at its original opening. Neither native clip is
crossfaded, phase shifted, shortened, or retimed by this mode. Root placement is
separate from the original pose Actions. Save creates a new checkpoint and new
bridge/path Actions; the original Actions and prior checkpoints remain intact.

The layered-production Adventurer `walk_back` to `walk_left` reference has run
through a clean candidate installation, real Vulkan generation, preview, native
restart, fresh Blender evaluation, and a 72-frame OptiX render with client movie
playback. The same accepted checkpoint supplies preview and render. Native bone
poses and original Action hashes are preserved. Its approximately 0.55-second
generated interval is separate from both full native clips.

That reference uses explicitly reviewed root-only copies of the original
in-place takes. A constant path previously caused roughly 34 mm of source floor
penetration. Positional foot retargeting and the documented source preparation
reduce the measured full-sequence penetration to 0.9 mm; reviewed generated
stance markers drift at most 18.0 mm for a 1.85 m character. Those are specific
fixture measurements, not a promise for arbitrary clips, terrain or rigs.
Unprepared source motion can still slide or penetrate. Numerical seams and
scripted workflow checks do not constitute artistic approval. Private assets
and their rendered evidence remain outside this repository.

## Verified upstream operation

Use the pinned source, GGML, model, checksums and licenses in
[MOTION_BRICKS_CAPABILITY_AUDIT.md](MOTION_BRICKS_CAPABILITY_AUDIT.md).
The model is G1 keyframe-conditioned motion, not text-to-motion. There is no
invented inference CLI or service. The existing isolated standalone Python
worker calls the actual C ABI. Blender never loads the native model library.

After setting both four-frame boundaries, the adapter applies these verified
constraint masks (source slots first, then target slots):

| Field | Mask | Meaning |
|---|---|---|
| GLOBAL_ROOT | 1,1,1,1,0,0,0,0 | Source placement is given; destination absolute placement is predicted. |
| LOCAL_ROOT | 1,1,1,0,1,1,1,1 | Retain local incoming context, including target motion and height. |
| POSE | 1,1,1,1,1,1,1,1 | Both body-pose contexts condition the model. |

Apply masks **after** the boundary helpers, which otherwise reset them. A real
model experiment moves the target placeholder by metres and requires output
invariance within 1e-5; changing the target pose must change output. This proves
the model selects placement while still consuming the second animation. It does
not promise physically correct contacts or exact endpoint pins. There is no
silent deterministic fallback.

## Setup and supported inputs

1. Register/build the pinned backend using `tools/setup_motion_bricks.py` and
   explicitly acquire its separately licensed weights as described in the audit.
   Keep models outside Git. The configuration must include the standalone
   `python_executable`; Blender's executable is not a Python worker command.
2. Set `ASSET_DIRECTOR_MOTION_BRICKS_CONFIG` to that absolute configuration path
   before starting an isolated application installation. The bounded job worker
   forwards this specific setting. CPU or Vulkan is explicit; there is no
   automatic device fallback. Model workers serialize through the existing lock,
   enforce time and memory budgets, and release the process after each job.
3. Discover the real model skeleton (`execute(config)` returns `skeleton`).
   Inspect the intended rig and supply explicit anatomical roles, hierarchy,
   rest geometry and flat-ground height. Do not infer compatibility from names.
4. Prepare a **new** profiled Blender file with the real Blender executable:

```text
blender --background --factory-startup --disable-autoexec input.blend \
  --python tools/prepare_motion_bricks_rig.py -- \
  --rig OBSERVED_RIG --skeleton discovered-skeleton.json \
  --mapping reviewed-roles.json --ground-z OBSERVED_METRES \
  --output /absolute/new-profiled.blend
```

The mapping JSON maps the roles listed in `motion_bricks_retarget.GROUPS` plus
left/right `toe` and `hand_tip` to distinct observed bones. It is a reviewed
mapping input, not an automatic mapping tool or contact annotation. Import the
new file through the existing working-scene/checkpoint workflow.

The first implementation supports upright humanoids with positive uniform world
scale, scene unit scale 1, transform-only native Actions with matching complete
body rotation channels, stable parent space, and native heading (no additional
heading control). Unsupported constraints, rigs, channels, rest changes and
ambiguous mappings fail with actionable messages. Geometry, rest and scale are
checked again, and every sampled native context must round-trip through the
adapter within 1e-5 rig units and 0.05 degrees before inference. Saved mapping
identity is independent of animated root translation, including vertical motion.

G1 serial hip, shoulder and wrist axes are factored while retaining the group's
end orientation. Source evidence is the pinned official G1 XML, SHA256
`5d76cf92f00dd49d6eb9fae38d7d38e46886848b602ac691051e886c3bcccfb1`.
Model proportions remain G1: this is not arbitrary-rig or contact-safe retargeting.
Head, finger and toe channels outside the physical model use preserved native
endpoint interpolation only within the generated interval; the UI identifies the
provider and the saved provenance records this limitation.

## Timing, stitching and persistence

The model contract is metres, right-handed Y-up/+Z-forward, local XYZW at 30 FPS.
Blender uses Z-up and WXYZ internally. Four evaluated native samples on each side
are converted explicitly. Model output includes both context windows: only
indices 3 through N-4 form the bridge, so duration is `(N-7)/30` seconds for
N=24,28,...,64. Choose a compatible transition duration; only the generated
interval may be retimed, bounded to 0.85..1.15 of that duration. Native clips keep
their source clock. The actual fractional native endpoint is used; the UI's
rounded occupied tail is not a duplicate moving frame.

The model selects the destination horizontal placement. Compact quaternion-log
residuals match native endpoint value and angular velocity at the generated
edges; their influence is zero in the recorded central interval. Body velocity
uses the SO(3) right Jacobian and shortest quaternion paths. Generated world-root
motion becomes the rig's separate path, avoiding double-applied root motion.
The root residual matches evaluated native world velocity across the same compact
window; correcting only the baked endpoint slope can concentrate acceleration
in the first quarter-frame segment, especially at higher scene FPS. The real
30/60-to-60-FPS regression retains the same 0.05-height/second velocity threshold
and 1/1536-second derivative estimator before and after this correction.
Native pose/path channels own their original intervals. Source and target
vertical pose boundaries are retained. No frozen middle frame hides a seam.

Provider requests/results and diagnostics live in the real job directory.
The saved timeline records request/result/profile hashes, seed and sampling,
backend/model/library identity, generated timing, resource measurements and
quality limitations. The checkpoint hash and existing runtime identity select
its preview. Changing clips, timing, mapping or provider creates a new request
and accepted artifact; an old preview cannot become a successful new Save.

## Validation and troubleshooting

- Ordinary contracts: `python tools/run_checks.py --offline` and the existing
  launcher Node tests. These do not prove model or Blender execution.
- Actual Blender mapping regression, also registered in the headless CI motion
  suite: `blender --background --factory-startup --disable-autoexec
  --python tools/motion_bricks_retarget_fixture.py -- /absolute/new-output`.
- Actual pinned provider, sparse-placement influence, exact same-backend repeat,
  canonical Blender save/reopen/export, timeout, memory exhaustion, cancellation
  and recovery: `python tools/motion_bricks_fixture.py --config provider.json
  --blender /absolute/blender --output /absolute/new-output`.
- `tools/motion_bricks_profile.py` measures cold/warm inference separately from
  production's one-process-per-job lifecycle. GPU acceptance requires measured
  execution on the stated device; CPU passes are not GPU evidence.

For changed mapping errors, prepare a new profile and inspect again; never edit
the stored hash to match a different rig. For unsupported durations, choose a
model-supported interval rather than slowing either source clip. A source
foot-slip or ground-penetration defect remains a source/contact failure; do not
claim it was repaired because the generated seam passes. Recorded raw model
boundaries can fail even when the corrected Blender seams pass; retain both.

The native-client test also reproduced an independent camera handoff failure:
imported checkpoints had no saved scene inventory despite a completed Shots
inspection. The verified read-only inspection now attaches its observed inventory
to that exact checkpoint, enabling named-shot creation without changing the
Blender file or inventing a camera.


## Positional foot retargeting

The G1 model and a destination humanoid have different hip sockets and leg
lengths. Rotation transfer alone can leave a planted model foot floating on the
character. Generated intervals therefore transfer the model's evaluated foot
positions as well as its body rotations. A bounded two-joint solve uses actual
child joint heads, not imported Blender display tails. Evaluated skin vertices
with more than 0.8 mapped foot/toe weight supply the posed sole height. A smooth,
bounded pelvis-height correction makes a reachable step possible without
stretching the bones. A disclosed clearance band removes small model floor-height
noise: zero below 0.02 times the reviewed pelvis height, with a C2 release to
unmodified lifts at 0.05 times that height. These values are recorded, not labeled
as authored contacts. Unreachable or singular steps fail explicitly.

Only the generated interval receives this cleanup; its leg rotations and pelvis
height can change throughout that interval to fit the destination geometry. Its endpoint value and
angular derivatives are matched again after IK. Native Action bone curves are
unchanged. The model's foot positions are **not authored contact annotations**;
contact and rendered-playback acceptance remain separate measurements. Missing
sole geometry, animated/additionally modified skins, and ambiguous skin owners
are refused by this initial adapter. Geometry selection and maximum corrections
are recorded in the generated provenance.

## Preparing root travel for in-place clips

A constant-speed path can slide under an otherwise valid in-place gait. For
reviewed source clips, `tools/prepare_root_contact_paths.py` creates new Action
copies with root translation derived from explicit sole-vertex stance intervals.
Every bone curve and the source clock remain unchanged. Original Actions and the
existing timeline remain present; the new takes are added in muted tracks. The
existing native baseline is extended only after verifying that all prior sources,
rest geometry, placement and unkeyed defaults still match.

This is an offline Blender preparation step, not an automatic contact classifier.
Supply a JSON object with `schema: "root-contact-preparation-v1"`, the prepared
`profile_sha256`, and 1 to 8 `clips`. Each clip specifies:

- `action`: an observed unambiguous source Action name.
- `source_sha256`: the source channel digest from its review.
- `name`: a distinct name for the new take.
- `placement_delta_m`: the intended two-component world XY cycle placement.
- `contacts`: ordered, non-overlapping core stance intervals, each with `side`
  (`left` or `right`), source-frame `start`/`end`, bound `mesh`, and integer
  `vertex`. The first/last intervals must include the source endpoints. Each
  landmark must have dominant weight on its explicitly mapped foot/toe.

```sh
blender --background --factory-startup --disable-autoexec profiled.blend \
  --python tools/prepare_root_contact_paths.py -- \
  --rig Rig --contacts reviewed-contacts.json --output /absolute/new-source.blend
```

The tool never overwrites the input. Review the copied takes' planted intervals
and rendered motion before adopting them. In the client, select the prepared
native takes and leave added path movement off: they now own their root travel.
Choose **MotionBricks repositioning** for the interval between them. Do not add a
second travel path or describe the deterministic source preparation as AI motion.

## Local resource arbitration

MotionBricks inference and application Blender render/preview jobs share one
process-scoped OS lock per local user. Waiting is bounded and checks cancellation;
process death releases ownership without deleting another job's lock file. This
prevents heavy application rendering and inference from overlapping on the same
GPU. Provider budgets still include display/client headroom and measure actual
whole-device usage. The lock does not control unrelated external applications.

`tests/test_execution_resources.py` exercises real process contention, queued
cancellation, timeout and release after process termination. The headless mapping
fixture also tests root-only source preparation on an existing managed timeline,
wrong-foot landmark rejection and preservation of the original data.


## Normal desktop startup

For a studio installation, place the verified provider settings at
`SystemRuntime/UserData/MotionBricks/provider.json` under that studio root. The
normal desktop launcher passes this persisted configuration to its harness and
isolated workers. No terminal environment variable is needed. Alternatively,
set `motionBricksConfig` to an absolute local JSON path in the studio's existing
`SystemRuntime/UserData/Launcher/config.json`. Explicit studio configuration takes
precedence over inherited environment; other studios and host settings are not
modified. Direct CLI use still supports `ASSET_DIRECTOR_MOTION_BRICKS_CONFIG`.

Build/acquire the pinned backend using the documented provider setup first, and
retain its verified binary/model paths and standalone `python_executable` in
these settings. Missing or changed files produce setup/stale-provider errors,
not an undisclosed deterministic fallback. Models are never packaged into the
application or this repository.


Mapped pelvis translation is native motion, including ordinary idle sway. A
connection may retain it only when the saved anatomical profile still verifies
that pelvis against hierarchy and rest geometry. The separate added-travel
control continues to refuse a second path, and translations on other unreviewed
joints remain unsupported. Imported object coordinates may not be world XY;
source-offset fixtures convert declared world offsets through the parent matrix.


## Real rig sequence acceptance runner

`tools/run_motion_bricks_sequences.py` runs each case through the real pinned
provider, native Action/NLA application, save, and a separate Blender reopen.
It measures resources, preserves every failure, and uses the original continuity
tolerances. It is explicit GPU/provider acceptance, not a skipped ordinary CI
job. The portable tests and headless mapping fixture remain in ordinary CI.

Use a locally authorized, already profiled `.blend` and a manifest such as:

```json
{
  "schema": "motion-bricks-sequence-fixture-v1",
  "blend": "/absolute/profiled-fixture.blend",
  "provider_config": "/absolute/provider.json",
  "rig": "Observed rig name",
  "height_m": 1.85,
  "source_fps": 24,
  "cases": [
    {"name":"back-left", "clips":["Observed back take","Observed left take"], "fps":24, "extra":12},
    {"name":"mixed-fps", "clips":["Observed back take","Observed left take"], "source_fps":[30,60], "fps":60, "extra":32},
    {"name":"offset", "clips":["Observed back take","Observed left take"], "offset":[3,-2], "fps":24, "extra":12},
    {"name":"multi", "clips":["Observed back take","Observed left take","Observed back take"], "fps":24, "extra":12}
  ]
}
```

```sh
python tools/run_motion_bricks_sequences.py --manifest /absolute/fixture.json \
  --blender /absolute/blender --output /absolute/new-evidence
```

`--case NAME` can be repeated. Each case has a finite 300-second process limit
(configurable up to 900); later cases still run after a failure. A fresh process
checks every recorded frame and original Action hashes. Source-FPS variants are
new copies with explicitly rescaled key/handle times and source/scene clock
normalization. Offsets are declared in world XY. Existing source bytes, original
Actions, and the production project are not changed. A new test timeline is
constructed only inside the disposable fixture worker.

PASS from this runner covers continuity, source preservation, clocks and
persistence. It **does not** accept contact quality, visual quality, the client
journey or a packaged build. Supply nonempty reviewed stance intervals and real
client/render evidence separately. The production Adventurer test uses the
existing legally acquired model and reviewed root-only preparation; its assets
and local project paths are not distributed with the source repository.


## Interrupted saves and recovery

After an interrupted execution, the previous accepted checkpoint and preview stay
current. Open **Task and job history**, inspect the unfinished Save, and choose
**I stopped it ? resolve task**. The harness checks both the executor and Blender
worker identities before marking native execution INTERRUPTED and releasing its
writer. A live process or unreadable identity refuses recovery. No partial scene
or model output is adopted. **Reset failed native job for retry** archives the
entire stopped attempt; generating again is a separate Save.

Native jobs now retain PID and creation identity for their executor and worker,
use an OS execution lease that releases after process death, and give Blender a
watchdog for its original executor. MotionBricks retains its separate Blender-owner
watchdog. Legacy attempts without birth identity recover only when the recorded
PIDs are absent; missing/unverifiable ownership requires retained-file inspection.
Recovery can mark an old implementation's stopped attempt, but cannot bypass
current implementation, source, provider or license validation for retry/execution.
Direct CLI equivalent: `asset-director --library /absolute/library job-recover
JOB_ID --confirm-stopped`.

`tools/job_recovery_fixture.py` runs in the real headless Blender CI continuity
suite. It refuses recovery of a live queued worker, terminates its owned executor,
requires Blender child release within five seconds, preserves the failed attempt,
then actually retries and renders in a fresh Blender process. Portable contract
and process-death tests run in ordinary CI. This fixture creates its own cube;
it does not substitute for the separate real Adventurer client journey.
