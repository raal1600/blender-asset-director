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

Each job is content-addressed by operation, options, input hashes and implementation. `job-run` verifies inputs before and after, uses a clean child environment, disables auto-run scripts, enforces a deadline, records bounded logs and writes only a new job output. A separate process is defense in depth, not an OS sandbox. `job-retry` explicitly preserves failed-attempt evidence. Do not alter a job/receipt manually.
