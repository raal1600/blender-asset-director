# Installer-default follow-up — September 16, 2026

## Issue and correction

The consolidation PR's automated review identified a remaining installer bug:
`install.py`, `install.sh` and `install.ps1` still selected `0.6.0-dev.2`, although
that development version was not the documented published release. The earlier
bootstrap tests explicitly supplied the checkout version and therefore did not
exercise the default online path. A green offline-bootstrap job was insufficient.

All three defaults now select the existing **v0.5.0** release. The reviewed
published version and source commit are recorded in
[`published-release.json`](../published-release.json); the single-file bootstrap
scripts remain standalone and do not need that file at installation time.
Development source remains `0.6.0-dev.4`. No release, tag, runtime algorithm,
private asset, installed skill, user configuration or repository protection is
changed by this fix.

## Tests and evidence

Nine portable regressions cover the three entry-point defaults, published-pin
identity, README consistency, the Python default download URLs, explicit version
overrides, invalid versions, and refusal to fall back after a failed download.
Their transport/package fixtures are mocked and are not live-install evidence.
They run within the regular unit matrix.

The separate five-job **Published installer defaults** workflow runs
`tools/published_install_smoke.py` against the actual public HTTPS endpoints:
Python on Linux, POSIX shell on Linux/macOS, and both Windows PowerShell and pwsh.
These five checks deliberately omit every version and archive argument. They
verify the downloaded source commit, installed receipt version, repeat-install
idempotence, installed-manager verification/removal, library preservation, and
unchanged sentinel host configuration in isolated temporary homes. No GitHub
credential is passed to an installer subprocess. Failed checks fail the job;
there is no fallback to a local package or moving main.

Each run retains `published-default-*` JSON artifacts for 14 days, including the
tested source SHA, run ID, shell, selected release identity and checks completed.
Actions summaries distinguish these live checks from the existing explicit-version
development-archive install/update/uninstall tests. Neither kind of installer test
certifies a live Blender/MCP session or artistic motion quality.

The follow-up PR and its final acceptance comment retain exact Actions run/SHA
pairs. This document describes coverage, not an assertion that a queued run passed.
Full public CI, the five live installer jobs, source packaging, and Transition Lab
validation must pass before merge; fresh main gates and Pages deployment must pass before branch cleanup.

## Contributor guidance

When changing the published default, deliberately update the three scripts,
`published-release.json` and current installation documentation together after
verifying the selected release/tag and packaged source identity. Never substitute
`pyproject.toml`'s development version for an available published default. A future
release requires its own explicit authorization and release validation; this fix
does not publish one. Standalone entry points and explicit offline overrides must
remain supported.

Use `--version <version>` (Python/POSIX) or `-Version <version>` (PowerShell) when
installing a different reviewed release or a locally built development archive.
Use the matching explicit version with `--archive`/`-Archive` and its independently
reviewed checksum. See [installation and troubleshooting](INSTALL.md).

The private repository's passing consolidation pipeline remains evidence for its
pinned runtime. This installer-only follow-up does not change `src/`, `skills/`,
Blender fixtures or private test inputs. It does not reinterpret historical media
approval as approval of new or complete performances.

## Final cleanup

The original branch inventory and consolidation tip are preserved. Only the named
follow-up branch is added to the existing guarded cleanup process: it must have a
matching merged PR and be an ancestor of the fully passing, still-current main.
Moved, protected, unrelated or divergent work is preserved. The post-main cleanup
run records its decisions and deletion in Actions; no history is rewritten.
