# Setup acceptance — 0.2.1 preview

This release adds a pinned-release bootstrap (Windows PowerShell and macOS/Linux shell), SHA256 archive verification, managed installation/update/uninstall, local path configuration, Blender path discovery, and a read-only Codex first-run workflow. The README now starts with prerequisites, installation and two trial prompts.

## Test boundaries

Offline unit tests cover configuration precedence, rejecting overlapping library/skill paths, missing Blender, secret-free read-only MCP summaries, malformed settings, package checksum/path/collision/symlink checks and version identity. The process-level bootstrap smoke exercises installation, repeated installation, an update with backup, remembered paths, unchanged Codex configuration and offline uninstall preserving the library. CI runs it on PowerShell 5.1/7, Linux and macOS.

Existing Blender/import/retarget/studio fixtures and live asset tests remain in the main CI workflow. Release publication is gated on this workflow, then a separate anonymous-download smoke tests the actual published package. A green packaging step alone is not the installation test.

This document initially describes the gates, not a claim that every platform has already passed. The executed run/commit evidence is recorded in the final setup evidence update.

## Not established by these tests

No test here authenticates a user's Codex or DeepSeek account, operates a user's Blender GUI/MCP, certifies a model's vision, or approves artistic output. The first-run prompt is an actual local acceptance step. Installation cannot give a hosted cloud session direct access to a user's desktop. Python/Blender/Codex/MCP are prerequisites, not secretly installed dependencies.

## Distribution trust

The bootstrap selects a version tag and refuses fallback to main. Release ZIP bytes must match the checksum before extraction. Both come from the same GitHub publisher; this is integrity verification, not a detached signature, attestation or independent audit. Install/update runs no paid calls or model requests. Changes are confined to the managed skill and Asset Director's path configuration/library; existing Codex/provider/MCP/Blender settings are not rewritten.
