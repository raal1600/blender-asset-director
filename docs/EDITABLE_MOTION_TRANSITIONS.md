# Editable native motion and explicit turns — development

This extends the existing Action layer; it is not a new application or an
installed release. No model, new dependency, animation-name classifier, external
asset download or inferred bone-role mapping is introduced.

## Client flow

Select an animation block to edit its distance, replace its observed native take,
delete it, or use the source trim/split controls. Select the amber connection to
edit the added time and choose **Smooth join** or **Turn and connect**. The viewer
stays the primary surface; detailed timing stays in the adjacent inspector.
Undo and Discard remain local until Save creates a new checkpoint.
Reset view includes the selected red path, including long paths outside the
current camera view. Dragging a path never automatically moves the view camera.

### Selecting and turning in the viewer

Selecting a clip pauses the saved scene preview at that clip's displayed first
frame. Selecting an amber connection seeks its displayed first frame instead;
**Edit connection** and **Back to animation** follow the same rule. A pending
preview load cannot overwrite a newer selection or seek into another scene or
checkpoint. Selection itself does not edit, save, create a job or approve motion.
If a draft extends outside the saved preview's range, the viewer stays within
the available saved frames and explains the timing limit. Save is required to
see the new timing and motion.

The amber **Character rotation** ring is separate from the red travel endpoint.
It edits body turn and keeps the degree controls synchronized. It is available
only for an inspected supported rig whose exported root and visible skin can
be isolated without including another performer. Missing or ambiguous ownership
leaves the visual control unavailable; detailed inspection remains in Blender.
Rig-child accessories follow that isolated hierarchy. External rigid accessories
connected only through Blender constraints have no trusted ownership in the
current GLB preview; they are not included in the temporary orientation override.
Review the complete native result after Save for those dependent objects.

On the first rotation interaction, the viewer moves to the incoming clip's
start and shows an **orientation-only draft** of that pose. This is not playback
of an unsaved transition. A connected clip changes to **Turn and connect** when
its body turn is edited with the ring. A later disconnected clip must first be
connected; the control does not silently invent a transition interval. Automatic
travel rotates its measured direction with body turn; manual travel remains a
separate authored path. No anatomical facing is inferred from a name or pose.

The rotation handle is keyboard-focusable. Arrow keys adjust the turn by 5°;
Shift plus an arrow adjusts it by 15°. Holding Shift during a pointer drag snaps
the angle in 5° increments. Escape cancels the current pointer rotation, and
Undo restores a previous draft edit. Numeric body-turn controls remain available.
Dragging the ring retains the canvas, view camera and pointer capture while its
inspector updates.

Play and timeline scrubbing remove the temporary orientation override and show
the saved motion again; they do not discard the authored draft. Save creates a
new native checkpoint, after which playback can show the executed turn. This
preview does not plant feet, retarget a rig, solve contacts or certify a natural
transition. Existing checkpoints and source animation keys remain untouched.

The two connection modes are deliberately different:

- Smooth join blends endpoint poses and planar velocities without changing body
  heading. This remains the behavior of existing connections.
- Turn and connect brakes the path, holds its position during the middle half of
  the interval while changing body heading, and accelerates into the next clip.
  It is a procedural preview, not a planted-foot or anatomically solved turn.

Body turn is world-Z yaw relative to the saved base orientation. It is not a
semantic instruction such as “walk forwards.” A backward or side-step take
retains that footwork. Choose an appropriate observed take for the following
motion; changing its travel arrow cannot convert one gait into another.

An existing native turn/stop animation can be inserted as a separate editable
clip between the original two clips. The picker does not certify a take as a
turn by name. Acquiring new motion, retargeting it and approving its quality
remain separate reviewed workflows.

Source In/Out and split currently support a **single native pass without added
travel or repetition**. Travelling clips remain editable by distance,
speed, heading, replacement and removal. Range-specific stride calibration is
not implemented, so trimming a repeated path is refused rather than silently
using a full-cycle estimate. Connected later clips ripple when duration changes;
independent gaps retain explicit shift controls.

Playback shows the saved checkpoint, while the red arrow and paused rotation
target describe a local draft. Save and play to inspect an executed revision.
The orientation-only target is not an unsaved native-motion preview pipeline.
Saving, playback and a successful numerical test are not human motion/contact
approval.

## Stable native calibration

The former bridge could acquire unkeyed location/scale channels. Imported rigs
with nonzero unkeyed defaults then changed after a connected save, invalidating
their earlier automatic pace. Sampling full world positions also introduced
translation-dependent cancellation into measured stride.

The native sampler now retains an exact component baseline, including unkeyed
defaults. Bridges key only the source-owned components. Gait sampling uses the
translation-free native basis. Calibration identity binds native source keys,
rest data, units, parent space and unkeyed defaults rather than hashing derived
floating-point samples. Generated travel/heading are not a new native baseline.
Rest binding also covers bone inheritance options and armature pose mode. Mesh
geometry is preserved separately; this estimator does not measure a mesh sole.

Old receipts and saved calibrations are never rewritten by inspection. An old
automatic clip with a changed identity offers **Refresh measured pace** only
when a current reliable measurement exists. This is an explicit draft edit,
recomputes duration, and does not invent repeat/loop review. Manual calibration
persists through later distance edits. An unreliable gait remains available as
native motion without an added path; no made-up metres-per-cycle value is used.

## Wire and execution boundaries

The runtime advertises `action_motion_edit: native-motion-edit-v1`; each matching
performer inspection carries `timeline.edit_version`. Optional clip fields are
`source_range: [in, out]`, `heading_deg`, and `transition.mode: blend|turn`.
Absent fields preserve legacy behavior. API and Blender independently enforce
source bounds, capabilities, native ownership and exact checkpoint/inspection
identities before creating a writer or changing scene state.

One generated delta Action owns added path and body heading. Original object
rotation, static World placement, Actions, rest/skin and prior checkpoints stay
intact. Different headings require an explicit turn interval, not an unexplained
hard-cut rotation. A heading change above 135 degrees requests an observed
intermediate take or manual Blender work. Unsupported animated/constrained,
reflected, sheared or nonuniform parent spaces refuse this adapter. Native
object axis-angle heading is also refused without changing its rotation mode;
the existing axis-angle bone-pose bridges remain supported.

The incoming native clip replaces the preceding pose bridge at its own start;
the preceding gait is not left blended throughout the new clip. Contact locking,
terrain adaptation, arbitrary choreography and generic rig retargeting are not
implemented by this change.

Repeated edits also preserve tracks with duplicate legacy display names. New
track labels retain a bounded digest before Blender's byte-length truncation.
Preservation verifies the complete ordered prior-track prefix, with only its
requested mute state changed; names are not used as unique native identities.
All new tracks explicitly append, regardless of which old track was active.

## Verification

The existing portable, native timeline, native stitching, gait and browser
regressions remain required. Additional source-specific fixtures are:

- `tools/native_calibration_fixture.py`: save/reopen at different frames,
  automatic-first/manual-second editing, unchanged earlier clip/source, and
  refusal of changed rest, native keys, units, parent or unkeyed defaults.
- `tools/motion_edits_fixture.py`: explicit heading, added stationary path
  interval, exact incoming native keys, source trim/split, save/reopen and
  preservation in real Blender.
- `tools/motion_edits_browser_check.mjs`: isolated authenticated UI → API → real
  Blender → saved preview, later distance revision, replacement, intermediate
  insertion, connection editing, trim/split, Undo and responsive screenshots.
- `tools/motion_heading_preview_fixture.py` and `motion_heading_glb_check.mjs`:
  saved native mesh points independently compared with Three.js playback before,
  inside and after the turn, at whole scene frames.
- `tools/motion_refresh_fixture.py` and `motion_refresh_browser_check.mjs`:
  an explicitly synthetic obsolete calibration, navigation to the blocking clip,
  deliberate refresh without implicit Save, then numeric/pointer edits and
  repeated native saves with a stable profile identity.
- `launcher/test/action-selection.test.mjs` and
  `launcher/test/action-turn-preview.test.mjs`: selection races, unchanged draft
  state, exact exported ownership, reversible orientation-only geometry and
  saved-heading interpretation. These are local logic checks, not native
  playback or human acceptance.
- `tools/motion_visual_controls_browser_check.mjs`: a separate generated studio
  exercises clip/connection seeking, pointer and keyboard rotation, inspector
  synchronization, orientation-only versus saved playback, Undo and real native
  Save/reload. No existing production is used as a test fixture.

These fixtures join the existing CI evidence partitions without renaming or
making earlier gates optional. Test definitions do not claim execution. Local
reports identify actual attempts; public/private exact-commit CI, packaged
staging, reversible live deployment and licensed-character temporal review are
separate acceptance gates.
