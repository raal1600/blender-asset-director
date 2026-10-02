# World menus and the Save bar

World's sticky Save bar must not intercept an open More menu or the library's
Filters & view panel. Both menus use stacking level 9, above Save (8) and below
blocking notices (10). Native modal dialogs retain their browser-managed top
layer. More closes after a menu choice, on an outside pointer action, or on
Escape. A menu choice and Escape return focus to the visible disclosure; open
modal dialogs keep their own Escape handling. No save, import, source-use or
approval behavior changes.

The metadata-only `tools/layer_library_check.mjs` regression uses the real
authenticated launcher and Chrome with 10,000 synthetic catalog entries. At
1280, 1024 and 390 pixel widths it:

- Clicks Add scene and Checkpoint history using ordinary pointer hit-testing.
- Opens Add scene by keyboard and cancels without creating a scene.
- Verifies dismissal/focus and the Ingredients -> library -> Escape return path
  leaves Save unobstructed. The real guided World journey still clicks Save.
- Checks all advanced filter controls receive pointer hits and actually switches
  list/grid views.
- Rejects browser writes and verifies the project and source registry unchanged.
- Retains screenshots, page errors and an explicit PASS/FAIL report.

The check runs inside the existing full installed-studio journey's embedded
viewer suite on Windows and Linux; it does not replace any evidence partition.
The fixture does not execute Blender, approve licensed inputs, or claim human
acceptance. Visibility assertions alone are insufficient for overlapping menus.
