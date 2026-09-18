# Native Windows workbench acceptance

The existing 23 acceptance partitions are preserved. In addition, the required
launcher job runs `tools/native_desktop_fixture.py` on the real compiled EXE and
Blender GUI. The final aggregate downloads its `native-desktop-<commit>` report
and calls `tools/native_desktop_contract.py` to verify ordered checks, exact source
identity, and attachment hashes. Missing, skipped or failed GUI evidence fails
acceptance. A fixture definition is not a passing execution.

The disposable test studio opens WebView2, verifies second-launch reuse, creates a
synthetic scene via authenticated HTTP, opens a dedicated Blender task, and keeps
an unrelated unsaved Blender window alive. Actual native keyboard input moves the
selected object one unit and invokes the real checkpoint operator through F3.
The saved audit must measure that transform; sending a keystroke is not a pass.
Collection produces a review candidate, never automatic adoption or approval.
It checks active-close/tray/restore, idle-close/server shutdown, restart/session
rotation and checkpoint persistence. Only captured fixture process IDs are stopped.
No existing studio, model account, original asset or user preferences are modified.

Run only on an unused disposable Windows desktop. The native input helper refuses
to type unless the foreground window belongs to the exact fixture process. A
runner without the required desktop/graphics capability fails; a headless worker
or synthetic API response cannot substitute for this gate. Native screenshots,
checkpoint metadata and event evidence contain synthetic data, not private assets.

The dedicated task now exposes **Save checkpoint & return** in Blender's top bar
as well as F3/sidebar. Its heartbeat observes this process's expected working file,
dirty state, selected target and workspace. On unrelated file drift, details of
that file are withheld. A heartbeat is not an OS visibility or live MCP claim.
It never releases writer locks or approves work. Later edits to an old working
copy are not silently collected into its frozen checkpoint.

Passing the native fixture establishes only that measured scenario. Authorized
Codex use, representative private assets, other display/driver configurations,
human usability and artistic/temporal film acceptance remain separate release
gates. There is no automatic merge, production install or release on CI success.

Primary API references:
- https://docs.blender.org/api/5.0/bpy.app.timers.html
- https://learn.microsoft.com/en-us/dotnet/desktop/winforms/input-keyboard/how-to-simulate-events
