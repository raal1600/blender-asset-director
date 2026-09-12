# First run in local Codex

Use this for setup, "first-run check", installation verification, and troubleshooting.
This is a local filesystem skill, not a connection from hosted ChatGPT to the user's desktop.

1. Confirm this installed SKILL.md and `scripts/runtime/asset_director` exist. The managed installer bundles the runtime; copying only the repository skill folder is not sufficient.
2. Use system Python 3.11+ to run `python <this-skill>/scripts/director.py doctor`. Paths from the installer are saved outside the skill. The command automatically resolves the saved library and Blender executable. `BAD_LIBRARY` and `BAD_BLENDER`, or explicit CLI arguments, override saved paths. Do not print credentials or an entire environment/configuration.
3. Distinguish EXECUTABLE_FOUND, MCP CONFIGURED and LIVE CONNECTION VERIFIED. The installer reads only the user-level MCP declaration. It does not launch the MCP, start Blender, send a model request, or prove host skill discovery. An MCP may instead come from a trusted project/plugin. Discover the actual host's tools and use its MCP list before concluding the connection is missing.
4. If Blender is missing, explain the prerequisite and ask the user to install/open it. A portable install can be selected with `director configure --blender <absolute-executable>`; the global `--library <path>` can be supplied before `configure` to choose a library. Never reinstall or replace an existing Blender.
5. With Blender open, find the existing MCP read/scene-info tools. Make one read-only scene query. No file loads, saves, renders, object creation or scene resets. Summarize only the current filename/dirty state if available, counts and active camera. A failed connection is not a successful test.
6. Do not silently add an MCP, change Codex providers, ask for API keys in chat or enable global auto-run. On a fresh machine without an MCP, direct the user to the upstream Blender MCP setup and explain the exact required change before asking authorization. The teaching overlay is optional and never an installation prerequisite.
7. Report installed skill version, Python, selected Blender path, library, MCP discovery, live scene query, and visual-review capability separately. Return READY_FOR_WORKING_COPY_TEST only after the actual host read succeeds. Otherwise return the precise missing step. No artistic task begins unless requested.

`doctor` makes no network/model requests. Provider availability is checked only when an authorized asset task needs it. Retarget-backend installation and starter-animation acquisition are on-demand, not installation side effects.

Explicit self-service commands:

```text
python <skill>/scripts/director.py doctor
python <skill>/scripts/director.py configure --blender <absolute-path>
python <skill>/scripts/director.py --library <absolute-path> configure
python <skill>/scripts/manage_install.py --dest <skill> --verify
python <skill>/scripts/manage_install.py --dest <skill> --uninstall
```

Uninstall preserves the external asset library and local path configuration; it removes only receipt-owned, unedited skill files. A fresh Codex session may be needed when discovery is cached. A custom `--dest` must be a location that Codex actually scans. Do not duplicate the same skill into multiple locations to fix discovery.
