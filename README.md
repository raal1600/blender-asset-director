# Blender Asset Director

**Give Codex a small Blender production team—not another Blender harness.**

Blender Asset Director is a scene-independent Codex skill that can inspect an existing `.blend`, reuse suitable assets, discover genuinely missing assets, plan shots, adapt animations, improve camera/lighting, and review technical evidence. It selectively loads seven responsibilities: director/producer, production design/scouting, performance, cinematography, lighting/look development, editorial/finishing, and continuity/QA.

**Current preview: v0.4.0.** This adds reviewed **Lighting / Look Development authoring**: adapt observed existing lights (`light-adjust`), edit the active world's background within safe bounds (`world-adjust`), set scene exposure, view transform, look, display device and white balance where the running Blender exposes them (`look-adjust`), and inspect what is safely editable first (`look-audit`). Every look mutation returns a full before/after snapshot, proves unrelated lights, the world and the material set are untouched, and validates version-dependent values against the running Blender instead of assuming them. No genre presets, no shader-node scripting, no scenario or scene-name special cases.

## Before you install

You need:

- **Python 3.11+**
- **local Codex**
- **Blender**
- a **working Blender MCP connection** for live scene work

The Teaching Overlay is optional. Keep your current model provider and MCP setup—the installer does not replace or rewrite them.

## Install on Windows — one copy/paste

Open PowerShell and paste:

```powershell
$installer = Join-Path $env:TEMP ("bad-install-" + [guid]::NewGuid().ToString("N") + ".ps1")
Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/raal1600/blender-asset-director/v0.4.0/install.ps1" -OutFile $installer
powershell -NoProfile -ExecutionPolicy Bypass -File $installer
```

No Git clone, `pip install`, administrator account, or extra API key is required. `ExecutionPolicy Bypass` applies only to that installer process; it does not change the machine-wide policy.

The bootstrap downloads the **pinned v0.4.0 release**, verifies its SHA256, runs the offline checks, installs the complete managed skill/runtime, detects Blender from conventional locations, creates the separate asset library, and saves local paths.

If Python is installed in a non-standard place:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File $installer -PythonPath "C:\Path\To\python.exe"
```

If Blender is portable/custom:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File $installer -BlenderPath "D:\Apps\Blender\blender.exe"
```

## macOS / Linux

```sh
installer=$(mktemp)
curl --fail --silent --show-error --location --proto '=https' \
  https://raw.githubusercontent.com/raal1600/blender-asset-director/v0.4.0/install.sh \
  -o "$installer"
sh "$installer"
```

Set `BAD_PYTHON` if you want to select an explicit Python 3.11+ interpreter.

## Then open a new Codex session

Paste this into **Codex**, not PowerShell:

```text
$blender-asset-director
Run the first-run check. Verify the existing Blender MCP read-only.
Do not modify my scene. Tell me exactly what is ready or missing.
```

This is the local acceptance step. The installer can prove the skill files, paths, Python and Blender executable are available, but only the fresh Codex session can prove that Codex discovers the skill and can actually query your live Blender MCP.

## First safe scene test

With Blender open, try:

```text
$blender-asset-director
Improve the lighting and framing of my selected object.
Inspect the scene first. Preserve the original .blend and work on a separate copy.
Do not change geometry or replace existing materials.
Render one small CPU preview and report exactly what changed.
```

For a broader test:

```text
$blender-asset-director
Turn the currently open Blender project into a cinematic showcase.
Inspect the actual scene first. Reuse suitable existing assets and search only for genuinely missing elements.
Preserve the original file, use a working copy, keep previews small, and do not use paid services.
```

## What installation changes

| Location | Purpose |
|---|---|
| `~/.agents/skills/blender-asset-director` | Managed Codex skill, role references, bundled runtime, notices |
| `~/CGI-Library` by default | Asset catalog, downloads, animations, previews and working jobs |
| OS-local `runtime.json` | Library, Blender, Python and skill paths only |

The installer **does not modify** Codex provider settings, DeepSeek/OpenAI configuration, MCP declarations, Blender preferences, existing `.blend` projects, credentials, or API keys. It does not bulk-download assets or start rendering user scenes during setup.

## How the studio works

```text
prompt
  ↓
director / producer
  ↓
actual scene audit
  ↓
reuse / adapt / missing / uncertain
  ↓
only the required specialist roles
  ├─ production design / scout
  ├─ performance
  ├─ cinematography
  ├─ lighting / look development
  ├─ editorial / finishing
  └─ continuity / QA
  ↓
one controlled Blender execution path
  ↓
small previews + evidence review
```

The host model interprets creative meaning. The deterministic runtime validates object references, production contracts, source licenses, job identity, resource budgets, and evidence. Technical validation is not a beauty score, and a text-only model cannot claim visual acceptance of rendered frames.

## Camera work and preview artifacts

`camera-fit` remains the locked-off technical fit. `camera-plan` authors a deliberate move from host-supplied values - frame checkpoints, a world `position` or a `direction` with `distance`/`fit`, an aim (subject with optional bounds fractions, or an explicit world point), lens per plan or per checkpoint, the normalized `screen` position the aim should occupy, and optional roll, focus and interpolation - then verifies every checkpoint with real projection. Explicit point aims need no scene object and are verified exactly like subject aims, and mixed plans are supported. Orientation is solved as a roll-free frame, so zero requested roll measures zero and a nonzero roll measures back to the requested value while the aim point stays on its requested screen position. It creates a new camera or adapts an existing one, preserving that camera's earlier action in a muted NLA track. It will not choose a lens, duration, frame rate or format for you, it refuses orthographic plans rather than approximating them, and a smaller `fit` margin does not guarantee a larger subject when the aim sits off-centre.

Preview renders exist to bound CPU cost. A preview job records the project's own engine, resolution, resolution percentage, samples, output path/format, thread settings and frame, restores them before saving, and labels its result `PREVIEW_ARTIFACT` with `delivery_master: false`. Keep a working/master `.blend` and any final delivery render separate from preview output; nothing renders a whole sequence automatically.

## Lighting and look development

Look work is explicit and reversible. `look-audit` reports what exists and what is safely editable; `light-adjust` adapts observed lights (energy, color, per-light exposure, temperature, size/shape, sun angle, spot cone, soft radius, location/rotation, render visibility) and rejects properties that are not meaningful for that light type instead of storing values Blender would ignore; `world-adjust` edits the active world's background strength and colour only where the graph is a single unlinked Background node; `look-adjust` sets exposure, gamma, view transform, look, display device and white balance where the running Blender exposes it. Enum and range validity are checked against the running version at execution time - nothing is silently clamped or substituted, and complex world graphs are refused (`WORLD_GRAPH_UNSUPPORTED`, `WORLD_COLOR_LINKED`) rather than rewritten. `light-rig` remains the additive CREATE path.

Every mutation reports `classification` (PRESERVE is the absence of an operation), a full `before_snapshot` and `after_snapshot` (lights with properties, world state, colour management, render engine, material set), the values Blender measured back, and isolation guarantees for unrelated lights, the world and materials. Materials are never mutated by look operations. Numbers are not a beauty score: look acceptance still requires rendered before/after images and an image-capable reviewer.

## Asset and animation support

The current toolkit supports local catalog search, Poly Haven, ambientCG, Sketchfab search/authenticated acquisition, and a verified Quaternius animation-pack route. Mixamo, BlenderKit and Poly Pizza remain host-tool/manual acquisition paths where appropriate; private APIs are not scraped.

Animation tooling includes source indexing, rig inspection, pinned retargeting backend support, NLA assembly, root-motion handling and numerical QA. Root-height terrain following is **not** full foot IK, and arbitrary production rigs still require local visual acceptance.

## Update / verify / remove

Re-run the v0.4.0 installer with `-Update` when updating a different managed installation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File $installer -Update
```

Managed updates back up the prior version and refuse to overwrite edited or unowned skill directories.

Useful installed commands:

```text
python <installed-skill>/scripts/director.py doctor
python <installed-skill>/scripts/manage_install.py --dest <installed-skill> --verify
python <installed-skill>/scripts/manage_install.py --dest <installed-skill> --uninstall
```

Uninstall preserves the external asset library and local path settings.

## Tests and evidence

The release pipeline separately verifies unit/policy/studio/setup tests, Windows PowerShell 5.1 and 7 bootstraps, macOS/Linux bootstraps, Blender 4.5.3, 5.0.0 and 5.2.1 fixtures, live asset/source-motion checks, release publication, and anonymous public installation from the published release.

The v0.3.0 release added a Blender fixture (`tools/camera_fixture.py`) that authors camera moves on synthetic scenes with unrelated names, aspects, sensor fits, frame rates and lenses; validates an establishing-to-closer move whose subject changes screen position; confirms that adapting a constrained camera preserves its prior action and refuses a kept constraint that would defeat the authored aim; and proves a real preview job saves a `.blend` whose resolution, percentage, engine, samples, output format/path, thread settings and frame are the project's own rather than the preview's. v0.3.1 extends it with all-point-aim plans (constant and changing lens, create and adapt mode), an explicit camera-check call with point targets, and roll cases covering zero roll on centred and aggressively off-centre targets, explicit positive and negative roll, and a roll ramp across one move. v0.4.0 adds `tools/look_fixture.py`: adapting point/area/sun/spot lights, additive lights, exposure, gamma, a runtime-discovered view transform, white balance where available, safe world strength/colour edits, graded refusal of linked and ambiguous world graphs with the graph left intact, per-type property rejections, snapshot evidence and preview-settings restoration after a look adjustment. Unit coverage for the camera-plan, target and look contracts runs on every unit target.

The v0.2.2 release specifically fixes the environment-dependent `test_job_missing_blender_actionable` failure reported by a real Windows installation using Blender-bundled Python. The corrected test now mocks Blender discovery **before** local configuration is created, so it tests the missing-Blender branch independently of the host machine.

See [setup acceptance](docs/SETUP_ACCEPTANCE.md), [studio acceptance](docs/ACCEPTANCE.md), [installation details](docs/INSTALL.md), [design](docs/DESIGN.md), [security](SECURITY.md), and [third-party notices](THIRD_PARTY_NOTICES.md).
