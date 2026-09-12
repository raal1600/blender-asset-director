# Acceptance evidence — implementation candidate

## Executed in the build environment

- **PASS:** 65 independent Python unittest methods. Tests include catalog rebuild, schemas, license policy, ranking, job identity/stale input, environment credential removal, safe intake/extraction, URI boundaries, mock redirect credential separation, download-budget enforcement and motion metrics.
- **PASS:** installer round trip in a temporary directory: fresh installation, bundled runtime launch, protection of edited files, and uninstall preserving the library.
- **PASS:** Python compilation and CLI doctor/planner smoke checks.
- Platform: Linux, Python 3.13.5. These results do not establish Windows or Blender compatibility.

## Prepared but not executed

- **NOT RUN:** Windows/Python 3.11 CI.
- **NOT RUN:** Blender 4.5.3 and 5.0.0 real GLB/FBX import, renamed/resized fixture rig transfer, FPS/NLA/root-controller and save tests.
- **NOT RUN:** live Quaternius acquisition and per-clip indexing.
- **NOT RUN:** real retrieved-motion retarget and small CPU previews.
- **NOT RUN:** live Poly Haven/ambientCG acquisition/import and Sketchfab authenticated download.
- **REQUIRES HUMAN CONFIRMATION:** the actual local Codex/DeepSeek/MCP integration and visual quality on the user's warrior.

## Publication blocker

Both Git data creation and file-content creation were rejected by GitHub with HTTP 403, `Resource not accessible by integration`. The connected GitHub app installation uses selected-repository access; the new `blender-asset-director` repository is not included in that installation selection. Account-level `push: true` metadata was insufficient to establish app write authorization.

No code has been pushed by these failed calls and no GitHub Actions run has been started. Add the new repository to the installed app's repository selection, then publish the candidate and run the actual CI workflow. Do not call this version validated for the local scene before those gates pass.

## Quality limits that remain even after CI

The fixture proves only the cases it actually exercises. It does not prove arbitrary-rig compatibility, foot IK, cloth/weapon contact, historically accurate motion or natural cinematic movement. The terrain controller handles gentle root-height changes only. Final acceptance requires review of the actual source motion and user scene in a separate working copy.
