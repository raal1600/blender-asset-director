# Scene workbench: asset-first silent-film MVP

This is a development candidate in PR #6, not a release or permission to replace
an installed studio. Keep the working production at its current version until
its native acceptance is recorded. Runtime version alone is not build identity;
record `git rev-parse HEAD` and the separately tested PR merge SHA.

## A scene owns its work

Use `SystemRuntime/Launcher/Start Workbench.ps1` in the staging studio, or
open `/workbench` in the existing authenticated local launcher. Productions has only **Scenes**
and **Final film**. Each scene keeps its own **World → Action → Shots → Light →
Render** position, source choices, immutable checkpoints, and review decisions.
The legacy launcher stays available during migration.

World exposes the actual harness catalog and the independent original database
packages. Search, inspect provenance and package images, and select ingredients.
An item marked **Selected** is not an imported object. For a Blender package,
inspect its actual collection names before selecting which collections to import.
A file containing only loose scene-root objects has no appendable collections;
prepare a separate package with a named collection in Blender, leaving the
original unchanged.
For another supported model member, choose its exact recorded file. A user must
confirm source use for this project's pinned versions; native license policies
still apply and can refuse the operation. No source is automatically relicensed.

**Import into world** executes the existing bounded harness import worker, binds
its job to this project before execution, verifies its output and object tags,
and copies its saved result byte-for-byte into a new project checkpoint. Source
references were made absolute by that worker. This keeps native derivation hashes
and the originals intact. The result is a candidate, never automatic approval.

Use **Keep & continue building** to adopt the candidate without completing World.
Add another ingredient or refine placement in Blender. Use **Keep checkpoint &
continue** only when you want to finish the current activity. Returning to an
earlier activity and adopting a new checkpoint invalidates dependent work, not
its historical records or older approved film files.

## Detailed editing and specialists

A task opens a separate Blender working copy with task-specific editor context
and observed targets. **Save checkpoint and return to launcher** writes a new
candidate and receipt; collect and review it in the same scene. Other Blender
windows, their unsaved edits and user preferences remain independent. An opened
window is not proof that the existing MCP connection controls that window.

The source library includes acquired models and indexed motion, but not every
record is directly importable geometry. Rig transfer, material assignment and
HDRI work use the existing specialist workflow. The launcher prepares the selected
scene, checkpoint, native source IDs/versions, selected motion and role for the
existing Codex terminal. It does not ask users to retype those identities.
Authentication, trust prompts, costs and reviews still belong to that session.
For motion transfer, source/target inspection and the exact transfer-plan review
remain mandatory. There is no automatic rig guessing or live viewport streaming.

Human task editing and mediated agent jobs share the project writer semaphore.
This coordinates supported application paths, not arbitrary external shell writes
or OS-level access. Never edit a frozen checkpoint or manually repair its receipts.

## Rendering and Final film

Readiness inspects the saved checkpoint, cameras, frame range, external files and
unsupported features. Full shot renders need a separate explicit user action.
`render-frames` produces verified PNG sequences; `film-assemble` encodes and fully
decodes H.264 MP4 using configured FFmpeg/FFprobe. No encoder is downloaded by
normal launcher usage. Preview artifacts are not delivery masters.

The initial output contract is silent, square-pixel H.264/yuv420p, up to 360 frames
per shot, 1920×1080, 3600 assembled frames and bounded CPU execution. Clips must
share an exact frame rate and dimensions. The assembler refuses silent retiming,
rescaling or missing/tampered frames. Audio, transitions, compositor/VSE scenes,
and broader simulation delivery need explicit additional engineering.

Play the actual shot movie before approving it. Final film arranges approved
render references, builds a new cut, shows the actual movie, then records a
separate whole-film approval. Technical encode success remains distinct from
human creative acceptance. Changing sources never silently replaces cut inputs.

## Isolated Windows staging

Use `tools/create_workbench_studio.py --help` to create a **new** studio with
explicit absolute Blender, Python and existing Codex executable paths; FFmpeg
and FFprobe are optional explicit paths. Node 20+ must be available to the launcher. The target must not exist. The tool copies this
source into a matching harness/launcher layout and creates a separate catalog;
it does not migrate private data or update an existing installation. Its receipt
says `runtime_ready: NOT_VERIFIED` until the actual environment is tested.

Build the Windows host with `launcher/tools/build-launcher.ps1 -RestoreDependencies`
and retain its exact-source build receipt. The compiled host alone is not proof of
window focus, tray handling, Blender UI interaction or authenticated Codex use.

## Evidence and boundaries

Run `python tools/run_checks.py --offline` and `node --test` inside `launcher/`.
New native catalog tests exercise pinning, source-use scope, refusals, candidate
adoption, stale bytes/rights and preparation failure with a synthetic executor.
They do not claim actual Blender execution.

The existing **04 · Scene authoring and preview E2E** and **06 · Full installed
studio E2E** journeys additionally exercise the real installed catalog, observed
Blender collection import, checkpoint adoption, CPU rendering, FFmpeg encode,
authenticated HTTP media delivery and actual browser movie playback on Windows
and Linux. Scripted review choices are labelled as such. The real authoring
matrix also makes and verifies a three-scene film. Keep their existing aggregate
and exact-commit evidence semantics; a fixture's presence is not a passing run.

CI downloads a pinned portable Windows encoder only into its disposable runner
using `tools/ci/fetch_ffmpeg.py`; Linux installs its encoder on the disposable
runner. Production startup never installs them. Git wiki publication tests run
on source checkouts, not inside no-Git installer archives, where that explicit
repository-only skip is reported.

Before calling this production-accepted, record native Windows staging of the
launcher → Blender edit → checkpoint → launcher round trip, authorized Codex,
representative private assets with retained rights, and human review of the
resulting film. Public synthetic CI does not establish those claims. Do not merge,
release or replace the live studio merely because portable tests pass.
