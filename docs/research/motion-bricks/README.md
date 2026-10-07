# Public research packet

This packet supports a GitHub-only review of the completed local implementation.
Its scope and access limits are in [the cloud entry point](../../MOTION_BRICKS_CLOUD_RESEARCH.md).

## Reading order

1. [Research brief](RESEARCH_PROMPT.md): questions, source hierarchy and deliverables.
2. [Implementation handoff](../../MOTION_BRICKS_RESEARCH_HANDOFF.md): architecture,
   exact revisions, source map, chronology, licenses and unresolved questions.
3. [Input/provenance contract](../../MOTION_BRICKS_INPUT_CONTRACT.md),
   [client workflow](../../MOTION_BRICKS_CLIENT_RECONCILIATION.md) and
   [repositioning policy](../../MOTION_BRICKS_REPOSITIONING.md).
4. [Acceptance matrix](../../motion-bricks-acceptance.json) and
   [chronological capability audit](../../MOTION_BRICKS_CAPABILITY_AUDIT.md).
5. The numerical files and procedure sources below, alongside actual implementation
   code. Local evidence identifiers in the older documents are not downloadable
   reports; use these explicitly redacted public projections instead.

## Available evidence

| Public file | Contents and scope |
| --- | --- |
| [delivery-summary.json](delivery-summary.json) | Tested source identities, clean-head local test counts, disclosed skips and limitations. |
| [quality-results.json](quality-results.json) | All three final reference candidates, both three-candidate contact batches, raw boundary scalar diagnostics, retargeted/corrected stage metrics, baked metrics and thresholds, hard failures, ranking, diversity and 240/480 Hz comparisons. |
| [coverage-results.json](coverage-results.json) | Every legacy, prepared-follow-up, Beta-grid and insufficient-context case; independent source/target influence measurements. Rejections and failures remain visible. |
| [lifecycle-media-results.json](lifecycle-media-results.json) | Redacted stale/cancel/crash/restart/acceptance outcomes, multi-join review status and numerical accepted-source preview parity. Media themselves remain private. |
| [benchmark-samples.json](benchmark-samples.json) | Eighteen before/after/final complete pipeline repetitions, eight native jobs with stage timings, ten preview jobs, three loaded-model profiles with warm-call observations, candidate batches and repeated native cancellation. |
| [procedure-manifest.json](procedure-manifest.json) | Original/private and public/redacted SHA-256 identities for fourteen actual procedure source copies, including the parity and dense-quality measurement implementations. |
| [packet-validation.json](packet-validation.json) | Publication checks: original report hashes, exact candidate metric/limit transcription, retained failures, procedure syntax and packet file hashes. This validates the projection, not the underlying motion. |
| [procedures](procedures) | Native alternatives, contact refinement, lifecycle faults, multi-join reconciliation, cancellation, rendering/playback, parity, dense quality and legacy-failure reconciliation procedure logic. |
| [evidence manifest](../../motion-bricks-evidence-manifest.json) | 101 retained original local report/procedure identifiers and hashes. Hashes bind provenance; they do not grant access to private contents. |
| [Benchmark discussion](../../MOTION_BRICKS_BENCHMARKS.md) | Measurement scope, sample counts, resource interference and optimization limits. |

Numerical files select explicit fields from retained reports. They omit project,
process and request IDs, absolute paths, timestamps, scene snapshots, raw motion,
geometry, raw process logs and resource time series. Scalar motion quality and
timing results are retained at their measured precision. Each section identifies
its original report hash and actual application revision. Redaction is not a new
test run and does not upgrade a local result to independently verified evidence.

Procedure copies end in `.txt` and are **review material, not portable executable
fixtures**. Absolute workstation locations are replaced by literal placeholders;
assertions and procedure logic remain. Their private configuration, prepared clips
and exact starting checkpoints are not published. Do not remove their ownership,
hash, quality or preservation assertions to make a different setup appear valid.

## Numerical interpretation

Quality limits belong to `upright-grounded-kinematic-v2` and were fixed before
candidate selection. Read `motion_bricks_quality.py`, `motion_bricks_validation.py`
and the corresponding tests. A rank is meaningful only after every join passes;
it is not a naturalness score. Contact metrics require genuine nonempty planted
evidence. Missing raw-stage contact measurements remain unavailable, never zero.

Raw model-local and corrected world-rotation diversity use different joint sets
and frames; their RMS values cannot form a correction-retention ratio. Contact
refinement changes both support windows and deterministic cleanup. The reported
drift reduction alone does not prove an annotation-independent improvement over
a fixed evaluation interval; the research brief explicitly requests this audit.

Nested timing stages must not all be summed. Different seeds and preview sources
are not identical-input repetitions. Cold-model means newly loaded, not forced
cold OS/driver caches. Observed maxima are not p95. GPU values measure the whole
device and can miss short peaks. The production worker remains per-job isolated.

The Beta grid is one unseen Action with nine explicit boundary pairs, seven
passes and two failures. Do not call that nine independent motion styles. The
unchanged legacy suite still fails three unprepared requests. Separate reviewed
preparation enables two successful requests and exposes a genuine unstable-contact
refusal for the third. Rejected requests do not count as generated-motion coverage.

## Reproduction tiers

Public source-only checks, from the implementation checkout:

```text
python tools/run_checks.py --offline
cd launcher
node --test
```

The existing public tools provide actual Blender/provider fixtures:

```text
python tools/motion_bricks_fixture.py --config <authorized-provider.json> --blender <blender-executable> --output <new-output-directory>
python tools/run_motion_bricks_sequences.py --manifest <reviewed-local-manifest.json> --blender <blender-executable> --output <new-output-directory>
```

Read each tool's CLI and setup/license instructions before executing. These need
separately acquired pinned dependencies and authorized assets, and do not claim
to recreate the private Windows application journeys automatically. CPU execution
is not evidence of Vulkan parity or performance. Public CI results must be cited
by actual run/commit; local test counts are not remote CI approval.

## Publication boundaries

The user authorized publication of source and redacted research documentation.
No assets or raw workstation evidence were uploaded. No history was rewritten,
base branch merged, release deployed, model upgraded or production installation
replaced. Review the draft stacked PR and exact commit, not an assumed default
branch snapshot. The original implementation's private reports remain immutable.
