# Blender Asset Director

A reuse-first Blender production harness and project launcher. Start with an
existing scene or approved source, prepare explicit work, execute in bounded
Blender workers, and review the resulting evidence. Technical success is not
artistic acceptance.

## Read the system in order

[Getting started](Getting-Started.md) explains the first safe session.
[Architecture](../docs/DESIGN.md) explains the portable core, Blender adapter,
agent skill and storage boundary.
[Project lifecycle](Project-Lifecycle.md) follows a project from brief to recovery.
[CI and E2E](../docs/CI_WORKFLOWS.md) maps those journeys onto GitHub Actions.

## Production guides

| Work | Guide |
|---|---|
| Install and verify the skill | [Installation](../docs/INSTALL.md) |
| Use the project application | [Studio and launcher](../launcher/README.md) |
| Find assets and retain provenance | [Asset sourcing](../skills/blender-asset-director/references/asset-workflow.md), [providers](../skills/blender-asset-director/references/providers.md) |
| Prepare and execute bounded work | [Job execution](../skills/blender-asset-director/references/jobs.md) |
| Index and adapt motion | [Local motion](../docs/LOCAL_MOTION_LIBRARY.md), [transfer planning](../docs/REVIEWED_TRANSFER_PLANNING.md), [sequences](../docs/REVIEWED_SEQUENCES.md) |
| Understand the agent's responsibilities | [Agent skill](../skills/blender-asset-director/SKILL.md) and the seven role pages in the sidebar |
| Debug a refusal or failed run | [Troubleshooting](Troubleshooting.md), [installed studio tests](../docs/STUDIO_E2E.md) |

## Why this wiki is live

A repository workflow rebuilds these pages from the exact source commit. Core
guides are mirrored from their canonical Markdown files, not maintained as
independent copies. Command, operation, workflow and evidence inventories are
generated from code. Every page carries a source-commit link.

Use the sidebar's **Build Identity**, **CLI Reference**, **Job Operations**,
**Workflow Reference**, **Evidence Inventory** and **Source Index** for the
machine-derived view. See [the update policy](../docs/LIVE_WIKI.md) before editing.

This wiki describes its displayed branch, which can be ahead of main or a
published release. Publication does not install software, publish a release, or
certify that the displayed revision passed CI. Private assets and workstation
state never form part of wiki generation.
