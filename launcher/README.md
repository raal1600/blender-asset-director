# Asset Director Launcher 0.1.0

The scene workbench is the only client: `/`, `/index.html`, and `/workbench` open the same application. The old frontend and `-Legacy` startup switch are removed; existing project schemas, source folders, provider/MCP definitions and reviewed backend APIs are retained. Studio contains diagnostics and recoverable project archive/restore.

Local Node 20+ application; no npm dependencies, build service, API key, or cloud storage. Double-click `Asset Director.exe` to open the dedicated desktop window. It uses the installed Microsoft Edge WebView2 runtime and starts or reuses the loopback server. Closing the desktop window stops the server when idle. The PowerShell script remains available for browser-only use; browser tabs do not control server lifetime.

The launcher is a project and environment adapter around the existing installed harness. It does not replace the harness catalog, change installed skill code, provide an arbitrary command endpoint, or imply license approval. Blender connection checks use only the add-on's read-only `get_addon_info` handshake. No second MCP provider or configuration is installed.

## Data ownership

- `Database/Animations`, `Characters`, `Meshes`: original shared packages. Keep package dependencies together. Each animation file is a clip; character directories are packages; mesh directories are grouped by category then package.
- `Database/Registry`: launcher-owned source IDs and immutable file-hash manifests, separate from `Database/AssetDirector`. Hash manifests are **not copies of the source bytes**. If originals change, pinned references become stale. Preserve old original packages separately when changing them.
- `Database/AssetDirector`: harness-owned catalog, licensing, jobs and evidence. The launcher never injects project fields into those receipts.
- `Workspace/Projects/<slug>--<id>/project.json`: authoritative project ID, brief, selected scene, pinned source versions, and owned harness job IDs.
- Each project owns `Scenes`, `Renders`, `Deliverables`, `Docs`, and `Runs`. Runs are launcher operation receipts, not duplicate harness jobs. Run failures remain visible on disk.
- `SystemRuntime/UserData/Launcher`: local executable configuration, last health report, session descriptor and server logs. The session descriptor contains the local access token; do not share it.

There is no global active production project: the UI selection is local to the browser, and every operation carries a project ID. Revision checks prevent stale tabs overwriting newer project changes. The one local server serializes writes. CLI commands go through that server, not around its lock.

## Commands

`node cli.mjs projects`, `health`, `verify PROJECT_ID`, `audit PROJECT_ID`, and `bind-job PROJECT_ID JOB_ID`.

The first production operation exposed by this version is a read-only saved-scene audit. It prepares a normal harness job, validates ownership, associates it before execution, and preserves a launcher receipt. Other reviewed creative operations continue through the installed skill; project AGENTS.md instructs the agent to bind each prepared job before execution. Direct use of the raw harness CLI can bypass the launcher, so this is not a universal enforcement layer over all external tools.

Start Codex session opens a visible interactive PowerShell terminal and invokes the installed Codex CLI with --cd set to the selected project and an initial setup prompt. That prompt loads the project instructions and checks the harness, asset references, and live Blender connection without starting creative production. Normal Codex trust or sign-in prompts remain interactive. Changing projects in the UI does not retarget an existing Codex conversation or Blender scene.

## Local boundary

HTTP binds only to 127.0.0.1, checks Host/Origin/Fetch-Metadata, and requires a random bearer token on every API call. Files are served from a fixed static allowlist. Commands use fixed executables and argument arrays, never a user-supplied shell. Folder operations are allowlisted; project paths are checked against resolved roots, including links. No permanent deletion, arbitrary script execution, provider downloads, or automatic render endpoint is included. Scene review opens the selected saved file in a separate Blender window. Existing windows and unsaved scenes are preserved.

## Verification

Run `npm test` for synthetic project isolation, changed-source detection, optimistic concurrency, path containment and HTTP access controls. Real harness, Blender, and browser checks are separate and documented in the workspace's Setup-Checks directory.

Runtime configuration: `SystemRuntime/UserData/Launcher/config.json`. Paths are explicit; executable updates or moving the root require updating that file and rechecking the setup. Normal source asset additions only require Refresh library.

Official API references used: [Node child processes](https://nodejs.org/download/release/v20.17.0/docs/api/child_process.html), [Codex CLI](https://learn.chatgpt.com/docs/developer-commands?surface=cli), [MCP for Blender](https://github.com/ahujasid/mcp-for-blender).

## Project Trash

Use the three-dot menu beside a project under Your Projects, then Move project to Trash. Close that project in Blender/Codex before moving it. The folder is moved intact to Archive/Trash/<project-id>/<original-folder>; shared database sources and harness job records remain untouched. Unfinished operations block the move. Trashed projects continue to reserve their job ownership.

System > Project Trash provides Restore, which returns the project to its exact original path and refuses to overwrite an existing folder. There is no permanent-delete endpoint.

The Blender action restores and focuses an existing editor, or starts a new visible instance if none is running. A protocol connection alone is not treated as proof that a window is visible. An instance on another Windows desktop is reported explicitly.

## Project wizard

Projects follow six steps: create, describe, choose capabilities, link library sources, start Codex, and review working scenes. Back/Continue saves project fields and progress in project.json with revision checks. Existing manifests remain valid; no source or project migration is required.

Capabilities use the installed studio-contract identifiers. Automatic mode asks Codex to propose scope from the brief; explicit mode uses the checked capabilities. Director/Producer and Continuity/Quality remain baseline responsibilities. Checkboxes do not imply every capability has an automated executor.

Step 5 shows the generated startup prompt. Launch requires a brief and a reviewed library selection (which may be empty), checks the reviewed project revision and verifies linked bytes. Each launch saves its exact prompt and context under Docs/Codex with a unique session ID. The terminal receives a short reference to that project-local prompt, avoiding command-line length and quoting problems. It proposes a plan within the harness review workflow; launch status does not certify production completion.

Step 6 lists saved .blend files directly in Scenes/. Refresh after Codex saves work, select a file and open it in a separate Blender review window. A review window is not asserted to own the existing MCP connection.
`nUse node cli.mjs scene-info PROJECT_ID for live read-only metadata through the existing Blender MCP add-on. This does not establish scene ownership or visual acceptance. New projects do not need a selected saved scene for initialization; production creates a separate working scene through the harness workflow.


## Interactive questions in Codex

Launcher-created terminals add a session-scoped asset_director MCP entry through Codex command-line configuration. Existing providers, global configuration and Blender MCP entries remain unchanged. The stdio adapter is bound to one project and one saved session. It exposes prepare_project, ask_project_question, run_project_job and a harmless interaction_test.

prepare_project verifies the current pinned files, then requests a standard MCP form when a matching source-use attestation is absent. The user sees the project, requested work and exact source versions. The form has no supplied default; uncertainty is listed first. Cancel, decline, malformed input, a missing form capability or changed inputs leave the checkpoint pending. No response deadline becomes approval. Native clients may impose a tool timeout; that is a failure, not consent.

Answers are private project records in Docs/Interactions. They bind project, brief, requested capabilities and source IDs/hashes, with session identity, timestamp and actual submitted content. A changed scope or source version requires a new answer. These records are user attestations, not license grants. Native harness evidence, retained terms, root review scope, job review and budget rules still apply. A project-specific confirmation must not be expanded into approval of other files in a motion root.

run_project_job checks project ownership and source-use confirmation before invoking the existing harness executor. Cancelled questions never reach job-run. The executor continues to reject missing or stale native evidence. Runs receipts and an exclusive project lock preserve unfinished work. This is enforced by the adapter's execution path; it is not an OS security boundary over arbitrary shell commands or manually edited files. Startup instructions route prepared jobs through that path.

ask_project_question collects other required decisions with choices inside Codex. Such answers are not automatically license grants or reviewed-job approvals. The adapter never accepts an answer in the model's tool arguments and does not ask for credentials.

Tests: npm test includes interaction state, source staleness, cancellation, native executor failure and stdio protocol tests. tools/codex-elicitation-check.mjs validates the installed Codex app-server forwarding a form and cancellation using a synthetic project, without a model request or production permission. Native terminal display is a separate human acceptance check.

## Desktop window

Double-click `Asset Director.exe`. The executable and three WebView2 DLLs must remain in this folder; use a shortcut elsewhere. Node.js, .NET Framework and the installed Microsoft Edge WebView2 runtime are required. This is a local desktop host for the existing UI, not a standalone bundle. It does not use PowerShell to start the server.

- A second launch restores the existing window, including from the notification area.
- Closing an idle window stops the local server and exits.
- Active operations, unfinished receipts and writer locks block **backend shutdown**, not your ability to exit the desktop. The close dialog names the project, scene and recorded failure. Choose **Exit Director only** to close its window and leave the local server and work running, **Keep running in tray**, **Exit when finished**, or Cancel. Reopening reconnects to the same authenticated session when the backend is still running.
- **Inspect selected task** checks the task's actual process. **Close Blender task** requests a normal window close for that exact task only; respond to Blender's normal Save Changes prompt. It never force-kills Blender, Codex or a worker, and sending the request does not mean the task has stopped.
- **Recover stopped task** requires a fresh stopped-process check, explicit confirmation, unchanged project revision and no uncollected checkpoint. It uses recorded recovery, retains working files and failure evidence, and records no creative approval. A saved return receipt offers **Collect checkpoint** instead.
- Unknown, unreadable or mismatched process identity disables close/recovery. You can still exit only Director; backend locks and evidence remain intact. Failed setup disables indefinite **Exit when finished** waiting and asks for attention. The authenticated stop endpoint continues to refuse unfinished work.
- Desktop-launched servers write their own logs under UserData, independent of the host window's lifetime. Exit-only is not a claim that background jobs or the server have stopped. Reopen Director to inspect them and stop the backend when idle.
- `Start Launcher.ps1` remains the browser-only entry point. Closing a browser tab still leaves that server running. System > Stop also refuses unfinished work.

Source: `tools/AssetDirectorLauncher.cs`. Rebuild with `tools/build-launcher.ps1` while the desktop app is closed. The local executable is unsigned. SDK DLLs are from Microsoft.Web.WebView2 1.0.3800.47 on NuGet; see WEBVIEW2-LICENSE.txt. WebView2 data stays in SystemRuntime/UserData/Launcher/WebView2.

Validation: `node --test` includes authenticated lifecycle checks, active HTTP operations, independent job records and locks, older unfinished receipts, corrupt receipts, and idle shutdown. Native window, focus, tray and close behavior also need desktop verification.

## Source checkout

For rebuilding, installation layout, CI and the difference between source and an installed studio, see [the repository launcher guide](../docs/LAUNCHER.md). On Windows, `tools/build-launcher.ps1 -RestoreDependencies` downloads the pinned, checksum-verified WebView2 SDK before compiling. The generated EXE/DLL files are not stored in Git.
