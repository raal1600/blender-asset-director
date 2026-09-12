# Scene-independent studio layer — 0.2.0 candidate

The same skill now supports capability-based production planning without assuming a warrior, desert, armature, sunset, fixed lens, object name, coordinate origin, aspect, FPS or duration. Example scenes live in tests, not runtime selection tables. One coordinator selectively loads seven responsibility modules; no new MCP or competing Blender harness is installed.

## Implemented

- Director/producer, production-design/scout, performance, cinematography, lighting/look-development, editorial/finishing and continuity/QA modules, with shared scope and handoff rules.
- Host-authored production contracts validated against actual scene audits. Reuse/adapt/missing/uncertain assessments require explicit references/reasons. Missing assets produce search queries, not fabricated candidates.
- Capability-based routing: material repairs skip performance/camera; object animation does not require skeletal retargeting. Sound remains planning-only.
- Revision-bound handoff and evidence review checks. These are coordination checks, not a host sandbox or autonomous scheduler.
- Generic scene audit including geometry, materials/images, camera/world, units, color settings and timebase. Saved-file jobs include input SHA256.
- Explicit subject-relative camera fitting and checkpoint framing checks for perspective/orthographic projection. Lens, direction and subject identities are supplied from the shot plan.
- Explicit additive light plans, preserving the existing world/lights/materials.
- Preview jobs no longer require an armature. A product or environment can render through the actual worker.

## Compatibility and boundaries

`plan` no longer emits the old narrow keyword-motion hints: it returns an unfilled intake with HOST_INTERPRETATION_REQUIRED. The host interprets the prompt and fills the contract; `studio-plan` validates it. Existing search, catalog, acquisition, indexing and retarget commands remain available.

This is not automatic semantic/visual understanding, a universally cinematic scene generator, an enforced independent-agent permission system, a foot-IK solver or an audio backend. Camera fitting is a technical full-bounds operation, not an artistic composition or path/occlusion guarantee. Lighting power and color are explicit choices, not automatic physical calibration.

Compact audit hashes cannot fingerprint every internal shader or animation edit. Saved-file job hashes supplement them. Re-audit updated working copies, invalidate stale reviews, preserve originals, and select one result lineage. Role prose alone cannot prevent unrestricted host tools from bypassing the workflow.

Baseline total budget remains eight CPU preview frames and two repair passes, with no paid services, local inference or heavy GPU rendering. The host tracks totals across jobs; per-job guards alone do not enforce a whole-session budget.

## Verification

`tests/test_studio.py` exercises arbitrary/Unicode names, role routing, static/material-only tasks, existing versus missing assets, FPS/shot timing, stale handoffs/reviews, evidence and budget gates. `tools/studio_fixture.py` evaluates simple geometry at different scales, offsets and aspect ratios, both projection types, animated bounds and a real rig-free CPU preview job. These are technical fixtures, not product-quality artwork.

Prior acceptance remains in ACCEPTANCE.md. New executed results belong in STUDIO_TESTS.json. Existing online animation acquisition, actual source motion, the user's workstation and visual acceptance remain separate gates. A new role layer does not turn an older failed provider test into a pass.
