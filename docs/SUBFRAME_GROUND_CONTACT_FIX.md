# Bounded subframe contact correction

Development fix based on reviewed-transfer commit
`8c11012dda3f706a80763d0cb6ee8a94d836a968`; runtime remains `0.6.0-dev.3`.
Identify the build by its fix-branch commit, not the version string alone.
The installed working skill is not updated by this change.

## Problem and change

The previous local transfer passed structural/timing checks but its vertical
repair left about 1.413 mm penetration at half frames, failing the explicit 1 mm
contact tolerance. Correcting integer keys does not constrain the deformed mesh
between keys: rotating feet can dip below a linearly interpolated pelvis height.

`ground_contact.subdivisions` is an opt-in integer in 1..8, default 1. It subdivides
each actual bake interval, including a shorter fractional final interval. The
grounding pass now runs after the uncorrected action is finished and linearized.
It inserts only anchor-location keys, retains rotation curves and action duration,
and rechecks the finished action at all requested contact checkpoints.

The correction cap is measured against the uncorrected anchor at each sample.
Using only the residual after previous correction keys could hide a larger total
displacement. Both the application and final verification enforce the total cap
and sampled horizontal preservation. Work is bounded to 2,881 checkpoints and
50 million explicit mesh-vertex evaluations.

`subdivisions: 4` was reviewed for the local defect. It is not a new universal
default, a foot lock, an IK solver, permission to ground jumping motion, or a
continuous collision guarantee. Re-run contact diagnostics between correction
keys; a changing subdivision request needs a new exact proposal/host review.

## Executed local evidence

- Blender 5.2.1 LTS; offline suite: 420 tests, one skipped, PASS.
- Temporary installer self-tests PASS; no global installation/configuration edit.
- Existing transfer-planning fixture: all 11 gates PASS.
- New `tools/ground_contact_fixture.py`: reproduces 106.97 mm midpoint penetration
  between clear frame keys on synthetic rotating geometry. Requested subframe
  correction reduces checkpoint error below 0.0001 mm. Rotation curves, horizontal
  travel, rig fingerprint and fractional endpoint are retained; an excessive total
  correction is refused. Added to the existing Blender CI matrix; remote CI has
  not been run for this local change.
- Real test reused the authorized Mixamo motion and existing Quaternius target,
  copied catalog/license evidence and a fresh target file. No acquisition.
- Mapping, alignment, 16 mm cap and timing match the prior reviewed repair;
  the only proposal-option change is `subdivisions: 4`.
- 125 correction checkpoints, independently checked at 249 times (eighth-frame
  spacing). Integer, half and quarter-frame clearances are within floating-point
  error of the calibrated floor. Worst eighth-frame penetration: 0.098296 mm,
  PASS against the unchanged 1 mm tolerance.
- Maximum correction 14.777958 mm, within the same 16 mm cap. Maximum sampled
  horizontal difference from the uncorrected transfer: 0.0000002384 m.
- Rotation-curve signatures, mesh/weights, material slots, old action signatures,
  rest fingerprint, 30 FPS, 1.033333-second duration and frame-32 endpoint preserved.
- Independent evaluated-mesh clearance measurements exactly match contact-check.

Detailed private evidence lives at the configured library's
`reports/subframe-ground-fix-20260915-01/`, including `real-verification.json`,
`contact-check.json`, the exact plans/reviews, worker logs and separate results.
The earlier failed acceptance is preserved at
`reports/reviewed-transfer-acceptance-20260914-235956/`.
User assets, outputs and license records are not included in this repository.

## Limits

TECHNICAL: PASS for these tested cases. Measured subframe contact: PASS at 1 mm.
PERFORMANCE: PENDING. HUMAN: NOT ESTABLISHED for the new result.
Samples do not prove all continuous extrema or artistic quality. Terminal head-axis
review and explicit fourth-finger endpoint selection remain the earlier planner's
documented decisions; they were not changed to fix contact. No live Blender window,
production project, installed skill or historical preservation finding is changed.
