# Resume the published Codex skill

The current published installer preview is **v0.2.1**, source commit `7d19b6d53726bb861b15e8eca3500ccd575660f4`. Release workflow 34725395309 passed all 13 jobs, including actual public-download installs on Windows, macOS and Linux. Read SETUP_ACCEPTANCE.md and SETUP_TESTS.json for evidence; documentation commits may follow the released code.

The README is the installation entry point. The bootstrap verifies an explicit version's release ZIP, runs offline checks and uses the managed installer. It remembers Blender/library paths without modifying Codex, DeepSeek, MCP or Blender preferences. Python 3.11+, local Codex and a functioning Blender MCP are prerequisites, not secretly installed dependencies. Teaching overlay is optional. Keep assets and credentials outside the public repo.

Next meaningful gate: use the user's actual local Codex session to invoke `$blender-asset-director` and run references/first-run.md. Verify discovery, paths and a read-only scene query. Do not open another file, discard unsaved work or begin artistic changes merely to test installation. After the user requests a creative task, operate on a separate working copy.

The seven-role layer remains scene-independent. `plan` returns an unfilled intake; the host interprets the actual prompt and fills an audited contract. For material-only work, do not route skeletal work; products and environments need no armature. Object motion is separate from humanoid retargeting. Existing scene assets are reused or adapted before justified external scouting.

Technical CI is not artistic acceptance. Source motion was acquired and tested, but arbitrary rigs, foot IK, equipment/cloth cleanup, full video/audio output and human quality review are not established solely by those tests. A text-only model cannot approve images. Preserve numeric warnings and source receipts; enforce the user's preview/repair budget across jobs.

For updates, preserve managed install receipts and edited files. Prepare fresh jobs after code/input changes rather than bypassing hashes. Do not move or overwrite a published version/tag to hide a failure. A new release request must name a new reviewed version; publication is gated by reusable CI and followed by public installer tests.
