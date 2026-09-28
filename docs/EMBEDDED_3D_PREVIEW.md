# Embedded 3D inspection

Director has two distinct inspection surfaces: an in-app WebGL view of saved
geometry, and a separate native Blender preview/editing surface. Neither selects
an asset, imports objects, keeps a checkpoint, approves rights or approves output.
This is not a live stream of unsaved Blender edits or an embedded Blender editor.

## User flow

Asset Details provides **View in 3D**, followed by the existing **Preview in
Blender** option. Choose the exact source member first. The canvas supports orbit,
zoom, pan, reset, grid and wireframe. Embedded takes expose play/pause and a scrub
control at their native timebase; this does not retarget motion. Zero-duration
entries remain selectable as **Static pose**, without fake playback. Camera fit
uses the evaluated pose after take selection, not stale bind-pose bounds. Changing the
member or closing the inspector disposes the old view.

Saved scene evidence provides **View saved scene in 3D**, independently of a
camera. **Rendered still** remains a separate collapsed section, explicitly
requiring an observed CAMERA object. An EMPTY named Camera is not a camera.
Scene/checkpoint navigation releases the previous viewer. Blender remains the
place to edit; return a newly saved checkpoint to inspect changes in Director.

## Identity, storage and bounds

Both endpoints require the existing loopback Bearer session, same-origin checks,
project/scene identities and an exact recorded version/member or checkpoint hash.
Every original is verified before preparation, after conversion and before a
cached derivative is served. Source files, catalog and project manifests are not
modified. Serving a preview requires a current session grant for its scene;
verified successful IDs may be reused after explicit preparation in a new session.

The direct glTF/GLB path needs no Blender process. It packages only recorded
relative buffers and PNG/JPEG textures into an embedded GLB. External/data URLs,
path escapes, unrecorded resources, compressed geometry and GPU instancing are
refused. Native files use the existing isolated, script-disabled, two-thread
Blender preview worker, a 180-second deadline and a separate library. Absolute
checkpoint dependencies may only resolve to verified copied files from its
retained catalog/package pins; arbitrary external references are refused.
Embedded BLEND copies use short, source-mapped paths for both catalog assets and
checkpoints, avoiding nested Windows path failures without altering source paths.

Private outputs and failures live in `SystemRuntime/UserData/ViewerPreviews`.
Successful previews are reused across sessions only after validating an indexed
provenance record, exact source/profile/shot identity, current launcher/native
implementation and Blender executable hash, metadata/output hashes, successful
native evidence (where applicable), and the GLB description. Altered evidence
refuses visibly and remains on disk; an old/unindexed attempt is never promoted
into a trusted cache entry automatically. Native identity checking is deliberate
work on a warm request, not a zero-cost cache lookup.

At most 64 recently accessed preview descriptors, and at most 32 MiB of their
serialized metadata, remain in memory (not a promise about total process RSS). Older
descriptors may be evicted without deleting files; reopening them re-verifies the
persisted cache. Preparing a 65th preview does not require restarting Director.
An old media grant that was evicted must be prepared again before serving bytes.
Repeated concurrent preparation is serialized and reuses the verified result;
failed promises do not poison the queue. Source and project scope is rechecked
for every request. No session token or credential is persisted in this cache.

Closing or replacing a view aborts its preparation/geometry HTTP requests. The
existing authenticated preparation handler observes that disconnect and cancels
queued or preflight work before allocating a conversion attempt. This signal is
limited to read-only preview preparation; it never cancels an explicit scene Save,
render, review or other writer just because a browser went away. There is no new
unauthenticated cancellation endpoint or general Blender command channel.

Once a conversion attempt has been allocated, its bounded native work completes
normally. A departed view receives no active lease; verified successful bytes can
be reused when reopened. Actual failures keep their original failure evidence.
This cancels obsolete requests, not already-started Blender processes. No process
is killed, source changed, checkpoint created or approval inferred by navigation.

The implementation still refuses a source above 512 MiB / 4096 files,
with one compatible optimization for saved checkpoints: new native audits may
record `preview-dependencies-v1`, bound to the exact saved file SHA-256. For clean
snapshots with simple absolute file references, the copy includes that checkpoint
and only its observed, already-pinned dependencies. Both the Blender path inventory
and supported data-block references must agree. This does not import a missing
dependency, grant rights, or skip production-wide pinned-source verification.

Older audits, wrong-byte observations, relative paths, linked libraries,
time-varying resources and unknown path types retain conservative all-pinned
copying. Existing projects are not rewritten to obtain the optimization. Actual
native conversion still rejects unrecorded references and verifies copied bytes.
The source-copy limit is unchanged; it applies after the safe selection.

Other limits remain:
128 MiB GLB, 10000 nodes, 2 million displayed vertices,
128 textures, 8192-pixel texture dimensions or 64 million decoded texture pixels.
Conversion supports up to 3600 frames per take / saved scene and 20000 total take
frames. Before another copy it reserves space under a 100 GiB preview-folder budget.
This is a cumulative storage ceiling, not preallocated disk space; the per-preview
source, conversion and GLB limits above remain unchanged.
No automatic deletion of old copies or failed evidence is performed. Very large
packages, procedural/simulation/volume content and rig-only files use Blender.

## Reviewed preview cleanup

Studio -> Preview storage scans private derivatives and presents removable payload
bytes, protected copies and exact relative targets. It does not clean the asset
library or project history. Nothing is removed until the user confirms the exact
current review, including that these cached copies are not open manually in Blender.
Viewing another scene or Final film releases the prior in-app view; another open
window still protects its copy. Each UI view has a separate scope-bound grant.
Closing a view releases its cleanup protection, not the existing bounded session
media descriptor. Previously prepared historical bytes remain readable until LRU
eviction or explicit cleanup. Media reads share the cleanup queue, so removal
waits for an in-flight read and revokes its descriptor before removing payloads.
Lost/crashed view grants remain protected until session restart rather than being
expired on a timer. Older API clients without view IDs receive conservative
session protection for their 64 most recent preparations.

Only indexed, successful, byte-verified derivatives whose original sources still
verify are eligible. For native previews this includes the copied source payload,
model GLBs and derived BLEND files, not request/viewer metadata, catalog databases,
job/result/receipt records or worker logs. Failed, interrupted, unindexed, unknown,
linked, multiply-linked, drifted or actively viewed copies remain protected.
Scanning is bounded to 50,000 files, review metadata to 16 MiB and each removal
batch to 128 copies. These are conservative refusals, not recursive deletion.

Apply rechecks the complete review and native process command lines, then each
target immediately before unlinking. Missing native process information refuses
removal. Command-line checks cannot discover a file opened later through Blender's
File menu, so the user's explicit closed-copy confirmation is still required.
Normal scene-editing Blender windows must not be closed just to clean previews.
Preparation and removal are serialized; one closed browser view cannot revoke
another view's protection. Abandoned asynchronous views release their grant if
preparation finishes later, without pretending that the native job was cancelled.

The cache-index pointer is removed first so a partial attempt cannot be reused.
Its original record, reviewed hashes, write-ahead target and actual removals remain
in a synced JSON journal under ViewerPreviews/Cleanup. Any failure stops further
removal and reports PARTIAL with the journal path; remaining evidence is protected,
not retried or erased automatically. This is not an atomic multi-file transaction.
Removed payloads have no undo but can be regenerated from verified originals.
Net recovered space differs from payload bytes because the journal is retained.

## Preview fidelity and failure presentation

Native Blender conversion now reduces static textures only in temporary image
datablocks: at most 2048 pixels per edge and 16 Mi pixels total (smaller when
necessary). Original files and the saved Blender inspection copy retain their
full-resolution textures. Bindings are restored even if export fails. The
receipt records source/preview dimensions; the viewer labels optimized previews.
Input conversion remains bounded to 128 images, 8192 pixels per source edge and
128 Mi source pixels. Movie, sequence and UDIM textures still require Blender.
The direct glTF/GLB fast path does not resize textures; its existing limits and
the final GLB validator remain unchanged. Reduction does not make unsupported
shaders or simulations faithful: use Blender for exact material inspection.

Failed previews show an explanation, retained technical details and an explicit
Blender-preview button for assets. Failure never imports, selects or approves
an asset, and never automatically opens another application.

The app uses inspection lighting and glTF material approximations, not Cycles,
saved scene look, compositor or final render evidence. A played clip is not human
acceptance of motion. Derived files retain their source identity and inspection-
only status; they are not general redistribution exports or license grants.

## Offline vendor identity

Three.js 0.186.0 is MIT licensed and vendored locally. `tools/vendor_three.py`
downloads only on an explicit `--download` developer action; the application and
installer never download it. The published archive SHA-512 is pinned in that
tool; `launcher/public/vendor/three/VENDOR.json` records archive SHA-256 and exact
upstream/adapted file hashes. The sole adaptation resolves addon imports to local
modules. Its MIT notice ships at `launcher/public/vendor/three/LICENSE`.
No global packages, PATH, provider, authentication or MCP settings are changed.
The browser allows local blob texture decoding while still refusing external
connections; no CDN, remote decoders, script execution from assets or uploads.

## Regression evidence

`launcher/test/embedded-preview.test.mjs` covers authentication, isolation,
source/cache drift, resource refusal and vendor integrity. The existing real
`asset_preview_fixture.py` adds native asset and camera-free checkpoint GLB
exports without changing its original evidence partition. `embedded_viewer_suite.py`
uses actual catalog intake, real native conversion and real Chrome WebGL, checks
rendered-pixel changes for navigation/animation, and verifies originals/catalog/
manifest preservation. Screenshots and logs remain in the explicit evidence
directory and are not automatically published.

`preview-cache.test.mjs` covers fresh-session reuse, 66 distinct previews with a
64-entry memory bound, profile isolation, concurrent repeated requests and
corrupt/escaped/oversized metadata refusal. `preview_cache_check.mjs` measures
actual native cold/warm/restart conversion and transfer, verifies fresh-session
authentication, original/manifest preservation and real workbench WebGL/selection
before and after restart. Timings are measured evidence, not universal promises.
Its RSS measurement covers the launcher only, not Blender or browser peak memory.
`preview_cleanup_check.mjs` drives two real browser views, actual native conversion,
an owned short-lived Blender process, authenticated removal refusal, scripted
decline/confirmation, exact allowlisted cleanup and actual native rebuilding. It
verifies retained database/log/receipt/source/checkpoint/manifest hashes. Unit
coverage separately simulates a locked-file partial failure and protects drift,
unknown files and hard links. Test decisions are not human production approvals.
Representative large-source timing and broader resource measurements remain
separate acceptance work; automatic cache eviction never deletes disk files.

`preview_cancel_check.mjs` verifies browser navigation actually aborts the request,
queued cancellation avoids a native conversion, an observed RUNNING native job
finishes safely, and returning reuses its exact result without another conversion.
Its deterministic queue gate holds the response of a real completed first native
job; it does not simulate native success or claim a native process was interrupted.
Original/checkpoint/manifest preservation and absent active-view leaks are checked.

`preview_dependencies_fixture.py` observes real saved texture, packed-image,
relative-path, sequence, modifier-cache and linked-library cases.
`preview_dependencies_check.mjs` verifies the authenticated native conversion and
browser canvas copy only the needed recorded inputs and reuse the same result.
Semantic camera/light fingerprints exclude this copy-only metadata; the native
Save/reopen and existing source/checkpoint byte checks remain independent gates.

Synthetic/local test success is not exact-commit CI success, desktop WebView
acceptance, a runtime update or production/creative acceptance. Installation
still requires a newly identified candidate, verified staging and reversible
cutover; never patch the installed runtime in place under its old identity.
