# Acceptance evidence — scene-independent studio candidate

## v0.3.1 — correctness patch from the real v0.3.0 acceptance test

Tested implementation commit: `08c908d` (release request `0b7bc07`, tag `v0.3.1`).
Technical CI: https://github.com/raal1600/blender-asset-director/actions/runs/34730860035 — all ten jobs passed.
Release: https://github.com/raal1600/blender-asset-director/releases/tag/v0.3.1 (run 34730860117: verify, publish and anonymous public install on Windows, macOS and Linux all passed; archive SHA256 `76b1285518b79795746224a791ba92de0227d4200663c1f1f4f5e4182f3c9160`).

Two defects found by exercising v0.3.0 on a real Blender 5.2.1 project:

| Defect | Root cause | Fix |
|---|---|---|
| An all-`aim.point` camera plan failed with `RESOURCE_LIMIT: Provide one to 32 screen targets` | The plan built its internal verification targets only from subject/bounds aims, so point-only plans produced an empty list, which `camera-check` rejects | Targets may name an explicit world `point`; the plan emits one verification target per checkpoint; the target contract moved into the portable module |
| A plan requesting `roll_deg: 0` produced up to ~0.174 deg of measured roll early in the move | The screen offset was solved by yawing about the camera's *local* up axis, which is tilted by the base pitch, injecting roughly `yaw * sin(pitch)` | Orientation is built directly as a roll-free frame (closed form), and the screen offset is un-rolled before an explicit roll is applied |

| Check | Actual result |
|---|---|
| Unit/policy/studio suite | 185 tests passed on Windows/Python 3.11, Ubuntu/Python 3.11 and Ubuntu/Python 3.13 |
| Blender fixtures | 4.5.3, 5.0.0 and 5.2.1: existing import/retarget/NLA, generic studio and camera fixtures all passed |
| Camera fixture (re-run locally on 5.2.1) | 152 checks, including all-point-aim plans (constant and changing lens, create and adapt mode), a standalone `camera-check` call with point targets, and roll cases: zero roll on centred and aggressively off-centre targets, +7 deg, -4 deg and a 0/+3/-2 deg ramp across one move |
| Measured roll error | <= 5.2e-6 deg against requested values of 0, +7 and -4 deg (v0.3.0 drifted 0.174 deg) |
| Point-aim screen error | <= 5.6e-7 normalized |
| Public install | v0.3.1 installed anonymously on Windows, macOS and Ubuntu runners; runtime doctor, receipt verify and library-preserving uninstall passed |

What this establishes: explicit world-point aims are authorable and verifiable with no scene object behind them, in both create and adapt mode and with constant or changing lens; a requested roll is measured back from the evaluated camera within a tolerance far below visual significance; and the v0.3.0 camera, preview, preservation and budget behaviour is unregressed on all three tested Blender versions.

What this does not establish: `camera-plan` remains perspective-only; occlusion evidence is still bounded ray testing rather than collision or clearance safety; between-checkpoint extrema are not evaluated; and numerical framing and roll evidence is not an artistic verdict. No user scene was modified for this patch.

## v0.3.0 — animated camera authoring and preview-artifact fix

## v0.3.0 — animated camera authoring and preview-artifact fix

Tested implementation commit: `8a1618c29f4b4dc50b745965af13fe26b2b51c71`.
Technical CI: https://github.com/raal1600/blender-asset-director/actions/runs/34729010248 — all ten jobs passed.
Verified preview release: https://github.com/raal1600/blender-asset-director/releases/tag/v0.3.0 (run 34729010327: verify, publish and anonymous public install on Windows, macOS and Linux all passed; archive SHA256 `e29704738f0b18a2b566a24801f5d95c5b4bd47291e2ef1f7998703262f3ecee`).

| Check | Actual result |
|---|---|
| Unit/policy/studio suite | 172 tests passed on Windows/Python 3.11, Ubuntu/Python 3.11 and Ubuntu/Python 3.13 |
| Blender fixtures | 4.5.3, 5.0.0 and 5.2.1: existing import/retarget/NLA fixtures, generic studio regressions and the new camera fixture all passed |
| Camera fixture (re-run locally on 5.2.1) | 80 checks: create-mode moves on unrelated names, aspects, sensor fits, frame rates and lenses; establishing-to-closer move with a changing screen position, a per-checkpoint lens change and an animated subject; host-chosen world positions honoured exactly; adapt mode preserving the prior action and refusing a kept constraint that would defeat the authored aim; sampled checkpoints, screen-target error and bounded occlusion rays |
| Preview-settings regression | A real preview job saved a `.blend` whose resolution, resolution percentage, engine, samples, output format/path, thread settings and frame were re-verified as the project's own |
| Public install | v0.3.0 installed anonymously on Windows, macOS and Ubuntu runners; runtime doctor, receipt verify and library-preserving uninstall passed |

What this establishes: `camera-plan` authors and verifies explicit camera moves from host-supplied values on synthetic scenes with unrelated names, formats and timebases; the perspective screen-space solve matches Blender's own framing for AUTO, HORIZONTAL and VERTICAL sensor fits on the tested versions; adapting a camera preserves its earlier action and refuses a kept constraint that would silently defeat the authored aim; and preview rendering no longer contaminates the settings of the file it saves.

What this does not establish: `camera-plan` authors perspective cameras only and rejects orthographic plans rather than approximating them; the fixture is synthetic geometry with no rigs, cloth or terrain contact; occlusion evidence is bounded ray testing rather than collision or clearance safety; framing numbers, screen-target errors and successful saves are not an artistic verdict; and no user scene, local Codex/MCP session or human review was involved. Artistic acceptance of any shot remains with the user.

## Earlier recorded run — studio candidate (v0.2.x)

Tested implementation commit: `4af4711981088a0442a1f3d91b73f0456c65775a`.
GitHub Actions run: https://github.com/raal1600/blender-asset-director/actions/runs/34723246054
All five jobs completed successfully in that run. This records technical execution, not a claim that arbitrary scenes are artistically accepted.

## Passed in the recorded run

| Check | Actual result |
|---|---|
| Unit/policy/studio suite | 109 tests passed on Windows/Python 3.11, Ubuntu/Python 3.11 and Ubuntu/Python 3.13 |
| Skill installer | Bundled runtime launch, role/license presence, edited-file protection and library-preserving uninstall passed on all three targets |
| Blender 4.5.3 | Existing synthetic import/retarget/NLA fixtures and new generic studio regressions passed |
| Blender 5.0.0 | The same technical fixture groups passed |
| Generic studio regression | Different scales, offsets and 16:9/9:16/1:1/21:9 aspects; perspective/orthographic cameras; sampled animated bounds; existing subject/world/light preservation |
| Rig-free preview | Actual worker produced a 64x64, one-sample Cycles CPU PNG without any armature; original .blend file hash stayed unchanged |
| Quaternius live acquisition | Creator-posted Standard package downloaded and indexed; 46 action records observed, including A_TPose. This is not a claim of 46 distinct production-ready motions |
| Real retrieved motion | Actual Walk_Loop evaluated and baked over 33 output frames to a renamed/scaled duplicate source skeleton in Blender 5.0.0; three small CPU preview frames rendered |
| Poly Haven live integration | HDRI search, acquisition and Blender import passed |
| ambientCG live integration | Material search, ZIP acquisition and Blender material construction passed |

The previously blocking OpenGameArt connection timeout did not occur in this run. No security checks were weakened to obtain a pass. Earlier failed-run history is retained in ACCEPTANCE_0_1.md. A later provider outage is still possible; this is evidence for the recorded execution, not a perpetual availability guarantee.

## What these passes establish

The studio entry point no longer selects a fixed character, terrain, lighting setup, lens, frame rate or duration. Capability-selected role modules and observed-object contracts are executable coordination mechanisms. Camera/light helpers work on the tested geometric variations, and previews do not depend on character rigs.

The scene tests use simple synthetic geometry, not finished product/interior films. They establish framing and preservation invariants, not realism. The motion test uses an actual downloaded clip, but its target is a renamed/scaled duplicate skeleton, not an unrelated artist rig or the user's warrior. Numeric QA retained POSSIBLE_FOOT_SLIDING warnings; contact metrics are heuristic and an in-place clip without calibrated travel is not a foot-lock demonstration. Visual acceptance remains pending human review.

## Still requiring acceptance

- Local Windows Blender GUI, the installed Codex/DeepSeek session and existing MCP/teaching overlay.
- Runtime host discovery of the installed skill and real prompt-to-role execution.
- Arbitrary-rig retargeting, grip/cloth cleanup and terrain foot planting. Root-height following is not foot IK.
- Actual artistic quality against user briefs and reference images. Metadata scores and camera bounds are not aesthetic scores.
- Authenticated Sketchfab and account-based/manual provider workflows.
- Audio acquisition/mixing and full authorized animation delivery, which are not implemented by a planning role alone.

No user project was accessed or modified. The candidate is ready for controlled local installation/read-only compatibility checks and then a separately authorized creative test on a working copy. Do not advertise universal scene support or a production-quality autonomous studio solely from CI success.
