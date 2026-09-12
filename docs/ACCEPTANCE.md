# Acceptance evidence — scene-independent studio candidate

Tested implementation commit: `4af4711981088a0442a1f3d91b73f0456c65775a`.
GitHub Actions run: https://github.com/raal1600/blender-asset-director/actions/runs/34723246054
All five jobs completed successfully in that run. This records technical execution, not a claim that arbitrary scenes are artistically accepted.

## Passed in the recorded run

| Check | Actual result |
|---|---|
| Unit/policy/studio suite | 109 tests passed on Windows/Python 3.11, Ubuntu/Python 3.11 and Ubuntu/Python 3.13 |
| Skill installer | Bundled runtime launch, role/license presence, edited-file protection and library-preserving uninstall passed on all three targets |
| Blender 4.5.3 | Existing synthetic import/retarget/NLA fixtures and new generic studio regressions passed |
| Blender 5.0.0 | The same technical fixture groups passed |
| Generic studio regression | Different scales, offsets and 16:9/9:16/1:1/21:9 aspects; perspective/orthographic cameras; sampled animated bounds; existing subject/world/light preservation |
| Rig-free preview | Actual worker produced a 64x64, one-sample Cycles CPU PNG without any armature; original .blend file hash stayed unchanged |
| Quaternius live acquisition | Creator-posted Standard package downloaded and indexed; 46 action records observed, including A_TPose. This is not a claim of 46 distinct production-ready motions |
| Real retrieved motion | Actual Walk_Loop evaluated and baked over 33 output frames to a renamed/scaled duplicate source skeleton in Blender 5.0.0; three small CPU preview frames rendered |
| Poly Haven live integration | HDRI search, acquisition and Blender import passed |
| ambientCG live integration | Material search, ZIP acquisition and Blender material construction passed |

The previously blocking OpenGameArt connection timeout did not occur in this run. No security checks were weakened to obtain a pass. Earlier failed-run history is retained in ACCEPTANCE_0_1.md. A later provider outage is still possible; this is evidence for the recorded execution, not a perpetual availability guarantee.

## What these passes establish

The studio entry point no longer selects a fixed character, terrain, lighting setup, lens, frame rate or duration. Capability-selected role modules and observed-object contracts are executable coordination mechanisms. Camera/light helpers work on the tested geometric variations, and previews do not depend on character rigs.

The scene tests use simple synthetic geometry, not finished product/interior films. They establish framing and preservation invariants, not realism. The motion test uses an actual downloaded clip, but its target is a renamed/scaled duplicate skeleton, not an unrelated artist rig or the user's warrior. Numeric QA retained POSSIBLE_FOOT_SLIDING warnings; contact metrics are heuristic and an in-place clip without calibrated travel is not a foot-lock demonstration. Visual acceptance remains pending human review.

## Still requiring acceptance

- Local Windows Blender GUI, the installed Codex/DeepSeek session and existing MCP/teaching overlay.
- Runtime host discovery of the installed skill and real prompt-to-role execution.
- Arbitrary-rig retargeting, grip/cloth cleanup and terrain foot planting. Root-height following is not foot IK.
- Actual artistic quality against user briefs and reference images. Metadata scores and camera bounds are not aesthetic scores.
- Authenticated Sketchfab and account-based/manual provider workflows.
- Audio acquisition/mixing and full authorized animation delivery, which are not implemented by a planning role alone.

No user project was accessed or modified. The candidate is ready for controlled local installation/read-only compatibility checks and then a separately authorized creative test on a working copy. Do not advertise universal scene support or a production-quality autonomous studio solely from CI success.
