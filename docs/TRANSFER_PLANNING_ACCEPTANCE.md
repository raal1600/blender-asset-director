# Reviewed transfer planning: executed repository acceptance

Development runtime: `0.6.0-dev.3`.
Branch: `feature/reviewed-transfer-planning`.
Tested code: `444e374d5dede2f8f32e77c59ff33a8a4921d8b3`.
CI run: https://github.com/raal1600/blender-asset-director/actions/runs/34900256087
All ten jobs completed successfully. This documentation/skill-instruction update
follows the tested code; it does not alter runtime Python, fixtures or workflows.
No release, main merge or workstation installation was performed.

## Development input and scope

Read `docs/LOCAL_MOTION_SESSION_HANDOFF.md` from `4c6087b` and compared it with
the tested local-library branch `c11248c`. The handoff was documentation-only;
existing source/target provenance, successful 52-joint transfer and unresolved
shared-configuration preservation findings were retained, not reinterpreted.

Implementation through `ade9657` added numbered torso/finger discovery, a bounded
read-only transfer-plan, exact review-bound transfer-prepare/execution, evaluated
subframe contact-check, portable request validation and synthetic regressions.
`ed48aee` hardened extra-chain rejection/nonfinite contact evidence and corrected
bootstrap/test time comparisons. `444e374` corrected the contact fixture's local
axis assumption and added an independent deformed-mesh oracle.

No multi-window UI controller, full IK, reconstruction, realistic skin fitting,
new source downloader or capture dependency was implemented. Boundaries and local
contracts are in [REVIEWED_TRANSFER_PLANNING.md](REVIEWED_TRANSFER_PLANNING.md).

## What actually ran

| Gate | Result |
|---|---|
| Portable suite in the development container | 415 tests ran; PASS |
| Local installer self-tests | PASS; temporary install/repeat/runtime/edit protection/uninstall |
| Local POSIX bootstrap | PASS after explicit archive-version binding |
| CI unit jobs | Windows/Python 3.11, Ubuntu/Python 3.11 and 3.13: PASS |
| CI bootstrap | Windows PowerShell 5.1 and 7, macOS sh and Ubuntu sh: PASS |
| Real Blender fixtures | 4.5.3, 5.0.0 and 5.2.1: PASS |
| Existing live free-provider/source-motion check | PASS on Blender 5.0.0; not duplicated on other versions |
| User's real Mixamo/Quaternius assets and live windows | NOT RUN / not accessed |

Platform-specific skips remain reported by individual unit logs; job success does
not imply a skipped platform-specific test executed. Blender ran in GitHub runners,
not in the development container. These are development-source/bootstrap checks,
not anonymous installation tests for a new public release.

The new transfer fixture passed eleven gates on Blender 5.2.1. Downloaded evidence:
`blender-5.2.1-evidence`, artifact ID `10370376721`, ZIP SHA256
`4457d330da63dd30c1d6eda09f51891f64b02bbdf1d891ea1c930af2e9e5243f`.
The archive contains transfer_planning_report.json and other diagnostic evidence,
not user source animations. Measured results include:

- 52 mappings with separate character/motion provenance; measured yaw
  66.99999440415698 degrees from an unrelated synthetic 67-degree setup.
- Measured scale proposal tested against 1.18 synthetic proportions, not a
  stored scene-specific default. Separate unit-conversion case also passed.
- Reference-direction one-minus-dot error <= 5.9604642999033786e-8.
- Mapped rotation quaternion one-minus-absolute-dot error <=
  5.960464477539063e-8 over 32 matched-time checkpoints. These dimensionless
  orientation metrics are not millimetres, dance-quality scores or motion capture.
- Source imported start frame 2, retargeted start frame 1; compared by elapsed
  seconds. The 24 FPS case retained a final key at 25.8 and scene end 26.
- Deliberately changed world placement rejected despite unchanged rest fingerprint.
- Existing target geometry, weights, rest fingerprint, original action, unit pose
  scales, unmapped root, duration and inherited license grants preserved.
- Completed planning jobs reused without another worker or changed output files.
- Contact probe: integer clearances 0; half-frame penetration approximately
  0.029999975 m. Runtime values matched an independently evaluated mesh oracle.
  Integer PASS and subframe FAIL were reported separately, with no channel change,
  foot locking or automatic repair. Diagnostic states did not become performance
  acceptance. Source/target input hashes remained unchanged.

## Failures retained and corrected

The first CI iteration failed bootstrap identity checks: the generated archive
was dev.3 while the test let installer defaults request dev.2. The test now passes
its archive's actual version; archive verification and public release defaults
were not weakened.

The first transfer fixture compared equal frame labels across an imported source
start offset. It now evaluates 32 matched elapsed times without increasing the
accuracy tolerance. This was a test error, not evidence the original retarget
should be changed to fit a phase-shifted comparison.

The next fixture failure assumed pose-bone local Z was world Z. Its supposed
vertical penetration actually moved sideways, so the runtime correctly reported
zero penetration. The fixture now converts the desired world-down offset through
the observed rest basis and independently verifies deformed sole heights before
asking the diagnostic to measure them. No runtime tolerance was relaxed to pass.

## Remaining acceptance

Repository TECHNICAL: PASS for the tested cases.
Real workstation transfer via the new planner: NOT RUN.
Formal PERFORMANCE: PENDING.
HUMAN: NOT ESTABLISHED for this new implementation.
Multi-window playback/bone display controller: NOT IMPLEMENTED.

Use a new isolated worktree and a saved target COPY for the local test. Reuse the
existing authorized/indexed Mixamo clip and actual Quaternius mannequin, not new
proxy bodies. Compare proposed mapping, facing, units, ratios and reference bases
with prior local evidence; do not hardcode prior values. Approve the exact proposal
only after inspection. Retarget once, inspect integer/half-frame sole diagnostics,
then perform a separately justified bounded vertical repair only if needed.
Keep old outputs, hashes and permission evidence. At most eight CPU stills at
640x360/16 samples; a model that inspected stills cannot certify continuous motion.
Do not upgrade the installed runtime, merge, publish, touch Desert Warrior or
restore shared configuration. The older unexplained configuration-change failure
stays part of the record. User approval of the earlier playback remains informal
feedback on that particular output, not a retroactive general performance pass.
