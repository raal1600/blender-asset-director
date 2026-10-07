# MotionBricks capability audit (2026-10-05)

## 2026-10-07 — continued repair and native falsification

The subsequent `b23e76d1e4e75f1ace63ffed8dcb058846551b8d` native build verified
distinct attempt jobs, raw/corrected numerical diversity, active cancellation,
and stale completion. `native-faults-b23e76d-r3/report.json` additionally records
an owned provider-process crash and a launcher/host restart during generation.
The accepted checkpoint and five prior candidate identities survived; the
interrupted unpublished output was quarantined rather than counted successful.
These are real Windows/WebView2/process tests. They do not establish successful
motion acceptance or final render parity; all generated candidates failed quality.

Independent copied Beta and Paladin humanoids were inspected locally. Both have
ambiguous straight rest elbows. New explicit measured hinge calibration accepts
only reviewed, consistent signed planes bound to rest/mapping/content evidence.
Beta's measured planes agree within 0.00013 degrees; its 32 native-pose
encode/decode checks measured at most 0.0000011 m and 0.000125 degrees error.
Paladin's observed 36–39 degree plane dispersion does not establish a supported
calibration. Neither rejection nor round-trip calibration counts as successful
second-rig generation. Beta's full-interval transition was rejected before
inference because its source context had no planted grounded foot. Read-only
analysis found five eligible interior contexts out of 29; it did not change the
selected native interval. Evidence: `beta-mapping-contexts.json`,
`beta-sequence-v1`, `beta-hinge-review.json`, `second-rig-profile-review.json`.
Private assets remain local; this technical inspection grants no redistribution
rights. The original file hashes and native channel preservation are retained.

A subsequent, separately requested fixture selected Beta intervals [1,9] and
[3,32] at 30 FPS. It exposed a unit bug: the context round-trip guard compared
rig-space displacement directly with 0.00001, incorrectly rejecting a 0.01-scale
rig whose physical error was under that metre limit. The guard now compares
world-metre displacement and retains both units in diagnostics. Actual model
generation, baking, native preservation and fresh reopening then succeeded.
Quality still failed at 16,511 degrees/s²; no second-rig quality pass is claimed.
The separate [1,2] source interval correctly refused insufficient context before
inference. The original full-interval rejection remains unchanged. Evidence:
`beta-explicit-range-v1`, `beta-explicit-range-v2`, and their explicit manifests.

Private continuous-spline experiments isolated the reference acceleration
problem. Endpoint-curvature energy reduced the peak but still failed; increasing
smoothing also introduced penetration. A bounded continuous world-rotation
variant then passed the reference's unchanged kinematic gates at 240 and 480 Hz
(4,830 and 4,841 degrees/s² respectively), with structural preservation and
fresh reopening. This is an experimental script, not yet the application path.
Its 72-frame diagnostic render was inspected as three complete contact sheets;
full-speed temporal review, broader rigs/seeds and native acceptance are pending.
Evidence: `continuous-bounded-v1`, including the retained failed precursors.

The bounded continuous refinement was subsequently implemented in the application
(`motion_bricks_spline.py`, `motion_bricks_world_refinement.py`, and the existing
refinement/baking path). `application-continuous-v1` passes the real reference
generation, unchanged hard quality gates, source preservation and fresh reopen.
`application-continuous-seeds-v1` passes seeds 7 and 42; seed 1234 remains rejected.
These are application-path results, not yet an accepted native-client revision.
The independent Beta request fails the optimizer's convergence limit under this
implementation; its mandatory generalization gate remains unfulfilled.
The complete portable/installer run records 805 tests (802 passed, three
disclosed skips). Broader coverage, final native acceptance and benchmarks remain
pending. No preset quality threshold or backend pin was relaxed.

The Beta convergence failure was then reproduced from captured, evaluated
optimizer inputs. At the finer 69-sample grid, six finger curves exhausted the
iteration limit. Scaling the numerical ADMM penalty with the existing smoothing
weight made all 52 curves converge (maximum 880 iterations, primal residual
below 1e-8 and dual residual below 1e-6). The objective, endpoints, curvature
bound and quality thresholds are unchanged; both residuals are now required.
This numerical repair does not establish suitable motion: the original Beta
duration is still refused for excessive additional filtering. Explicit 30- and
42-frame bridge alternatives pass continuity, contact and fresh reopening but
fail the 45-degree total correction limit at 58.46 and 59.46 degrees respectively.
Evidence: `beta-optimizer-diagnosis.json`, `beta-optimizer-rho-1.json`,
`beta-continuous-v2`, and `beta-duration-v1`. All failed attempts are retained.
The application rerun with that numerical change
(`application-continuous-rho-v1`) again passes argmax and stochastic seeds 7/42,
including fresh reopening; stochastic seed 1234 still fails penetration. The
four-case report correctly remains FAIL because it retains that failed sample.

The clean `4e45674bc2305900d8a8c9d82b38c7be3477e0ad` native Windows build
generated three immutable candidates, of which two passed quality. Actual
source-aligned A/B controls played both passing alternatives. Explicit acceptance
persisted the chosen checkpoint and event, but the client then recreated its old
working draft during snapshot refresh and left the accepted preview empty. The
complete journey is therefore FAIL, not an acceptance/render pass. The accepted
artifact remains intact. Snapshot guards now inspect cached edits without lazily
reconstructing the prior request; unit regressions protect both this repair and
real unsaved edits. A fresh isolated native rerun is required. Evidence:
`native-accept-4e45674/report.json`, `accepted-wait.txt`, and
`snapshot-reconciliation-unit-v1.log`.

The local `c401b33a77eb751aff462d3c0a6a66e73c501368` build passed the visible
Windows comparison, input-change staleness and active-Blender cancellation
procedure (`native-review-c401b33-r2/report.json`). Accepted state survived.
Candidate quality still failed; no successful acceptance/render is inferred.
The earlier `7fc75d2` client failed to load an unserved helper. The subsequent
HTTP import-graph regression catches that integration failure.

Further private reference experiments retained the fixed limits: explicit early
tangent increments moved the acceleration peak and failed; stronger local
smoothing exceeded 15 degrees; world-rotation smoothing at 0.05 seconds still
measured 13,388 degrees/s², and at 0.075 seconds required 17.35 degrees of local
correction. A bounded world-acceleration optimization also exceeded the preset
correction limit. These experimental corrections were not adopted. Evidence:
`endpoint-increments-v1`, `strong-filter-v1`, `world-filter-v1` through `v3`.

Distinct generation-attempt job identities and hash-verified raw/corrected
duplicate detection now also have the b23e76d native evidence described above.
No new backend, weights, dependency version or acceptance threshold was introduced.

## 2026-10-07 authoring investigation (in progress)

### Subsequent native review and dense quality falsification

`native-review-9474cca/report.json` verifies actual visible Windows/WebView2
three-candidate generation, unchanged accepted checkpoint, two real baked
previews, source-aligned comparison and full-speed controls. It recorded no page
errors. All three candidates failed quality. The 96.743-second click-to-review
observation is one sample, not a performance percentile or acceptance/render pass.

Later source experiments replaced repeated partial foot-orientation projection
with fixed targets and added constrained endpoint/tangent smoothing. The fixed
acceleration threshold was not loosened. `dense-quality-convergence.json` shows
why a coarse pass is insufficient: the same repeated travelling-clip candidate
measured 4,795 degrees/s² at 60 Hz, 6,778 at 240 Hz and 11,081 at 480 Hz. The
reference also has large near-stitch peaks. The current v2 quality preset uses
240 Hz by default, checks that the measured contact landmark itself is grounded,
and still requires further convergence/visual evidence. It is not a physical
feasibility certificate. Historical 60 Hz passes are not inherited.

`final-tangent-reconcile-v2` reduced the corrected root acceleration enough to
pass its dense gate with 4.83 mm maximum additional generated-root smoothing.
Joint acceleration still failed at about 13,468 degrees/s². Native preservation
and fresh reopening passed. The sequence runner now returns overall FAIL for
failed kinematic quality, while retaining continuity and fresh-process results
separately. Earlier runner PASS labels covered only their declared continuity
scope. No quality-failed candidate has been accepted.

`cleanup-comparison-240.json` evaluates identical reference inputs/bakes with the
same validator: earlier cleanup measured 29,275 degrees/s² joint acceleration
and 58.46 m/s² root acceleration; retained refinement measured 13,468 and 16.48,
respectively. The joint gate still fails. An experimental clamped spline bake
increased the peak slightly and was reverted. `stage4-checkpoint-offline.log`
passes 797 tests (794 passed, 3 skipped) and installer checks;
`stage4-checkpoint-node-r3.log` passes 390 launcher tests for this local stage.

Restart unit tests cover an interrupted unpublished attempt, publication before
launcher failure, preservation of the accepted scene and refusal to clear a live
writer's lease. Their synthetic transport is not native fault-injection evidence.
New queue/native/save/hash traces and camera focus are awaiting final native
validation. In-progress portable checks passed 795 tests (792 passed, 3 skipped)
plus installer checks, and 386 launcher tests, before subsequent refinements.

Pinned code/weight license texts were inspected and copied by the updated setup
helper into a new isolated evidence directory. Their exact hashes are retained
in `setup-notices-proof.json`; code and weight terms remain distinct. See
`THIRD_PARTY_NOTICES.md`. No private assets or model binaries were added to Git.

### Later repair-loop evidence, following 91cb591

The actual isolated Windows/WebView2 client generated three immutable model
candidates in 91.606 seconds (`native-review-91cb591/report.json`, one observation,
not a latency percentile). The accepted checkpoint remained unchanged. All three
failed hard quality checks and the visible Accept controls were disabled.
Comparison loaded its first baked candidate, then failed because initialization
read the not-yet-selected second candidate. The source repair and a sequential
viewer regression test pass; native comparison rerun remains outstanding.

The v2 anatomical arm calibration reduced maximum reference correction from
75.1 to 31.7 degrees. Short 3D support locks fixed the measured floating contact;
bounded rotation filtering, reach-margin planning, and support/floor projection
were tested as subsequent independent experiments. `bounded-refinement-v1`
passes its seam, planted-contact, penetration, speed and correction gates but
still FAILS acceleration (11,100.6 degrees/s² against 6,000). Longer-duration
experiments also failed sliding/penetration/acceleration before the latest
projection repair. These are retained failures, not supported quality coverage.
No candidate from this repair loop has been accepted as good motion.

`seam-convergence.json` separates an estimator defect from those real quality
failures. On identical baked motion, the old second-order angular seam estimate
was 142.27, 35.56, 8.93 and 2.23 degrees/s as h decreased from 1/384 to 1/3072 s.
The cubic one-sided estimate at h=1/768 and 1/1536 s was below 0.56 degrees/s.
The implementation now uses four samples on each side and a common rotational
frame. The 5 degrees/s threshold is unchanged. The acceleration failure is not
removed by this derivative correction.

A v3 knee-plane calibration was also tested on a separate copied rig. Its real
inference path refused excessive filtering (`anatomical-v3`,
`MOTION_BRICKS_EXCESSIVE_FILTER`). V2 remains the default. V3 is an unaccepted
experimental source capability, not an advertised runtime improvement.

The client now has persisted bridge support intervals and explicit stationary
root intent, draft undo, stale-request checks, explicit discard, and comparison
repair. These source changes require the next complete native-client pass.
Stage-three offline checks passed 792 tests (789 pass, 3 disclosed skips) and
installer checks; the launcher passed 382 tests before the final additional
discard/derivative regressions. This chronology does not transfer passes to a
later source revision automatically.

Isolated branch `feature/motionbricks-authoring-20261006`, foundation commit
`90db942`, extends the combined #31/#30/visual-turn ancestry. Earlier entries
remain historical evidence, not current acceptance of all quality gates.
Private evidence root: `AssetDirector-MotionBricks-Authoring-20261006` under the
operator's Documents directory. No private assets or model binaries are tracked.

Verified in the current Windows Vulkan runtime: the configured DLL is the file
actually loaded; SHA-256
`e0b61e7e7113cf7a65f17343d270dbb3a2b745bfb31d2fae95e56bb599919aa7`.
The pinned backend/GGML/weights remain unchanged. Same-setting raw repetitions
were exact on this device. Changing the seed under argmax had no effect.
Gumbel temperature 1 produced material differences, including after correction:
two seed comparisons measured 7.14 and 7.24 degrees RMS interior local joint
rotation difference. This demonstrates variation for the reference rig/pair,
not naturalness, physical feasibility, or cross-device reproducibility.

The expanded fixed quality preset falsified the older reference's overall
acceptability despite passing endpoint seams: no qualifying measured stance in
some outputs, excessive joint speed/acceleration, and about 75 degrees of maximum
deterministic correction. Seeds 1234/7/42 and longer 1/1.5/2-second requests did
not remove the large arm correction. These are mandatory quality FAILs.

Investigation found a rest-calibration defect: independent shortest-arc segment
alignments encoded a 76.24-degree, multi-axis elbow offset at rest, whereas G1
has a hinge elbow. The new `g1-anatomical-frames-v2` uses the complete reviewed
rest arm plane and the segment controlled by the final shoulder axis. A real
reference run reduced maximum correction from 75.11 to 31.75 degrees and maximum
joint speed from 1094 to 679 degrees/second while preserving round-trip, native
channels, stitches and fresh reopening. Contact and acceleration gates STILL
FAIL; the repair is not full acceptance. Straight/degenerate rest arms need
explicit calibration rather than an invented bend plane. Legacy profiles remain
readable for existing artifacts. New calibration changes the dependency hash.

Implemented but not yet native-client-verified: separate immutable review
checkpoints, stale-checked atomic acceptance, exact restore, persisted working
requests, bounded three-seed alternatives, physical-time A/B viewing and restart
reconciliation. Synthetic transport tests cover separation, failure, cancellation,
corruption and acceptance idempotence; they do not substitute for visible native
WebView2 journeys. See `motion-bricks-acceptance.json` for outstanding gates.

## Earlier capability proof (2026-10-05)

This is source evidence and a completed isolated CPU/Vulkan capability proof,
not full neural-transition application acceptance. The user explicitly authorized local provider
inference for this task. No installed runtime, user project, or original asset
was changed.

The subsequent [generated repositioning integration](MOTION_BRICKS_REPOSITIONING.md)
uses verified sparse masks to predict destination placement, with real native-client
Save/restart/render evidence. Contact quality is still not fully accepted. The
fixed-destination proof below is historical, not the only available C ABI mode.

## Exact identities and reproducibility

| Component | Identity / state |
|---|---|
| Latest upstream inspected | `93850c4f68598e7c47722e30972764dad13debde` |
| Latest upstream build | BLOCKED: pinned GGML `0a249dd4d2f4dfcd962123a3d881f73f93588ccf` is unavailable from its declared `ggml-org/ggml` remote. Git fetch returned `not our ref`; independent GitHub API lookup returned 422 `No commit found for SHA`. |
| Reproducible prior candidate | `ee0cf5d9035f639ed0787f390fb1ce05d6a4c463` (Support building and running on Windows) |
| Candidate GGML | `8c63e70982c95ceb862e3a1073a2c1beef75d60a` (v0.20.2), fetched successfully |
| Published weights | `LocalAI-io/MotionBricks-G1-GGML@cc2a47603dbc203a4f18f35dd06ed3611833f506` |
| Original NVIDIA model | `NVlabs/GR00T-WholeBodyControl@a0732b642c0333077e127a2f56ab0014c196bca4` |

`git diff` confirms `include/motionbricks/inference.h`, `src/inference.cpp`,
`src/planner.cpp`, and `src/motion_rep.cpp` are unchanged between the prior
candidate and latest inspected revision. The older candidate is a complete
upstream pin, not latest source with an arbitrarily substituted GGML version.

Primary source links below bind to the reproducible candidate:

- [Inference contract](https://github.com/localai-org/motion-bricks.cpp/blob/ee0cf5d9035f639ed0787f390fb1ce05d6a4c463/docs/API-INFERENCE.md)
- [Public inference header](https://github.com/localai-org/motion-bricks.cpp/blob/ee0cf5d9035f639ed0787f390fb1ce05d6a4c463/include/motionbricks/inference.h)
- [Boundary conversion and validation](https://github.com/localai-org/motion-bricks.cpp/blob/ee0cf5d9035f639ed0787f390fb1ce05d6a4c463/src/inference.cpp)
- [Actual planner](https://github.com/localai-org/motion-bricks.cpp/blob/ee0cf5d9035f639ed0787f390fb1ce05d6a4c463/src/planner.cpp)
- [Pose representation / FK](https://github.com/localai-org/motion-bricks.cpp/blob/ee0cf5d9035f639ed0787f390fb1ce05d6a4c463/src/motion_rep.cpp)

## Verified capabilities and limitations

This is keyframe-conditioned G1 motion inference, not text-to-motion. The C ABI
accepts both existing source context and target context. Create an opaque
`mb_inference_request`, call `mb_inference_request_set_boundary_poses` for
boundary 0 and 1, then `mb_model_infer`. Each boundary is exactly four frames,
12 root floats and 544 local quaternion floats. Source slots occupy output
frames 0..3; target slots occupy N-4..N-1. Both influence root, pose-token and
VQ decoder paths. This operation does not require styles, an agent or physics.

Output duration is 24..64 frames in multiples of four, including boundary
regions. The 11-element duration mask can force one supported frame count.
Duration otherwise uses argmax. Pose tokens use seeded Gumbel sampling by
default; explicit argmax is diagnostic. Request RNG restarts on every call.
Same-backend repeatability is supported; equal seeds do not promise identical
PyTorch draws or cross-device floating-point decisions.

Constraints are conditioning, not exact pose pins. The stateless operation
performs no seam correction, overlap removal, contact cleanup,
or animation scheduling. Four source/target context frames cannot be treated
as exact guaranteed boundary output. The host application must validate and
stitch any accepted result and preserve source animation outside that interval.

[Upstream Kimodo diagnosis](https://github.com/localai-org/motion-bricks.cpp/blob/ee0cf5d9035f639ed0787f390fb1ce05d6a4c463/docs/KIMODO_TRANSITION_DEBUG.md)
explicitly retains FAILED observational clip QA after fixing virtual endpoint
conditioning: recorded physical-joint exit rotation gaps remain 4.87 and 8.81
degrees, and entry failures remain. Those are upstream measurements, not local
results or evidence for Asset Director. Matching names and finite quaternions
alone are insufficient compatibility checks.

The installed CLI only implements `abi`, `inspect BUNDLE_DIRECTORY` and
`replay-info REPLAY_FILE`; it has no inference command. Use the actual C ABI in
a small isolated helper, not invented CLI flags or the demo network service.
The Go binding is not an exhaustive wrapper for the stateless API.

## Motion data contract

- Skeleton: G1Skeleton34 / `g1skel34`, fixed model order and model neutral joint
  positions. Query names, parents and neutral positions from the loaded model.
  Parent topology and rest geometry must both match a verified mapping.
- Coordinates: right-handed, metres, Y up, +Z forward at zero yaw. Heading is
  radians around +Y. Input and output local rotations are row-major XYZW;
  Blender quaternion properties use WXYZ and Blender normally uses Z up.
- Root: separate root translations `[frames,3]` and root local quaternion in
  `[frames,34,4]`. Canonicalize both contexts in one frame using first source
  X/Z and heading; preserve height. Restore the saved world placement once.
- Timing: strictly 30 FPS inside the model. Resample evaluated source poses
  explicitly; retain rational source FPS in provenance. No arbitrary native
  24/60 FPS or arbitrary-duration promise is exposed.
- Pose helper FK uses the model neutral offsets. Virtual hand/toe endpoints
  7, 14, 25 and 33 keep FK positions but have global-identity conditioning
  rotations. Input authored arrays are not modified. Source outgoing velocity
  slot 3 is masked; target final velocity repeats the previous velocity.
- Raw conditioning fields exist: global root 8x5 (X, height, Z, cosine/sine
  heading); local root 8x4 (yaw velocity, X/Z velocity, height); pose 8x303
  (33 non-root positions and all 34 global rotations in 6D columns). Pose Y
  is absolute height; X/Z are root-relative. Feature normalization is internal.
- Inputs are finite and bounded to magnitude 1e4; quaternion norms must be
  within 1 +/- .01. This numerical validation is not physical feasibility.
- There is no public contact annotation/mask input or contact-labelled output.
  Sparse root conditioning is supported; an arbitrary full trajectory is not
  a public input. Optional SONIC/MuJoCo robot physics is a separate subsystem,
  not a generic Blender-rig transition cleanup service.

## Integration fit, lifecycle, and resources

Prefer one subprocess per accepted provider job using the installed C ABI,
with an explicit bounded request/response format. This isolates Blender's
Python ABI and native backend crashes and lets the existing job controller
terminate timed-out/cancelled work. ABI handles have matching free operations.
There is no public progress callback, cancellation token, timeout, memory budget,
or selected GPU index. Calls sharing a loaded model must be serialized.

The public devices are CPU and Vulkan. `AUTO` explicitly selects CPU; Vulkan
initializes device 0 and returns unavailable rather than silently selecting
CPU. The runtime disables Vulkan F16/cooperative-matrix paths to retain F32
parity. No public CUDA device is exposed. Expose the selected provider, device,
mode, revision, model hash and any explicit fallback in application provenance.

Model allocation failure returns `MB_OUT_OF_MEMORY`; C++ `bad_alloc` maps to the
same status. Output is null on API failure. The host still must handle native
process crashes and allocator/driver failures. Model/backend buffers are owned
by RAII resources, but lifetime/resource-release measurements are a required
real test, not established by source ownership alone.

Real hardware probe on 2026-10-05: NVIDIA GeForce RTX 4070, 12,282 MiB total,
2,737 MiB used at that instant, driver 616.56. This only establishes hardware
presence. It does not establish peak VRAM, successful Vulkan execution, or
workflow acceptance. Configure headroom and serialize heavy rendering/inference.

## Build, packaging, and licensing

CMake >=3.25, C11/C++23 and pinned GGML are required. Ninja presets exist.
Python is used for model acquisition; the downloader validates byte sizes and
SHA256 hashes from the version-controlled distribution manifest. It downloads
roughly 0.733 GB of F32 model files plus styles. File size is not peak VRAM.
The F32 learned parameter count is 183,148,382. BF16 pose conversion is an
experimental option with documented changed predictions, not a transparent
low-memory fallback.

[Build configuration](https://github.com/localai-org/motion-bricks.cpp/blob/ee0cf5d9035f639ed0787f390fb1ce05d6a4c463/CMakeLists.txt)
has Windows DLL paths. The public CPU packaging report explicitly limits its
measurements to Linux x86-64 and says Windows/macOS were not tested there.
The isolated Windows experiment below must establish actual local support.
Package GGML libraries/backend modules alongside the native library. A native
static archive is not standalone. No installation or production runtime change
is authorized by this proof.

Source code is Apache-2.0. Weights and styles retain NVIDIA Open Model License
terms and NOTICE; do not relabel them Apache or commit/distribute weights in
this application. Preserve the exact [license and notice](https://github.com/localai-org/motion-bricks.cpp/tree/ee0cf5d9035f639ed0787f390fb1ce05d6a4c463/scripts/hf/MotionBricks-G1-GGML)
when following the upstream acquisition/distribution procedure.

## Local proof evidence and decisions

Checkout: `%TEMP%/motion-bricks-transition-20261005`.
Evidence: `%TEMP%/motion-bricks-transition-evidence-20261005`.
Portable tools are isolated and SHA256 checked against official release assets:

| Tool | Pin | SHA256 |
|---|---|---|
| LLVM-MinGW UCRT x86-64 | 20260922 | `e3ad77d117a4bea19a7a3b333341824d79a5a371004a10e25b8504e7b3047666` |
| CMake Windows x86-64 | 4.4.4 | `bace36e94b31c68ab6fa295f26dfa11219e0701cf7c94b0284a7d1cb13dac536` |
| Ninja Windows | 1.13.2 | `07fc8261b42b20e71d1720b39068c2e14ffcee6396b76fb7a795fb460b78dc65` |

The complete configured CPU CTest set passed: 12/12, including actual model
inference and batching (`ctest-cpu.log`, `ctest-cpu.xml`, 7.07 seconds total).
Optional parity/physics fixtures that were not available were not configured;
this is not a claim that every optional upstream test ran. Missing optional
`safetensors` appears in configure output and did not prevent native build or
the real inference tests. The application contract suite contains 13 tests.

Actual Blender 5.2.1 LTS (`9e2066aef7ef`) and its Python 3.13.13 ran the
synthetic exact-G1 proof. No copyrighted animation clips were required. The
fixture authors two original Actions, samples their evaluated poses, sends
both four-frame contexts through the real native model, bakes 40 generated
frames onto the same rig, saves a new Action/.blend, exports glTF, then opens
the saved file in a fresh Blender process, evaluates every frame and renders
eight frames covering both context boundaries. Mixed Euler/quaternion source
channels and their evaluated hashes remain unchanged. Candidate marker/limb
meshes are created entirely by the fixture and are genuinely skinned to the rig.

Results before the final provenance-only rerun are retained in
`blender-proof-preservation/` and `blender-proof-vulkan-final/`. Final execution
evidence uses `acceptance-cpu/` and `acceptance-vulkan/`; inspect their
`summary.json` and stage logs rather than inferring success from file presence.
`provider-candidate.blend`, `provider-candidate.glb`, `request.json`,
`result.json`, `repeated-result.json`, `altered-target-result.json`,
`recovered-result.json`, `bake-metrics.json`, `reopen-metrics.json`,
`source-action-hashes.json` and `candidate-frame-*.png` are preserved there.

| Acceptance item | Method / fixed threshold | Result and evidence |
|---|---|---|
| Real two-sided inference | Change target root by 0.2m; output must change | PASS CPU and Vulkan; altered-target result differs |
| Seed reproducibility | Same backend/model/seed/request, exact root/quaternion arrays | PASS repeated fresh jobs and 30 calls to one loaded model; cross-device identity is not promised |
| Applied Blender data | Every baked and fresh-reopened frame: root <=1e-5m and local rotation <=0.05 degrees | PASS CPU root0m, rotation0.0000354 degrees; Vulkan root0m, rotation0.0000437 degrees |
| Source preservation | Evaluated full source/target Action hashes unchanged before/after bake and reopen | PASS, including mixed Euler/quaternion channel modes |
| Rendering/export | Actual rigged candidate glTF and eight Blender-rendered boundary frames | PASS artifact generation and visible connected rig inspection; no continuous accepted-transition claim |
| Same-timestamp seams | Position <=0.001H; orientation <=1 degree; root velocity <=0.05H/s; angular velocity <=5 degrees/s | FAIL raw generated seams on both devices; detailed metrics below |
| Contacts | Confirmed planted intervals, drift <=0.01H and penetration <=0.005H | NOT VERIFIED for generated candidate; upstream exposes no contact contract and this proof does not invent contact masks |
| Timeout / resource exhaustion | Finite deadline / real child killed after64MiB host limit | PASS structured TIMEOUT/RESOURCE_EXHAUSTED; no accepted partial result |
| Queued/running cancellation | OS lock queue, then real native child above100MiB during loading; kill and wait | PASS; subsequent same request reload reproduces exactly |
| Owner death | Kill owning process while native worker is loading; child must exit <=3s | PASS CPU `owner-death-proof/summary.json`:0.030s; Vulkan `owner-death-vulkan-final/summary.json`:0.065s; no accepted partial result |
| Hardware budget | Actual RTX4070 Vulkan; whole-device <=9216MiB and2048MiB free headroom | PASS isolated provider/Blender workflow and repeated native profiling; not full client neural workflow |
| Neural client acceptance | Accepted seam/contact-gated result through visible transition controls | NOT VERIFIED / integration PARTIAL; capability intentionally has `accepted_transition:false` |
| Packaged provider installation | Clean packaged distribution of native dependencies and model acquisition | NOT VERIFIED; optional pinned setup tool is provided, no weights or native SDK are bundled |

`result.json.boundary_diagnostics` compares source slot3 against generated
slot3 and target slot0 against generated slotN-4 at the **same timestamp**.
Derivatives use one-sided1/30s differences in common canonical world space;
angular velocities use shortest quaternion logarithms. The height is
1.078972995m. These tolerances were fixed before examining outputs.

| Raw neural result | Joint position gap (m) | Joint orientation gap (degrees) | Root velocity gap (m/s) | Angular velocity gap (degrees/s) |
|---|---:|---:|---:|---:|
| CPU entry |0.077521|22.2535|0.038293|91.8627|
| CPU exit |0.073456|27.2603|0.065445|98.4968|
| Vulkan entry |0.077522|22.2535|0.038292|91.8640|
| Vulkan exit |0.073453|27.2603|0.065442|98.4931|

The model genuinely conditions on both boundaries, but the raw result cannot
satisfy the application's accepted transition contract. No retargeted arbitrary
rig, contact guarantee, inferred pose pin, or hidden deterministic fallback is
claimed. The existing transition workflow uses its separately validated native
deterministic stitch provider. MotionBricks capability discovery reports its
real supported operation and marks it unavailable as an accepted transition.
This is deliberately **partial integration**, not completion of a neural
transition feature. Creating a separate demo alone would not satisfy the task;
the application modules and reproducible real-provider tests establish only
the useful verified conversion/execution capability described here.

## Vulkan build and measured resources

The host's actual Vulkan loader and NVIDIA ICD enumerate the RTX4070 (API1.4.351,
driver616.56), so no driver installation was needed. Source-built shaderc avoids
an official CI binary link that returned404. Dependencies are isolated under
the evidence `tools/` directory and pinned to:

- shaderc `ba3e587dbc13d423c713e964ac08e094731a034d`
- glslang `e1b562a8bed273a02f30b59b66a5d499793cede5`
- SPIRV-Headers `04fd3caa1e8267e4d95c806cad901181728e1006`
- SPIRV-Tools `ef96ed763b43b59b33b31b362f09a02b729fa1c9`
- Vulkan-Headers `6802bb4733b63ed5efd3adb308a6c885ef180ea1` (v1.4.363)

The native Windows loader exports supply the isolated MinGW import library;
no installed loader, GPU driver or application was modified. Vulkan CMake
configuration explicitly supplies `Vulkan_INCLUDE_DIR`, `Vulkan_LIBRARY` and
`Vulkan_GLSLC_EXECUTABLE`, with `MOTIONBRICKS_ENABLE_VULKAN=ON`,
`MOTIONBRICKS_CPU_ALL_VARIANTS=OFF`, `MOTIONBRICKS_DOWNLOAD_MODELS=OFF`.
Clang23.1.2's C++ `-O3` compile of `ggml-vulkan.cpp` exceeded600s. Only the
positively identified owned compiler children were terminated. A bounded
retry with `CMAKE_CXX_FLAGS_RELEASE=-O1 -DNDEBUG` succeeded, preserving upstream
source and shader code (`build-vulkan-o1.log`). C compilation remains `-O3`.
The registered Vulkan library SHA256 is
`e0b61e7e7113cf7a65f17343d270dbb3a2b745bfb31d2fae95e56bb599919aa7`.

`native_log_tail` records the actual selected GPU, including
`NVIDIA GeForce RTX 4070`, F16 disabled, and no matrix cores. Explicit Vulkan
selection does not silently fall back to CPU. The provider obtains whole-device
memory from the [NVIDIA NVML API](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlInitializationAndCleanup.html),
sampling approximately every20ms; the dedicated profile samples every10ms.
The initial `nvidia-smi`500ms experiment missed short warm allocation peaks and
is retained as earlier evidence, not used as the final peak measurement.
These are sampled measurements, not proof of an allocator-enforced maximum or
per-process attribution under WDDM. Native allocation errors and sampled
budget overruns cause structured failure with the child terminated and reaped.

| Measured workload | CPU (2threads) | Vulkan RTX4070 |
|---|---:|---:|
| Model load in30-call profile |0.3713s|0.7763s|
| First inference in loaded model |0.1461s|0.0461s|
| Warm inference range (29calls) |0.0763–0.1595s|0.0248–0.0303s|
| Peak host memory in30-call profile |777.54MiB|1130.48MiB|
| Whole-device GPU baseline / sampled peak / after exit |not used|2510.71 /3248.55 /2510.71MiB|
| Repeated fresh GPU worker host memory |not applicable|893.01–894.15MiB|

Measurements are in `profile-cpu/summary.json`, `profile-vulkan/summary.json`,
`profile-vulkan/gpu-samples.json` and each fixture summary. End-to-end isolated
job latency additionally includes hashing733MB of pinned weights, subprocess
startup and validation: final CPU acceptance jobs5.7–12.2s; final NVML Vulkan
acceptance jobs8.3–12.5s on this active workstation. Every successful GPU job
returned to its observed whole-device baseline or within2MiB below it. No unexplained growth appeared across fresh
workers; the retained-model diagnostic's peak is higher and ends with complete
process resource release. These are representative measurements, not a promise
for all rigs, durations, drivers or concurrent workloads.

## Setup, execution, and troubleshooting

Use an isolated trusted compiler/runtime and the exact complete source pin.
Do not copy model files into Git. Upstream weights/styles carry NVIDIA's model
license and NOTICE, separately from source Apache-2.0. `--download-models`
explicitly invokes the pinned upstream downloader with size/SHA256 checks.
For example, after cloning the upstream repository and its exact submodule:

```text
git checkout ee0cf5d9035f639ed0787f390fb1ce05d6a4c463
git submodule update --init ggml
python tools/setup_motion_bricks.py --source <upstream> --output <new-config.json> --compiler-bin <trusted-clang-bin> --ninja-bin <trusted-ninja-bin> --cmake <trusted-cmake.exe> --download-models
```

The last command runs from this application checkout. `--library <built-library>`
registers a separately built native library instead; `--runtime-dir` may be
repeated. Select `--device vulkan` only with a working Vulkan build/runtime.
Registration verifies exact source/submodule state, records library SHA256,
verifies every pinned model component and actually loads the model through the
isolated worker before writing the configuration. Existing configuration files
are never overwritten. Setup commands reuse the application test guardian so
compiler/download descendants are contained on timeout or owner loss.
`setup-owned-proof.json` records the unchanged native-library no-op build and
structured missing-command/timeout checks (0.24s/0.47s). Configure
`ASSET_DIRECTOR_MOTION_BRICKS_CONFIG` with its
absolute path for application capability discovery. Discovery does not load
native code or claim the candidate passed seam/contact acceptance.

Configuration fields `host_memory_budget_mib`, `gpu_memory_budget_mib` (increase
over initial whole-device usage), `gpu_total_limit_mib` (default9216MiB),
`gpu_headroom_mib` (default2048MiB), `threads` and `timeout_seconds` are explicit.
Keep heavy GPU rendering and inference serialized at the application job level;
the provider's OS lock additionally serializes provider jobs across processes.
`python_executable` identifies a standalone worker Python, preventing accidental
launch of `blender.exe -m ...` when invoked from Blender Python. Each job validates
the installation and releases its native process; a process-owner watchdog
also terminates the native child if its owner dies during an ABI call.

Reproduce the real proof from this application checkout:

```text
python -m unittest discover -s tests -p test_motion_bricks_provider.py -v
python tools/motion_bricks_fixture.py --config <config.json> --blender <blender-executable> --output <fresh-evidence-directory>
python tools/motion_bricks_profile.py --config <config.json> --request <evidence-directory/request.json> --output <fresh-profile-directory>
python tools/motion_bricks_lifecycle_fixture.py --config <config.json> --request <evidence-directory/request.json> --output <fresh-owner-death-directory>
```

Set `PYTHONPATH=src` for direct unit discovery. The fixture scripts add it
themselves. Repeat with separate CPU/Vulkan configurations. The tests consume
actual source context and the pinned model; no canned model output, mock binary,
or API-only green response is accepted as native integration evidence.

Actionable failures distinguish absent library/runtime (`MISSING_BINARY`),
absent or mismatched model (`MISSING_MODEL`/`MODEL_HASH`), changed installation
(`INSTALL_IDENTITY`), incompatible conventions/rest geometry, native backend
unavailable, corrupt output, timeout, cancellation and resource exhaustion.
Names here are suffixes of `MOTION_BRICKS_...` codes. Do not select CPU without
disclosing an intentional provider configuration change. Unsupported mappings,
non-root joint translations, non-rigid evaluated transforms, constraints/drivers
or active NLA during candidate baking are rejected instead of silently lost.
Mac/Linux packaging and generic retargeting remain unverified/unsupported.
