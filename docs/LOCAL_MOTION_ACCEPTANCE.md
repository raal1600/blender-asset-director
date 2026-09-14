# Pull and test the motion foundation

Branch `feature/motion-foundation`, development runtime `0.6.0-dev.1`.
**Not a published release. Do not replace the installed working skill yet.**
Read AGENTS.md, MOTION_FOUNDATION.md and the installed motion reference first.

## Checkout

Fetch the branch into a separate checkout/worktree; preserve existing local changes.
Never reset/clean the user's repository, installed runtime, or asset library.
Record `git rev-parse HEAD` before testing. For an existing repository:

```text
git fetch origin feature/motion-foundation
git worktree add --detach ../asset-director-motion-test origin/feature/motion-foundation
```

Choose another unused worktree path if that example already exists. Use the actual
registered Blender-bundled Python, not the broken Windows Store python alias.

## Offline and packaging checks

```text
python tools/run_checks.py --offline
python tools/install_skill.py --dest <new-temporary-skill-directory>
python <new-temporary-skill-directory>/scripts/director.py --help
```

Do not pass --configure or overwrite the production skill. The source install
bundles the runtime; a generic copy of SKILL.md alone is not a functional install.
The main README's release installer still installs v0.5.0, not this branch.

## Actual Blender fixture

Create a new disposable library. Set PYTHONPATH to this checkout's src only for
these commands. Acquire the existing pinned backend into that test library with
`python -m asset_director --library <test-library> backend-install`, or reuse a
previously verified backend there and verify it. No new models/GPU dependencies.

```text
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/motion_foundation_fixture.py -- <new-output-directory> <test-library>
```

Use the discovered absolute blender.exe path, not a guessed executable. The fixture
creates synthetic motion; exports an immutable record; tests offline rediscovery,
matched-time reconstruction, source-shaped and short-leg/long-arm proxies, body
profiles, v0.5 transfer, stale-profile refusal, camera/light and a tiny CPU preview.
Keep motion_foundation_report.json and logs. It needs no live MCP and must not open
or read a production .blend. Never disable a guard to make a case pass.

## One real existing motion after synthetic success

Reuse an already-acquired licensed motion; do not download duplicate assets. Inspect
actual source rig/action, semantic roles, unit/axis convention, range and rights.
Capture_method=unknown is correct when an asset page does not prove mocap.

Follow the installed reference contracts:
motion-scout -> existing intake/index as needed -> motion-evidence -> motion-export
-> motion-collect -> body-audit -> retarget-profile -> clay-proxy -> motion-retarget
-> existing assembly/presentation -> numerical and actual temporal review.

Use returned IDs/paths. Do not copy synthetic identity alignment or units onto an
unrelated rig. Declare target_meters_per_unit independently of morphology ratios.
Keep unsupported IK, rig, format or licensing cases blocked and report them.

For source export, use a saved copy. For any live production access, first verify
the actual current target read-only and preserve unsaved work through an authorized
copy. No resetting/reopening the live window just to run fixture tests.

Keep detailed data on disk. Do not load entire logs, arrays, or many high-resolution
images into the model session. A model that only sees still images must leave
performance pending; this branch does not add a video renderer or expand budgets.

## Report and stop

Report exact commit/runtime; offline/Blender results; license and capture evidence;
canonical hashes/timestamps/reuse; source/target proportions and root scale; proxy
and target paths; rig/mapping/alignment review; numerical metrics; temporal evidence
actually inspected; unchanged source files; and reproducible failures.

Separate TECHNICAL PASS/FAIL, PERFORMANCE PASS/REJECTED/PENDING and HUMAN NOT
ESTABLISHED. Do not claim a generic clip became authentic choreography through
retargeting. Do not automatically merge, publish, replace the user's installed
skill, start GPU/model installation, or change a production scene after this test.
