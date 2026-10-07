# Copyable research brief

Perform an independent, evidence-based Deep Research review of Blender Asset
Director's implemented MotionBricks offline transition-authoring system.

You are cloud-based. Use the published implementation branch and redacted research
packet on GitHub. You cannot access the workstation or private assets/media. Do
not claim to inspect them. This is a research review, not permission to change,
merge, deploy or replace the implementation.

## Exact sources and reading order

Repository: https://github.com/raal1600/blender-asset-director

Branch: `feature/motionbricks-authoring-20261006`. Begin with
`docs/MOTION_BRICKS_CLOUD_RESEARCH.md` on that branch, then follow its packet links.
Record the exact published commit you inspect. Do not substitute the default
branch. The publication extends the completed local delivery
`5befbde9d25b5dc55aef68fb146732713fbb2441` with documentation only.

Tested application: `5d4a7baaaa9b4f7172ba717cd45fa7433bfd652c`.
Motion/persistence implementation: `5f1b8b89ba2de306c2290f2a1fbfa676ca3c797e`.
Check the actual differences and evidence revision for each claim; source
equivalence is not a claim that every journey was rerun at every later commit.

Combined baseline: PR #31 at `cea64d0ebeaf09302adcf650b83b70d459b12bf9`, on PR #30
at `c5b91b131db8bdc282ee39ee75988f00554f70fe`, on visual-turn ancestor
`f2b39f2e001ebc5c0ddfa32dd08b4b9fd4c2ac07`. Inspect current ancestry rather than
assuming recorded PR status is still current.

Pinned backend: https://github.com/localai-org/motion-bricks.cpp at
`ee0cf5d9035f639ed0787f390fb1ce05d6a4c463`.
GGML: `8c63e70982c95ceb862e3a1073a2c1beef75d60a`.
Weights: https://huggingface.co/LocalAI-io/MotionBricks-G1-GGML at
`cc2a47603dbc203a4f18f35dd06ed3611833f506`.

Read the implementation handoff, input contract, client guide, capability audit,
acceptance matrix, public quality/coverage/benchmark data, procedure source copies
and licensing notices. Follow their code references. Inspect pinned backend
`include/motionbricks/inference.h`, `docs/API-INFERENCE.md`, `src/inference.cpp`,
`src/planner.cpp` and `src/motion_rep.cpp`. Distinguish pinned behavior from newer
upstream developments and historical application failures from repaired behavior.

## Product objective and invariant

Selected native X → separately generated connecting movement → selected native Y.

The system must evaluate actual motion, use real model inference, preserve both
selected native intervals and their timing, and apply the bridge to the intended
character. Native animation names must not determine motion compatibility or
travel. No silent trimming, phase shifts, consumption of Y or native retiming.
Interruption needs an explicit new trim request. Placement is an explicit timeline
composition transform with no double application of object/controller/root motion.

The normal workflow is Generate → Inspect → Refine/compare → Explicitly accept
→ Save/reopen. Generation, failure and cancellation preserve the prior accepted
revision. Preview/render must use the same accepted baked identity. Do not redefine
success as arbitrary human motion, physical simulation or a real-time game engine.

## Evidence discipline

Classify claims as directly inspected source, published redacted runtime reports,
independently reproduced runtime, historical reports, unsupported behavior or
blocked evidence. Published numeric extracts are not independent execution or
visual inspection of private clips. Report unavailable evidence precisely without
pretending the whole source review is blocked.

Audit the reported **40 PASS / 0 FAIL / 0 BLOCKED requirement-row aggregation**.
The unchanged legacy suite is **7 PASS / 3 FAIL**, Beta grid **7 PASS / 2 FAIL**,
and final reference batch **2 PASS / 1 FAIL**. Determine whether any row confuses
successful generation, correct refusal, explained failure or completion of a
procedure. Do not hide a mandatory failure through unsupported reclassification.
Prepared follow-ups do not erase old failures. Rejections are not generation
coverage. Beta is one unseen Action with multiple boundaries, not nine styles.

The local final checks report 811 Python passes, three environment skips,
installer passes and 409 launcher passes. Inspect subsequent public CI separately;
do not equate either source-only tests or remote synthetic fixtures with private
native-client/model/media acceptance.

## Prioritized questions

1. **Neural contribution and useful diversity.** Does bounded seam/contact
   correction preserve meaningful model variation, or dominate the result?
   Examine raw, retargeted, corrected and baked stages, correction limits,
   duplicate thresholds and candidate ranking. Raw/local RMS 10.18° and
   corrected/world RMS 15.40° use different frames/joints; do not divide them to
   infer retention. Propose a common-frame, common-joint comparison and held-out
   tests. Numerical noise and metadata differences are not useful alternatives.

2. **Contact refinement and evaluation independence.** The reported 0.16→0.08 s
   support edit lowers seed42 drift from 31.09 to 5.68 mm with identical neural
   output. Determine whether this improves movement over a fixed physical horizon
   or partly removes difficult samples from the declared planted interval. Audit
   nonempty genuine contact, independent contact evidence, release behavior,
   penetration/sliding outside annotations and fixed-horizon visual/numeric tests.
   Do not assume a smaller contact metric proves better animation.

3. **Generalization and annotation cost.** Separate generic analysis, legitimate
   rig calibration, model restrictions, clip annotations and fixture hardcoding.
   Assess name invariance, independent source/target influence, mapping/rest
   geometry, scale/parent spaces, root ownership and in-place travel ambiguity.
   How much reviewed preparation is required, and is the two-rig coverage enough
   for the claimed domain? Preserve rejection rates and selection history. Motion
   differences outside the four-frame context horizon need not change the bridge.

4. **Correct quality definitions.** Audit same-timestamp one-sided derivatives,
   physical units, common angular frame, reviewed fixed height H and sampling.
   Initial limits are 0.001H/1° position/orientation seams, 0.05H/s/5°/s velocity
   seams, 0.01H planted drift and 0.005H penetration. Inspect fixed acceleration,
   speed, joint and correction limits in `upright-grounded-kinematic-v2`, plus
   240 Hz production/480 Hz diagnostics and possible between-sample failures.
   Distinguish kinematic plausibility from dynamic balance and naturalness.
   Static frame inspection and automated playback are not human artistic approval.

5. **Safe longer-sequence authoring.** Inspect immutable candidate separation,
   dependency completeness, stale jobs, atomic acceptance, exact restore,
   cancellation, recovery/quarantine and preview/render identity. An early edit
   must invalidate the affected downstream chain without silently accepting it.
   Does accumulated placement or quality deteriorate despite local seams? The
   demonstrated requested sequence is walk_back→walk_left→idle→walk, with three
   real joins and explicit reviewed preparation.

6. **Actual latency bottlenecks.** Compare the public per-run traces and sample
   identities. Reported warm inference is 24.16 ms (87 calls), but three-candidate
   batches take 127–130 s and complete four-clip jobs about 84.3 s. Investigate
   evaluation, hashing, startup, correction, reopening and export first. Keep
   32 preview samples/frame unless parity/error bounds justify a change. A
   persistent-worker proposal must earn its complexity and preserve bounded
   memory/lifetime, serialization, cancellation, crash isolation, release and a
   per-job fallback. No p95 from tiny samples or real-time claim from warm inference.

7. **Backend boundaries and effective controls.** Verify G1 mapping, four frames
   per side, 30 FPS, N=24,28,…,64, bridge duration (N−7)/30, generated-only retiming
   0.85–1.15 and sparse masks. Check argmax seed invariance versus fixed-temperature
   Gumbel sampling. Conditioning is soft. Unconstrained target placeholders are
   not locks. Contact cleanup and channels outside G1 are deterministic processing.
   Do not recommend prompts, paths, hard pins or knobs absent from the interface.

8. **Licenses and resources.** Verify application MIT, backend Apache-2.0, GGML
   MIT and separately licensed weights plus native/runtime obligations. Preserve
   asset privacy. The RTX 4070 measurements use monitored budgets: 9216 MiB whole
   GPU, 8192 MiB provider increase, 2048 MiB headroom and 2048 MiB provider host.
   These are not hard allocator caps, and whole-device interference matters.

## Research method and requested output

Use primary sources: inspected code, official documentation, papers and relevant
upstream issues. Cite exact versions, dates and links. Focus on gaps that could
change this architecture, not a generic motion-generation survey. For each
technique explain the failure it addresses, interface compatibility, application
work versus backend change/retraining, cost, expected benefit and needed evidence.

Deliver:

1. A direct verdict and exact access/source inventory.
2. A claim-by-claim audit with evidence/revision, finding, confidence, limitation
   and next check, explicitly reviewing the aggregate acceptance count.
3. Prioritized findings with precise code references and primary-source support.
4. A minimal falsification plan: hypothesis, controlled variables, fixtures,
   measurements, predeclared pass/fail criteria, resource cost and the decision
   each experiment changes. Keep thresholds fixed before viewing outcomes.
5. A roadmap separating correctness repairs, broader validation, useful authoring
   improvements, performance work and optional longer-term research.
6. A defensible supported-domain statement and next-cycle completion gates.

Lead with issues most likely to invalidate the approach or acceptance claims.
Do not rubber-stamp narrow successes, discard useful evidence merely because it
is finite, or represent inaccessible private playback as inspected.
