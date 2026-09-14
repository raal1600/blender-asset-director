# Local motion inboxes — development milestone

Branch `feature/local-motion-library`, runtime `0.6.0-dev.2`.
Not merged into main or published. The public installer still selects v0.5.0.

## Why this is the next step

Start with a useful source performance. Manually acquire an animation through the
provider's official website, keep the download unchanged, and automate private
copying, indexing, search and original-character playback. Retarget only after
that performance is useful. Another proxy, sculpt operation, GPU model or private
Mixamo downloader is not required to remove the current import barrier.

The user's intended layout is an example configuration, not a runtime preset:

```text
E:\Blender\Animations\
  Mixamo\
  CMU\
  Rokoko\
  AIST\
  Custom\
  Incoming\
```

Register each confirmed provider directory, not the overlapping parent too.
Do not move `E:\Moonwalk.fbx`, create source folders or change originals merely
because this document mentions those paths. Root registration needs an existing
explicitly selected directory. Nothing scans other folders or a whole drive.

## Architecture

```text
Official manual download -> user-owned source inbox (read-only)
  -> bounded sync/hash -> verified CGI-Library private copy
  -> isolated Blender index -> actual clip/action/rig/timebase metadata
  -> local scout -> license/import preflight
  -> native character + original clip in a new scene
  -> floor/framing/native-speed temporal review
  -> optional target-specific retarget after source acceptance
```

There is no background watcher or scheduled task. The skill requests one bounded
refresh when a motion task begins and registered roots exist. A still-only task
does not need to refresh animation folders. User downloads and CGI-Library remain
separate. The runtime does not alter source ACLs/attributes or Codex/DeepSeek/MCP/
Blender settings. Read-only is a workflow rule, not OS-level write protection.

## Commands

Use the registered working Python and actual Blender executable; on this user's
Windows machine plain `python` may be a nonfunctional Microsoft Store alias.
Below, `director` means `python <branch skill>/scripts/director.py --library <library>`.

- `motion-root-add <existing-directory> --provider mixamo|cmu|rokoko|aist|custom|unknown`
- `motion-roots`
- `motion-root-scan <returned-root-id>`
- `motion-sync [--root <id>] [--index] [--blender <actual-executable>] [--max-new-files 8]`
- `motion-evidence <local-retained-terms-file>`
- `motion-root-review <id> --review <review-request.json>`
- `motion-license-revoke <review-id> --reason <text>`
- `motion-scout "moonwalk" --use commercial`
- `motion-preflight <asset-or-clip-id> [--purpose project_use|raw_redistribution]`
- `job-prepare native-clip --asset <indexed-clip-id>`, then `job-run <returned-job-id>`

The host agent handles the JSON and returned IDs. The user should not have to write
per-animation JSON files. A source filename supplies searchable intent, not proof
of a convincing performance. The actual internal action name remains unchanged.

`COMPLETE` means sync processing completed, not that licensing or performance
passed. Each asset's readiness is separate. Parent records expose clip IDs and
`SELECT_INDEXED_CLIP`; selected indexed clips can show native-playback `READY`.
No rig mapping is required to assess a character's own animation. Unskinned clips
remain skeletons; the importer does not pretend to create a skinned character.

## License review: specific, evidence-backed and optional future scope

Folder/provider labels are provenance hints. The default does not grant rights.
Only the narrow `adobe-mixamo-project-v1` profile is added here. It uses the internal
label `LicenseRef-Adobe-Mixamo`, not CC0. Other providers retain their existing
review routes; creating AIST or CMU directories does not create format adapters or
an unrestricted license exception.

Primary sources checked September 14, 2026:

- Adobe Mixamo FAQ: https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html
  allows royalty-free personal, commercial and nonprofit project use.
- Adobe General Terms, section 3.6: https://www.adobe.com/legal/terms.html
  distinguishes modification/incorporation for an end use from standalone
  redistribution. Applicable specific terms can supersede these general terms.

The profile admits reviewed private project processing and refuses standalone raw
redistribution requests. It is not legal advice, Adobe account verification,
permission to train models, or clearance of third-party character rights. No assets,
credentials or full Adobe terms are bundled in the public repository.

Retain the actual applicable FAQ/terms evidence with `motion-evidence`, then build:

```json
{
  "policy": "adobe-mixamo-project-v1",
  "reviewer": "actual approving user/reviewer",
  "reviewed_at": "actual timezone-aware ISO date",
  "official_downloads_attested": true,
  "terms_reviewed": true,
  "include_future_files": false,
  "evidence": [
    {"url": "https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html", "file": {"path": "returned path", "sha256": "returned hash", "size": 1}},
    {"url": "https://www.adobe.com/legal/terms.html", "file": {"path": "returned path", "sha256": "returned hash", "size": 1}}
  ]
}
```

These are schema placeholders, not valid evidence. Never invent an approval or
write true on the user's behalf without authority. Default false approves only
currently scanned FBX hashes. True requires explicit user adoption of the folder
as an inbox of legitimate official Mixamo downloads and approval of the same
profile for future files they place there. This remains **user-attested**, not
provider-verified. Mixed/unknown sources must stay outside that reviewed scope.

Each file gets an immutable grant bound to its exact private copy, original review,
retained evidence and permitted purpose. Indexed clips inherit it. Re-review then
sync updates clip grants without re-running Blender on unchanged source bytes.
Revocation blocks subsequent operations/reuse but deletes nothing.

Prepared jobs bind grant and evidence hashes, revalidated at execution/reuse.
Managed derivative `.blend` files retain a private scene marker and hash lineage;
canonical exports inherit restrictions even when a caller supplies a contradictory
CC0 label. The originating library's reviews are needed; a copied `.blend` alone
is not a portable license receipt. This is workflow enforcement, not DRM: deliberate
external removal of metadata is outside its guarantees. There is no new raw-asset
export or redistribution service; normal releases contain only code/docs/tests.

## Bounds and honest failure states

At most 16 non-overlapping roots. Per-root scan: 4096 entries, four nested directory
levels, 2 GiB of hashing; each source at most 500 MiB. Default new/index workload is
8 files per sync, explicit maximum 32. Budget deferrals are partial, not success.
Recently modified files are deferred for two seconds. Stable stat/file-descriptor
identity and hashes before/after read/copy reject active changes. Source hashes,
size and modification time are preserved; OS access-time effects of reading are
not a claimed invariant.

Symlink/junction/reparse ancestors and entries are refused, not followed. Missing
or inaccessible drives are unavailable, not empty. No deletion is synchronized:
missing originals leave their verified private copies available. Renaming/duplicate
content preserves aliases without another copy. New bytes at an old name create a
new asset; no old result is overwritten. Identical bytes under a different root
produce a provenance conflict rather than selecting the most permissive license.

Automatic file intake supports `.fbx`, `.bvh`, self-contained `.glb`. GLB resource
references are checked. `.gltf`, `.blend`, ZIP packages require the existing
explicit package intake/selection workflow. `.asf`, `.amc`, `.npz`, `.npy` need
unimplemented native converters; pickle is never deserialized. Mixed folders report
unsupported files without pretending they were processed.

FBX custom properties are not imported; recursive filename-based image search is
disabled. Background Blender is not a complete OS sandbox for malicious binaries.
Failed indexing jobs preserve evidence and need explicit retry; no endless loop.

## Compatibility and remaining work

The new modules separate portable scanning/review (`local_motion.py`,
`license_policy.py`), CLI (`local_motion_cli.py`) and Blender (`native_clip.py`).
Existing jobs/indexes carry grants and source labels. Existing canonical records
without new fields remain readable; restricted records require a compatible
runtime. Jobs still bind implementation hashes: prepare fresh downstream jobs,
never rewrite old receipts to pretend they were produced by new code.

Mixamo-like torso recognition resolves only a verified direct
Hips -> Spine -> Spine1 -> Spine2 chain, retaining distinct roles. Duplicate aliases,
broken chains and absent parent evidence stay ambiguous. Names don't prove actual
provider origin, rest-pose compatibility or performance quality.

No private website API, GPU reconstruction, contact IK, new full-video renderer,
sculpting or production-quality human skin is implemented by this change.

## Local acceptance

In a separate worktree and disposable library, read AGENTS.md, then:

```text
python tools/run_checks.py --offline
python tools/install_skill.py --dest <unused-temporary-skill-directory>
blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 11 --python tools/local_motion_fixture.py -- <unused-output-directory> <test-library>
```

Use the actual saved interpreter/executable. Reuse the already verified retarget
backend in the test library. The fixture generates synthetic FBX and synthetic
review evidence; it is not evidence of an Adobe download or license grant. It tests
sync/index/reuse, native timing, policy propagation through scene/canonical/retarget
stages, and revocation. It never reads a production scene or user asset.

After that passes, inspect the already downloaded user FBX in its authorized root,
verify provenance/evidence, and obtain the actual one-time scope approval. Do not
move the file at `E:\Moonwalk.fbx`, broaden roots, reinstall globally or download
another take without authority. Import the native pairing first. Add a floor and
clear framing using reviewed jobs. Keep performance pending until continuous
playback is actually reviewed, and human acceptance pending until the user accepts.
Stop after local acceptance; do not merge, publish or start another subsystem.
