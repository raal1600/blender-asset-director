# Troubleshooting

## A local command works but the application does not

Verify which runtime the launcher is actually configured to invoke. Compare the
installed skill and executable paths with the intended checkout or release.
Do not infer that updating source on GitHub updated your installation.
See [launcher setup](../launcher/README.md) and [installation](../docs/INSTALL.md).

## A job is blocked

Read its error code, project binding, source hashes and approval state. A refusal
is a safety result, not an invitation to bypass checks. Review the correct
source and prepare a new job against current inputs; never edit recorded hashes,
licenses or approval evidence to force a pass.

## Headless Blender passes but the live scene is unavailable

A background Blender worker and a live Blender add-on MCP connection are different
paths. Verify the existing live connection read-only. Do not reload Blender over
unsaved work or replace the user's host configuration. Read the
[first-run contract](../skills/blender-asset-director/references/first-run.md).

## Actions fail

Open **00 · Harness acceptance**, find the failed journey, and inspect its exact
commit and retained reports. A missing report, failed setup or skipped dependency
is not a passing E2E result. Follow [CI reproduction commands](../docs/CI_WORKFLOWS.md)
and [Windows fixture notes](../docs/CI_WINDOWS_FIXTURE.md).

## Wiki publication fails

The build artifact still contains the generated pages when publication cannot
connect to the wiki. A first-ever wiki needs a Home page saved through GitHub's
Wiki tab. An edited generated page causes a conflict rather than silent data
loss. Older source runs are rejected rather than allowed to overwrite newer
documentation. Follow [the live wiki policy](../docs/LIVE_WIKI.md).
