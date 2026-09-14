# Bone display regression

Problem: setting armature display to OCTAHEDRAL does not suppress custom bone
shapes. A rig using an icosphere widget can still show spheres on every body
joint. The widget object itself may also obstruct a render.

The new bone-display-audit reports actual assignments and per-bone overrides.
bone-display requires an observed armature fingerprint and explicit settings,
disables custom drawing via Blender's toggle without clearing shape references,
and resets per-bone overrides. Bone subsets and widget hiding are opt-in.
Widget hiding is limited to actual unshared, unskinned target widgets. No deletion,
general object hiding, rig reconstruction or live-control channel is introduced.

Run the registered Python on `tools/run_checks.py --offline`, then run the
registered Blender in factory background mode:

```
blender --background --factory-startup --disable-autoexec --python tools/bone_display_fixture.py -- NEW_OUTPUT_DIRECTORY DISPOSABLE_LIBRARY
```

The fixture deliberately uses a spherical custom shape and an ENVELOPE per-bone
override. It checks before-mutation refusals, read-only audit, saved/reopened
standard display, preserved shape references/skin/rest/actions/transforms,
completed-job reuse and explicit visibility isolation. No backend/download is
required. Detailed user assets/logs stay outside Git.

Live-window selection, foregrounding, pose mode, overlay configuration and playback
remain host responsibilities. Bone display is not visible in a normal beauty
render. Numeric settings alone cannot establish visual/temporal acceptance.
