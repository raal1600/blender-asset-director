# Installed studio E2E

The [CI workflow map](CI_WORKFLOWS.md) is the entry point. **00 · Harness
acceptance** runs five installed-studio scenarios on Linux and Windows:
`onboarding`, `execution`, `production`, `recovery`, and `full`. Each starts from
an isolated installation of the exact checkout; `full` executes all stages in
one studio. No personal data, model account, provider credential or E: mount is
required.

## The disposable installation

The fixture recreates the studio's `Archive`, `Database`, `Docs`, `SystemRuntime`
and `Workspace` layout in a temporary root with spaces. It installs the real
bundled harness, compares its runtime bytes to the checkout, checks the actual
SQLite catalog, and copies the real launcher. Harness, Blender and host settings
are redirected to the disposable root. A generated Codex configuration sentinel
must remain unchanged; Codex itself is not invoked.

## Executed journeys

The onboarding journey generates an animated cube in real Blender, starts the
installed Node launcher, verifies authentication and health, and uses Chromium
to create a project, save a brief, scan/attach/verify its source and run an actual
saved-scene audit through the UI.

The execution journey prepares and binds a native preview job, refuses a foreign
project's binding attempt, and connects a synthetic JSON-RPC client to the real
project MCP adapter. Cancellation must leave the job PLANNED without a render;
confirmation for generated inputs must produce a real CPU preview with verified
hashes and dimensions. Repeating the successful request must not change job,
worker, result or render evidence or ask for another source-use confirmation.

The production journey creates a two-checkpoint camera move, changes the observed
light, world and exposure, runs camera QA, and renders a bounded preview through
the installed harness/project adapter. It reopens the saved result in another
Blender process to verify the camera animation and authored settings, preserved
subject geometry/motion, and restored production resolution and sample count.
Derived scene copying is explicit fixture orchestration, not autonomous delivery.

The recovery journey changes only generated source bytes and requires verification
and audit to refuse execution. It restores those bytes without editing receipts,
restarts the server, rejects the old session token, verifies persistent jobs, and
moves/restores the project through the browser Trash UI. The original scene,
source, copied render, shared job evidence and Codex configuration must survive.

## Evidence and scope

`tools/studio_e2e/run.py` coordinates `support.py` and `journeys.py`; assertions
remain in real user journeys rather than a mock replacement system. Every run
writes incremental `report.json` and `junit.xml`. Reports start FAIL. Exact
ordered checkpoints and retained execution evidence are mandatory for PASS.
Each OS/scenario uploads commit-labelled reports, a UI screenshot, applicable
synthetic preview images and generated job/worker evidence for 14 days. Failure
screenshots and partial worker logs are captured when available. Whole studios,
settings, sessions, browser storage, SQLite and source/derived `.blend` files are
never uploaded. Textual session tokens are redacted.

Source-use answers are synthetic protocol responses, not production approvals.
Authenticated Codex/model decisions, native desktop EXE focus/tray, live Blender
add-on MCP, private/licensed assets, installed-studio retargeting and human
artistic acceptance are **not tested** here. Existing real motion regressions
remain a separate required integration module. No local installation or release
is updated by running these tests.

## Reproduce

With Python 3.11+, Node 20+, Blender 5.2.1 and Playwright 1.55.0 with Chromium:

```sh
python tools/studio_e2e/run.py --blender /absolute/path/to/blender \
  --scenario full --evidence /temporary/evidence
```

The runner always creates a fresh studio and never accepts an existing studio
path. Focused scenarios still run real installation/onboarding prerequisites.

Fixture teardown closes its synthetic browser/MCP clients, polls authenticated
lifecycle state, then requests normal backend shutdown after pending work drains.
It does not force-terminate a backend with unknown/unfinished work or delete a
temporary studio underneath its native children. Successful owned temporary roots
are removed only after shutdown; failures retain their generated directory and
record its path for diagnosis. This is test cleanup, not a live-studio updater.

`tools/studio_e2e/teardown_check.py --blender <existing-executable> --evidence <new-folder>`
adds a focused actual installed-backend check: generate/import an unapproved
synthetic checkpoint, observe its native preview job RUNNING, request fixture
shutdown, and verify native success precedes normal backend exit with source,
manifest, checkpoint and failure evidence preserved. It installs only into its
new test directory, downloads nothing, renders no movie and claims no native GUI
or human acceptance. The existing embedded-viewer suite invokes it without adding
a workflow identity or uploading the generated whole studio.

## Transition and cancellation acceptance

`tools/motion_stitch_browser_check.mjs` takes absolute paths for output, a PASS
`motion_stitch_fixture.py` directory, Python, Blender, Playwright's Node
`index.mjs`, Chrome (empty for the installed Chrome channel), and optionally a
fresh isolated studio root created by `tools/create_workbench_studio.py`.
The installed mode starts that studio's normal `SystemRuntime/Launcher/server.mjs`
entrypoint in a subprocess, restarts it, and repeats saved playback. With existing
FFmpeg/FFprobe configured it also uses the visible shot, lighting-preview and
render controls to render both connection boundaries. It retains browser video,
frame screenshots, failed-request records, immutable checkpoint identities and
actual rendered-movie evidence. This is the installed browser client, not the
native Windows desktop host or a live Blender add-on session.

Recording requires the pinned Playwright helper as well as Chrome:

```sh
python -m pip install playwright==1.55.0
python -m playwright install --with-deps chrome ffmpeg
python tools/action_cancel_suite.py --blender /absolute/path/to/blender \
  --evidence /new/temporary/cancellation-evidence
```

The cancellation suite creates another isolated installation and uses real UI
controls to cancel before Blender starts and after its child PID is observed
running. The queue fixture delays preparation only; it supplies no fake native
result. Both cases require a cancelled application/native receipt, no accepted
checkpoint, unchanged source bytes, released writer leases and an editable draft.
The running case also requires the owned child to be reaped. Full studio CI runs
this suite on Windows and Linux; a run must actually pass to count as evidence.
The temporary studio uses Python as an explicit unused Codex-path sentinel;
Codex and model calls are not exercised. Raw studios and session files are not
published by the summary-artifact step.
