# Reliable transition implementation and acceptance

This is a live engineering record, not a completion claim. Evidence remains outside Git in
`C:/Users/ramis/AppData/Local/Temp/asset-director-transition-evidence-20261005`.

## Isolation and baseline (2026-10-05)

- Application base: `f2b39f2e001ebc5c0ddfa32dd08b4b9fd4c2ac07`, latest Action controls branch.
- Work branch: `fix/reliable-animation-transitions-20261005` in a new temporary clone.
- Existing main and launcher checkouts are clean but older; existing branches and installed studio are untouched.
- Current main predates the client Action workflow. Using its descendant feature branch preserves the existing application requested by the user.
- Root AGENTS.md, CONTRIBUTING.md and CONSOLIDATION.md read before changes. No nested AGENTS.md found.
- Exact original failing project was not supplied. Generated fixtures reproduce representative behavior; any discovered failure is distinguished from the original report.
- GPU: NVIDIA GeForce RTX 4070, 12282 MiB total, 9355 MiB initially free, driver 616.56. Host RAM: 34196021248 bytes. Blender 5.2.1 LTS.
- Default shell sandbox failed before process launch (`helper_unknown_error: setup refresh had errors`). Reviewed elevated commands work.
- Portable baseline: 720 tests, PASS with 3 pre-existing skips; launcher: 358 tests, PASS. Installer self-test PASS.
- Real Blender baseline: motion_stitch_fixture PASS (26 checks); motion_edits_fixture PASS. Existing tests do not establish contact or requested derivative tolerances.
- Hosted baseline: run 37245540072 FAIL at this exact base; motion subsystem fails on 4.5.3/5.0.0/5.2.1 and the Linux embedded WebGL suite fails while preparing the same motion-edits fixture (before browser playback). Do not attribute these to new changes.
- Frozen local Windows motion suite: all 11 original fixtures PASS. An earlier overlapping source-edit run correctly refused STALE_IMPLEMENTATION; it is retained separately and does not represent the immutable baseline. Hosted Linux failures are not reproduced by the Windows pass.

## Checklist

- [x] Inspect local/remote branches, instructions, installed runtime and hardware.
- [x] Isolate work without changing existing checkouts or installation.
- [x] Run portable, launcher and initial real Blender baseline.
- [x] Reproduce representative defects with evaluated Blender metrics; record the baseline visible client journey separately (it passes its original 24 FPS case).
- [x] Pin and prove motion-bricks capability using real source/model/output.
- [x] Document and enforce motion data/provider contracts.
- [x] Implement smooth deterministic transitions, persistence and preview parity; keep raw neural candidates explicitly unaccepted.
- [x] Run generated motion scenario, contact and failure/recovery matrix.
- [x] Verify a clean copied-runtime client journey, fresh Blender reopen, render/export and playback.
- [ ] Verify the final CI-gated candidate ZIP in a new installation through the complete client journey.
- [x] Measure repeated jobs, GPU/host memory, cancellation and resource release.
- [ ] Run final candidate regression and inspect exact-commit hosted CI.

## Acceptance matrix (thresholds fixed before implementation)

NOT VERIFIED means no qualifying evidence yet. A numerical pass never implies visual/contact acceptance.

| Criterion | Fixture and method | Threshold | Evidence | State |
|---|---|---|---|---|
| A: client journey | Generated native rig, two clips; visible controls through normal authenticated launcher, save/reopen/play/render | All stages succeed; no console errors or failed application requests | client report, recording, worker receipts | NOT VERIFIED |
| B: positional boundary | Evaluated generated rig at same stitch timestamp, both endpoints | root/joint mismatch <= .001 character height | numerical Blender report | NOT VERIFIED |
| B: orientation boundary | Evaluated transforms at identical boundary times, shortest quaternion difference | <= 1 degree | numerical Blender report | NOT VERIFIED |
| B: velocity boundary | One-sided derivatives on each side at stitch; document sample spacing and source reference | linear <= .05 height/s; angular <= 5 degrees/s | numerical Blender report | NOT VERIFIED |
| C: planted contact | Generated reference with declared nonempty stance windows and ground | horizontal drift <= .01 height; penetration <= .005 height | contact samples and rendered sequence | NOT VERIFIED |
| D: timing/preservation | 24/30/60 FPS, trims, offsets, short/long joins, three clips | Intended seconds/ranges exact; no duplicate stitch timestamp; original bytes/actions unchanged | fixture report/source hashes | NOT VERIFIED |
| E: visual | Continuous playback and render at both boundaries | No snap/spin/teleport/detachment or unacceptable foot slip | before/after frame sequences/video plus inspection | NOT VERIFIED |
| F: persistence/parity | New Blender process opens accepted .blend, export and preview consume same hash | Numerical transforms agree within .001 height/1 degree; accepted artifact identity exact | fresh reopen/export/preview receipts | NOT VERIFIED |
| G: reliability | Missing/corrupt provider, unsupported rig, timeout/crash/OOM, queued/running cancel, restart, repeated jobs | No false success, accepted partial artifact, source corruption or orphan worker | failure injection and real process reports | NOT VERIFIED |
| H: target hardware | Actual RTX 4070; bounded provider/render concurrency and explicit memory budget | No OOM, no silent fallback, peak below configured budget | sampled nvidia-smi/host resources; cold/warm repeated runs | NOT VERIFIED |
| I: regression/CI | Existing portable/launcher tests and real Blender suites on final commit | All relevant checks pass; pre-existing failures identified | local logs plus hosted exact-SHA runs | NOT VERIFIED |
| Real provider | Pinned source/model, actual existing context -> inference -> intended rig -> evaluation | Actual output influences usable animation; constraints and seam metrics validated | provider provenance, Blender output/report | NOT VERIFIED |
| Clean package | New isolated install using repository packaging/launcher conventions | Full journey through installed entry point; no production install changes | installer manifest, native/browser logs | NOT VERIFIED |

## Decisions and limitations

1. Preserve the application architecture: existing Action controls, authenticated local launcher, job system, checkpoints, Blender worker and GLB preview.
2. Same-rig native object-root travel is now explicitly aligned. Bone-root planar travel, constrained/procedural channels and ambiguous ownership remain refused. Retargeted Actions use the separate pinned reviewed retarget pipeline before native sequencing.
3. Authored, rest-verified two-bone contacts receive constrained cleanup and sampled diagnostics. Unannotated results remain NOT_EVALUATED. Controlled planted intervals and rendered skin are measured separately from natural-motion claims.
4. motion-bricks has a real two-boundary conditioning C ABI, not an inference CLI. Source audit/build evidence is recorded separately. Soft constraints alone do not establish seamless animation.
5. User explicitly authorizes real local inference, GPU measurements, dependency setup and repeated isolated testing. Historical instruction-file limits on these operations do not require another approval.

## Reproduced defects and current evidence

- The original mathematical C1 bridge was baked as linear segments. At 60 FPS
  with two extra frames the new evaluated regression measured 49.75 degrees/s
  angular-velocity mismatch. A turning fixture measured .2315 m/s root mismatch
  (height 2m; preset limits 5 degrees/s and .1m/s). Explicit endpoint Bezier
  tangents and closer native derivative samples reduce preliminary maxima to
  .618 degrees/s and .00217 m/s. See `before-continuity` and `after-continuity-*`.
- Whole-frame GLB sampling disagreed with the actual saved pose at frame 25.25
  by .0235807m (limit .002m). Isolated evaluated quarter-frame sampling preserves
  native Actions and effective seconds. `fresh-60fps-short-2` passes exact sample
  parity; `fresh-60fps-short-3` also checks intermediate eighth-frame playback
  (maximum observed position difference .0011042m, orientation .093 degrees).
- Real timebase fixture `viewer-sampling-2` passes noninteger FPS, nonzero starts,
  existing scene time remapping and restoration after injected export failure.
  The attempted negative scene range was clamped by Blender and is retained as
  a failed experiment, not silently treated as supported.
- `installed-browser2` passes 12 checks through a copied, clean installed runtime
  and the normal launcher entry point: actual Blender Save, both-boundary scrub,
  video capture, fresh backend restart, changed-duration Save and new preview,
  18-frame CPU shot rendering and browser movie playback. Zero console/failed
  requests. This is generated data, not the unavailable original project.
- The Windows EXE built with the pinned WebView2 dependency and loaded, but
  `native-desktop-1` refused input because Windows denied foreground access.
  This local gate remains BLOCKED; hosted Windows native-desktop validation at
  `dc3d10aac32c23ae08f2cd9636ffabb830f6f3a6` passed. Final candidate
  packaging still requires matching exact-commit evidence; no guard was removed.
- `acceptance-1` uses an immutable candidate snapshot and records actual process
  tree RAM and device-wide VRAM. One portable inventory-count assertion failed
  when the new mandatory Blender fixture was added; the expectation was updated
  to include that fixture while preserving all 26 prior entries. A final rerun
  is required. All generated artifacts and failure evidence remain retained.
- Real pinned MotionBricks CPU source/model tests and the G1-to-Blender proof
  passed. Candidate generation is PARTIAL integration; exact seams/contact and
  raw neural contact quality remain unaccepted. Real Vulkan execution on the RTX 4070 now passes resource and Blender-data proof; it is not advertised as an accepted neural transition.

## Additional reproduced failures and validation scope

- `basis-roundtrip-before.log` reproduces four native heading identities changed
  by a quaternion/Euler/quaternion round trip. The hosted baseline motion-edits
  failure occurs on its next saved edit. `motion_heading.state` now reuses the
  exact captured baseline quaternion; no identity tolerance was weakened.
  `motion-edits-basis-fix` passes the new exact-identity cases and existing edits.
- Actual pinned Mwni retargeting exposed a fractional NLA interval bug:
  assigning a fractional strip start left its old end in place. A 29.75-to-37
  bridge ended at 36.25, briefly exposing a rest pose. The fixture measured a
  .21656m / 11.51-degree incoming jump. Explicitly retaining the intended end
  and verifying full strip coverage fixes it; `retarget-transition-3` measures
  4.92e-7m / .000039 degrees and .0678 degrees/s. The canonical suite now also
  includes a fractional speed case (15 cases total).
- Real cancellation initially exposed a Windows job.json access race between
  Blender opening its request and the parent publishing worker PID metadata.
  A separate version-bound worker-process record avoids concurrent receipt
  replacement. Publication failure kills/waits the exact child. Final
  `cancel-suite-final2` passes both queued and running visible-client paths.
- `contact-visual-comparison` retains before/after frames and inspection.
  The body-turn reference without cleanup drifts .04627m and penetrates the
  ground .02560m. With cleanup, drift is .000071m; the stricter evaluated
  **skinned surface** penetration is .00379m (fixed limit .01m). Earlier
  .000066m figures measured skeletal foot/toe positions only and must not
  substitute for the skin measurement.
- `retarget-transition-visible` uses actual pinned Mwni output on a renamed,
  1.2x target rig with explicit mapping/rest fingerprints. Foreign source-rig
  bindings are refused. This proves the reviewed retarget-then-transition path;
  it does not infer cross-rig compatibility from names.
- Real CPU and Vulkan provider/Blender proofs pass, including source preservation,
  target conditioning, fixed-seed repeatability and process cleanup. Vulkan
  profiling sampled 3248.55MiB whole-device usage against 9216MiB, returning to
  baseline after exit. Raw neural seams still fail the fixed limits. See the
  provider audit's separate matrix; integration remains **PARTIAL**.

The matrix above is the original pre-implementation gate inventory. Per-run
`ACCEPTANCE.json` and the final evidence index record actual states and exact
source identity. Earlier proofs are retained with their candidate versions;
final-commit regression and hosted CI must be recorded independently. Commands,
artifact meanings and known restrictions are in
[Transition validation](TRANSITION_VALIDATION.md).

## Hosted candidate feedback and final freeze

- Candidate `dc3d10aac32c23ae08f2cd9636ffabb830f6f3a6` passed all nine
  Blender version/subsystem partitions, Linux portable tests and Windows native
  desktop validation. Harness run `37251328504` failed on two distinct families:
  cross-platform guardian compatibility and derived-preview cleanup.
- macOS Python 3.11 lacks the original `waitid` API. The process guardian now
  owns its POSIX session/group, writes its command result, and terminates that
  reserved group on owner exit, timeout, command completion or receipt failure.
  Windows tests inspect OS wait handles instead of Python 3.11's inconsistent
  `os.kill(dead_pid, 0)` behavior. Six real Windows containment tests pass;
  the final exact-commit hosted run must verify macOS/Linux.
- The new worker identity record was correctly preserved by successful jobs but
  absent from the preview-cleanup allowlist. Cleanup now preserves only the
  exact hashed, job-bound record and rejects missing, altered or unknown files.
  Sixteen focused contracts and the real visible cleanup/rebuild journey pass
  (`cleanup-diagnosis.json`, `cleanup-corrected/RESULTS.json`).
- `final-acceptance-dc3d10a` completed all scoped checks, including installed
  playback/render and both cancellation paths, but validation-tool edits
  overlapped the run. `SOURCE-NOTE.json` labels it diagnostic evidence. A final
  immutable checkout is required. The acceptance runner now also rejects a
  source fingerprint, commit or dirty-state change during execution.

## Normal candidate ZIP setup regression

- Exact candidate `6b39e1789b950b3f829ce4f1669b82bf3d777f26` passed all
  31 hosted harness jobs and all five workflow conclusions (harness
  `37252474268`). Its immutable local runner passed all 77 checks with clean
  start/end source identity. These are retained as candidate evidence.
- The requested clean ZIP test then found a pre-existing `Setup.ps1` argument
  bug also present at baseline `f2b39f2`: PowerShell concatenation/array operator
  precedence joined each option and configured path into one argument. Normal
  installation failed before creating the studio, despite valid ZIP hashes.
- Parenthesizing option concatenation preserves separate option/value arguments.
  The existing candidate installer regression now executes the actual packaged
  PowerShell entry point on Windows using spaced script, destination and tool
  paths. It verifies all stored paths, repeat-install refusal and unchanged
  bundle integrity. The synthetic host is explicitly never executed; the final
  real ZIP/native-client journey is a separate acceptance gate.
- `candidate-6b39e17/setup-regression-before.log` reproduces the failure;
  `setup-regression-after.log` passes. Final-candidate CI, immutable regression
  and normal ZIP installation must be rerun after this fix. Earlier green CI
  is not evidence that the previously untested setup entry point worked.
