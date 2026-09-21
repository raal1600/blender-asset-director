# World import performance and diagnostics

Import still uses the bounded native worker and creates a separate, unapproved
checkpoint. Selection is not import or authorization. Original files, previous
checkpoints, source-use confirmation, rights checks, input/output hashes, job
ownership, writer locks and durable saves remain required.

The optimized path avoids rewriting an unchanged SQLite schema version, overlaps
independent source checks, avoids repeating native verification when validating
the current checkpoint, and publishes the job binding and scene run reference in
one atomic project revision before starting Blender. It does not cache integrity
results, disable SQLite synchronization, retain a background Blender worker, or
change security/provider configuration. Source integrity is checked again before
publishing the candidate.

The import dialog reports preparation immediately. Active imports poll status at
most twice per second with no overlapping requests; other tasks keep the existing
slower polling cadence. The workbench displays observed phases, not percentages or
estimated completion times. After a restart, only the persisted receipt is shown;
in-memory phase observations are not proof that a worker is still connected.

New import run receipts add `requestedAt`, `phase` and `timings`. Each timing lists
the phase, monotonic elapsed milliseconds and success/failure. `startedAt` keeps
its existing meaning (the durable run begins after preflight); `requestedAt`
includes preflight. Timings describe instrumented boundaries, not a full profiler
or browser click-to-paint latency. Existing receipts are never rewritten.

Use **Inspect operation** to see the receipt. Benchmark the full click-to-candidate
journey separately from the Blender worker, and report multiple samples, cold/warm
conditions and save-time variability. Generated fixtures are not proof of a speedup
for every licensed production asset. Keep workstation measurements and screenshots
private; exact-commit CI, packaging and live installation remain separate gates.

Regression coverage includes catalog reopen/lock behavior, atomic binding before
execution, source/checkpoint changes, unapproved publication, phase timing failures,
poll concurrency and browser module delivery. Real Blender and browser tests are
additional evidence, not replaced by the synthetic unit executor.
