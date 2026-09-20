# Project lifecycle

## 1. Discover and configure the installation

The launcher reads explicit Python, Blender, skill, library and host-agent paths
from the external studio configuration. The installed harness owns portable
contracts and durable catalog/job records. Code in a repository checkout is not
a substitute for that installation layout.

## 2. Establish the project and source boundary

Create the project, save its brief, scan available sources, attach selected
assets and verify their hashes. Source verification and permission to use a
source are separate checks. Keep shared originals in the library and derived
working scenes inside the project.

## 3. Prepare, bind and review work

A job is prepared against explicit inputs, options and an implementation identity.
The project adapter binds it to the intended project. Cancellation must not
execute the job; another project must not acquire its binding. Do not repair a
stale review by editing a receipt or hash.

## 4. Execute and measure

The project MCP adapter invokes the actual installed harness. The harness starts
a bounded Blender worker, writes new outputs and records execution evidence.
Camera, lighting, motion and sequence operations have distinct contracts.
Inspect their reports and output hashes. Preview settings must not silently
replace the production settings in the saved scene.

## 5. Resume and recover

Projects and job evidence survive launcher restart. A new launcher session uses
a new authentication token. Source drift causes refusal until the source is
restored or deliberately reviewed again. Project Trash/restore must preserve
working scenes and renders without deleting shared library originals or job
records.

## What CI proves about this path

[Installed studio tests](../docs/STUDIO_E2E.md) execute generated-source journeys
through a real browser, launcher, catalog, project MCP adapter and Blender.
Synthetic confirmation responses stand in for a host's source-use answer; they
do not evaluate autonomous model decisions. Real motion regressions are separate
from installed-app retargeting coverage. [The CI map](../docs/CI_WORKFLOWS.md)
identifies each observable checkpoint and each untested boundary.
