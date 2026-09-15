# Motion foundation acceptance — development milestone

Branch: `feature/motion-foundation`
Runtime: `0.6.0-dev.1` (not a tagged or published release)
Tested code/CI commit: `d84efa6dd656e27c7ef15987e7db73cf99fda6de`
CI: https://github.com/raal1600/blender-asset-director/actions/runs/34794457404

All ten jobs completed successfully on 2026-09-14. This documentation-only record
follows the tested runtime and does not change code or start a release.

## Executed gates

| Gate | Evidence |
|---|---|
| Ordinary Python | 279 tests passed: existing 223 plus 56 motion-foundation cases |
| CI Python/OS matrix | Ubuntu 3.11, Ubuntu 3.13 and Windows 3.11 all passed |
| Managed skill installation | Temporary install/repeat, bundled runtime, role/license presence, edited-install protection, library-preserving removal passed |
| Source-package bootstraps | Windows PowerShell 5.1 and 7, macOS sh and Ubuntu sh passed |
| Real Blender | 4.5.3, 5.0.0 and 5.2.1 passed all previous fixtures and the new canonical-motion/proxy/retarget chain |
| Existing live provider/motion regression | Passed in Blender 5.0.0; intentionally not duplicated on the other two versions |
| User workstation and real artistic performance | Not executed from this environment; local acceptance remains required |

No new public installer/release was published. Bootstrap checks used generated
local source archives on runners; they are not public-download tests for a release
that does not exist. The normal README installer still points to v0.5.0.

## New real Blender test

`tools/motion_foundation_fixture.py` runs jobs in isolated background processes
against generated synthetic assets. It verifies:

1. Evaluated action export into immutable manifest/binary motion and idempotent collection.
2. Offline local metadata rediscovery with a different alias.
3. Canonical reconstruction at 30 FPS preserving a one-second source trajectory.
4. A source-shaped proxy and a 0.7-leg / 1.25-arm proxy, fitted once in rest geometry.
5. Explicit canonical-to-v0.5 transfer with a measured leg-based root scale.
6. Rejection of a stale target fingerprint.
7. Body audit, numerical/performance-status separation, and completed-job reuse.
8. Camera/light/CPU preview execution with restoration and unchanged original hashes.

Downloaded Blender 5.2.1 evidence reports leg ratio `0.6999999958607885` and root
travel `0.335999995470047` for a synthetic 0.48-unit source displacement scaled by
0.7. It does not establish natural footwork, accurate skin deformation, contact IK
or realistic human dance. The proxy is segmented capsule geometry, not production
human skin. The fixture has no recorded human performance.

The evidence artifact SHA256 is
`3275687e8a99ae6d1d9033d6bb1c8f91cdd95d26add5c6fe12f88b68b314a772`.
It contains `motion_foundation_report.json` and other test reports/worker logs;
production assets and user data are not included.

## Implementation boundaries

The first milestone implements canonical motion storage, source action export,
metadata scouting through existing providers plus explicit host-search tasks,
rights/provenance gating, stable body profiles, a diagnostic clay proxy, an
explicit retarget bridge and temporal-review receipts. Reviewed mapping/reference
alignment are still required. Unit conversion is explicit and separate from body
proportion scaling. The synthetic retarget fixture exercises meter-based targets;
additional real-rig and non-meter workstation cases remain useful acceptance work.

CMU/AIST/AMASS native-format conversion and new direct dataset acquisition adapters,
GPU video reconstruction, model weights, contact IK, nonlinear limb fitting,
production-quality skin, semantic dance recognition and continuous-video rendering
remain deferred. A host discovery task is not an executed search. A contact
candidate is not proof of intended planting or gliding. A caller-attested review
receipt cannot prove a model actually watched a video.

Technical success never awards performance or human acceptance. No GPU inference,
paid API, user scene, installed skill, model/MCP settings or credentials were used
or changed. The original main branch and v0.5.0 release remain unchanged.

## Pull and test

Follow [LOCAL_MOTION_ACCEPTANCE.md](LOCAL_MOTION_ACCEPTANCE.md) in a separate
worktree and disposable test library. Do not run the published v0.5.0 installer and
expect this development code, or invent a v0.6.0-dev.1 release URL. Do not replace
the user's installed working skill before scoped local acceptance succeeds.

After synthetic success, use a copy of one already-acquired, permission-verified
source take and compare it over time with both proxies. Keep the source, raw
canonical record, retargeted results and all prior scene evidence separate.
