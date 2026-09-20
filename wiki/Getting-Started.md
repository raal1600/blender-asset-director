# Getting started

## Choose the right build

A source checkout, a managed skill installation, a published release and a
running desktop application are different things. Read the source commit on the
wiki page, then use [installation instructions](../docs/INSTALL.md) for the
intended version. Do not install development code over an existing production
workspace merely to explore the repository.

The skill expects a working Python interpreter, Blender and a configured host
agent. Existing provider accounts and Blender MCP connections belong to that
host; the installer does not silently replace them.

## First safe task

Ask the host to run the skill's read-only first-run check, verify the existing
Blender connection, and report what is ready or missing without modifying or
saving the active scene. Follow the [first-run contract](../skills/blender-asset-director/references/first-run.md).

For actual work, select an explicit project and keep source files read-only. Use
a separate saved working scene. Review source rights and the exact proposed job
before executing. A small CPU preview is evidence for review, not a delivery
master. See [job execution](../skills/blender-asset-director/references/jobs.md).

## For contributors

From an isolated source checkout:

```sh
python tools/run_checks.py --offline
cd launcher
node --test
```

These are portable checks, not the whole acceptance gate. Open **00 · Harness
acceptance** in Actions for installed-studio journeys, real Blender compatibility,
installation and browser playback. Start with [the workflow map](../docs/CI_WORKFLOWS.md)
and [contribution rules](../CONTRIBUTING.md).
