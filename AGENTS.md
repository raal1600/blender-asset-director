# Repository implementation rules

Maintain the separation between portable Python, Blender-only code and agent instructions. Run `python tools/run_checks.py --offline` after changes. Actual Blender/headless/provider checks are a separate gate; do not mock them into success. Preserve read-only originals and deliberate failure states.

Do not commit models, animation archives, textures, `.blend` files, credentials, user logs, SQLite databases or configuration backups. All production assets belong in the independent library. Tests generate clearly labeled synthetic fixtures and download public assets only in isolated CI workspaces.

Do not replace existing Codex/DeepSeek providers, MCP servers, Blender preferences or user rigs. No paid calls, local AI inference, broad scraping, blind SDK installation, or automatic permission relaxation. Before changing a pinned third-party backend, inspect the source change, licensing and actual Blender results. Keep quality claims narrower than the measured evidence.

Use tested pull requests for development. Read CONTRIBUTING.md and docs/CONSOLIDATION.md before resuming; dated handoffs are historical. Merge only a validated, unchanged head. Never rewrite main or overwrite unrelated future changes. Delete only merged, unchanged branches after successful main gates. Preserve the existing repository license.
