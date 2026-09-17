# Installed studio E2E

`Installed studio E2E` builds an isolated studio from the exact checkout on Linux
and Windows. It runs on development pushes, pull requests and manual dispatch.
It does not require a PR, personal assets, model access, or provider credentials.

The fixture creates a fresh temporary root with spaces in its path and the local
studio's `Archive`, `Database`, `Docs`, `SystemRuntime`, and `Workspace` layout.
It installs the bundled harness using the real installer, initializes its SQLite
catalog, copies the launcher from the same checkout, and redirects harness and
Blender configuration into the fixture. The server starts from its installed
location using the normal root-discovery behavior. No E: drive is required.

## Measured workflow

1. Generate a real animated cube scene with checksum-verified Blender 5.2.1.
2. Start the installed launcher and verify installation health and authentication.
3. Use Chromium to create a project, save its brief, complete onboarding, scan,
   link and verify the generated source package, and select a working scene.
4. Run a real saved-scene audit through the UI and inspect its successful job.
5. Prepare a native preview job and bind it to the project. Refuse another
   project's attempt to claim the job.
6. Connect a synthetic JSON-RPC client to the real project MCP adapter. Cancel
   its source-use form and assert the job stays PLANNED. Then submit a test-only
   confirmation for generated inputs and run the real Blender CPU render.
7. Verify output hashes, PNG dimensions, and unchanged source/scene bytes.
8. Change the synthetic source and verify that project verification and audit
   refuse it. Restore only the generated input bytes, leaving receipts intact.
9. Restart the launcher, verify persistent jobs, move the project to Trash via
   the UI, and restore it. Verify scenes, copied render and shared evidence.

Generated scene copying and render delivery are fixture setup/assertion steps;
this suite does not claim the agent autonomously created or delivered them.
Source-use answers are synthetic protocol responses, not production approvals.
No harness license or execution gate is bypassed; job receipts come from real
execution. The scene is simple geometry, not a rig/retarget acceptance test.

## Evidence and boundaries

Each OS uploads a commit-labelled artifact for 14 days containing `report.json`,
a UI screenshot, a synthetic preview PNG, and synthetic job records/worker logs.
A failing test remains a failing job. Reports begin with FAIL and become PASS
only after all assertions complete. The full studio, settings, session token,
Codex profile and browser storage are never uploaded.

Authenticated Codex/model calls, the desktop EXE's focus/tray behavior, live
Blender add-on MCP, private/licensed inputs, retargeting and human visual
acceptance are **not tested** here. Existing launcher unit/desktop-build and
Blender matrices remain separate required checks. This is not a release gate
substitute or an update to an installed local studio.

## Reproduce

Install Python 3.11+, Node 20+ and Playwright 1.55.0 with Chromium. Use a disposable
test environment with Blender 5.2.1, then run:

```sh
python tools/studio_e2e/run.py --blender /absolute/path/to/blender --evidence /temporary/evidence
```

The runner always creates a new temporary studio; it does not accept an existing
studio path. It never uses the user's project data or installed harness.
