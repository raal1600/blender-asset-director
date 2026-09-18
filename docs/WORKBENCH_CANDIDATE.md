# Workbench candidate distribution and task feedback

This extends the source-controlled [scene workbench](SCENE_WORKBENCH_MVP.md),
[CI journey map](CI_WORKFLOWS.md), and [native Windows test](NATIVE_DESKTOP_ACCEPTANCE.md).
The Vercel design demo is not connected to a local studio.

## Current acceptance and packaging extension

The earlier CI map's statement that launcher checks only compile the EXE describes
its original baseline. The launcher workflow now additionally executes a **real
native Windows/WebView2/Blender GUI** fixture. The original 23 partition reports
are unchanged; a separate mandatory `native-desktop-<commit>` report has eight
ordered checks and hashed attachments. The final aggregate validates both sets.
Missing or failed native evidence is a failure, not a headless or synthetic pass.
See the native test document for precisely which scripted interactions it proves.

Only after aggregate acceptance succeeds, `candidate` downloads the **same run's**
Windows host and native evidence. `tools/package_workbench_candidate.py` verifies
source HEAD, clean tracked files, build commit, native report commit and actual
executed EXE hash before producing `workbench-candidate-<commit>`. The archive
contains tracked source, the four tested host binaries, setup tools, notices,
and `CANDIDATE.json` with file hashes. It excludes `.git`, private data, user
configuration, and CI-only Mesa DLLs. PR builds identify their test-merge commit;
that is distinct from the branch head and does not mean the PR has merged.

This is an **unsigned new-only candidate**, not an automatically published release.
The installer verifies the manifest and creates a new studio, refusing existing
destinations. It can read executable paths from a user-selected configuration;
it never copies credentials, assets or the existing catalog. Python, Node,
Blender, the existing Codex executable, FFmpeg and FFprobe must already exist.
The result retains `user_environment_accepted: false`; CI does not approve an
arbitrary user's machine. Follow [local acceptance](WORKBENCH_LOCAL_ACCEPTANCE.md).

## The Blender return path

`task_entry` defers GUI task initialization until Blender's event loop is running.
After a file load, the task re-establishes the sole normal window in its dedicated
process with `Context.temp_override`; it never guesses among another process's
windows. Startup diagnostics are bounded and scoped to the validated project.
An ambiguous window, unknown target or changed file fails rather than claiming
successful setup.

Blender's top bar and F3 offer **Save checkpoint & return**. A one-second scoped
heartbeat reports the expected working file, selected target, workspace and dirty
state. The launcher distinguishes waiting, editing, a saved checkpoint, context
drift and stale/unavailable observations. It does not reconstruct the entire UI
for every heartbeat timestamp. **Continue in Blender** targets the exact task PID
only after checking project, scene, task identity and a fresh observation.
A checkpoint is collected as a candidate and is not automatically approved.

This helper reports its own process context, not live MCP ownership, hardware GPU
performance, OS-level exclusion of arbitrary writers, or artistic acceptance.
The existing terminal-based Codex specialist remains optional. Native private-input,
authorized-model and human review requirements remain separate from public CI.
