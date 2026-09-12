# Acceptance evidence — published implementation candidate

The GitHub app authorization problem is resolved. The complete implementation was published directly to `main`, preserving the original LICENSE. First implementation commit: `00a3f4287b3394b86bf2b0911ee021e349153d94`.

Latest tested code commit: `f5e6c6991f4d1df1f2f9881daf62b61562ec2f66`.
Evidence run: https://github.com/raal1600/blender-asset-director/actions/runs/34719768696

## Executed and passed

| Gate | Evidence |
|---|---|
| Unit/policy suite | 69 independent tests passed on Ubuntu/Python 3.11, Ubuntu/Python 3.13, and Windows/Python 3.11 |
| Skill installer | Fresh installation, bundled runtime launch, edited-file protection, and uninstall preserving the library passed on all three matrix targets |
| Real Blender 4.5.3 | GLB/FBX import/export, action/rig indexing, renamed/resized target transfer, FPS conversion, action preservation, rejection of an unskinned target, NLA repeats, one path controller, and separate-file save passed |
| Real Blender 5.0.0 | The same real Blender fixture assertions passed |
| Pinned backend acquisition | Reviewed Mwni source acquired and validated against pinned Git blob hashes |
| Poly Haven live integration | Searched for a desert HDRI, acquired the file, and imported it into Blender 5.0.0 successfully |
| ambientCG live integration | Searched for a sand material, acquired its ZIP, extracted it, and built the material in Blender 5.0.0 successfully |

The offline suite also passed in the build environment on Linux/Python 3.13.5. The original 65-test suite exposed two Windows dependency-path errors in CI. Canonical-root handling fixed them and a regression test was added. Three additional tests verify bounded failover between validated public server addresses and rejection of private fallback destinations.

The original Blender download endpoint returned HTTP 403. The CI downloader now uses Blender's official HTTPS mirror service while retaining release SHA256 verification. Both tested Blender versions downloaded successfully after that change.

## Failed / blocked

**Quaternius live acquisition: FAIL.** The hosted runner could not establish a TCP connection to any validated public address for `opengameart.org`. The request timed out before receiving an HTTP response. The final error was `CONNECTION_FAILED`, not a GitHub permission error. We have not established whether this is a site/network restriction or a temporary availability problem.

**Actual retrieved-animation indexing/retargeting: BLOCKED.** No animation pack was acquired in that CI run, so the real-motion test was not executed. It has not been silently skipped into a pass. The overall CI result intentionally remains failed until this required gate succeeds.

Source: https://opengameart.org/content/universal-animation-library

The creator-posted Standard archive remains the intended source. A supported creator download or explicit local intake with verified provenance may be used to continue. Do not substitute a random mirror, fabricate clip names, weaken download security, or describe a synthetic fixture as an actual retrieved animation.

## Not yet established

- Authenticated Sketchfab downloads (no user token supplied in CI).
- BlenderKit, Poly Pizza or Mixamo host-tool/account workflows.
- Windows GUI Blender, the local Codex/DeepSeek session, and the existing Blender MCP/teaching overlay integration.
- Rig compatibility and visual quality for `Desert Warrior.blend`. That file has not been accessed or modified here.

## What the fixture pass means

The synthetic fixtures prove their stated technical assertions, not natural locomotion. The numerical QA deliberately reports possible foot sliding on the synthetic gait; those warnings were retained. A successful transfer and save does not establish arbitrary-rig compatibility, historically accurate motion, weapon grip or cloth clearance.

Terrain following adjusts root height on gentle routes only. It is not a full foot-IK/contact solver. Full source-motion and user-scene visual acceptance remains pending.

**Readiness:** published and ready for controlled installation/read-only compatibility checks. Not yet fully validated for the end-to-end desert-warrior animation benchmark.
