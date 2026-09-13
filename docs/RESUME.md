# Resume the published Codex skill

The current published installer preview is **v0.3.1**, release commit `0b7bc07` (implementation `08c908d`). Release workflow 34730860117 passed its verify, publish and anonymous public-install jobs on Windows, macOS and Linux. Read SETUP_ACCEPTANCE.md, ACCEPTANCE.md and STUDIO_TESTS.json for evidence; documentation commits may follow the released code.

v0.3.1 is a correctness patch from the real v0.3.0 acceptance test: explicit world-point camera aims are authorable and verifiable in both create and adapt mode (an all-point plan previously failed with `RESOURCE_LIMIT`), and camera orientation is solved as a roll-free frame so a requested roll is measured back from the evaluated camera instead of drifting through yaw/pitch composition. `camera-check` now compares requested versus measured roll per checkpoint.

v0.3.0 adds reviewed animated camera authoring (`camera-plan`): host-supplied checkpoints, placement, aim, lens, normalized screen position, roll, focus and interpolation are solved, keyed and verified with real projection, and `camera-check` samples a move for framing, clip planes, lens/sensor, orientation, screen-target error and bounded occlusion rays. Preview jobs now restore and re-verify the project's own render settings before saving, so a preview artifact cannot become a delivery master. `camera-plan` remains perspective-only and orthographic plans are refused rather than approximated.

The README is the installation entry point. The bootstrap verifies an explicit version's release ZIP, runs offline checks and uses the managed installer. It remembers Blender/library paths without modifying Codex, DeepSeek, MCP or Blender preferences. Python 3.11+, local Codex and a functioning Blender MCP are prerequisites, not secretly installed dependencies. Teaching overlay is optional. Keep assets and credentials outside the public repo.

Next meaningful gate: use the user's actual local Codex session to invoke `$blender-asset-director` and run references/first-run.md. Verify discovery, paths and a read-only scene query. Do not open another file, discard unsaved work or begin artistic changes merely to test installation. After the user requests a creative task, operate on a separate working copy.

The seven-role layer remains scene-independent. `plan` returns an unfilled intake; the host interprets the actual prompt and fills an audited contract. For material-only work, do not route skeletal work; products and environments need no armature. Object motion is separate from humanoid retargeting. Existing scene assets are reused or adapted before justified external scouting.

Technical CI is not artistic acceptance. Source motion was acquired and tested, but arbitrary rigs, foot IK, equipment/cloth cleanup, full video/audio output and human quality review are not established solely by those tests. A text-only model cannot approve images. Preserve numeric warnings and source receipts; enforce the user's preview/repair budget across jobs.

For updates, preserve managed install receipts and edited files. Prepare fresh jobs after code/input changes rather than bypassing hashes. Do not move or overwrite a published version/tag to hide a failure. A new release request must name a new reviewed version; publication is gated by reusable CI and followed by public installer tests.
