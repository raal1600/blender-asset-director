# Installation and troubleshooting

## Starting from scratch

Install these separately, in the same OS environment where you will run Codex:

1. [Python 3.11 or newer](https://www.python.org/downloads/). Verify `python --version`, `python3 --version`, or `py -3 --version`.
2. [Local Codex](https://developers.openai.com/codex/quickstart). Sign in or configure your preferred supported provider. This skill does not require a particular model or extra API account. It does not configure DeepSeek.
3. [Blender](https://www.blender.org/download/) and your reviewed [Blender MCP setup](https://github.com/ahujasid/blender-mcp). Follow the upstream add-on and Codex MCP configuration instructions. Open Blender and start the connection. In Codex, `/mcp` lists the actual active servers. A teaching overlay is optional.

Now run the [README installer](../README.md#install--one-copypaste), start a fresh Codex session, and invoke `$blender-asset-director` for a first-run check. You do not need Git, Node or uv for **this skill installer**; your chosen MCP may have its own prerequisites.

The downloaded PowerShell/shell script and Python bootstrap are executable code from this repository. Read them before running. They select an explicit release tag, not arbitrary moving main. SHA256 downloaded from the same release is an integrity check, not independent proof of publisher identity. No global execution-policy change, administrator prompt or secret is needed.

## Paths and overrides

Default skill: `$HOME/.agents/skills/blender-asset-director`.
Default library: `$HOME/CGI-Library` (or a previous configured path).

Runtime path-only configuration:

- Windows: `%LOCALAPPDATA%\BlenderAssetDirector\runtime.json`.
- macOS: `~/Library/Application Support/BlenderAssetDirector/runtime.json`.
- Linux: `${XDG_CONFIG_HOME:-~/.config}/blender-asset-director/runtime.json`.

`BAD_CONFIG` selects an alternative path-only settings file. `BAD_LIBRARY` and `BAD_BLENDER` override saved library and Blender paths. Explicit CLI arguments have highest precedence. The installer records the Python interpreter that performed setup. If that interpreter is not on PATH, the agent can use its absolute path or `py -3`/`python3` as appropriate.

Windows bootstrap flags:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -PythonPath "C:\Python311\python.exe" `
  -BlenderPath "D:\Apps\Blender\blender.exe" `
  -LibraryPath "D:\CGI-Library" `
  -SkillPath "$HOME\.agents\skills\blender-asset-director"
```

Python/macOS/Linux equivalent:

```sh
python3 install.py --blender /absolute/path/to/blender --library /absolute/library --dest /absolute/skill/path
```

Only choose a skill directory that local Codex actually scans. `CODEX_HOME` changes the user config location inspected for MCP declarations; it is not automatically treated as a replacement for `$HOME/.agents/skills`. The installer deliberately does not rewrite Codex's skills configuration. Avoid duplicate copies with the same skill name.

A previously selected Blender executable is not silently replaced when its path goes missing. Select the intended replacement explicitly. Automatic detection prefers PATH, then conventional versioned Blender installation directories. Portable apps, sandboxed installations and remote Blender require explicit paths and local validation.

## What the first-run check proves

The installer verifies package integrity, offline code tests, bundle execution, managed destination ownership and local paths. It initializes the separate library and reads only a small user-level Codex configuration summary. It does not print commands, arguments, keys or environment values from that file.

It does not connect to Blender, run a model request, test authenticated providers, prove model vision or prove Codex discovery. Those checks happen **in your real Codex session** under [first-run.md](../skills/blender-asset-director/references/first-run.md). A read-only scene query is the live gate. `CONFIGURED_LIVE_TEST_PENDING` intentionally does not say connected.

No starter pack, backend or paid service is fetched automatically. A later authorized scene task can acquire the specific free assets it needs. Unknown rights and sign-in requirements remain explicit.

## Troubleshooting

| Message / symptom | Next step |
|---|---|
| Python not found / wrong version | Install Python 3.11+, reopen the terminal, or pass `-PythonPath`; no automatic Python reinstall occurs |
| Download 404 | Use the exact published release version; no fallback to main. A prerelease need not appear under GitHub's “latest” endpoint |
| SHA256 mismatch | Stop. Redownload from the same release and investigate; never bypass validation |
| Proxy/TLS failure | Use your organization's approved HTTPS/proxy setup or the offline package route; do not disable certificate checking |
| Already installed | Same-version reinstallation is idempotent. A different version requires `-Update` / `--update` |
| Installed files changed / unowned destination | Preserve your edits. Compare with the managed backup or install into a separate Codex-scanned location. Do not delete your library |
| Blender not found | Open/install Blender and provide `configure --blender <absolute-executable>` for custom locations |
| MCP not detected in user config | The connection may be defined by a project/plugin. Check `/mcp` in Codex; do not blindly add a duplicate |
| MCP configured but scene query fails | Start Blender's MCP connection, inspect its local error, and retry read-only; no scene work should begin |
| Skill not listed | Start a fresh local Codex session; verify the installation path and any disabled-skill policy. Hosted Codex cannot automatically reach desktop Blender |
| WSL sees nothing installed on Windows | Install in the same native environment as Codex. WSL/Windows interop and remote Blender are not validated by this installer |
| “Stale implementation/input” after updating | Prepare a new job from the actual current working copy; don't edit hashes or reuse old job specifications |
| Agent cannot inspect preview images | Use human review or an explicitly chosen image-capable model; the skill cannot add vision to a text-only model |

## Update and rollback

Download/review the bootstrap for the **target** release version and use `-Update` or `--update`. No unattended upgrades or main-branch polling occur. Managed files are verified before update; edited/unowned files block replacement. Previous managed snapshots are backed up under `%LOCALAPPDATA%/BlenderAssetDirector/install-backups` on Windows, or `~/.local/share/BlenderAssetDirector/install-backups` elsewhere.

To roll back, verify/uninstall the current unedited managed skill using its `scripts/manage_install.py`, then install the prior reviewed release. Alternatively restore the complete previous managed snapshot (including receipt) into the empty skill destination. Do not downgrade library schemas or delete asset files to make a rollback pass. A failed stage promotion attempts to restore the prior snapshot automatically.

## Offline installation

Download from one release: `install.py`, `install.ps1` (Windows) or `install.sh`, `blender-asset-director-<version>.zip`, and `SHA256SUMS.txt`. Keep the bootstrap files together. Review the script and obtain the expected checksum from the trusted release; do not calculate a new checksum from an untrusted file and call it verified.

```sh
python3 install.py --archive ./blender-asset-director-0.2.1.zip --sha256 <expected-64-character-sha256>
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Archive .\blender-asset-director-0.2.1.zip -Sha256 <expected-sha256>
```

No download occurs on this route. The checksum must match before extraction or execution of packaged code. This uses the named **release asset**, not GitHub's automatically generated source-code ZIP.

## Remove the skill

Use Python 3.11+ and the **installed** manager (replace the path for a custom destination):

```powershell
py -3 "$HOME\.agents\skills\blender-asset-director\scripts\manage_install.py" --dest "$HOME\.agents\skills\blender-asset-director" --uninstall
```

```sh
python3 "$HOME/.agents/skills/blender-asset-director/scripts/manage_install.py" --dest "$HOME/.agents/skills/blender-asset-director" --uninstall
```

No network needed. Only receipt-owned, unedited skill files are removed. The library and runtime settings remain. You can remove the path-only settings file separately, but do not delete the library unless you intentionally want to delete its assets and working results.

## Source development

```sh
git clone https://github.com/raal1600/blender-asset-director.git
cd blender-asset-director
python3 tools/run_checks.py --offline
python3 tools/install_skill.py --configure
```

After reviewed edits use `--update --configure`. The source installer bundles the runtime; a generic installer that copies only the SKILL.md folder will not. Run `python3 tools/bootstrap_smoke.py --shell python` for a disposable installation/update/uninstall test. Real Blender and live-provider tests remain separate gates.

Official Codex references: [skills/discovery](https://developers.openai.com/codex/skills) and [MCP configuration](https://developers.openai.com/codex/mcp). No claim of an OpenAI-endorsed or marketplace-published plugin is made.
