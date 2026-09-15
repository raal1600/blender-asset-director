# User-managed animation folders

Use for a motion request, not every still scene. Check `motion-roots`; if roots
exist refresh once with bounded `motion-sync --index --max-new-files 8` using the
registered Blender executable. Search local clips with `motion-scout` before remote
discovery or asking for another download. This is on-demand, not a background watcher.

Register only existing user-approved provider folders using `motion-root-add PATH
--provider mixamo|cmu|rokoko|aist|custom|unknown`. Do not hardcode a drive, discover
sources with a broad disk scan, or register overlapping parent/child roots. Sources
must be outside CGI-Library and remain untouched. Paths and reviews are stored only
in the private library, never by changing Codex/DeepSeek/MCP/Blender configuration.

Inspect per-asset `motion-preflight`; intake/index success is not import eligibility.
A folder name is only a provider hint. Licenses must have evidence. For Mixamo,
retain applicable official FAQ and terms via `motion-evidence`, then prepare the
explicit review described in `docs/LOCAL_MOTION_LIBRARY.md` from the source repo.
Do not make the user type per-file JSON. Required request fields are policy
`adobe-mixamo-project-v1`, reviewer, timezone-aware reviewed_at, true explicit
`official_downloads_attested` and `terms_reviewed`, boolean `include_future_files`,
and exactly two `{url,file:{path,sha256,size}}` references:

- https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html
- https://www.adobe.com/legal/terms.html

Call `motion-root-review ROOT_ID --review REQUEST_JSON`. Default future scope false
covers current scanned hashes only. True requires explicit user approval of future
official downloads into that dedicated inbox. Never fabricate that approval. The
result remains user-attested, not independent proof. The scope is project use, not
standalone redistribution, public library publishing, or model training. Unknown
sources and other providers do not inherit this permission.

Sync again after approval; copies/index are reused and grants flow to clips. An
already completed index doesn't need to run again merely to update rights metadata.
`motion-license-revoke REVIEW_ID --reason TEXT` blocks future use without deleting
originals or rewriting historical outputs. Provider terms are not CC0.

For a useful new animation, select a returned indexed clip and prepare/run
`native-clip --asset CLIP_ID`. This creates a fresh source-only working scene with
its original character/action, correct indexed FPS and covered endpoint, without
retargeting. `SELECT_INDEXED_CLIP` means use a parent record's returned clip IDs.
A file with no skinned character stays a skeleton; don't report a human model.

Use existing reviewed floor/camera/light jobs. Inspect travel, timing, loop seams
and native-speed continuous movement before attempting another target or clay body.
Do not expand preview budgets or claim performance from stills. A filename is a
search label, not proof of motion technique; an intentional glide is not an order
to lock feet. Preserve the user's rejection of previous motion.

Sync copies FBX/BVH/self-contained GLB only. Gltf/blend/ZIP packages need explicit
package intake; ASF/AMC/NPZ need unavailable converters. Unavailable roots, partial
scans, recently changing downloads and failed indexes are not empty-library success.
Handle bounded errors and explicit failed-job retry, not endless loops. No downloads,
private endpoint access, token extraction, additional addon or inference model.

Managed derivative scenes and canonical records retain restrictive scope. Keep the
originating private library/evidence. Copying a restricted blend elsewhere does not
transfer its review; prepare only with verified lineage. These are workflow checks,
not DRM or independent legal clearance. Never publish user assets in GitHub releases.
