# Asset browser and separate Blender previews

The scene workflow remains Productions → Scenes / Final film, with World, Action,
Shots, Light and Render inside each scene. This change does not restructure the
asset library, replace the catalog, or introduce global role pages.

## Browse, preview, add, import

The [library readiness flow](LIBRARY_READINESS.md) adds This production / My library
views and explicit **Prepare & add** for supported local World packages. Ordinary
preview remains read-only and never silently intakes a source.

- Browse defaults to assets relevant to the current activity. World includes
  environments, props and characters; Action contains animation; Light contains
  material/HDRI records. Entire library is an explicit escape.
- Details shows source members, sizes, rights evidence, version identity and
  observed motion timing/performer metadata where available. Preview… opens that
  sheet without selecting the asset.
- Preview in Blender verifies and copies the selected package, prepares it with
  the bounded harness and opens a new factory-startup, autoexec-disabled Blender.
  It never retargets a live window, contacts MCP, selects the ingredient, binds a
  project job, grants rights or creates a scene checkpoint.
- Add stores an ingredient reference. Only the separately authorized World
  import creates real objects in a new unapproved candidate. Animation records
  cannot use World import, including when found through Entire library.

## Supported inspection and limits

Preview members: blend, glTF, GLB, FBX and BVH. Indexed native motion uses the
existing native-clip pairing/timebase checks (interchange animation only). Source
packages remain original-registry identities, not silently intaken catalog assets.
OBJ, material and HDRI visual adapters are not included in this first preview path;
the UI describes unavailable previews instead of fabricating them.

Each explicitly requested attempt copies at most 4096 files / 512 MiB. The native
worker uses the existing bounded job executor with a 180-second deadline. No
render, downloads, AI/model calls or dependency installation occurs. Missing,
changed, unrecorded external dependencies and ambiguous native pairings fail closed.
Separate Blender execution is defense in depth, not an OS sandbox.

The Blender Asset preview sidebar opens automatically after drawing and offers
framing, native take selection and play/pause. It lists only observed action/NLA
bindings, not inferred bone mappings. Readiness requires visible preview controls.
Unassigned/object animation can be inspected with Blender's normal timeline.
Native-speed continuous playback and artistic acceptance still require human review.

The GUI opens PREVIEW_COPY.blend, separate from the immutable job result. Saving
edits in that disposable viewer does not overwrite the job result or originals.
Preview windows remain normal Blender windows: close with X and handle any save
prompt deliberately. Director may exit after preparation without closing Blender.
No process is killed to hide an unconfirmed window; startup failures retain logs.
Each preview uses its own native temporary directory, including Blender's exit
recovery file. Provider credentials are not inherited by the preview process.

## Storage and taxonomy

Attempts and failure evidence live in SystemRuntime/UserData/AssetPreviews, outside
projects and the shared catalog. request.json binds exact source IDs, versions,
members and hashes. receipt.json binds the job, result, viewer and metadata;
process.json and window-ready.json bind the specific initialized Blender window.
Readiness is not human approval. No automatic cache deletion is included.

Subcategories prefer recorded metadata/tags or original registry collection types.
Unknown models stay unclassified; a rigged tag alone does not prove Character.
Details allows an explicit display-label correction for a model/pack. Labels are
stored separately in UserData/Launcher/asset-labels.json and retain history under
AssetLabelHistory. They match the exact catalog source version and expire from
display when that version changes. They never rewrite catalog metadata, hashes,
source files, rights or project approvals. Filtering occurs before pagination.

Texture maps are no longer arbitrarily displayed as model previews. Only
conservatively named source-reference images (preview/thumbnail/reference etc.) are
offered as reference images; these are explicitly distinct from the live 3D preview.

## Verification boundaries

Portable and launcher tests cover refusal, identity, paging, labels and unchanged
project/source state. The asset-preview fixture belongs to the existing authoring
Blender suite across its three supported versions; it exercises actual blend/GLB
preparation, indexed native animation and external-reference refusal. Existing
workflow partition names are unchanged. Public synthetic tests do not certify a
workstation's graphics, licensed assets, human playback review or a live update.
