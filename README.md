# Blender Asset Director

A reuse-first asset toolkit and scene-independent Blender studio skill for Codex or another compatible host. Interpret a prompt, inspect the existing project, reuse what is suitable, scout actual gaps, adapt assets/motion, and review evidence. No default warrior, desert, armature, sunset or ten-second shot is assumed.

**0.2.0 candidate:** the studio layer extends the asset/motion foundation. Read [studio scope](docs/STUDIO_UPGRADE.md), [production contracts](skills/blender-asset-director/references/studio-contracts.md) and [baseline acceptance](docs/ACCEPTANCE.md). Technical tests do not establish cinematic quality or compatibility with every supplied rig. No claim of a completely validated release is made while required acceptance gates remain open.

## Architecture

One discoverable `blender-asset-director` skill selectively loads seven internal responsibilities: director/producer, production-design/scouting, performance, camera/focus, lighting/look development, editorial/finishing and continuity/QA. They share the existing Python toolkit, external library and controlled working-file jobs. They are not seven autonomous writers or seven extra model subscriptions.

The host interprets creative meaning. Deterministic code validates contracts, actual object references, resource limits and evidence. It does not pretend keyword matches are semantic understanding or a beauty score. Existing Blender MCP remains the live inspection/handoff connection. Bounded background Blender jobs run mutations on separate working copies.

## Preserve your workstation

Keep the existing Codex/DeepSeek provider, Blender MCP and teaching overlay. Never reinstall them for this skill. Preserve live unsaved work and original .blend files. Assets and credentials stay outside this public repository. No paid calls/assets, local AI inference or heavy GPU renders are required. Host/model API charges still apply.

Default previews are limited Cycles CPU jobs, not full animation rendering. The default production budget is eight preview frames and two repairs; the host tracks the total across jobs. Script auto-execution remains disabled. Separate workers are defense in depth, not OS sandboxes.

## Install after reviewing the candidate

Requires system Python 3.11+, a supported installed Blender executable for Blender jobs, and an already working host/MCP connection for live handoff. The Python core uses the standard library.

```powershell
git clone https://github.com/raal1600/blender-asset-director.git
cd blender-asset-director
python tools/run_checks.py --offline
python tools/install_skill.py --dest "$HOME\.agents\skills\blender-asset-director"
```

Discover the actual host skills directory rather than assuming it when customized. Restart the host if skill discovery is cached and verify the skill is available. The installer bundles the runtime and notices, records ownership/hashes, refuses to overwrite edited installations, and does not change Codex or MCP configuration.

For a reviewed update, use `--update`; old managed files are backed up. For explicit removal use `--uninstall`. Uninstall does not remove the independent asset library.

## Start with an audit, not a recipe

```text
python <installed-skill>/scripts/director.py --library <library> doctor
python <installed-skill>/scripts/director.py --library <library> plan "<actual request>"
```

`plan` returns an unfilled intake, not generated scene instructions. This is a deliberate change from the 0.1 keyword hints. Use `scene-audit` against a saved working copy and `inspect` when detailed rigs/actions are relevant. The host fills a brief and runs:

```text
director studio-plan --brief brief.json --audit scene_audit.json
```

Here `director` abbreviates the installed script invocation with an explicit library path. Follow the [contract reference](skills/blender-asset-director/references/studio-contracts.md) for targets, requirements, shots, budgets, handoffs and reviews. No helper automatically knows whether an existing material is visually suitable; observations, inferred suitability and uncertainty remain distinct.

## Asset and motion services

Search the actual scene, then the local SQLite catalog, then supported external providers. Poly Haven supports models/materials/HDRIs; ambientCG primarily materials. Sketchfab has a search adapter and authenticated download route. Quaternius supplies one verified starter-pack route, not a catalog of imagined clip names. Mixamo, BlenderKit and Poly Pizza use a discovered approved host tool or manual acquisition/intake; no private API scraping is claimed.

```text
director providers
director search "<gap query>" --provider local --kind model
director search "<gap query>" --provider polyhaven --kind hdri
director acquire <asset-id>
director seed
director seed --download
director job-prepare index --asset <acquired-asset-id>
director job-run <job-id> --blender <executable>
director index-collect <asset-id> <job-id>
```

Only execute acquisition for a justified shortlist. Records retain source/author/license, file hashes, sidecar dependencies and actual animation slots. License policy is conservative, not complete legal clearance. Do not commit assets, tokens, temporary signed URLs or user projects. See [provider contracts](skills/blender-asset-director/references/providers.md).

For skeletal motion, inspect source/target, install the pinned reviewed backend with `backend-install`, retarget on flat ground and then assemble. Preserve root ownership and equipment. Root-height terrain following is not foot IK. Unrigged/unsupported characters require further work, not stand-ins. Object/mechanical motion is a separate capability and does not need humanoid retargeting.

## Scene-independent Blender helpers

- `scene-audit`: observed geometry/material/image/camera/light/timebase facts.
- `camera-fit`: explicit subjects, lens and view direction; evaluated bounds and actual aspect; new perspective/orthographic camera.
- `camera-check`: sampled framing and clip-plane checks, not collision/occlusion certification.
- `light-rig`: explicitly specified additive lights relative to observed geometry; no universal studio/sunset recipe.
- `preview`: bounded CPU images with an existing camera, no armature requirement.

Existing inspect/import/index/retarget/assemble/qa jobs remain. Read [job contracts](skills/blender-asset-director/references/jobs.md) and use `--help`; never invent flags. New jobs write separate results and reject altered inputs/code. A new code version requires preparing new jobs rather than bypassing stale-hash checks.

## Evidence and testing

```text
python tools/run_checks.py --offline
```

CI separately runs Windows/Linux unit tests, installer tests, actual Blender 4.5.3/5.0.0 fixtures, multi-scene camera/light and rig-free preview tests, and live provider/source-motion checks. Online failures are not silently converted into passes. The baseline recorded a Quaternius/OpenGameArt connection failure; consult actual current run evidence for its state.

Fixtures test technical invariants using synthetic geometry/motion. They do not prove natural performance, historical accuracy, visual realism or the user's actual model. A contact sheet is not continuous-motion acceptance. Text-only models report visual review PENDING. A review record/hash validates evidence identity, not the correctness of an opinion. Final human acceptance is explicit.

Read [studio upgrade](docs/STUDIO_UPGRADE.md), [baseline acceptance](docs/ACCEPTANCE.md), [design](docs/DESIGN.md), [security](SECURITY.md), and [third-party notices](THIRD_PARTY_NOTICES.md). Adapted studio-method notices are retained inside the installed skill in [upstream-licenses.md](skills/blender-asset-director/references/upstream-licenses.md).
