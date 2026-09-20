# Launcher source baseline

The `launcher/` directory preserves the local project launcher and Windows desktop
host alongside the harness. Harness runtime code and the installed skill are not
changed by this import. The local launcher was previously a separate repository
(initial commit `1085037`); this source snapshot includes subsequent project wizard,
Codex interaction, Blender review-window and desktop lifecycle changes.

The desktop hosts the local UI in WebView2. It restores the existing window on a
second launch, stops the local server on an idle close, and offers tray or deferred
exit when operations are unfinished. Blender and Codex processes remain independent.
See [launcher documentation](../launcher/README.md) for scope and limitations.

## Development and installation layout

Run `node --test` from `launcher/` for synthetic tests. On Windows, build with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File launcher/tools/build-launcher.ps1 -RestoreDependencies
```

The restore downloads the fixed Microsoft WebView2 SDK version from NuGet and checks
its SHA-256. Generated EXE/DLL files and dependency caches are ignored. The SDK license
and notice are retained. Running the desktop additionally requires the installed
WebView2 runtime, .NET Framework and Node.js.

This source checkout is not the installed workspace. To deploy, copy the launcher
files and generated EXE/DLL files into `<studio>/SystemRuntime/Launcher`. Preserve
the existing `<studio>/SystemRuntime/UserData/Launcher/config.json`, which selects
absolute Python, Blender, installed skill, library and Codex executable paths. The
launcher derives the studio root from this installation layout. Do not launch it
directly from the repository expecting it to locate an existing studio automatically.

Production state stays outside source control: Database, Workspace, UserData,
session tokens, logs and configuration backups. One-time local migration and
workspace-document scripts are not imported. The optional Codex elicitation check
uses temporary synthetic fixtures and `CODEX_EXECUTABLE` (or `codex` on PATH); it
is distinct from CI and does not certify native terminal rendering.

## Validation scope

The local desktop work passed 25 synthetic launcher tests. A real local desktop
launch loaded its interface; a second launch reused the process; normal idle window
close removed the server session. Visual and tray interaction checks remain pending
because the desktop inspection helper was unavailable. No real production job was
started for these checks. Full repository checks and exact CI results belong in the
pull request; this document does not assert that remote gates have passed.

This import is a development baseline, not a release or a change to installed
runtime defaults. Use the repository's existing review and merge gates.
