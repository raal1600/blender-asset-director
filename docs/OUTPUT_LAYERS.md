# Progressive Render and retained films

Render presents the selected shot and its actual retained movie first. Before a
movie exists, the saved-shot 3D view is inspection only: approximate materials
and lighting are not delivery evidence. There is no general asset shelf here.

## Explicit output, unchanged scene

Readiness remains bound to the saved checkpoint. Rendering uses the named shot's
observed camera and inclusive range. Width, height, samples and device are local
delivery choices scoped to production/scene/shot; typing them neither saves a
scene nor approves a job. A separate explicit render decision is still required.
Existing dimension, frame, pixel-sample and execution bounds remain enforced by
the backend. No renderer or encoder is installed automatically.

An explicitly selected observed OptiX device survives refresh and navigation.
If it disappears from readiness, output is disabled until a new device is
deliberately chosen. GPU failure never silently falls back to CPU. CPU remains
the initial default, not a claim that GPU rendering is unavailable.

The current movie plays inline with an explicit review decision. Delivery
settings, optional 3D source inspection and earlier shot outputs are collapsed
after rendering. Opening the Render page with a movie does not automatically
start a new hidden 3D conversion. Old movies remain playable; outdated ones
cannot be approved for current delivery. Active tasks, failures and recovery
remain tied to the existing receipts and writer controls.

## Film context and revision

Final film separates the editable shot arrangement from the saved cut being
watched. Choosing a historical cut changes only playback, not the arrangement.
Cut selection and playback position are local, production/cut-scoped state.
Edit source selects the exact referenced scene and named shot; Return to Final
film retains the chosen cut, position and working arrangement. Refresh retains
the same current movie element instead of downloading it again unnecessarily.

A source or shot revision makes affected old movies/cuts historical. The UI
explains stale inputs and disables building until current approved replacements
are selected. Server-side approval/build guards remain authoritative. Replacement
renders and cuts get new identities; previous movie and manifest bytes remain
accessible. Playback and successful encoding never manufacture human approval.

## Evidence boundary

`tools/output_browser_check.mjs` drives a separate generated three-scene browser
fixture through the actual authenticated API, Blender rendering and native film
adapter. It authorizes at most 19 tiny CPU movie frames: four original shots
(two cameras in one world) and one revised replacement. These are technical test
outputs, not a production-quality film. Scripted stage/output decisions are
explicitly labelled; human, Codex and native desktop acceptance remain untested.

The check covers declined decisions without dependent work, actual movie playback,
paused-position refresh, ordered film assembly, stale approval/build refusal,
replacement cuts, historical-cut access, source roundtrips, mobile overflow,
browser errors and preserved source/checkpoint/movie/manifest hashes. The native
adapter probes and fully decodes output with the supplied FFprobe/FFmpeg pair.
It runs in the existing embedded-viewer journey, without renaming evidence
partitions or replacing the established full-studio tests.

Local/CI results must cite their exact commit or dirty worktree. Synthetic
checks do not replace licensed-input testing, native manual handoff, authenticated
specialist decisions, real artistic review or verified staging/live deployment.
