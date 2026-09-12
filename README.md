# Blender Asset Director

**Give Codex a small Blender production team—not another Blender harness.**

Use a prompt and an existing `.blend` to inspect the scene, reuse suitable assets, search for missing ones, plan shots, adapt existing animations, improve cameras/lighting, and review the result. One skill loads only the needed roles: director, production designer/scout, performance, cinematography, lighting/look development, finishing, and continuity/QA.

**Current preview: v0.2.1.** Installation is automated. Cinematic quality and compatibility with your specific scene still need a real test. No warrior, desert, fixed object names, camera lens, frame rate, or duration is assumed.

## Before you install

You need **Python 3.11+**, **local Codex**, and **Blender with a working Blender MCP connection** for scene work. The teaching overlay is optional. Keep any existing setup—you do not need to reinstall it or change your model provider.

Starting from scratch? See [the three prerequisites](docs/INSTALL.md#starting-from-scratch). This installer adds **our skill**, not Blender, Python, Codex, API accounts, or an MCP server. It will identify missing pieces rather than claim they work. Use the installer in the **same operating-system environment as Codex**; native Windows and WSL have different home directories.

## Install — one copy/paste

No Git clone, `pip install`, administrator account, or API key is needed for this installation. The bootstrap downloads **v0.2.1**, verifies the release ZIP's SHA256, runs offline checks, installs the complete skill/runtime, and remembers your local paths.

### Windows: PowerShell 5.1 or newer

```powershell
$installer = Join-Path $env:TEMP ("bad-install-" + [guid]::NewGuid().ToString("N") + ".ps1")
Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/raal1600/blender-asset-director/v0.2.1/install.ps1" -OutFile $installer
powershell -NoProfile -ExecutionPolicy Bypass -File $installer
```

`Bypass` applies only to this installer process. It does not change the machine's execution policy. The script is readable: [review install.ps1](install.ps1) and [install.py](install.py) before running. SHA256 protects package integrity; it is not an independent publisher signature or a security audit.

### macOS / Linux

```sh
installer=$(mktemp)
curl --fail --silent --show-error --location --proto '=https' https://raw.githubusercontent.com/raal1600/blender-asset-director/v0.2.1/install.sh -o "$installer"
sh "$installer"
```

The installer selects Python 3.11+ from your environment. Set `BAD_PYTHON` to an explicit interpreter when needed. [Review install.sh](install.sh).

### Then: open a new local Codex session

Paste this into **Codex**, not PowerShell:

```text
$blender-asset-director
Run the first-run check. Verify the existing Blender MCP read-only.
Do not modify my scene. Tell me exactly what is ready or missing.
```

The check verifies the installed files, saved paths, available MCP tools, and an actual read-only scene query. Installer output such as `CONFIGURED_LIVE_TEST_PENDING` is **not** proof of a live connection. Codex may discover the skill immediately; start a fresh session if it is not listed.

## Try a scene

Once the first-run check passes, open any project in Blender and ask:

```text
$blender-asset-director
Improve the currently open scene into a cinematic showcase.
Inspect it first and preserve my original file. Work on a separate copy.
Reuse existing assets and search only for genuinely missing elements.
Explain the shot plan, use small CPU previews, and show what changed.
Do not render a full animation or use paid services.
```

For a narrower test:

```text
$blender-asset-director
Improve the lighting and framing of my selected object. Do not change its
geometry or replace its materials. Save a working copy and render one small preview.
```

The **host model** interprets your request. The skill supplies role guidance, validated production contracts, asset tools, and Blender helpers—not a hidden extra model. A text-only model cannot visually critique a render; it must leave visual acceptance pending for you or an explicitly selected image-capable model.

## What installation changes

| Location | Purpose |
|---|---|
| `~/.agents/skills/blender-asset-director` | Managed Codex skill, all role references, bundled runtime, license notices |
| `~/CGI-Library` by default | Separate asset catalog, downloads, animations, previews, working jobs |
| OS-local `runtime.json` | Only library, Blender, Python, and skill paths; [exact locations](docs/INSTALL.md#paths-and-overrides) |

Codex configuration, DeepSeek/OpenAI/other provider settings, MCP declarations, Blender preferences, existing `.blend` projects, and credentials are **not changed**. No assets are bulk-downloaded. Retarget-backend installation and provider authentication happen only when an authorized task needs them.

Blender is detected from PATH or conventional installation directories. Portable/custom installs can be selected explicitly. Job commands use saved paths so you normally do not need to repeat `--library` or `--blender`.

## Update, diagnose, remove

Download/review the bootstrap for the version you intend to install, then run it with `-Update` (Windows) or `--update` (macOS/Linux). Re-running the same version is safe; upgrading a different managed version requires that explicit flag. Edited or unowned skill folders are never overwritten. Updates back up the previous managed installation.

Windows examples, using the `$installer` downloaded above:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File $installer -Update
powershell -NoProfile -ExecutionPolicy Bypass -File $installer -BlenderPath "D:\Apps\Blender\blender.exe" -LibraryPath "D:\CGI-Library"
```

From Python 3.11+ (use `py -3` on Windows or `python3` on macOS/Linux where appropriate):

```text
python <installed-skill>/scripts/director.py doctor
python <installed-skill>/scripts/director.py configure --blender <absolute-executable>
python <installed-skill>/scripts/manage_install.py --dest <installed-skill> --verify
python <installed-skill>/scripts/manage_install.py --dest <installed-skill> --uninstall
```

Uninstall is offline and preserves your library and local path settings. [Troubleshooting, custom paths, offline installation, and source-development setup](docs/INSTALL.md).

## What is implemented

The asset services search the local catalog, Poly Haven, ambientCG, and Sketchfab (authenticated downloads need your token). A Quaternius starter-pack route indexes actual source actions. Mixamo, BlenderKit, and Poly Pizza use a discovered approved host integration or manual download/intake—not invented private APIs.

The studio layer validates requirements against an actual scene audit; generates gap queries; routes role-specific work; and offers subject-relative camera fitting/checks, additive light plans, bounded CPU previews, motion indexing, retargeting, and NLA assembly. Original inputs are hashed, separate working results are saved, and stale jobs are rejected.

These are technical tools and guidance. Camera bounds are not a beauty score; terrain root-height following is not foot IK. Finishing/sound planning is not a complete audio mixing or final-video delivery backend. Default production budget: eight CPU preview frames and two repair passes, tracked across jobs by the host. No paid generation or local AI inference is required; normal Codex/model usage charges still apply.

## Tests and evidence

[CI](https://github.com/raal1600/blender-asset-director/actions/workflows/ci.yml) separates unit/policy tests, managed installation, platform bootstrap tests, real Blender 4.5.3/5.0.0 fixtures, and live asset/source-motion checks. Release publication waits for that workflow; separate post-publication tests exercise the real anonymous download route. See [setup acceptance](docs/SETUP_ACCEPTANCE.md) and [studio acceptance](docs/ACCEPTANCE.md) for exact executed results and limitations.

To develop from a source checkout:

```sh
python tools/run_checks.py --offline
python tools/install_skill.py --configure
```

Use the managed installer rather than copying only `skills/blender-asset-director` with a generic skill installer: the executable runtime must be bundled too. [Design](docs/DESIGN.md) · [studio contracts](skills/blender-asset-director/references/studio-contracts.md) · [provider contracts](skills/blender-asset-director/references/providers.md) · [security](SECURITY.md) · [third-party notices](THIRD_PARTY_NOTICES.md).
