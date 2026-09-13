# Working-file jobs

In examples, `director` means `python <skill>/scripts/director.py --library <library>`. `BLENDER` is the actual installed executable path, discovered without installing a replacement. After managed setup, `--library` and `job-run --blender` are optional because the saved local paths are used. Explicit paths still override defaults. Job/asset IDs below are placeholders returned by real commands.

```text
director doctor
director plan "warrior slowly walks over a dune and stops"
director search walk --provider local --kind animation
director seed --download
director job-prepare index --asset ASSET_ID
director job-run JOB_ID --blender BLENDER --timeout 900
director index-collect ASSET_ID JOB_ID
director search walk --provider local --kind animation
director show CLIP_ID --full
director backend-install
```

Inspect a **saved working copy**:

```text
director job-prepare inspect --input "path/to/Working Copy.blend"
director job-run JOB_ID --blender BLENDER
```

If the live project has unsaved edits, use existing Blender MCP to save a separate copy before inspecting on disk. This CLI does not know the open GUI's unsaved state. Do not reload the live file. To inspect unsaved state directly, the host can execute the packaged `inspect_scene()` function through its reviewed Blender MCP; do not call worker mutations inside the live process.

Retarget options JSON (use names/slot from actual index and target inspection):

```json
{"target_object":"ACTUAL_TARGET_ARMATURE","target_fps":24}
```

```text
director job-prepare retarget --input "path/to/Working Copy.blend" --asset CLIP_ID --options retarget.json
director job-run JOB_ID --blender BLENDER
```

The indexed clip supplies source action, slot, source object and FPS. Optional `mapping` is a one-to-one source-name to target-name dictionary; optional `alignment` contains **reviewed target pose-basis** row-major 4x4 matrices. Do not manufacture mappings from vague name similarity. Backend errors such as `NEEDS_RIGGING`, `ALIGNMENT_REVIEW_REQUIRED`, or `SOURCE_OBJECT_MOTION_REVIEW` are real gates, not invitations to bypass checks.

Retarget the second clip using the first job's `result.blend` as input so both actions remain in the working project. Read exact resulting action names and slots from `result.json`.

Sequence options example:

```json
{"target_object":"ACTUAL_TARGET_ARMATURE","fps":24,"clips":[{"action":"ACTUAL_BAKED_WALK","slot":"ACTUAL_SLOT","start":1,"repeat":2},{"action":"ACTUAL_BAKED_IDLE","slot":"ACTUAL_SLOT","start":45,"blend_in":4}],"controller_speed":0.6,"direction":[0,-1,0],"travel_frames":[1,45]}
```

The example speed/start values are **not suitable defaults**; measure and choose them for the actual motion and scale. FPS conversion preserves duration. Repeat is allowed only for measured in-place motion. Character facing and path direction need visual confirmation. An external controller moves the complete armature hierarchy; an existing armature parent or unresolved attachments produce a review gate.

`terrain_object` adds gentle root-height following with a slope cap. This does not solve two-foot contact on uneven terrain. QA with terrain requires calibrated `sole_offsets` for `foot_l` and `foot_r`; ankle coordinates alone cannot establish sole penetration.

Preview options:

```json
{"frames":[1,24,48],"width":640,"height":360,"samples":8,"target_object":"ACTUAL_TARGET_ARMATURE"}
```

An existing camera is required unless `stage:true` explicitly authorizes a simple preview camera/light rig in the disposable output. Every render is Cycles CPU. No full animation render is automatic.

Preview artifacts are not delivery masters:

- a **preview render** is one bounded Cycles CPU image;
- a **preview artifact** is the disposable `.blend` a preview job saves; its result records `artifact_kind: PREVIEW_ARTIFACT` and `delivery_master: false`;
- a **working/master `.blend`** is the file you keep editing or deliver. Preview jobs record the project's own engine, resolution, resolution percentage, samples, output format/path, thread settings and frame, and restore them before saving, so the saved file keeps production settings;
- a **final delivery render** is a full-quality render you authorize separately. No operation renders an entire sequence automatically.

The job runner launches Blender with a bounded `--threads` value, so the thread count a job sees and saves reflects that bound rather than a value stored in the file.

## Animated camera authoring (perspective only in this version)

```json
{"mode":"create","subjects":["ACTUAL_SUBJECT"],"lens_mm":50,"sensor_fit":"AUTO","fps":24,"frame_range":[1,96],
 "interpolation":{"type":"BEZIER","easing":"EASE_IN_OUT"},
 "keyframes":[
   {"frame":1,"aim":{"subject":"ACTUAL_SUBJECT","bounds":[0.5,0.5,0.55]},"direction":[0.3,-1,0.2],"fit":{"margin":0.3},"screen":[0.5,0.5]},
   {"frame":96,"aim":{"subject":"ACTUAL_SUBJECT","bounds":[0.5,0.5,0.8]},"position":[ACTUAL_X,ACTUAL_Y,ACTUAL_Z],"screen":[0.38,0.6],"lens_mm":85}]}
```

```text
director job-prepare camera-plan --input "path/to/Working Copy.blend" --options camera-plan.json
director job-run JOB_ID --blender BLENDER
```

Every creative value is caller-supplied: frame checkpoints, placement (a world `position`, or a subject-to-camera `direction` with `distance` or `fit`), aim (`subject` with optional `bounds` fractions, or an explicit `point`), lens (plan-level or per checkpoint), the normalized `screen` position the aim point should occupy, optional `roll_deg`, interpolation/easing, and optional explicit `fps`/`frame_range`. `job-prepare` validates the whole contract on ordinary Python, so a malformed plan is rejected before Blender starts.

Point aims are first-class. A checkpoint may aim at an explicit world point with no scene object behind it, and the runtime verifies the projected point against the requested screen position exactly as it does for subject aims; mixed plans are supported. Orientation is solved as a roll-free frame rather than by composing a yaw about the camera's local up axis, so `roll_deg` omitted or zero measures zero on the evaluated camera, and an explicit nonzero roll measures back to the requested value. The screen offset is un-rolled before the roll is applied, which keeps screen placement and horizon tilt independent instead of letting a requested roll drag the aim point.

`mode:"create"` authors a new camera. `mode:"adapt"` edits an observed camera and preserves its previous action in a muted NLA track (`existing_animation:"preserve"`), or keeps it as a fake-user action (`"clear"`). Camera constraints are muted by default; `constraints:"keep"` is refused when a kept constraint defeats the authored aim, because the operation judges the evaluated camera rather than the raw transform it just wrote.

The operation solves each checkpoint with real projection, then keys location and rotation (plus lens, `use_dof` and focus distance when requested) and applies the chosen interpolation. It reports per checkpoint: camera location, aim point, requested versus achieved screen position, screen error, distance, lens, roll, and the resulting verification. `focus_object` is a static assignment because object pointers are not keyframable; key focus distances or animate the target object instead.

It never invents a lens, duration, frame rate or format, and orthographic plans are rejected rather than approximated: `camera-fit` remains the locked-off technical fit. A smaller `fit` margin does not guarantee a larger subject, because the margin constrains the whole bounds around the chosen screen position - with a strongly off-centre aim the near margin binds first. Read the reported bounds rather than assuming.

## Camera QA across a move

```json
{"subjects":["ACTUAL_SUBJECT"],"camera":"ACTUAL_CAMERA","sample":{"start":1,"end":96,"count":6},"occlusion":true,
 "targets":[{"frame":1,"subject":"ACTUAL_SUBJECT","screen":[0.5,0.5]}]}
```

A target names either an observed `subject` (with optional `bounds` fractions) or an explicit world `point`; adding `roll_deg` to a target makes the report compare `requested_deg`, the measured `roll_deg` and `error_deg` with a tolerance verdict. `camera-check` accepts explicit `frames` or a bounded `sample`, optional expected `screen` targets, and optional `occlusion`. Each checkpoint reports normalized bounds, depth, clip planes, lens/sensor, camera location, forward/up vectors, pitch and roll (roll 0 means a level horizon), distance, and the screen-target error in normalized units and pixels. Occlusion uses bounded ray tests against non-subject geometry and reports obvious external occluders only; it is not collision, clearance or composition safety. Successful renders and passed numbers are not artistic acceptance.

## Lighting and look development

These operations execute only explicit values. There are no genre presets, no scene-name switches and no arbitrary shader or Python surface: the host decides, the runtime validates and applies, then reports what Blender measured back.

```text
director job-prepare look-audit --input "path/to/Working Copy.blend"
```

`look-audit` is read-only. It returns the full look state - every light with its type and properties, the active world's mode and which of its fields are safely editable, colour-management values, the render engine, the material set and the object count - plus explicit reasons where an edit is unsupported.

```json
{"lights": [{"name": "ACTUAL_LIGHT", "energy": 250, "color": [1.0, 0.8, 0.6], "location": [2, -3, 4]},
            {"name": "ACTUAL_AREA_LIGHT", "size": 2.5, "shape": "RECTANGLE", "size_y": 1.0},
            {"name": "ACTUAL_SUN", "angle_deg": 3.0, "use_shadow": false}]}
```

`light-adjust` adapts **observed** existing lights. Supported per type: energy, color, exposure, `use_temperature`/`temperature`, normalize, `use_shadow`, `use_soft_falloff`, `cutoff_distance`, location, `rotation_euler_deg` (Euler-mode objects only), `rotation_quaternion` (quaternion-mode objects only), `hide_render`; AREA adds `size`, `size_y` and `shape`; SUN adds `angle_deg`; SPOT adds `spot_size_deg` and `spot_blend`; POINT and SPOT add `shadow_soft_size`. Anything else is refused by light type (`LIGHT_PROPERTY_UNSUPPORTED`) rather than stored and ignored, `temperature` is refused unless the same entry enables `use_temperature`, and values outside this Blender version's own limits are refused. Unrelated lights and properties are proven unchanged, or the job fails with `LIGHT_ISOLATION_VIOLATION`.

```json
{"strength": 0.35, "color": [0.6, 0.4, 0.25]}
```

`world-adjust` edits only the active world's background strength and colour. A plain non-node world uses `world.color`; a node world must have exactly one Background node, and each input must be unlinked. Linked inputs are refused (`WORLD_COLOR_LINKED`, `WORLD_STRENGTH_LINKED`) and ambiguous graphs with several Background nodes are refused (`WORLD_GRAPH_UNSUPPORTED`) - the executor never rewires or simplifies a user node graph. Blender 5.x always keeps world nodes enabled, so the plain-colour path applies only where the running version allows disabling them.

```json
{"exposure": 0.4, "view_transform": "AgX", "look": "None", "display_device": "sRGB",
 "use_white_balance": true, "white_balance_temperature": 5200, "white_balance_tint": 8}
```

`look-adjust` sets scene exposure, gamma, view transform, look and display device, plus white balance where the running Blender exposes it. Enum values are not assumed: each value is applied and read back, and a value this Blender rejects fails with `LOOK_VALUE_REJECTED` (including Blender's own message listing what it accepts). Version-specific fields that do not exist are refused with `LOOK_PROPERTY_UNAVAILABLE` instead of silently skipped. `light-rig` remains the additive CREATE path; all four operations report their classification (`ADAPT`, or `CREATE` for `light-rig`) and a full `before_snapshot` / `after_snapshot` for QA. Materials are never mutated: a material change fails with `MATERIALS_CHANGED`.

Look-development previews use the existing `preview` operation, which still restores the project's own render settings before saving its artifact.

Each job is content-addressed by operation, options, input hashes and implementation. `job-run` verifies inputs before and after, uses a clean child environment, disables auto-run scripts, enforces a deadline, records bounded logs and writes only a new job output. A separate process is defense in depth, not an OS sandbox. `job-retry` explicitly preserves failed-attempt evidence. Do not alter a job/receipt manually.
