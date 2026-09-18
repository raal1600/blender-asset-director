# Scene workbench MVP — integration in progress

This branch implements the approved asset-first Windows launcher UX. It is not a release and must not replace a working studio before acceptance.

The project has two workspaces, Scenes and Final film. Each scene owns World → Action → Shots → Light → Render. Blender remains the editing surface. Source selection, import, checkpoint creation, user review, activity completion, render approval and film approval are separate states.

Implementation is being reconciled against source baseline `2476bab725c1c8cc4881283659d58c4cc5d7e5b1`. Intermediate commits on this development branch are not production acceptance evidence. Review the final unchanged PR head and full CI artifacts.

Do not merge or install until the named deterministic CI journeys, native Blender matrix, Windows desktop staging, authorized Codex handoff and private-input acceptance relevant to the change are complete. Public synthetic tests do not certify private assets, artistic quality, unsaved GUI behavior or live agents.

Original assets, existing Blender windows, MCP/provider configuration and installed studio data must remain untouched. No public binaries, assets, databases, credentials or production logs belong in this repository.
