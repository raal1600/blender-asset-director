# Live wiki: source-controlled documentation

**Docs · Live wiki — build, verify and publish** rebuilds the wiki on every
branch push. Pull requests build and validate a preview without publishing.
Manual runs are also supported once this workflow exists on the default branch.
There is no polling loop, paid service, model call or personal access token.

## Sources and generated references

`wiki/config.json` explicitly maps canonical Markdown sources to wiki page names.
Edit those source files, not the generated copies in GitHub's Wiki editor.
`wiki/` contains the onboarding and navigation pages. Architecture, production,
safety and CI guides reuse existing repository documentation.

`tools/wiki/build.py` rewrites relative documentation links, attaches source
identity and creates the sidebar/footer. The actual portable argument parser,
job operation registry and CI coverage contract generate CLI, operation and
evidence references. All workflow definitions and a tracked-source index are
included. `catalog.py` runs in an isolated environment and rejects network access;
no job, provider acquisition, Blender process or model call is executed.

Semantic explanations are maintained by contributors in the same change as the
implementation. Automation mirrors them and regenerates factual inventories;
it does not infer undocumented behavior or claim that tests passed. New guide
pages require an entry in the explicit map. New commands, operations, workflow
files and tracked documentation appear in the generated inventories automatically.

## Exactly one publishing branch

Before this workflow lands on the default branch, the bootstrap publishing
source is `feature/consolidated-updates-20260917`. Other branch pushes and pull
requests are previews only. Once the default branch contains `wiki/config.json`,
it becomes the publishing source automatically. This prevents the development
branch and main from alternating incompatible wiki versions after merge.

The workflow rechecks this policy and the source branch's current HEAD just
before publication. A stale run fails instead of overwriting a newer snapshot.
Publishing runs share one concurrency group; pushes are fast-forward only.
The source branch and exact commit are visible on every page. A documentation
publish does not assert acceptance, merge code, change branch protections,
install a runtime, or publish a software release.

## First publication

GitHub stores a wiki in a separate Git repository. Enable **Wikis** in repository
settings and save its first **Home** page through the Wiki tab. Use this body:

```html
<!-- live-wiki-bootstrap -->
```

A standard GitHub `Welcome to the blender-asset-director wiki!` Home is also
recognized as a disposable seed. Then rerun the failed **publish** job in the
existing live-wiki Actions run. A manual workflow dispatch is not needed for this
one-time retry, so the source workflow need not be merged first.

Only the publish job receives `contents: write`, using the automatic
`GITHUB_TOKEN`. No account token should be pasted into source or chat. GitHub's
one-time page creation requirement is documented in
[Adding or editing wiki pages](https://docs.github.com/en/communities/documenting-your-project-with-wikis/adding-or-editing-wiki-pages).

## Safe updates and conflicts

The `.live-wiki-manifest.json` tracks generated page names and hashes. Sync
updates or removes only previously managed pages, preserves unrelated manual
pages, rejects symlinks/path traversal and refuses to overwrite a changed managed
page or an unowned conflicting filename. It never force-pushes or wipes wiki
history. Repeating the same source snapshot produces no new wiki commit.

To fix a manual-edit conflict, first copy the wanted edit back to its canonical
repository source. Preserve any needed wiki edit/history, then restore the
managed page to its last generated version and rerun publishing for the current
source. New manually maintained pages should use names outside the generated
map. There is no silent two-way sync.

After a push, publishing clones the wiki afresh and verifies the manifest and
all page hashes. A page-generation failure, unavailable/uninitialized wiki,
conflict, stale source or failed verification makes the workflow fail visibly.
The build and publishing reports distinguish generated, unchanged and published
states; an uploaded preview artifact alone does not mean the wiki is live.

## Tests and reproduction

The wiki tests execute the full generator and publisher against disposable local
Git repositories: clone, sync, commit, push and independent read-back, plus a
second unchanged run, safe removals, preserved manual pages, conflicts, broken
links and corrupt manifests. This tests publishing mechanics, not authenticated
GitHub availability or the Blender harness itself.

```sh
python -m unittest discover -s tests -p 'test_live_wiki.py' -v
python tools/wiki/build.py --output /temporary/empty-wiki \
  --repository raal1600/blender-asset-director \
  --commit FULL_CHECKOUT_SHA --branch YOUR_BRANCH
```

The CI job also runs `python tools/run_checks.py --offline`. Generated artifacts
contain only explicitly selected public Markdown, public definitions and hash
manifests; they never read an E: drive, a studio, credentials, a catalog database
or private assets. Build artifacts and publication reports are retained for 14 days.
