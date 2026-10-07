# MotionBricks implementation evidence — working handoff

This record is **IN PROGRESS, NOT ACCEPTED**. No Deep Research was launched.
Mandatory quality and complete native-client acceptance remain unfinished.
Do not treat historical continuity passes or unit tests as production readiness.

## Revisions and isolation

The implementation branch is `feature/motionbricks-authoring-20261006` in the
isolated `blender-asset-director-motionbricks-authoring` worktree. The latest
committed native-client evidence currently identifies
`b23e76d1e4e75f1ace63ffed8dcb058846551b8d`; subsequent explicit measured hinge
calibration and correction experiments are under investigation. Native b23e76d
evidence verifies attempt identities, numerical candidate diversity, stale
completion, active cancellation, provider crash and interrupted-job recovery.
All candidates still failed quality. A final delivery must replace this
paragraph with its exact tested source/build receipt.

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
  7.14/7.24 degrees RMS joint differences between seeds. **Final cleanup diversity
  still needs retesting.** No cross-device bitwise reproducibility claim.
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

- Reference and unseen-pair generation preserve native intervals but fail
  acceleration and, in some experiments, contact/correction limits.
- `dense-quality-convergence.json` falsifies a 60 Hz apparent pass: the same
  repeated-clip bake fails at 240/480 Hz. Dense endpoint acceleration is a real
  unresolved acceptance issue, separate from the repaired seam derivative
  estimator. Thresholds were not loosened.
- Two independent verified humanoid rigs, all required generalization cases,
  four-clip reconciliation, native A–E journeys and complete accepted rendering
  remain outstanding. The inspected Arabic-Warrior GLB is an unrigged static
  mesh, not second-rig evidence. Rejected clips do not count as successful
  generation coverage.
- Acceptance/restore/recovery/corruption tests using synthetic transport verify
  persistence logic only. Real native-client fault and acceptance journeys are
  separate mandatory gates.

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
