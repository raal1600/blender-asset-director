# MotionBricks pipeline measurements

Measured locally on Windows 11 Home, RTX 4070 (12,282 MiB), driver 616.56,
about 31.85 GiB RAM, Blender 5.2.1 LTS `9e2066aef7ef`, pinned Vulkan backend.
No silent CPU fallback, dependency upgrade or persistent production model worker.
The exact pins/build are in [the handoff](MOTION_BRICKS_RESEARCH_HANDOFF.md).
Raw reports named below are under the private evidence root identified there.

## Identical-input optimization comparison

`soles-pipeline-comparison-final-v1.json` retains 18 complete real fixture jobs:
three identical requests per rig at each of a08e46d (before), 0c804ca (after) and
5f1b8b8 (final motion implementation). Every request, raw numeric array, corrected
sample/path/world pose and evaluated baked frame is exactly equal within each
rig across all nine repetitions. Every hard gate, native preservation and fresh
reopen check passes, with owned process release.

| Complete fixture generation plus separate reopen | n per revision | Before median / max (s) | After median / max (s) | Final median / max (s) |
| --- | ---: | ---: | ---: | ---: |
| Reference | 3 | 46.411 / 46.573 | 45.703 / 46.175 | 46.176 / 46.721 |
| Beta | 3 | 41.476 / 42.185 | 33.281 / 33.746 | 33.958 / 34.118 |

The sole-height optimization transforms only the foot-dominated vertices used
by the existing check, preserving the evaluated mesh and world matrix. No sampling
density or validation threshold changed. The reference timings mostly overlap;
the denser rig has a clear observed reduction in this small sample. The earlier
16-pose/twenty-calls-per-method microbenchmark also has exact height equality.
Three repetitions do not support a population p95 claim. Fixture timings include
diagnostic seam sampling beyond the normal client operation.

## Native authoring and preview

`final-native-timings-5f1b8b8-v1.json` joins eight actual native jobs to their
launcher, Blender and provider traces: six reference candidates across two
contact settings and two identical complete four-clip requests. Final 5d4a7ba
changes only ranking presentation; `runtime-scope-identity-5d4a7ba-v1.json`
verifies identical motion/persistence/preview source trees.

| Observation | n | Median (s) | Observed maximum (s) |
| --- | ---: | ---: | ---: |
| Refined single candidate, server admission to publication | 3 distinct seeds | 41.499 | 41.662 |
| Same candidate jobs, native execution | 3 | 39.515 | 39.726 |
| Loaded scene to boundary support | 3 | 8.207 | 8.225 |
| Fresh reopen/quality validation | 3 | 8.466 | 8.558 |
| Checkpoint copy/hash verification | 3 | 0.249 | 0.261 |
| Complete four-clip candidate, server admission to publication | 2 identical requests | 82.451 | 82.796 |
| Complete four-clip native execution | 2 | 80.400 | 80.606 |
| Four-clip fresh reopen/quality | 2 | 10.536 | 10.545 |
| Actual uncached preview native jobs, differing sources/profiles | 10 | 12.384 | 17.631 |
| Same jobs' evaluated export operation | 10 | 10.120 | 14.787 |
| Fixed-source cached native comparison click to ready | 3 | 1.448 | 1.463 |

These are nested spans and must not all be summed. Preview export is separate
from candidate publication. Different seeds/sources are not identical-input
replications; the raw JSON retains each identity, stage and resource observation.

The native contact batches take 126.524 and 127.230 seconds from click to three
reviewable outcomes, with different support windows. The final ranked batch at
5d4a7ba takes 129.862 seconds. Both refined batches have two hard passes and one
retained failure. The two identical complete four-clip requests take 84.319 and
84.289 seconds click-to-review. These figures include far more than native
inference; candidate preview loading can add separate time afterward.

Launcher trace stages cover queue admission, preflight, preparation, execution,
contract/hash validation, checkpoint copy and atomic publication. Blender traces
cover startup estimate, input load, context sampling, conversion, per-join model
execution, retargeting, seam/contact processing, baking, save and fresh reopening.
Provider receipts contain model load, native inference and request/output
conversion. Exact preview IDs link to their own native trace; client-ready
measurements are harness observations, not inferred from model timings.

## Cold-model and warm-model inference

`provider-profile-5f1b8b8-v1/report.json` profiles three separately loaded models,
each with 30 identical calls. Numeric output hashes are equal within and across
the three runs on this same device. This bounded diagnostic retains a model;
production still starts and releases an isolated worker for every request.

| Stage | n | Median | Minimum–maximum |
| --- | ---: | ---: | ---: |
| Model loading | 3 | 0.7002 s | 0.6964–0.7007 s |
| First inference after loading | 3 | 34.92 ms | 34.25–37.79 ms |
| Same-model warm inference | 87 | 24.16 ms | 22.31–25.85 ms |
| Complete diagnostic profile process | 3 | 2.533 s | 2.483–2.538 s |

Cold here means newly loaded model, not a forced cold operating-system cache or
driver. OS caches were not flushed. No cross-device bitwise identity is promised.
The historical 24–27 ms warm inference and approximately 99-second client test
are not authoring latency targets or isolated complete-generation benchmarks.

## Cancellation, release and monitored resources

`native-lifecycle-5f1b8b8-v1` measures one native cancellation at 0.78 seconds after
an actual Blender job begins and verifies preservation through provider/launcher
crashes. The final 5d4a7ba native cancellation procedure repeats three times: median
0.782 s, minimum 0.778 s, maximum 0.790 s from Cancel to terminal state, with
owned Blender process release, unchanged accepted hash and normal host exit
(`native-cancellation-5d4a7ba-v2/report.json`). Its first procedure completed
cancellation but timed out at the native shutdown safeguard. Safe Refresh status
recovery and the corrected wait for asynchronous discard/preview remain recorded
in the v1 report and `exit-recovery.json`; the v1 run is not a clean harness pass.
These measurements do not claim interruption inside the approximately 30 ms
native inference kernel. Provider cancellation/timeout/budget execution and
process ownership are separate real-worker checks.

Configured budgets remain 9,216 MiB whole GPU, 8,192 MiB increase over baseline,
2,048 MiB GPU headroom and 2,048 MiB provider host. Final eight-job native traces
show provider host peaks 877.94–880.04 MiB and whole-device peaks 2,964.62–3,058.50
MiB. `provider-faults-5f1b8b8-v3` safely lowers limits in disposable dictionaries,
verifies admission/runtime refusal and actual worker termination, then succeeds
with the original unchanged Vulkan configuration. All three profile processes
return observed GPU use within 32 MiB of their respective baselines.

NVML measures the whole device, including unrelated display applications, at
approximately 10–20 ms intervals. Host peak/private-memory counters and GPU
samples are monitored limits, not hard allocator caps. A terminated Windows
process can retain readable peak-memory counters while a handle remains open;
the corrected release procedure checks process termination, not absence of those
counters. All observed resource limits and measurement gaps are preserved in raw
reports. No CPU performance distribution was measured.

## Remaining performance questions

The 32 evaluated samples per scene preview frame were verified in
`viewer_sampling.subdivisions`/`evaluated_sampling` and `viewer_timebase.normalize`.
Only a disposable preview worker is resampled; source Actions and physical output
time are preserved. Density was not reduced. Final reference/four-clip GLB parity
has maximum skin error 0.01183 mm and joint orientation below 0.162 degrees against
fresh Blender at every rendered frame and fractional stitch samples.

Measured time is dominated by work outside inference. Correctly invalidated
evaluation/hash/preview caches deserve investigation before a persistent model
worker. Any such worker must earn its complexity through measured benefit,
bounded lifetime/memory, real cancellation, crash recovery and a return to per-job
execution. No claim of real-time application performance follows from this report.
