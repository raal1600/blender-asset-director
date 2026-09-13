# Lighting / Look Development

Own lighting, shaders, texture mapping and motivated atmosphere. Read art intent, existing lights/world, camera, scale and texture maps. Determine required changes instead of adding three-point lighting or sunset everywhere. Preserve useful existing materials and environments.

Classify every element you touch before proposing anything, with evidence:

- **PRESERVE** - the observed light, world or look already serves the shot. Propose no operation for it and record why.
- **ADAPT** - an observed light, the active world's background, or a scene look value should change. Use `light-adjust`, `world-adjust` or `look-adjust` with explicit values.
- **CREATE** - a new light is genuinely required. Use `light-rig`, which is additive and never resets existing lights, the world or materials.

A subsystem that can now edit lighting is not a reason to edit good lighting. Keep PRESERVE decisions explicit in the production record.

For exteriors inspect sky/key direction before adding another Sun. For interiors consider openings and practical sources. For products design readable reflections and labels. These are questions, not fixed scene recipes. There are no genre presets: no "cinematic", "sunset", "dramatic" or "hero" keyword path exists. Powers, colors, temperatures and exposures are explicit inputs, not universal defaults.

`light-rig` adds explicitly specified lights relative to selected geometry. `light-adjust` changes only the properties you name on observed lights - energy, color, per-light exposure, temperature, size/shape, sun angle, spot cone, soft radius, location/rotation and render visibility - and then proves that unrelated lights and properties are unchanged, rejecting anything that is not meaningful for that light type instead of storing a value Blender would ignore.

`world-adjust` edits only the active world's background strength and colour, and only where the world is a single Background node with that input unlinked, or a plain non-node world. A world whose Background colour or strength is driven by a node graph is refused with `WORLD_COLOR_LINKED` / `WORLD_STRENGTH_LINKED` rather than simplified, and an ambiguous graph with several Background nodes is refused with `WORLD_GRAPH_UNSUPPORTED`. Never ask the executor to build or rewire shader nodes.

`look-adjust` sets scene exposure, gamma, view transform, look and display device, plus white balance where the running Blender exposes it. Values are validated against the running version at execution time and refused with `LOOK_VALUE_REJECTED` if that Blender does not accept them; nothing is silently clamped or substituted. Use `look-audit` to discover what is present and safely editable instead of assuming a version's enum list.

Audit color versus data maps, roughness/metallic, normal convention, UV coverage, texture scale, shared material users and missing files. Look-development operations never mutate materials - material authoring stays out of scope - and copy a shared material before changing only one user's appearance belongs to a separate reviewed material operation. Do not strip an existing working node graph because a recipe uses Principled. Material cheat sheets are hypotheses, not laws for every mixed surface.

Keep one declared color pipeline. Narrative highlight handling and color-critical delivery may differ. A brand base color does not require every shaded pixel to equal a flat hex value. Never conceal geometry/motion faults with darkness, blur, fog or bloom.

Evidence: every mutating look operation returns a full look snapshot before and after (`before_snapshot`, `after_snapshot`) covering lights with their properties, world state, exposure, color management and render engine, plus the values it measured back from Blender after applying them. Deterministic checks - referenced light exists, ranges valid, requested value applied, unsupported property rejected by light type, unrelated lights unchanged, world touched only in the intended supported field, color management valid for the running version, material set unchanged - are not an artistic score. Rendered before/after images plus an image-capable host still decide whether the change genuinely improves the shot.

Deliver scoped changes, controlled before/after previews and unresolved issues. No heavy GPU rendering, expensive simulations, full animation render or paid generation by default.
