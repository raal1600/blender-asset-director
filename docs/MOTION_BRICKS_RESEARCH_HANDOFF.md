# MotionBricks offline authoring — research handoff

**Cloud readers:** start with the [public research entry point](MOTION_BRICKS_CLOUD_RESEARCH.md).
The subsequent source/documentation publication adds redacted numerical results
and procedure source copies for GitHub-only review. Private paths below identify
retained local evidence and are not public links. The original delivery chronology
remains unchanged; publication is not a new application/runtime test or release.

This is an evidence handoff for a later review, not a Deep Research result.
No Deep Research, broad research, model upgrade, push, merge or deployment was
performed. The supported offline authoring path works on the reviewed fixtures;
it is not a claim of universal motion quality, physical validity or real-time
game behavior. Failed candidates and legacy scenario failures remain recorded.

## Exact source, build and isolation

Branch: `feature/motionbricks-authoring-20261006`. Runnable application revision:
`5d4a7baaaa9b4f7172ba717cd45fa7433bfd652c`. Later commits on this branch may update
only this evidence documentation; use the isolated build receipt to identify
the executable runtime. Final native host SHA-256:
`fdc1f89f4869e023a557246ed05c4bdba0dd7f5b084e44b32ba04408a1eec6da`.

The runnable isolated client is under the private evidence root at
`Studio-review-5d4a7ba/SystemRuntime/Launcher/Asset Director.exe`. Its copied
project retains the accepted reference, candidate history and rendered movie.
`Studio-review-5f1b8b8` retains the accepted four-clip scene. Launching either
does not replace the main installation. `delivery-inventory-v1.json` verifies
all 335 installed runtime/host files against the creation receipt and the final
accepted reference hash. `FINAL-DELIVERY.json` records the subsequent documentation
commit and clean-head local checks separately from the tested runtime revision.

The inspected baseline is PR #31 at
`cea64d0ebeaf09302adcf650b83b70d459b12bf9`, descending from PR #30 at
`c5b91b131db8bdc282ee39ee75988f00554f70fe`, itself descending from the visual-turn
branch at `f2b39f2e001ebc5c0ddfa32dd08b4b9fd4c2ac07`. Both PRs were open drafts
when inspected on October 6, with heads equal to the supplied references. This
does not assert their remote state has remained unchanged. Work used the combined
feature ancestry, an isolated worktree, copied assets and candidate installations.
Original production assets, existing history and the main installation remain
untouched. Local commits are not published CI or release artifacts.

Motion, persistence, tools and preview/render source trees at the final revision
are byte-identical to `5f1b8b89ba2de306c2290f2a1fbfa676ca3c797e`; the only subsequent
application change displays hard-gated candidate rankings. The exact tree proof
is `runtime-scope-identity-5d4a7ba-v1.json`. Runtime evidence below identifies its
actual tested revision rather than relabeling older runs as new executions.

| Dependency | Inspected and loaded identity |
| --- | --- |
| motion-bricks.cpp | `ee0cf5d9035f639ed0787f390fb1ce05d6a4c463` |
| GGML | `8c63e70982c95ceb862e3a1073a2c1beef75d60a` |
| LocalAI-io/MotionBricks-G1-GGML | `cc2a47603dbc203a4f18f35dd06ed3611833f506` |
| Actual Windows DLL SHA-256 | `e0b61e7e7113cf7a65f17343d270dbb3a2b745bfb31d2fae95e56bb599919aa7` |

The worker verifies the loaded module path/hash and every pinned model component,
not only configuration strings. The reused Windows build is Vulkan enabled,
C++ `-O1 -DNDEBUG`, C `-O3 -DNDEBUG`, CPU variants disabled. The inspected source
includes `inference.h`, `API-INFERENCE.md`, `inference.cpp`, `planner.cpp` and
`motion_rep.cpp`. No backend or weight revision changed during this work.

## Architecture and review workflow

Selected native X → real neural bridge → selected native Y. The four context
frames on each side span 0.1 seconds at internal 30 FPS. Only those contexts
condition the model; differences outside that horizon need not change the
bridge. Valid output lengths are 24, 28, …, 64 including context. Native bridge
duration is `(N-7)/30` seconds, with generated-only retiming bounded to 0.85–1.15.
The adapter retains the documented sparse masks and predicted destination
placement. Unconstrained target-position placeholders are not target locks.
Conditioning is soft; deterministic bridge correction supplies bounded seams.

The client workflow is select connection → generate → inspect/compare → refine
→ explicitly accept → save/reopen. Three alternatives use verified Gumbel
sampling at backend-fixed temperature 1. Argmax seeds do not create alternatives.
The quality order includes only current, verified, nonduplicate candidates with
every join passing every hard gate. A score cannot compensate for a failure.
Tied scores share a rank; ranking is a kinematic review aid, not artistic approval.

Working requests, attempts, candidates, validation reports and acceptance events
are distinct. Candidate generation does not replace the accepted checkpoint.
Acceptance revalidates dependencies and artifact hashes under existing atomic
project persistence. Repeated acceptance is idempotent for the same event;
another acceptance event for an already accepted candidate is refused. Restoring
history selects the exact prior artifact. Interrupted outputs are quarantined.
Cancellation and provider failure terminate owned processes, not just UI labels.

An early join change identifies the affected downstream chain and generates a
complete working timeline. Downstream motion is not silently accepted. A/B review
uses one physical clock aligned at the selected source stitch, labels differing
durations/target stitches and does not time-warp either side. Candidate previews
are explicitly unaccepted; normal rendering resolves the accepted checkpoint.

In-place ambiguity is explicit. Reviewed stationary intent cannot erase native
root travel. Travelling in-place motion uses separately reviewed derived root data,
preserving original Actions and bone curves. The client imports and reviews that
prepared checkpoint before continuing. A complete interactive root-preparation
editor is not implemented. Contact controls persist reviewed support sides and
intervals and alter bounded bridge cleanup; they do not change C ABI conditioning.
No decorative sliding slider, arbitrary trajectory, waypoint, prompt, precision
or heading-lock control is advertised.

## Code references

| Responsibility | Source |
| --- | --- |
| Input schema, model timing, physical boundary kinematics | `src/asset_director/motion_bricks_contract.py` (`boundary_motion`, context/contact policies) |
| Evaluated input/root/contact analysis | `motion_bricks_analysis.py`, `root_contact_preparation.py`, `native_basis_contract.py` |
| Reviewed anatomical mapping and rest/hinge calibration | `motion_bricks_retarget.py`; `tools/inspect_motion_bricks_hinges.py`, `prepare_motion_bricks_rig.py` |
| Separate raw, retargeted, corrected and baked artifacts | `motion_bricks_timeline.py`; `action_timeline.py`, `action_layer.py` |
| Isolated C ABI, loaded DLL checks and monitored budgets | `motion_bricks_provider.py` (`execute`), `motion_bricks_worker.py` (`Native`) |
| Bounded bridge-only correction | `motion_bricks_feet.py`, `motion_bricks_refinement.py`, `motion_bricks_spline.py`, `motion_bricks_world_refinement.py` |
| Hard kinematic gates and correction diagnostics | `motion_bricks_quality.py`, `motion_bricks_validation.py` (`evaluate`) |
| Immutable candidates, atomic acceptance and recovery | `launcher/lib/transition-review.mjs`, `checkpoint-job.mjs`, `action-layer.mjs`, `runtime.mjs` |
| Actual review, contact editing, ranking and A/B | `launcher/public/action-timeline-*.mjs`, `transition-review-view.mjs`, `transition-comparison.mjs`, `workbench-action.mjs` |
| Preview identity and physical playback | `src/asset_director/action_preview.py`, `viewer_sampling.py`; `launcher/lib/embedded-preview.mjs` |

Python filenames without prefixes in this table are under `src/asset_director`.
The request/result schema and provenance fields are described in
[MOTION_BRICKS_INPUT_CONTRACT.md](MOTION_BRICKS_INPUT_CONTRACT.md).

## Current runtime evidence and failures

Private evidence root `R` is
`C:/Users/ramis/Documents/AssetDirector-MotionBricks-Authoring-20261006`.
Git contains only the [acceptance matrix](motion-bricks-acceptance.json),
[redacted manifest](motion-bricks-evidence-manifest.json), code and documentation.
Private assets, model binaries, databases, images and raw workstation logs remain
local. Report hashes bind the observations; accessible local evidence was
actually inspected. No unavailable historical playback is claimed as inspected.

| Claim | Actual evidence and limits |
| --- | --- |
| Final native A and ranking | `native-ranked-5d4a7ba-v1`: three real alternatives, two hard passes, one penetration failure; quality ordering, physical A/B, explicit accept, exact restore and native reopen pass. |
| Final native render/parity | `native-render-ranked-5d4a7ba-v1`, `native-playback-ranked-5d4a7ba-v1`, `native-parity-ranked-5d4a7ba-v1`: accepted hash `977dcff8230c5f7c6474b9ab85b96e892d52eed30a9e8b2534ee99d8f53ff470`; 72 frames, 24 FPS, OptiX, actual media ID, complete 1x playback. Maximum GLB/fresh-Blender skin error 0.01183 mm and orientation error 0.14951°. |
| Native B | `native-contact-5f1b8b8-v1`: support windows 0.16 → 0.08 s; seed42 drift 31.09 → 5.68 mm, identical neural request/raw arrays; comparison, explicit refined acceptance and restart. Two refined alternatives pass, one remains rejected. |
| Native C/D and faults | `native-lifecycle-5f1b8b8-v1`: stale completion, actual cancellation (0.78 s), owned provider crash, launcher restart during generation, interrupted-output quarantine, duplicate motion, corrupted unaccepted artifact refusal, acceptance-event idempotency and reopen. Prior accepted result survives. |
| Final cancellation repeat | `native-cancellation-5d4a7ba-v2`: three cancellations, median/max 0.782/0.790 s, owned process release, accepted hash preservation and normal native exit. The first harness's shutdown timeout and safe recovery remain retained separately. |
| Native E | `native-multi-2cd8ed9-v1`: prepared checkpoint review, four full native intervals, three real joins, early duration change, explained downstream chain, selected-join A/B with differing durations, explicit complete acceptance, exact restore and reopen. Earlier missing review controls and failed procedures remain retained. |
| Current four-clip regression | `native-render-four-5f1b8b8-v1`, `native-parity-four-5f1b8b8-v1`: accepted hash `9596edda74e1f58da7d646c170da983ac4b0b95078a878bf76fa4e59a3775ea6`; three joins, 176-frame saved scene/render, 1x native playback; maximum skin error 0.01183 mm/orientation 0.16106°. All 176 frames inspected. The scene end can retain padding beyond the last selected interval; native intervals are not retimed to fill it. |
| Second rig and independent influence | `beta-boundary-grid-f30b389-v1`: seven of nine predeclared trim pairs pass on independently calibrated 65-bone Beta at scale 0.01. Two fail correction/support limits (22.2% rejection in this small grid). Independent source and target boundary changes affect raw and corrected motion. This is one unseen Action with distinct explicit intervals, not nine independent motion styles. |
| Final second-rig regression | `soles-pipeline-final-v1`: three real repeats per rig on 5f1b8b8, all quality/preservation/reopen passes; exact raw/corrected/baked parity to prior revisions. `dense-final-quality-v1` passes 480 Hz diagnostics for Beta center and all three accepted native four-clip joins. |
| Label, timing and transform tests | `rename-generation-v1`: opaque Action renaming leaves model request/raw/corrected output equal. Final broader rerun covers 24/30/60 FPS and root offsets; `translated-parent-5f1b8b8-v2` and `scaled-parent-5f1b8b8-v2` pass supported parent spaces. Reparenting that changes calibrated rest geometry is refused. |
| Early refusals | `context-refusal-5f1b8b8-v1`, `native-domain-refusals-5f1b8b8-v2`: insufficient real context, airborne/mixed support and invalid mapping refused before model artifacts; originals preserved. |
| Resource/model faults | `provider-faults-5f1b8b8-v3`: unavailable model, safely reduced admission/host budgets, actual worker exit and healthy Vulkan recovery; installed config unchanged. Earlier procedure errors remain recorded, including Windows retained process-memory counters and sandbox Git identity lookup. |

The unchanged ten-case legacy suite at 5f1b8b8 is **7 PASS / 3 FAIL**. Six are
successful generated scenarios and one is an expected heading refusal. The three
failures are unprepared `idle→walk`, `walk→idle`, `walk→run` requests rejected for
root-intent ambiguity. Their assertions and failure reports were not overwritten.
`qualified-broader-5f1b8b8-v1` then passes two new, explicit full-interval requests
using reviewed derived walk preparation, plus correct refusal of the run entry
for unstable contact. `broader-reconciliation-5f1b8b8-v1.json` binds this triage.
Neither unprepared nor airborne refusals count as successful generation coverage.
The broader matrix row records rerun and reconciliation under the requested input
contract, not an assertion that the unchanged legacy runner is wholly green.

Raw and corrected stages retain separate metrics. Raw contact measurements are
unavailable where evaluated skin/contact evidence is absent; they are not zero
error. Head/finger/toe interpolation and IK/spline processing outside G1 are
deterministic corrections. Fixed limits include 0.001H/1° seams, 0.05H/s/5°/s
velocity seams, 0.01H planted drift and 0.005H penetration. H comes from reviewed
rest calibration. One-sided cubic derivatives share the stitch timestamp and
common world rotational frame, with h=1/1536 s. Final baked quality uses 240 Hz;
480 Hz is an additional check, not a loosened preset. Acceleration, speed, knee
and correction limits are fixed in `upright-grounded-kinematic-v2`.

All 72 final reference and 176 current four-clip rendered frames were inspected
as contact sheets with feet/whole character visible. Full-speed native playback
and static agent inspection are separately identified. The Beta center's 60
frames were statically inspected; `beta-movie-playback-v1` additionally verifies
1x playback to the end of its two-second movie in an isolated visible browser.
That auxiliary browser test is not substituted for native-client acceptance.
No human artistic approval, dynamic balance or general naturalness is claimed.

## Diversity, reproducibility and performance

Pinned planner source and ten initial real-worker experiments establish that
argmax ignores seed variation. Gumbel samples differ materially. The final two
hard-valid alternatives differ by 15.40° RMS in corrected world rotations;
their raw model-local rotations differ by 10.18° RMS. Different joint sets and
frames make those numbers unsuitable as an attenuation ratio. Fixed requests
repeat exactly on this tested device, including final two four-clip candidates
that the client labels near duplicates. Numerical noise is not useful diversity.
There is no cross-device bitwise promise; only Vulkan is profiled here.

[MOTION_BRICKS_BENCHMARKS.md](MOTION_BRICKS_BENCHMARKS.md) links raw stage traces.
Three newly loaded models have median first inference 34.92 ms; 87 same-model
warm calls have median 24.16 ms. Production remains per-job isolated, with no
persistent-model service. Native three-candidate batches take about 127–130 s;
two identical complete four-clip jobs reach review in 84.29/84.32 s. Ten actual
uncached preview jobs have median/max 12.38/17.63 s across differing sources;
three fixed-source cached comparison openings take 1.45/1.46 s median/max.
These small samples do not justify p95 claims or latency guarantees.

An exact-parity sole-height optimization changes selected evaluated vertex work,
not sampling density. Three identical complete runs per rig per revision give
reference median 46.41 → 46.18 s and Beta 41.48 → 33.96 s from baseline to final.
The 32 evaluated samples per preview frame remain unchanged. Per-stage traces
show substantial work outside native inference: context/evaluation, model hashing,
contact correction, fresh reopening and preview export. No validation was removed.

Verified workstation: Windows 11 Home, RTX 4070 12,282 MiB, driver 616.56, about
31.85 GiB RAM, Blender 5.2.1 LTS `9e2066aef7ef`. Monitored budgets remain whole
GPU 9,216 MiB, provider increase 8,192 MiB, headroom 2,048 MiB and host 2,048 MiB.
Final eight-job native traces observe provider host peaks 877.94–880.04 MiB and
whole-device peaks 2,964.62–3,058.50 MiB. NVML includes unrelated desktop use and
can miss short peaks; these are monitored budgets, not hard allocator caps.

## Reproduction and classification

Use fresh output directories; never overwrite failed evidence. Commands use the
configured standalone Python, Node, Blender and FFmpeg binaries, with no downloads.

```text
python tools/run_checks.py --offline
node --test                         # cwd launcher
python tools/run_motion_bricks_sequences.py --manifest <R>/broader-scenarios-manifest-v1.json --blender <blender.exe> --output <fresh-folder>
python tools/run_motion_bricks_sequences.py --manifest <R>/qualified-broader-manifest-v1.json --blender <blender.exe> --output <fresh-folder>
python tools/motion_bricks_profile.py --config <provider.json> --request <reviewed-request.json> --output <fresh-folder>
node <R>/native_cancellation_5d4a7ba_v2.mjs
node <R>/native_ranked_5d4a7ba_v1.mjs
node <R>/native_contact_5f1b8b8_v1.mjs
node <R>/native_lifecycle_5f1b8b8_v1.mjs
node <R>/native_multi_2cd8ed9_v1.mjs
```

The dated private harnesses intentionally assert fresh outputs and specific
isolated fixture baselines. To repeat, create a new candidate installation/copy
and change only its input/output roots. Their build receipts, scripts, reports
and hashes are in R and the redacted manifest. Native harnesses attach to the
owned visible Windows/WebView2 host and verify its loopback listener ancestry.
They do not substitute standalone Chromium for native application testing.
Portable checks pass 814 tests (811 passed, three disclosed environment skips)
plus installer checks; launcher tests pass 409/409. Local results are not CI.

Verified current runtime: the paths and bounds above. Implemented but not covered
by this runtime matrix: CPU performance/reproducibility, every possible supported
rig/constraint combination and cross-device equivalence. Reported historical
evidence: the original October 5 workstation results, plus all earlier failed
repair attempts retained in the chronological capability audit. Unsupported:
arbitrary rigs, negative/nonuniform scale, changing parent spaces, terrain/jumps,
airborne/unstable boundaries, arbitrary target trajectories, text prompting,
hard endpoint pins and real-time game-engine behavior. No external-access blocker
was encountered for these local fixtures. Private fixtures are required to repeat
their exact claims elsewhere; no redistribution right is implied.

## Licensing and next research priorities

[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) and setup receipts distinguish
application MIT, backend Apache-2.0, GGML MIT and NVIDIA Open Model License weights.
The pinned weight license/notice and upstream attribution are retained by setup.
Redistribution must preserve the applicable agreement, attribution, notices and
actual compiler/runtime/Vulkan/WebView2 components' terms. Code licensing does
not relicense weights or private assets. No model/native/private asset binaries
are included in Git.

Prioritized falsification work for the later review:

1. Determine whether useful variation survives correction across substantially
   more held-out motions, not just these two rigs and selected intervals. Keep
   raw/local and corrected/world comparisons in consistent frames before drawing
   attenuation conclusions.
2. Expand independently reviewed rigs and rest geometries. The Beta grid's two
   retained failures and rejected uncertain hinge calibrations matter as much as
   its seven passes; do not generalize from the reference alone.
3. Measure the annotation effort needed to resolve in-place travel and contacts.
   Current preparation is explicit derived data; no reliable automatic inference
   of intended travel from stationary roots has been demonstrated.
4. Test longer sequences and accumulated placement. Three accepted joins with
   dense local gates and full-scene playback do not establish arbitrary-length
   quality or physical plausibility.
5. Profile end-to-end workloads before caching models or reducing evaluation.
   Investigate correctly invalidated preparation/hash/preview caches, with actual
   cancellation, resource admission and crash recovery. Keep the isolated worker
   as the operational fallback. Do not equate warm 24 ms inference with authoring
   responsiveness.

This handoff supports a scoped evidence-based review. It does not declare the
system universally production-ready or the unresolved research questions solved.
