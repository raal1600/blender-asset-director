# Setup acceptance — published 0.2.2 preview

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
