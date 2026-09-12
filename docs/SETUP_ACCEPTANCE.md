# Setup acceptance — published 0.2.1 preview

Release: https://github.com/raal1600/blender-asset-director/releases/tag/v0.2.1

Tested and released source commit: `7d19b6d53726bb861b15e8eca3500ccd575660f4`.

Evidence: https://github.com/raal1600/blender-asset-director/actions/runs/34725395309

**All 13 jobs completed successfully:** nine verification jobs, release publication, and three public-download installation jobs. This documentation update follows the tested code; it does not move the published tag or replace release assets.

## What was executed

| Gate | Result and scope |
|---|---|
| Unit/policy/studio/setup suite | 140 tests passed on Windows/Python 3.11, Ubuntu/Python 3.11 and Ubuntu/Python 3.13 |
| Managed installer | Fresh installation, repeat installation, bundled runtime, role/license presence, edited-file protection and library-preserving uninstall passed |
| Windows PowerShell 5.1 bootstrap | Actual process-level archive verification, install, repeat install, update with backup, saved paths, unchanged Codex config and offline uninstall passed |
| Windows PowerShell 7 bootstrap | Same process-level checks passed |
| macOS shell bootstrap | Same process-level checks passed |
| Linux shell bootstrap | Same process-level checks passed |
| Blender 4.5.3 and 5.0.0 | Existing real Blender import/retarget/NLA fixtures, generic studio camera/light cases and rig-free CPU preview regressions passed |
| Live asset/source motion | Required live provider and retrieved-animation checks passed in the Blender 5.0.0 job |
| Release publication | Created the v0.2.1 preview and uploaded the release ZIP, three launchers and SHA256SUMS.txt after verification |
| Actual public Windows installation | A runner without repository checkout or supplied GitHub credentials fetched the tag-pinned PowerShell launcher, downloaded the published release ZIP, installed it, ran doctor/receipt verification and uninstalled while preserving the library |
| Actual public macOS and Linux installation | Equivalent public shell-bootstrap and installed-runtime checks passed on both platforms |

The public installation jobs were run with Python available and explicit temporary destinations, not on a completely unprovisioned desktop. Their missing-Codex/MCP status was reported honestly. They demonstrate the published download path, not live Codex skill discovery.

Release ZIP SHA256:

```text
1c773a32e0c49bdb82f90a04db34f1e903a0cffc1b8876bc0b48611653de101d
```

## Failures found and corrected

The first Windows run exposed ZIP path normalization differences. Archive validation now checks the original stored entry name, and fixtures write the unsafe raw names deliberately on every OS. No traversal/collision checks were disabled.

A repeated Windows test exposed a floating-point clock assertion (`15.000000000000007` versus `15`). The connection-timeout regression now uses a deterministic clock and separately tests an expired deadline. Production timeout and destination restrictions were not weakened. Failed historical runs remain visible.

## What installation adds

A pinned-release bootstrap, integrity-checked archive, complete managed skill/runtime, seven role modules, notices, path-only local configuration, a separate asset library, Blender executable discovery and first-run guidance. The installer runs offline checks before replacing a managed skill, refuses edited/unowned destinations, and supports explicit backed-up updates. Uninstall is offline and preserves library/settings.

It does not install or replace Python, Blender, Codex, model providers or MCP servers. It does not launch a model call, bulk-download assets, enable Blender auto-run or render the user's scene. Existing Codex/provider/MCP configuration is not rewritten. The optional teaching overlay is not a prerequisite.

## Remaining local acceptance

The actual user must start a new local Codex session and invoke the first-run workflow. It must verify skill discovery and an actual read-only Blender MCP scene query. A configured declaration or executable path is not a live connection.

No cloud test here authenticates the user's Codex/DeepSeek account, certifies the model's image capability, operates the user's Blender GUI or approves artistic output. Arbitrary-rig transfer, foot planting, equipment/cloth clearance and full authorized animation/audio delivery remain separate capabilities and acceptance scopes. See [studio acceptance](ACCEPTANCE.md) for those boundaries.

## Distribution trust

The bootstrap selects an explicit version and refuses fallback to moving main. ZIP bytes must match the published SHA256 before extraction. The ZIP and checksum come from the same GitHub publisher: this is integrity verification, not a detached publisher signature or independent security audit. Review the bootstrap code before execution. Runtime path records contain no provider keys.

Machine-readable summary: [SETUP_TESTS.json](SETUP_TESTS.json).
