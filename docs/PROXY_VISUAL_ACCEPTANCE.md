# Proxy surface correction — executed repository acceptance

Branch: `feature/motion-foundation`.
Development runtime: `0.6.0-dev.1` (no new tag or release).

Implementation commits:
- `977c6d6ef11ade6607ad84993ff44141ec80450d`: anatomical visualization graph,
  endpoint-bound proxy skin, evaluated attachment QA, unit/Blender regressions.
- `9af3f6ecf883a61bfc6c4e502b86cc1939725593`: outward surface winding,
  signed-volume/manifold regression, and an articulated midpoint preview.

The exact second commit passed all ten jobs in:
https://github.com/raal1600/blender-asset-director/actions/runs/34798852723

This documentation-only commit follows the tested runtime. It does not update
main, publish a release, change the user's installed skill, or alter local assets.
The development runtime version alone does not distinguish this build: pin the
commit. The full roadmap remains incomplete; this patch addresses visualization.

## What actually ran

| Gate | Result |
|---|---|
| Portable suite | 296 tests, including 12 new anatomy-graph regressions |
| CI unit matrix | Windows/Python 3.11, Ubuntu/Python 3.11 and 3.13 passed |
| Managed install | Temporary installation/repeat, runtime launch, edit protection and library-preserving removal passed |
| Bootstrap matrix | Windows PowerShell 5.1 and 7, macOS sh, Ubuntu sh passed |
| Real Blender | 4.5.3, 5.0.0 and 5.2.1 passed previous fixtures and the new deformed-surface fixture |
| Existing live provider/motion regression | Passed in the 5.0.0 job; intentionally not duplicated on other versions |
| Source assets/user workstation | Not accessed; real-source local revalidation remains required |

The offline tests/install checks also ran in the development container. Blender
execution took place in GitHub runners, not in that container. These are source
bootstrap tests, not anonymous public installation tests for a new release.

## Stronger regression, not another skeleton-only assertion

`tools/proxy_visual_fixture.py` creates an unrelated synthetic rig with:
- a 1.316 m root-to-hips offset, stationary root and traveling hips;
- long decorative display tails and upper-body leaf controls;
- an intermediate rotating helper between anatomical landmarks;
- renamed bones and explicit semantic roles;
- source-shaped and 0.8-leg/1.15-arm generated proxies.

The fixture reopens saved results and measures actual deformed mesh ring/landmark
centres at 25 timestamps (43 attachments per proxy in this fixture). It confirms
root/helper bones remain in the rig but have no direct surface groups or rendered
segments. It also tests that deliberately displaced skin fails attachment QA and
an added root vertex group is refused, even though the skeleton remains valid.

Downloaded Blender 5.2.1 evidence reports:
- source-shaped maximum attachment error: 6.447228089804631e-7 scene units;
- altered-proportion maximum attachment error: 4.918001095863418e-7 scene units;
- altered leg ratio: 0.8; arm ratio: 1.1499999540547536;
- root/helper direct surface weights: zero.

The fixture uses meters. These errors measure MESH-TO-RIG attachment only. They
must not be confused with source-to-target retarget accuracy or dance fidelity.

Two 480x480, eight-sample CPU previews at frames 1 and 16 were downloaded and
visually inspected. They show a connected segmented diagnostic figure without a
separate root capsule or decorative helper spikes in these two synthetic views.
The midpoint pose includes articulated limbs. This is not continuous playback
review, photorealistic anatomy, seamless human skin, or acceptance of the user's
actual Moonwalk performance. Render settings were restored.

Blender 5.2.1 evidence artifact SHA256:
`80d87e222b3ab9164798d2ee43d15400d74fdd604150bc8c115ef95a8385329f`.
It contains `proxy_visual_report.json`, `proxy-rest.png`, `proxy-pose.png`, and the
existing fixture reports/logs. It contains no user source assets.

## Preserved boundaries and next local test

The code responsible for semantic limb scaling, endpoint timing, canonical source
samples and evaluated-pose transfer was not changed. Source data and previous
failed outputs remain immutable. Generated geometry is new, so rerun downstream
proxy/retarget jobs; do not edit old completed job receipts or reuse old proxy
surfaces as if updated by the code change.

Follow [PROXY_VISUAL_FIX.md](PROXY_VISUAL_FIX.md) and reuse the already-verified
canonical Moonwalk record on the user's workstation. Generate both new proxies
with the actual .8-leg/1.15-arm request. Inspect their excluded-bone manifests,
actual skin groups, and `proxy_attachment_check`; compare the rendered surface,
not just bones, with the prior failing views. No download/re-export is required.

Keep the user's previous TECHNICAL FAIL and PERFORMANCE PENDING as historical
evidence. Only a new real-source test can close that particular local defect.
A successful synthetic fixture is not a retroactive local acceptance pass.

No sculpt mode, remeshing, contact IK, body-volume fitting, GPU reconstruction,
new provider acquisition, paid API, production project, or global configuration
change was used. Endpoint blending may shear or self-intersect; those remain
explicit visualization limitations rather than hidden performance guarantees.
