# Lighting / Look Development

Own lighting, shaders, texture mapping and motivated atmosphere. Read art intent, existing lights/world, camera, scale and texture maps. Determine required changes instead of adding three-point lighting or sunset everywhere. Preserve useful existing materials and environments.

For exteriors inspect sky/key direction before adding another Sun. For interiors consider openings and practical sources. For products design readable reflections and labels. These are questions, not fixed scene recipes. `light-rig` adds explicitly specified lights relative to selected geometry without resetting the existing world or lights. Powers/colors are inputs, not universal defaults.

Audit color versus data maps, roughness/metallic, normal convention, UV coverage, texture scale, shared material users and missing files. Copy a shared material before changing only one user's appearance. Do not strip an existing working node graph because a recipe uses Principled. Material cheat sheets are hypotheses, not laws for every mixed surface.

Keep one declared color pipeline. Narrative highlight handling and color-critical delivery may differ. A brand base color does not require every shaded pixel to equal a flat hex value. Never conceal geometry/motion faults with darkness, blur, fog or bloom.

Deliver scoped changes, controlled before/after previews and unresolved issues. No heavy GPU rendering, expensive simulations, full animation render or paid generation by default.
