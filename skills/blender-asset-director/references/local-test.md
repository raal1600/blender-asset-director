# Local acceptance: two gates

## Gate A — setup and safe readiness

1. Verify installed skill discovery, system Python, library location, installed Blender version and existing MCP connection. Never replace Codex provider/MCP configuration.
2. Run CLI `doctor`, the offline unit tests from the repo, and installer self-test in temporary directories.
3. Acquire/index the free starter pack using real commands. Confirm actual clip count and names. Run the repo headless fixture tests with this machine's Blender and pinned backend.
4. Through existing MCP, inspect the live file path and unsaved state. Locate `Desert Warrior.blend` only within relevant project paths. Never scan the whole drive.
5. Save a separate working copy if needed, preserving unsaved edits. Inspect actual skinning, rig roles/rest pose, equipment, constraints, existing actions and scene scale.
6. Report `NEEDS_RIGGING` or other blockers accurately. Do not replace the warrior with a library mannequin.
7. Select actual walk/idle candidates and propose a flat-stage test. Do not mutate the artistic scene until the user explicitly says **Run the Desert Warrior test**.

The cloud fixture result is not proof of this machine's MCP, Blender build or warrior compatibility. A text-only model must hand visual review to the user or an already authorized image-capable model, not pretend it saw frames.

## Gate B — actual warrior benchmark

On a new working copy, retrieve and retarget the best evidenced motions. Validate a short flat-ground clip first. Only after that succeeds, assemble a short walk-stop-idle sequence on a gentle dune route. Preserve the existing hero, terrain and original file. Do not invent a walk from per-bone keyframes.

Use a measured source pace, correct FPS, deliberate transition and one root-motion owner. Preserve weapon/clothing attachments. Record any required alignment or mapping edits. Render at most eight modest CPU frames, provide playback of the working file, and ask for human confirmation of naturalness.

Report separately:
- retrieval/provenance passed or blocked;
- source quality reviewed or pending;
- numerical transfer/contacts passed, warning, or failed;
- actual Windows/Codex/Blender MCP flow verified or not;
- human visual acceptance pending/passed/failed.

Do not call the test successful merely because a file saved or an armature moved. Persist outputs and reports so a new session can resume without repeating downloads or losing the original.
