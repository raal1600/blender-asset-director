# Blender Asset Director

**Give Codex a small Blender production team—not another Blender harness.**

Blender Asset Director is a scene-independent Codex skill that can inspect an existing `.blend`, reuse suitable assets, discover genuinely missing assets, plan shots, adapt animations, improve camera/lighting, and review technical evidence. It selectively loads seven responsibilities: director/producer, production design/scouting, performance, cinematography, lighting/look development, editorial/finishing, and continuity/QA.

**Current preview: v0.2.2.** This release fixes an installer test that could falsely fail on machines where Blender was already discoverable or where the installer was run with Blender's bundled Python. No warrior, desert, object name, lens, frame rate, duration, or scene type is hard-coded.

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
Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/raal1600/blender-asset-director/v0.2.2/install.ps1" -OutFile $installer
powershell -NoProfile -ExecutionPolicy Bypass -File $installer
```

No Git clone, `pip install`, administrator account, or extra API key is required. `ExecutionPolicy Bypass` applies only to that installer process; it does not change the machine-wide policy.

The bootstrap downloads the **pinned v0.2.2 release**, verifies its SHA256, runs the offline checks, installs the complete managed skill/runtime, detects Blender from conventional locations, creates the separate asset library, and saves local paths.

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
  https://raw.githubusercontent.com/raal1600/blender-asset-director/v0.2.2/install.sh \
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

## Asset and animation support

The current toolkit supports local catalog search, Poly Haven, ambientCG, Sketchfab search/authenticated acquisition, and a verified Quaternius animation-pack route. Mixamo, BlenderKit and Poly Pizza remain host-tool/manual acquisition paths where appropriate; private APIs are not scraped.

Animation tooling includes source indexing, rig inspection, pinned retargeting backend support, NLA assembly, root-motion handling and numerical QA. Root-height terrain following is **not** full foot IK, and arbitrary production rigs still require local visual acceptance.

## Update / verify / remove

Re-run the v0.2.2 installer with `-Update` when updating a different managed installation:

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

The release pipeline separately verifies unit/policy/studio/setup tests, Windows PowerShell 5.1 and 7 bootstraps, macOS/Linux bootstraps, Blender 4.5.3 and 5.0.0 fixtures, live asset/source-motion checks, release publication, and anonymous public installation from the published release.

The v0.2.2 release specifically fixes the environment-dependent `test_job_missing_blender_actionable` failure reported by a real Windows installation using Blender-bundled Python. The corrected test now mocks Blender discovery **before** local configuration is created, so it tests the missing-Blender branch independently of the host machine.

See [setup acceptance](docs/SETUP_ACCEPTANCE.md), [studio acceptance](docs/ACCEPTANCE.md), [installation details](docs/INSTALL.md), [design](docs/DESIGN.md), [security](SECURITY.md), and [third-party notices](THIRD_PARTY_NOTICES.md).
