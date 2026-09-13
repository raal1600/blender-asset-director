# v0.5.0 preview — completed release verification

## Published source

The incoming `fix/evaluated-pose-retarget` branch, including commits `52b8ab3`
and `493ad49`, was completed and fast-forwarded into `main` after verification.
No branch history or earlier release was overwritten.

- Completion runtime: `7820ec90c215ce2a16cf8fa8e975643202143371`.
- Release source and tag target: `66263eb4e1352dc9de4468178d484701713a7471`.
- Published preview: https://github.com/raal1600/blender-asset-director/releases/tag/v0.5.0
- Completion CI: https://github.com/raal1600/blender-asset-director/actions/runs/34788489612
- Release verification: https://github.com/raal1600/blender-asset-director/actions/runs/34789036643

All **14 release-workflow jobs completed successfully**: ten verification jobs,
publication, and three actual public installation jobs. This documentation-only
record follows the tested release and does not change its tag, code or assets.

## Gates actually executed

| Gate | Result |
|---|---|
| Unit tests | 223 passed on Windows/Python 3.11, Ubuntu/Python 3.11, Ubuntu/Python 3.13 |
| Managed installation | Installation, repeat installation, bundled runtime, edit protection, library-preserving removal passed |
| Bootstrap variants | Windows PowerShell 5.1 and 7, macOS sh and Ubuntu sh passed |
| Real Blender | 4.5.3, 5.0.0 and 5.2.1 passed existing fixtures plus evaluated-pose, sole-topology/floor and the new full retarget job-chain fixture |
| Live asset/source-motion checks | Passed in the Blender 5.0.0 job; intentionally not duplicated on other versions |
| Release publication | Versioned ZIP, launchers and SHA256SUMS.txt uploaded; no previous release overwritten |
| Public install | Anonymous download, installation, doctor, receipt verification and library-preserving removal passed on Windows, macOS and Ubuntu |

The public installation runners had Python provisioned and temporary destinations.
They prove the published distribution path, not a completely unprovisioned desktop
or the user's current Codex/DeepSeek/Blender GUI connection.

The new job-chain fixture preserves a one-second glTF take indexed at 24 FPS when
retargeting in a 30-FPS scene. At 25 output FPS and playback speed 0.8, the NLA
strip lasts 1.25 seconds and ends at frame 32.25; retained integer frames are
[1, 32], excluding the uncovered rest-pose frame. It also tests sole correction,
hips-only travel rejection of an extra controller, floor, camera, light, bounded
CPU preview, restored render settings, unchanged source hashes and job reuse.

These are technical regression fixtures, not evidence of authentic choreography.

## Archive identity

File: `blender-asset-director-0.5.0.zip` (246025 bytes)

SHA256:

```text
720ceb34a6e6fc9934d8076f4804075455bd22f63876ba7ca82d56f3f854e647
```

The source archive was also reproducibly packaged in the development container;
its hash matches the published GitHub asset. That container ran ordinary Python
checks, not Blender: real Blender execution occurred in the GitHub runners.

## What remains separate

The user's installed skill, local library, Blender projects and unsaved GUI state
were not accessed or updated. An explicit managed v0.5.0 update and scoped local
acceptance are still needed before treating this version as workstation-verified.

Grounding is vertical-only, not horizontal foot locking, IK, force estimation or
support for jumps/stairs. Retargeting remains bounded and explicit. Integer-frame
coverage is not continuous-motion or seamless-loop proof. Performance quality and
human acceptance remain separate from successful transfer.

The [capture roadmap](CAPTURE_ROADMAP.md) is researched design, **not implemented
video-to-mocap or real-time capture**. No new capture provider was authenticated,
no video was uploaded, no paid call was made, and no capture hardware was tested.

See [retarget acceptance](RETARGET_ACCEPTANCE.md) for detailed changes and
remaining limits, and [README](../README.md) for the version-pinned managed update.
