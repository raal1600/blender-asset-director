# Retarget foundation acceptance — v0.5.0

## Scope and provenance

Based on the user's branch `fix/evaluated-pose-retarget`, commits `52b8ab3` and
`493ad49`. Implementation completion commit:
`7820ec90c215ce2a16cf8fa8e975643202143371`.
That exact runtime passed all ten jobs in
https://github.com/raal1600/blender-asset-director/actions/runs/34788489612 .
The later v0.5.0 packaging request reruns the release gate before publication.
No published v0.4.0 tag is moved. No user workstation or project was accessed.

## Executed evidence

- 223 ordinary Python unit tests, up from 205 on the incoming branch. Executed
  locally in the development container, and in CI on Windows/Python 3.11 and
  Ubuntu/Python 3.11 and 3.13. Managed installer checks also pass.
- Four bootstrap configurations pass: Windows PowerShell 5.1 and 7, macOS sh,
  Ubuntu sh. These are source-package bootstrap checks; a public v0.5.0 install
  must be recorded separately after its release workflow completes.
- Real Blender 4.5.3, 5.0.0 and 5.2.1 all pass the existing import/retarget/NLA,
  studio, camera and look fixtures plus the newly registered evaluated-pose,
  floor/contact and end-to-end retarget pipeline fixtures.
- The Blender 5.0.0 job also passes required live free-provider and retrieved
  motion checks. That step is intentionally not duplicated on the other two.
- Downloaded 5.2.1 evidence reports 25 pose samples, maximum cross error
  4.485224766520384e-7; the naive local-frame comparison is 0.28754929166640064.
  This is a synthetic geometric comparison, not a natural-motion quality score.
- The full job chain proves a 1-second glTF clip indexed at 24 FPS is retargeted
  in a 30-FPS target without changing its duration. Assembly at 25 FPS with
  playback speed 0.8 produces 1.25 seconds, strip end 32.25 and retained scene
  frames [1,32], excluding the uncovered rest frame. It also checks hips-only
  travel rejects a second motion controller, then creates a floor, fits a camera,
  adds a light, renders one 64x64/1-sample CPU preview, verifies settings restoration
  and source hashes, and reuses the completed job.

## What was fixed or strengthened

1. Source frame coordinates, capture rate, output FPS and intentional speed are
   separate. Indexed glTF imports select their recorded coordinate timebase;
   native capture FPS is not inferred from a Blender project setting.
2. Fractional bake endpoints preserve seconds; NLA no longer rounds a final
   fractional strip end out into an uncovered rest-pose frame. Integer sequence
   gaps are refused. Clips gain explicit `playback_speed`.
3. Grounded alignment must preserve world Z. Sole evaluation requires one active
   skin modifier and checks edge/loop connectivity, not only vertex count.
4. Evaluated transfer preserves reference bases of unmapped hierarchy bones;
   non-unit target reference pose scales are refused.
5. Root ownership checks include traveling hips beneath a stationary root.
6. Floor reports measure existing object/data/material identities and object
   transforms rather than returning an unsupported blanket preservation claim.
7. New Blender regressions now actually run in all three CI versions. Runtime
   reports explicitly leave performance quality unevaluated.

## Boundaries

Ground correction is a capped world-Z offset of an explicit translation anchor.
It is not horizontal foot locking, inverse kinematics, pressure inference or a
solution for stairs, jumps or irregular terrain. A moonwalk intentionally contains
sliding; applying a universal foot lock would corrupt the performance.

The unchanged legacy retarget path remains default. Evaluated-pose transfer is
opt-in and still needs explicit mapping/alignment, fixed armature transforms,
unconstrained chains and supported translations/scales. The new glTF timing path
is tested; arbitrary BVH/FBX capture timebases still need source-specific review.

Integer endpoint coverage is not continuous-motion acceptance or seamless-loop
proof. Subframe interpolation/contact and transition quality need review after
final retiming. The supplied Sketchfab moonwalk has not been made artistically
convincing by these changes. No source capture or motion reconstruction service
was executed, and no real-time listener or paid API integration was added.

The historical local handoff `HARNESS_HANDOFF.md` is retained as evidence of
pre-completion findings. Its unfixed timing/topology/CI statements are superseded
only by the scoped results above. Local project reports and asset bytes remain
outside Git. Human acceptance is not established.
