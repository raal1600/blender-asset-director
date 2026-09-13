# Setup acceptance — published 0.4.0 preview

Release: https://github.com/raal1600/blender-asset-director/releases/tag/v0.4.0

Release request commit: `662b506` (implementation `d9f93bc`, cross-version fixture fix `f53e9f2`).

Evidence: https://github.com/raal1600/blender-asset-director/actions/runs/34734198761 (verify, publish and anonymous public install).

## Why 0.4.0 exists

Real acceptance tests repeatedly found that the Lighting / Look Development role could reason about exposure, world contribution, colour management and existing-light changes while the reviewed executor had no safe operation for them - and the agent correctly refused to bypass the executor with arbitrary scene Python. 0.4.0 makes those decisions executable as explicit values: `look-audit`, `light-adjust`, `world-adjust` and `look-adjust`, with before/after snapshots, isolation guarantees and runtime validation of version-dependent values. It is a new capability, not a preset library: there is no genre keyword path, no shader-node editing and no arbitrary Python.

## v0.4.0 release gate

- Windows/Python 3.11 unit/policy/studio/setup suite (198 tests).
- Ubuntu/Python 3.11 and 3.13 unit/policy/studio/setup suites.
- Managed skill installation and uninstall checks.
- Windows PowerShell 5.1 and PowerShell 7 bootstrap install/repeat/update/health/uninstall checks.
- macOS and Linux bootstrap checks.
- Blender 4.5.3, 5.0.0 and 5.2.1 technical fixtures, including the new look fixture.
- Preview-settings restoration, original-file preservation and stale-job checks (unregressed).
- Required Blender 5.0 live provider/source-motion checks.
- Release publication and anonymous installation of v0.4.0 on Windows, macOS and Linux without a repository checkout or supplied GitHub credentials.

Published archive: `blender-asset-director-0.4.0.zip`, SHA256 `2a688ba058880ed9dc29ecd686c1502ba0f10c370c1ece5b0cfada7e2172379e`.

The first release request failed required CI: the new Blender fixture hardcoded the EEVEE engine identifier, which Blender 4.5.3 does not accept. The pipeline correctly refused to publish; the fixture now discovers a valid engine from the running version and the retried request (attempt 2) passed. Blender 4.5.3, 5.0.0 and 5.2.1 all pass with the corrected fixture.

The release remains a preview: cloud/CI success is not the user's local Codex/MCP session or artistic acceptance, and technically applied lighting or exposure changes still require rendered before/after inspection.

## Earlier record — 0.3.1 preview

Release: https://github.com/raal1600/blender-asset-director/releases/tag/v0.3.1

Release request commit: `0b7bc07` (implementation `08c908d`).

Evidence: https://github.com/raal1600/blender-asset-director/actions/runs/34730860117 (verify, publish and anonymous public install).

## Why 0.3.1 exists

A real local v0.3.0 acceptance test on Blender 5.2.1 authored an improved animated camera for a 240-frame push-in and exposed two correctness defects: an all-`aim.point` plan was refused with `RESOURCE_LIMIT: Provide one to 32 screen targets` because internal verification only built targets from subject-based aims, and a plan requesting zero roll produced up to ~0.174 deg of measured roll because the screen offset was solved by yawing about the camera's pitch-tilted local up axis.

0.3.1 makes explicit world-point aims first-class in both `camera-plan` and `camera-check`, and replaces the orientation composition with a closed-form roll-free frame plus an un-roll of the screen offset, so a requested roll is measured back from the evaluated camera. It is a correctness patch, not a new feature line.

## v0.3.1 release gate

- Windows/Python 3.11 unit/policy/studio/setup suite (185 tests).
- Ubuntu/Python 3.11 and 3.13 unit/policy/studio/setup suites.
- Managed skill installation and uninstall checks.
- Windows PowerShell 5.1 and PowerShell 7 bootstrap install/repeat/update/health/uninstall checks.
- macOS and Linux bootstrap checks.
- Blender 4.5.3, 5.0.0 and 5.2.1 technical fixtures, including the extended camera fixture.
- Preview-settings restoration, original-file preservation and stale-job checks (unregressed).
- Required Blender 5.0 live provider/source-motion checks.
- Release publication and anonymous installation of v0.3.1 on Windows, macOS and Linux without a repository checkout or supplied GitHub credentials.

Published archive: `blender-asset-director-0.3.1.zip`, SHA256 `76b1285518b79795746224a791ba92de0227d4200663c1f1f4f5e4182f3c9160`.

The release remains a preview: cloud/CI success is not the user's local Codex/MCP session or artistic acceptance, and `camera-plan` still authors perspective cameras only.

## Earlier record — 0.3.0 preview

Release: https://github.com/raal1600/blender-asset-director/releases/tag/v0.3.0

Release request commit: `8a1618c29f4b4dc50b745965af13fe26b2b51c71`.

Evidence: https://github.com/raal1600/blender-asset-director/actions/runs/34729010327 (verify, publish and anonymous public install).

## Why 0.3.0 exists

`camera-plan` adds reviewed animated camera authoring: a host supplies explicit frame checkpoints, placement, aim, lens, normalized screen position, roll, focus and interpolation, and the runtime solves, keys and verifies them with real projection. `camera-check` now samples a move for framing, clip planes, lens/sensor, orientation/roll, screen-target error and bounded occlusion rays. Preview jobs also stopped persisting preview render settings into the artifact they save, so a preview `.blend` cannot be mistaken for a delivery master.

## v0.3.0 release gate

- Windows/Python 3.11 unit/policy/studio/setup suite (172 tests).
- Ubuntu/Python 3.11 and 3.13 unit/policy/studio/setup suites.
- Managed skill installation and uninstall checks.
- Windows PowerShell 5.1 and PowerShell 7 bootstrap install/repeat/update/health/uninstall checks.
- macOS and Linux bootstrap checks.
- Blender 4.5.3, 5.0.0 and 5.2.1 technical fixtures.
- Generic studio camera/light and rig-free preview regressions.
- New camera fixture: create-mode moves across unrelated names, aspects, sensor fits, frame rates and lenses; an establishing-to-closer move with a changing screen position, a lens change and an animated subject; host-chosen world positions honoured exactly; adapt mode preserving a prior camera action while refusing a kept constraint that would defeat the authored aim; sampled checkpoints, screen-target error and bounded occlusion rays.
- Preview-settings regression: the resolution, resolution percentage, engine, samples, output format/path, thread settings and frame of the project were re-verified in the `.blend` a real preview job saved.
- Required Blender 5.0 live provider/source-motion checks.
- Release publication and anonymous installation of v0.3.0 on Windows, macOS and Linux without a repository checkout or supplied GitHub credentials.

Published archive: `blender-asset-director-0.3.0.zip`, SHA256 `e29704738f0b18a2b566a24801f5d95c5b4bd47291e2ef1f7998703262f3ecee`.

The release remains a preview because cloud/CI success is not the same as the user's local Codex/MCP session or artistic acceptance. `camera-plan` authors perspective cameras only; orthographic plans are rejected rather than approximated, and numeric framing evidence is not an artistic verdict.

## Earlier record — 0.2.2 preview

Release: https://github.com/raal1600/blender-asset-director/releases/tag/v0.2.2

Release request commit: `20d56b506f38e85f7bb3f14dad98b38a904e0d9a`.

Evidence: https://github.com/raal1600/blender-asset-director/actions/runs/34726272262

## Why 0.2.2 exists

A real Windows installation of v0.2.1 used Blender's bundled Python 3.13.13 and correctly discovered Blender 5.2. The offline test `test_job_missing_blender_actionable` configured the temporary runtime before mocking Blender discovery, so the real Blender executable was persisted into test settings and the test then incorrectly expected a `BLENDER_NOT_FOUND` result.

This was a test-isolation defect, not a failure to detect Blender. v0.2.2 moves the discovery mock before configuration, proving the missing-Blender branch independently of what is installed on the host.

No safety rule, path validation, provider restriction, or Blender detection behavior was weakened.

## v0.2.2 release gate

The corrected release gate passed:

- Windows/Python 3.11 unit/policy/studio/setup suite.
- Ubuntu/Python 3.11 and 3.13 unit/policy/studio/setup suites.
- Managed skill installation and uninstall checks.
- Windows PowerShell 5.1 and PowerShell 7 bootstrap install/repeat/update/health/uninstall checks.
- macOS and Linux bootstrap checks.
- Blender 4.5.3 and 5.0.0 technical fixtures.
- Generic studio camera/light and rig-free preview regressions.
- Required Blender 5.0 live provider/source-motion checks.
- Release publication.
- Anonymous/public installation from the published release on Windows, macOS and Linux, without repository checkout or supplied GitHub credentials.

The release remains a preview because cloud/CI success is not the same as the user's local Codex/MCP session or artistic acceptance.

## What setup adds

A pinned-release bootstrap, integrity-checked archive, complete managed skill/runtime, seven role modules, notices, path-only local configuration, a separate asset library, Blender executable discovery and first-run guidance.

It does not install or replace Blender, Codex, model providers or MCP servers. Existing Codex/provider/MCP configuration is not rewritten. It does not launch model calls, bulk-download assets or modify user `.blend` projects during installation.

## Remaining local acceptance

The user must start a fresh local Codex session and invoke `$blender-asset-director`. The first-run flow should verify skill discovery and perform an actual read-only Blender MCP scene query before any editing is authorized.

No cloud test authenticates the user's Codex/DeepSeek account, proves local MCP connectivity, certifies model vision, operates the user's Blender GUI, or approves artistic output. Arbitrary-rig transfer, foot planting, equipment/cloth clearance and full authorized animation/audio delivery remain separate acceptance scopes.
