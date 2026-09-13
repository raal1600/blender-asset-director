# Scene-independent production contracts

The host interprets the actual prompt; the runtime checks that its claims reference observed data. No keyword dictionary selects a scene or proves an asset's visual suitability. `director` below means `python <skill>/scripts/director.py --library <library>`.

## Inspect, then fill the contract

```
director plan "<actual brief>"
director job-prepare scene-audit --input "<saved working copy>"
director job-run <job-id> --blender "<actual executable>"
```

Save the `data` object from the job result as project-local `scene_audit.json`. It includes observed objects, bounds, materials/images, units, camera/world, color settings, timebase and input file hash. It does not assign semantic roles. Run the existing `inspect` job too when full skinning, rig or action facts are needed. Do not fabricate an audit from an expected startup scene.

A brief.json contains:
- schema_version: 1
- goal: nonempty original goal
- deliverable: still, sequence, scene, asset or repair
- capabilities: relevant entries from assets, set, reference, character-motion, object-motion, camera, lighting, materials, edit, graphics, sound, delivery
- targets: arbitrary semantic labels mapped to nonempty lists of exact observed object names
- requirements: evidence-based requirement records
- optional preserve, assumptions, shots, budget

Unknown fields are rejected. Preserve defaults to observed object identities; it does not authorize arbitrary property changes or deleting/replacing them. New assets remain missing requirements until acquired/imported/re-audited; never put imaginary object names in targets.

Requirement fields: id, kind (model/material/hdri/animation/scene/other), state (reuse/adapt/missing/uncertain), refs (observed names), evidence (nonempty reasons), optional query. Reuse/adapt needs references. Missing has no references and needs a specific search query. Uncertain remains an assessment blocker. A scene/other requirement may need provider-capability review rather than a direct search flag; use `--help` and supported provider kinds, not invented CLI flags. Existing-but-unsuitable is adapt/uncertain, not absent. For motion reuse, name the actual owning rig and identify its action/slot in the evidence.

Shots are optional: id, purpose, frames [inclusive_start,inclusive_end], targets [semantic labels]. Timing uses the audited FPS. A still/repair has no automatically invented shots. No arbitrary fixed duration is required.

```
director studio-plan --brief brief.json --audit scene_audit.json > production.json
```

Output includes selected role paths, explicit gap queries, assumptions, blockers and a revision. CONTRACT_VALIDATED_NOT_EXECUTED means structure passed; semantic assessment is still host-authored, not machine-certified realism.

## Handoffs and reviews

A proposal has plan_id, audit_revision, role, capability, subjects (observed names within approved targets), reason.

```
director studio-handoff --plan production.json --proposal change.json --audit scene_audit.json
```

This validates scope and revision before the executor prepares a bounded job. It is not a scheduler or host security boundary. Do not expose write tools to a read-only reviewer. Independent jobs may create separate outputs, but select one lineage; never merge binary .blend files or let multiple writers save the live project.

A review has audit_revision, technical (PASS/FAIL/UNTESTED), visual (PASS/FAIL/PENDING), evidence [{path,sha256}], findings [{owner,finding,basis}]. Owner is a role slug; basis is measured, visual or hypothesis.

```
director studio-review --review review.json --audit scene_audit.json
```

Use `--vision-available` only when the actual host supports image inspection and the reviewer inspected those images. The flag cannot create vision. Hashes bind files, not reviewer conclusions. Human acceptance is never automatically asserted. Re-audit changed working files; saved-file hashes supplement compact audit fields, which alone cannot capture every shader/animation edit.

## Generic Blender jobs

Use `job-prepare <operation> --input <copy> --options <json>` then `job-run`. Every mutation produces a separate result.blend; use a successful result as the next input.

**camera-fit**: subjects [actual geometry names], direction [x,y,z] from subject to camera, required lens_mm; optional frames (max32), sensor_width_mm, margin, projection PERSP/ORTHO. Fits evaluated bounds using actual aspect/pixel aspect. Creates a new camera without changing subjects or previous cameras. DOF stays disabled until deliberately set. Full-bounds fitting is a technical starting point, not artistic composition.

**camera-plan**: authors an explicit animated camera from host-decided values instead of fitting one mechanically. Required: subjects and keyframes; `mode` create/adapt; lens (plan-level or per checkpoint); optional sensor_fit/height, rotation_mode, interpolation, fps, frame_range, constraints, existing_animation, set_scene_camera, dof, roll_deg. Each checkpoint needs one of position or direction, an aim (subject with optional bounds fractions, or an explicit world point), and optionally distance/fit, lens_mm, screen, roll_deg, dof. Explicit point aims are fully authorable and verifiable and may be mixed with subject aims. Orientation is solved as a roll-free frame: a requested roll of zero measures zero, and a nonzero roll measures back to the requested value while the aim point stays on its requested screen position. The runtime solves, keyframes, applies interpolation and verifies; it invents no lens, duration, frame rate or format, and rejects orthographic plans rather than approximating them. Adapting preserves the previous action in a muted NLA track by default.

**camera-check**: subjects, exact camera name, and explicit frames or a bounded `sample`; optional margin, expected `screen` targets and `occlusion`. A target names an observed subject (with optional bounds fractions) or an explicit world point, and may request `roll_deg`; the report then compares requested versus measured roll with an error and a tolerance verdict. Reports sampled framing, clip planes, lens/sensor, camera location, forward/up, pitch and roll (roll 0 = level horizon), distance and screen-target error. Occlusion evidence is bounded ray testing against non-subject geometry: obvious external occluders only. It does not establish artistic composition, collision clearance, focus aesthetics or between-checkpoint extremes.

**light-rig**: subjects, lights (max8) with type (SUN/AREA/POINT/SPOT), energy, offset [x,y,z], color [r,g,b], optional size_ratio. Offset and AREA size are relative to selected subject bounds. Color is linear Blender RGB; powers are explicit caller choices. No universal studio/sunset preset. Adds lights without resetting world, existing lights or materials.

**look-audit** (read-only): no options beyond the target file. Reports every light and its properties, the active world's mode and safely editable fields, colour-management values and availability, the render engine, the material set and per-element reasons where an edit is unsupported.

**light-adjust**: `lights` (max 32) entries of an observed light name plus explicit property changes. Adapts existing lights only; per-type applicability is enforced (AREA size/shape, SUN angle, SPOT cone, POINT/SPOT soft radius), `temperature` requires `use_temperature`, values are checked against this Blender version's own limits, and unrelated lights and properties must remain unchanged or the job fails.

**world-adjust**: `strength` and/or `color` for the active world's background only. A single, unlinked Background node is required; linked inputs and ambiguous graphs are refused rather than rewritten. No node creation, removal or rewiring.

**look-adjust**: `exposure`, `gamma`, `view_transform`, `look`, `display_device` and white-balance fields where the running Blender exposes them. Values are validated at execution time by applying and reading them back; unsupported values or unavailable fields fail explicitly instead of being clamped or skipped.

**preview** needs a camera, not an armature. Legacy stage:true requires an explicit target and is diagnostic only; use deliberate camera/look plans for artistic work. A preview saves a disposable artifact, not a delivery master: the project's own render settings are restored before the job saves, and the result is labeled `PREVIEW_ARTIFACT` with `delivery_master:false`.

## Scope and budget

At most eight CPU preview frames and two repair passes under the baseline budget. Host coordination tracks totals across jobs; per-job guards alone do not enforce a whole-session budget. No paid calls, local AI or heavy GPU render.

This layer does not implement autonomous scheduling, full foot IK, automatic artistic critique, audio acquisition/mixing or universal reference reconstruction. Role guidance does not replace a missing tested helper. Existing source-motion and local-user-scene acceptance gates remain separate.
