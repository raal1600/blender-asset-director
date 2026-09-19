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
The Windows desktop host and normal Start shortcut open this workbench. The
old launcher UI has been retired. `/`, `/index.html` and `/workbench` all open the same workbench; there is no `-Legacy` switch. Existing project schemas and backend/MCP contracts remain compatible.

World defaults to model/pack catalog assets and Meshes/Characters source packages: environments, props and characters. Action defaults to animation/movement; its performer selector shows objects already observed in the scene. Light defaults to materials/HDRIs, using the reviewed specialist workflow for assignment. Shots uses observed cameras and Render uses shot outputs, not a general asset shelf. An explicit **Entire library** choice can find other or misclassified records; it is never the default. Filtering occurs before pagination for both stores and selected pins. No database schema migration, file relocation, automatic reclassification or source-version rewrite is performed.

World exposes the actual harness catalog and the independent original database
packages. Search, inspect provenance and package images, and select ingredients.
The scene shows a bounded Ingredients summary (four rows at most). **Browse
assets** opens a viewport-bounded browser with separate **Catalog assets** and
**Source packages** tabs, one scoped search, type/selected filters, grid/list
layouts and 24-result pages. Search, source tab, page and result scroll are kept
per scene **and activity** for the current browser session. Motion results use compact rows when
filtered by type; source texture sheets are not represented as motion previews.
**Checkpoint preview** shows a real rendered still tied to the displayed checkpoint, or the current rendered shot movie during Render. Its empty state is not an error or a live viewport: save a checkpoint, then explicitly authorize a preview. A still does not prove animation; temporal review remains in Blender or the actual movie. **Open Blender · assemble world** is the manual working-copy route. **Open Codex specialist** is the separately reviewed AI-assisted route; launching it is not approval, automatic import, or control of the manual task.

Productions exposes Open production and Archive production on every row, plus Archived productions for restore. The named archive confirmation preserves files/history and explains restoration; cancellation does not send a write. The selected row's ID/revision is used, never another open production. Existing stale-revision, active-writer and occupied-restore guards remain enforced. Studio also retains diagnostics and archive. Saved-file auditing verifies an explicit owned file without changing the project's scene pointer. Existing modular E2E journeys now use this surface, not an unlinked legacy test page.

Details and exact import gates remain in the inspector. Original packages are
not merged with catalog records based on a matching name.

The workbench opts into compact state responses (selected source summaries only)
and loads catalog/package pages only while browsing. The legacy state API remains
unchanged. Package paging is read-only; Refresh library explicitly confirms a
registry rescan. No schema migration, automatic intake, preview generation,
relicensing, dependency download or library rewrite is performed. Registry search
still reads its JSON index on the server; this is bounded response/DOM loading,
not a claim of an indexed large-scale database search implementation.

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

## Named shots and exact-camera previews

Pending candidates can be inspected with **Preview candidate** before either
keep decision. The explicit authorization renders one bounded CPU frame from
that exact frozen candidate through the existing project-bound worker. It does
not keep the candidate, complete an activity, or permit delivery rendering.
Source-use review, byte verification, writer coordination and selected-shot
checks still apply. External harness images are not automatically adopted as
scene evidence: use this workbench action to establish the exact binding.

Optional package-image absence returns authenticated HTTP 204 and keeps the
honest placeholder. Missing sources, stale image bytes and authentication failures
remain errors. Thumbnail requests are limited to four at a time and reused in
a bounded, version-keyed browser-session cache; Refresh explicitly rechecks them.
This cache contains package images only, never checkpoint previews or approvals.

Capture shots now saves named, versioned definitions using **observed cameras and
frame ranges** from a checkpoint audit or its current readiness report. A shot
references one scene; it never creates a duplicate world. Select a shot to carry
its exact camera, frame and playback range into the Blender task. The playback
range does not trim the saved scene's production range. Whole scene remains an
explicit option for legacy projects and broader edits.

Shot selection is not camera creation or a rendered thumbnail. Create or refine
cameras with the specialist or Blender, then collect the saved checkpoint. Numeric
shot metadata is entered only here, not repeated across World/Action/Light.
The selected shot supplies the render camera and range; editing those decisions
requires revising the definition rather than silently overriding it at render time.

An explicit-camera preview uses the chosen camera even when timeline markers
normally switch to another camera. It restores the original camera and marker
bindings before saving its disposable preview artifact. Checkpoints stay untouched.
Preview evidence is bound to the shot ID, shot revision and checkpoint; switching
to a different shot cannot display the previous shot's image as current evidence.

Lights are still shared scene state, not independent per-shot lighting overrides.
A new scene checkpoint conservatively invalidates dependent output. A changed
shot definition invalidates renders pinned to that shot's previous revision even
when the scene bytes are identical. Historical approved movies remain inspectable
but cannot be approved as current or silently reused in a new cut. Old film inputs
can be removed incrementally without trapping the user behind another stale input.
**Edit source → Return to Final film** keeps the film arrangement and review position.

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
says `runtime_ready: NOT_VERIFIED` until the actual environment is tested. Its
`port: 0` requests a distinct OS-assigned loopback port, so the staging launcher
does not compete with a running production launcher. Its session descriptor
contains the resulting origin and must remain private.

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
and Linux using the branded Chrome channel (including a codec preflight),
not the codec-limited Chromium headless shell. The launcher CSP is unchanged.
Scripted review choices are labelled as such. The real authoring
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

## Production acceptance before replacing the installed studio

The bounded silent-film implementation is not a claim of production acceptance.
Use a new staging root and retain evidence for the **same source commit**:

1. Run the unchanged-head public acceptance gate and retain its merge SHA, all
   partition reports, the Windows host build receipt, and hashes of delivered files.
2. On Windows, open the actual EXE, create/resume a project, open a dedicated Blender
   task, edit an object/rig/camera/light, save a checkpoint and collect it. Keep an
   unrelated unsaved Blender window open and prove its content was not replaced.
   Check second launch, idle close, active-work close, tray/restore and restart.
3. Use the configured, authorized Codex session on a representative private asset
   and motion. Confirm the intended target and native license/transfer review path.
   Exercise cancellation and a refused/stale source before permitting execution.
4. Make three related scenes and at least two named shots in one scene. Render,
   play and explicitly approve the shot movies. Assemble/review a complete film,
   revise a shot and a source scene, and demonstrate refusal of stale deliveries.
5. Record human temporal/visual acceptance of the final file's exact hash and the
   supported workload, plus backup/rollback instructions. Keep private source files,
   credentials, database and review evidence out of public CI and public Git.

A missing native/private/human record is **NOT TESTED**, never a synthetic pass.
Public CI records scripted approval inputs separately. Source changes reset the
required evidence; installer publication and live-studio migration remain explicit
release decisions. The Vercel site remains a design demo, not a remote studio.
