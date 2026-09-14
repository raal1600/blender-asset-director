# Reviewed bone display

Load when the user asks to see bones, compare skeletons, or change bone display.
Do not guess that spheres are joints, or that a floor-level control is stray mesh.

1. Inspect the saved working copy using `bone-display-audit` with its observed
   `target_object`. Normal `inspect` also includes `rigs[].bone_display`.
2. Read armature style, `show_custom_shapes`, actual custom-shape assignments,
   per-bone style overrides, visibility and widget objects. Custom shapes can
   override OCTAHEDRAL and make normal body bones look like spheres. A referenced
   widget can also be a visible mesh in the scene; distinguish the two displays.
3. Prepare `bone-display` against that working file with the returned
   `target_fingerprint`, `display_type` (OCTAHEDRAL or STICK), boolean
   `show_custom_shapes`, and boolean `show_in_front`. For standard pointed bones,
   explicitly choose OCTAHEDRAL and false for custom shapes. The operation resets
   per-bone style overrides but retains the actual custom-shape references.
4. Optional `visible_bones` is an explicit list of observed names; other bones
   become hidden, not deleted. Omit it to preserve current visibility. Use reviewed
   anatomy to choose a body subset, never mannequin/provider-specific names.
5. Optional `hide_widget_objects` must name actual custom-shape objects of this
   rig. It hides those objects in the current view layer and render in the NEW
   result. It never deletes them or guesses from names. Shared rigs/data/widgets,
   linked targets and skinned widgets are refused where changes could affect
   another character. Omit it to preserve widget-object visibility.
6. Reopen/audit the saved result. Inspect an actual viewport image when available;
   report configured settings separately from visual acceptance. Without image
   evidence, visual review remains PENDING. Do not claim the user saw pointed bones
   because the armature style or playback flag alone says so.

These are background working-copy operations. They do not control existing
windows, start playback, connect MCP, alter animation, resize display tails or
change preferences. Use only an actually available, correctly bound host tool to
present the result; never switch an unrelated unsaved window. Preserve originals
and report the display-only derived file separately from motion changes.
