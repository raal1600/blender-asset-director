# Contributing

## Start from main

Use Python 3.11 or newer. A source checkout is enough for portable tests; Blender
is required only for the actual Blender fixtures. Do not install a development
build over a managed production skill just to run tests.

```sh
git clone https://github.com/raal1600/blender-asset-director.git
cd blender-asset-director
git switch main
git pull --ff-only
git switch -c feature/describe-your-change
python tools/run_checks.py --offline
```

Read [AGENTS.md](AGENTS.md), [the current handoff](docs/CONSOLIDATION.md), and the
relevant feature contract before editing. The runtime version alone is not a
build identity: include `git rev-parse HEAD` in bug reports and handoffs.

## Where changes belong

| Directory | Responsibility |
|---|---|
| `src/asset_director/` | Portable contracts and CLI; Blender-only execution modules are kept separate. |
| `tests/` | Portable unit, policy and failure-path tests; no Blender installation needed. |
| `tools/` | Actual Blender fixtures, packaging, installers and bounded diagnostic tools. |
| `skills/blender-asset-director/` | Agent instructions and role/operation reference contracts. |
| `showcase/` | Synthetic lab and approved showcase UI/media; see [publication gates](docs/SHOWCASE_PUBLICATION.md). |
| `docs/` | Design, contributor guidance and commit-specific acceptance/handoff evidence. |

## Test and review process

1. Make a focused branch from current main. Add tests for success, refusal,
   preservation and compatibility behavior. Update the affected contract and docs.
2. Open a pull request. **Asset Director Tests** must pass all ten matrix jobs.
   **Transition Lab · Build and publish** must pass build and browser validation;
   deployment is deliberately skipped on pull requests. Review logs and uploaded
   JSON evidence, not just a green job name. **Published installer defaults** must
   pass all five real no-version HTTPS installation jobs; see
   [the installer-default follow-up](docs/INSTALLER_DEFAULTS.md). Do not ignore unexpected skips.
3. For source/runtime changes affecting licensed inputs, a maintainer updates the
   private test repository's `harness-ref.txt` to this exact public commit and
   runs its complete integration/recording workflow before merging. Public CI
   uses synthetic fixtures and cannot substitute for that private gate.
4. Merge only the tested head, after checking it has not moved. When main has
   passed its post-merge tests, delete only branches whose tips are included in
   main. Preserve divergent work and failed test history. Do not force-update
   main, relax protections, or turn failing tests into optional checks.

The contributor command above is a fast preflight, not a substitute for the real
Blender/OS matrix. A local pass is labelled local; a queued Actions run is not a
pass. The consolidation workflow's one-time cleanup is restricted to its recorded
branch inventory and is not a general automatic branch deletion policy.

## Safety and evidence

Never commit FBX, `.blend`, model archives, textures, credentials, production
logs, SQLite libraries or configuration backups here. Use generated fixtures.
Restricted originals, project derivatives and private reports stay in the private
test repository and its private Actions artifacts. A rendered video approval
applies to the recorded hash and scope, not to all current or future assets.

Keep originals read-only. Use isolated libraries and outputs. Preserve license
lineage, reviewed hashes, rig/skin/rest geometry and existing actions. Never edit
receipts or approvals to make a stale test pass. Do not scrape unsupported APIs,
change the pinned backend without review, introduce paid/GPU work, or mutate a
user's installation, Blender preferences, agent providers or MCP configuration.

## Finishing a change

A useful PR/handoff states the problem, chosen fix, full tested SHA, Actions links,
exact gates run, meaningful skips/failures, artifact names/expiry, limitations and
next steps. Technical, sampled contact, temporal/visual and human acceptance are
different claims. Archived handoffs are historical evidence, not instructions to
return to obsolete branches. New releases and installed-runtime updates require
a separate explicit release decision; source consolidation is neither.
