# Blender Asset Director

A reuse-first agent skill and Python toolkit for finding existing assets, indexing real animation clips, transferring motion to compatible Blender rigs, and checking the result. Keep the existing Codex/DeepSeek/Blender MCP setup; do not add another competing harness.

**Status: published implementation candidate.** 69 unit tests and installer checks pass on Windows and Linux. Real headless Blender fixtures pass on 4.5.3 and 5.0.0; live Poly Haven and ambientCG acquisition/import also pass. Quaternius acquisition is blocked by a hosted-runner connection failure, so the actual retrieved-motion gate remains unvalidated and CI correctly remains failed. See [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) for exact evidence. The user scene still requires local acceptance.

## Workflow

```text
User brief -> inspect existing scene -> local catalog -> supported provider search
  -> license/format checks -> acquire shortlist -> index actual clips
  -> inspect source and target -> retarget on flat ground -> numerical QA
  -> assemble NLA and one root-motion owner -> gentle terrain -> human review
```

This is not an AI motion-generation service. It calls no extra LLM, performs no local AI inference, and does not spend Higgsfield credits. Host/model usage is still billed under the user's existing arrangement. Render jobs explicitly use modest Cycles CPU settings.

## Implemented components

- A discoverable `blender-asset-director` skill, on-demand reference files and a bundled-runtime installer.
- Standard-library Python CLI; no runtime pip dependencies for the portable core.
- Rebuildable SQLite catalog backed by durable per-asset manifests and hashed library-relative files.
- Local search, transparent lexical ranking, rights gates and provenance reports.
- Direct provider code for Poly Haven, ambientCG, Sketchfab, and the creator-posted free Quaternius Standard pack. Network behavior must pass live tests; other marketplaces are honest host-tool/manual-intake routes.
- Bounded HTTPS acquisition, validated redirects, credential separation, safe ZIP extraction and glTF dependency checks.
- Versioned background Blender jobs with stale-input detection, separate output files, deadlines, clean child environments and explicit failed-job retry.
- Scene/skinning/rig inspection; actual action-slot indexing; pinned Mwni transfer adapter; NLA timing; in-place controller travel; gentle root-height terrain following; CPU previews and numerical diagnostics.

**Not implemented:** universal automatic rigging, arbitrary control-rig retargeting, a full foot-IK/contact solver, automatic weapon-grip or cloth repair, browser account scraping, guaranteed cinematic animation, or an Unreal adapter. Missing prerequisites produce explicit review gates rather than fake replacements.

## Prerequisites

System Python 3.11+, a Blender installation, and an agent host that supports filesystem skills. Existing Blender MCP is used by the agent for live project discovery; the CLI itself does not change MCP configuration or connect to its socket.

Headless fixtures have passed on Blender 4.5.3 and 5.0.0. These are tested versions, not a claim about the latest Blender release or arbitrary-rig compatibility. The actual installed Blender version and user scene must still pass local acceptance.

## Install the skill

From a checked-out copy of this repository:

```powershell
python tools/install_skill.py --self-test
python tools/install_skill.py
```

Default destination: `~/.agents/skills/blender-asset-director`. Verify that this is a supported skills root for the installed host/version. Use `--dest <full-skill-directory>` for an explicitly selected alternative. The installer does not inspect credentials or alter Codex provider, trust, approval, or MCP settings.

The installed copy includes `scripts/runtime/asset_director`; it does not require the development repository to remain in its original location. Start a fresh agent session if skill discovery is cached, then verify `$blender-asset-director` is actually listed.

Update explicitly with `python tools/install_skill.py --update`. Changes to receipt-owned files or unowned additions block overwrite. Uninstall with `--uninstall`; the asset library is preserved.

## Use the CLI

From the source checkout, PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m asset_director --library "$HOME\CGI-Library" doctor
python -m asset_director --library "$HOME\CGI-Library" plan "warrior walks over a dune and stops"
python -m asset_director --library "$HOME\CGI-Library" search walk --provider local --kind animation
```

From the installed skill, call `python <skill>/scripts/director.py ...`. `BAD_LIBRARY` can define the library path. No database, models, textures, secrets or `.blend` files are stored inside the code repository.

Explicitly acquire the free starter package:

```text
asset-director seed --download
asset-director job-prepare index --asset RETURNED_ASSET_ID
asset-director job-run RETURNED_JOB_ID --blender ACTUAL_BLENDER_EXECUTABLE --timeout 900
asset-director index-collect RETURNED_ASSET_ID RETURNED_JOB_ID
asset-director search walk --provider local --kind animation
```

Here `asset-director` abbreviates the launcher above; it is also an entry point after an optional normal Python package installation. Placeholder IDs are not real assets. Indexing reports the actual clip names, slots, owners and duration, not an assumed animation inventory.

For retargeting, run `backend-install` to acquire the reviewed upstream commit. Read [job examples](skills/blender-asset-director/references/jobs.md) and [motion boundaries](skills/blender-asset-director/references/motion.md) before preparing an operation. Every mutation produces a new `jobs/<id>/result.blend`, not an overwrite of the original.

## Test before using a valuable scene

```powershell
python tools/run_checks.py --offline
```

The offline tests exercise policy, schemas, catalog recovery, path/archive protections, credentials across mocked redirects, job identity and motion diagnostics. They do **not** emulate a successful Blender retarget.

The CI workflow additionally downloads checksum-verified official Blender builds, runs real synthetic-rig/import/NLA tests, and attempts real free-asset acquisition/indexing/retargeting. It uses no private assets or provider secrets. Provider outages, schema changes and real Blender failures remain visible; do not hide them as skips.

Follow [local acceptance](skills/blender-asset-director/references/local-test.md). Gate A verifies installation and read-only scene readiness. Gate B mutates a working copy only after **Run the Desert Warrior test** is authorized. The existing warrior is never replaced by a test mannequin.

## Licensing and privacy

Original toolkit code uses the repository's MIT license. The separately acquired Mwni backend declares GPL-3.0-or-later and is not relicensed or included in source bundles. Assets retain their own licenses. Read [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [SECURITY.md](SECURITY.md).

Poly Haven API use is credited independently of its CC0 asset license. Default selection accepts evidenced CC0 and CC BY 3.0/4.0; unknown/custom/editorial/noncommercial restrictions are review gates, not blanket legal decisions. Catalog reports preserve source/author/rights evidence. Images supplied to an agent host can still be transmitted to its model provider.
