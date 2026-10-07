# MotionBricks implementation evidence — working handoff

This record is **IN PROGRESS, NOT ACCEPTED**. No Deep Research was launched.
Mandatory generalization and complete native-client journeys remain unfinished.
Do not treat historical continuity passes or unit tests as production readiness.

Latest additions to the evidence record: f30b389 verifies native contact
refinement, accepted render/playback and preview parity; the same revision's
Beta grid passes seven of nine explicit interval pairs on the second rig.
a08e46d fixes fixture contact timestamps for the now-passing 60 FPS case.
0c804ca proves exact before/after motion parity for the measured sole-height
optimization. Exact full revisions and evidence paths are in the audit and
acceptance matrix. The older native observations below remain historical scope;
they do not stand in for a final delivery run. The mandatory four-clip and final
multi-join/fault/performance gates are still open.

## Revisions and isolation

The implementation branch is `feature/motionbricks-authoring-20261006` in the
isolated `blender-asset-director-motionbricks-authoring` worktree. The latest
committed native-client evidence currently identifies
`95234c3528bfd1c288f6670ca701c4789b0a1aff`: the reference now has two passing
stochastic alternatives, explicit acceptance, exact restore, native restart,
preview parity, actual OptiX rendering and retained-movie playback. Its initial
movie harness clicked the seek rail; the separate native playback retry passes
on the unchanged rendered artifact. The preceding 4e45674 build exposed and
retained a real stale-draft refresh failure, fixed at 95234c3. Native b23e76d
evidence verifies attempt identities, numerical candidate diversity, stale
completion, active cancellation, provider crash and interrupted-job recovery.
Those earlier b23e76d candidates all failed quality. A final delivery must
replace this paragraph with its exact final tested source/build receipt.

The inspected combined baseline is #31
`cea64d0ebeaf09302adcf650b83b70d459b12bf9`, descending from #30
`c5b91b131db8bdc282ee39ee75988f00554f70fe`, itself descending from the visual-turn
feature at `f2b39f2e001ebc5c0ddfa32dd08b4b9fd4c2ac07`. Both PRs were open drafts
when inspected. This is not a default-branch-only implementation. Existing
history, production installation and original assets were preserved; no push,
merge or deployment occurred.

Backend: `localai-org/motion-bricks.cpp@ee0cf5d9035f639ed0787f390fb1ce05d6a4c463`.
GGML: `8c63e70982c95ceb862e3a1073a2c1beef75d60a`.
Weights: `LocalAI-io/MotionBricks-G1-GGML@cc2a47603dbc203a4f18f35dd06ed3611833f506`.
Actual loaded Windows DLL SHA-256:
`e0b61e7e7113cf7a65f17343d270dbb3a2b745bfb31d2fae95e56bb599919aa7`.
The worker checks the loaded module path/hash and model-file hashes. Build and
device evidence is described in the capability audit; pins were not upgraded.

## Architecture and code entry points

- `src/asset_director/motion_bricks_contract.py`: supported domain, context
  timestamps, output lengths, generated-only retiming, sampling/contact plans.
- `motion_bricks_analysis.py`, `motion_bricks_retarget.py`: evaluated support,
  in-place ambiguity, reviewed rest geometry and anatomical calibration.
- `motion_bricks_timeline.py`: versioned evaluated dependencies, real request,
  raw/retargeted/corrected artifacts, predicted placement and generated bake.
- `motion_bricks_provider.py`, `motion_bricks_worker.py`: isolated real C ABI,
  exact pins, monitored budgets, cancellation and actual loaded DLL identity.
- `motion_bricks_feet.py`, `motion_bricks_refinement.py`: deterministic bounded
  bridge processing. These are application corrections, not neural features.
- `motion_bricks_spline.py`, `motion_bricks_world_refinement.py`: continuous
  clamped cubic smoothing with vector curvature bounds and bounded numerical
  convergence. Sampling density changes the numerical penalty, not the objective
  or quality limits. Failed convergence/correction is an explicit refusal.
- `motion_bricks_validation.py`, `motion_bricks_quality.py`: common-time seams,
  actual planted landmarks, dense baked kinematics and hard gates before rank.
- `launcher/lib/transition-review.mjs`, `checkpoint-job.mjs`: immutable candidates,
  working fingerprints, atomic acceptance, exact restore, interrupted-job
  quarantine and existing writer/process ownership.
- `launcher/public/action-timeline-*.mjs`, `transition-comparison.mjs`: normal
  authoring controls and physical-time A/B review aligned at the source stitch.

The accepted checkpoint remains usable while working candidates generate or
fail. Three alternatives use the verified fixed-temperature Gumbel sampler;
argmax seeds do not vary motion. Contact controls alter derived bridge processing
and request identity, not C ABI conditioning. Stationary intent is restricted to
evaluated stationary root travel. Travelling in-place preparation still requires
reviewed derived data; a complete preparation editor is not implemented.

An early-join change makes the complete working timeline dependent on new timing
and placement. Generation creates a complete candidate checkpoint; it does not
silently accept downstream joins. Normal preview/render resolves the accepted
checkpoint. Candidate comparison identifies its separate baked source.

## Evidence classification

Private evidence is local under
`Documents/AssetDirector-MotionBricks-Authoring-20261006`. Evidence names below
refer to that directory. Assets, databases, model files and images are not in Git.

Verified runtime observations:

- `baseline-sampling/report.json`: ten fresh real Vulkan workers; same settings
  repeated exactly on this device; argmax seed changes exactly equal; stochastic
  seed changes materially different; independent source/target influence and
  near invariance to unconstrained target XY placeholders.
- `corrected-diversity-comparison.json`: earlier cleanup retained roughly
  7.14/7.24 degrees RMS joint differences between seeds. The later actual
  `native-accept-95234c3/report.json` measures 15.40 degrees RMS corrected world
  joint difference between its two quality-passing candidates. Raw model-local
  and corrected world rotations use different joint sets/frames; their RMS
  values are not a correction-attenuation ratio. The six-job benchmark repeats
  each seed twice with exactly equal raw and corrected arrays on this device.
  No cross-device bitwise reproducibility claim.
- `native-accept-95234c3`, `native-playback-95234c3-r2`: explicit candidate
  acceptance, exact history restore, identical accepted preview after native
  restart, actual render and 1x movie playback. The retained first movie click
  failure was a harness seek-rail click. `preview-parity.json` and
  `agent-visual-review.json` bind the accepted Blender file, GLB, all 72 rendered
  frames and encoder receipt. Static agent inspection, automated temporal
  playback and absent human artistic approval are identified separately.
- `native-review-9474cca/report.json`: actual visible Windows host/WebView2;
  three model-generated candidates; accepted checkpoint preserved; two real
  candidate previews and synchronized full-speed controls exercised. All
  candidates failed quality. No successful acceptance/render journey follows
  from this report. The preceding `native-review-91cb591` comparison failed and
  remains retained as historical evidence of the repaired initialization bug.
- `stage1-provider/summary.json`: real ABI, synthetic G1 bake/reopen, provider
  cancellation/timeout/host-budget refusal and recovery. This is not independent
  second-rig retargeting coverage or artistic approval.

Current failures and missing evidence:

- Reference argmax and stochastic seeds 7/42 now pass the fixed quality gates;
  seed 1234 still fails penetration. Independent Beta generation preserves
  native intervals but its tested durations/seeds fail correction limits.
  No quality-pass second-rig or unseen-pair coverage is established yet.
- `dense-quality-convergence.json` falsifies a 60 Hz apparent pass: the same
  repeated-clip bake fails at 240/480 Hz. Dense endpoint acceleration is a real
  historical failure, separate from the repaired seam derivative estimator.
  Later bounded continuous correction passes the reference; convergence must
  still be demonstrated across the required broader coverage. Thresholds were
  not loosened.
- The Beta grid now supplies seven hard-quality passes on a second calibrated
  rig; broader generalization, four-clip reconciliation and native E remain
  outstanding. Native B is verified at f30b389. Native A
  now has the evidence above; C/D have earlier native fault/staleness evidence
  requiring final-build regression. The inspected Arabic-Warrior GLB is an unrigged static
  mesh, not second-rig evidence. Rejected clips do not count as successful
  generation coverage.
- Acceptance/restore/recovery/corruption tests using synthetic transport verify
  persistence logic only. The native acceptance and b23e76d fault evidence are
  separate; the entire mandatory fault matrix is not yet complete.

Unsupported scope remains arbitrary human motion, terrain/jumps, airborne or
unstable contact boundaries, negative/nonuniform scale, unreviewed rigs, exact
endpoint model pins, text prompts, arbitrary target trajectories and real-time
game behavior. Kinematic checks do not establish physical feasibility.

## Reproduction and evidence gates

Run `python tools/run_checks.py --offline` from the source root and `node --test`
from `launcher`. Use the configured real Python executable; this workstation's
Store alias was not a working Python installation. For real motion:

```text
python tools/run_motion_bricks_sequences.py --manifest <local-reviewed-manifest.json> --blender <blender.exe> --output <new-evidence-directory>
```

The runner now distinguishes continuity from the full kinematic gate and returns
failure when quality fails. It still reopens structurally valid failed candidates
in a fresh process to verify preservation/persistence. Historical runner PASS
rows covered their explicitly narrower continuity scope.

Native harnesses are retained locally as `native_review_9474cca.mjs` and its
isolated installation receipt `candidate-9474cca.json`. They bind CDP to the owned
visible Windows executable and verify loopback listener ancestry. They are not
ordinary standalone Chromium tests. The final harness/build must be rerun from
the final clean commit. No CI artifact is claimed for local-only work.

Consult [the acceptance matrix](motion-bricks-acceptance.json),
[the client guide](MOTION_BRICKS_CLIENT_RECONCILIATION.md),
[input/provenance contract](MOTION_BRICKS_INPUT_CONTRACT.md), and
[benchmark record](MOTION_BRICKS_BENCHMARKS.md). A final shareable evidence
manifest must retain hashes and redacted identities without copying private
assets or workstation playback into Git.

## Licensing and later research priorities

[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) distinguishes application MIT,
backend Apache-2.0, GGML MIT, and NVIDIA weight terms. Setup retains the actual
pinned license texts and hash receipts; compiler/runtime redistribution notices
remain tied to the actual build. No private asset license follows from those
software licenses.

The next research review should first try to falsify these hypotheses:

1. Alternating contact projection and endpoint baking can produce bounded,
   densely sampled acceleration without excessive correction or loss of neural
   variation. Compare raw, retargeted, corrected and baked trajectories, including
   the first/last quarter-frame segments; do not rely on frame-rate samples.
2. The anatomical calibration and cleanup generalize to an independently reviewed
   second rig. Explicitly report rejected clips and unknown rest-plane cases.
3. In-place root intent and contact ambiguity can be resolved with reasonable
   user annotation, without name heuristics or native-curve edits.
4. Passing individual joins remains meaningful across accumulated placements and
   complete multi-clip playback. Local seam passes alone are insufficient.
5. Evaluated Blender contact/retarget processing and preview export dominate
   latency. Measure before reducing validation or adding a persistent worker.

These are unresolved questions, not conclusions. The implementation goal remains
active until its mandatory gates are satisfied or precise external blockers are
reported alongside the work actually verified.
