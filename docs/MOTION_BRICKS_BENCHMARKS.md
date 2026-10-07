# MotionBricks pipeline measurements — in progress

Environment verified locally: Windows 11 Home, RTX 4070 (12,282 MiB), driver
616.56, approximately 31.85 GiB physical RAM, Blender 5.2.1 LTS
`9e2066aef7ef`, pinned Vulkan backend. CPU is an explicit alternative; no silent
fallback was used. Model and DLL identities are in the capability audit.

The ten fresh-worker baseline runs in `baseline-sampling/report.json` retain
individual inference, loading, total duration and sampled memory values. The
first request took 2.754 seconds end to end, including 1.496 seconds loading and
0.0617 seconds native inference. Later workers still load their own model;
filesystem/driver warming does not make them persistent warm-model requests.
These mixed sampling/context experiments are not a fixed-input latency percentile.

Native Windows three-candidate generation to review was 91.606 seconds at
91cb591 and 96.743 seconds at 9474cca, **one observation per build**. Their source
calibration/cleanup changed, so this is not an identical-input optimization
comparison. Candidate preview export follows separately. The 9474cca A/B control
journey passed, while candidate quality failed. The historical 24–27 ms inference
claim and approximately 99-second client test are not whole-pipeline benchmarks.

New source instrumentation links `Runs/<request>.json` to the native job and its
`blender-trace.json`. Launcher events measure queue admission, preflight, job
preparation, native execution, result validation, hashing, checkpoint copy and
atomic publication. Blender events cover input load, per-transition sampling,
provider, retargeting, seam/contact processing, baking, saving and fresh-reopen
quality validation. Provider receipts separately retain model loading, request
conversion, inference and result conversion. Client-ready/preview-ready timing is
an additional harness observation, not inferred from native inference duration.

The 32 evaluated samples per scene preview frame are real: see
`viewer_sampling.subdivisions` and `evaluated_sampling`, followed by
`viewer_timebase.normalize`. Only the disposable preview worker is time-remapped;
output seconds and source Actions are preserved. This density has not been
reduced. Dense quality convergence already found errors missed by 60 Hz checks,
so a lower preview density requires measured positional/orientation parity.

Monitored budgets remain whole GPU 9,216 MiB, provider increase 8,192 MiB, reserved
headroom 2,048 MiB and provider host 2,048 MiB. NVML whole-device sampling cannot
attribute unrelated applications' memory to this provider; these are monitored
admission/runtime limits, not allocator caps. Stage-one retained host peaks were
approximately 823–892 MiB; whole-device peaks approximately 3,111–3,134 MiB, with
whole-device memory returning to the observed 2,396 MiB baseline after those
workers exited. Other runs had different desktop baselines.

Mandatory work still outstanding: identical-input baseline/final repetitions,
fixed-input cold and warm distributions, complete single/batch generation,
preview timings, cancellation latency and release on final code. Report sample
counts, median and observed maximum/tail only after collecting them. No latency
target, persistent-worker benefit or final performance PASS is claimed here.
