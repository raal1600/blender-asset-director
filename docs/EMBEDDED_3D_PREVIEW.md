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
modified. Returned preview IDs belong to the current server session and scene.

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
Successful previews are reused within the running server session, bound to exact
sources. The implementation refuses more than 64 session copies, a 512 MiB /
4096-file source package, 128 MiB GLB, 10000 nodes, 2 million displayed vertices,
128 textures, 8192-pixel texture dimensions or 64 million decoded texture pixels.
Conversion supports up to 3600 frames per take / saved scene and 20000 total take
frames. Before another copy it reserves space under a 2 GiB preview-folder budget.
No automatic deletion of old copies or failed evidence is performed. Very large
packages, procedural/simulation/volume content and rig-only files use Blender.

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

Synthetic/local test success is not exact-commit CI success, desktop WebView
acceptance, a runtime update or production/creative acceptance. Installation
still requires a newly identified candidate, verified staging and reversible
cutover; never patch the installed runtime in place under its old identity.
