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

`mode:"create"` authors a new camera. `mode:"adapt"` edits an observed camera and preserves its previous action in a muted NLA track (`existing_animation:"preserve"`), or keeps it as a fake-user action (`"clear"`). Camera constraints are muted by default; `constraints:"keep"` is refused when a kept constraint defeats the authored aim, because the operation judges the evaluated camera rather than the raw transform it just wrote.

The operation solves each checkpoint with real projection, then keys location and rotation (plus lens, `use_dof` and focus distance when requested) and applies the chosen interpolation. It reports per checkpoint: camera location, aim point, requested versus achieved screen position, screen error, distance, lens, roll, and the resulting verification. `focus_object` is a static assignment because object pointers are not keyframable; key focus distances or animate the target object instead.

It never invents a lens, duration, frame rate or format, and orthographic plans are rejected rather than approximated: `camera-fit` remains the locked-off technical fit. A smaller `fit` margin does not guarantee a larger subject, because the margin constrains the whole bounds around the chosen screen position - with a strongly off-centre aim the near margin binds first. Read the reported bounds rather than assuming.

## Camera QA across a move

```json
{"subjects":["ACTUAL_SUBJECT"],"camera":"ACTUAL_CAMERA","sample":{"start":1,"end":96,"count":6},"occlusion":true,
 "targets":[{"frame":1,"subject":"ACTUAL_SUBJECT","screen":[0.5,0.5]}]}
```

`camera-check` accepts explicit `frames` or a bounded `sample`, optional expected `screen` targets, and optional `occlusion`. Each checkpoint reports normalized bounds, depth, clip planes, lens/sensor, camera location, forward/up vectors, pitch and roll (roll 0 means a level horizon), distance, and the screen-target error in normalized units and pixels. Occlusion uses bounded ray tests against non-subject geometry and reports obvious external occluders only; it is not collision, clearance or composition safety. Successful renders and passed numbers are not artistic acceptance.

Each job is content-addressed by operation, options, input hashes and implementation. `job-run` verifies inputs before and after, uses a clean child environment, disables auto-run scripts, enforces a deadline, records bounded logs and writes only a new job output. A separate process is defense in depth, not an OS sandbox. `job-retry` explicitly preserves failed-attempt evidence. Do not alter a job/receipt manually.
