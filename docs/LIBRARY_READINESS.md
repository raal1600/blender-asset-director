# Shared library and production usage

The browser separates **This production** from **My library**. Both retain the
existing catalog/package tabs, workflow categories, search and 24-result paging.
My library means locally recorded catalog assets and registered original packages,
not a claim that a remote listing is downloaded. No online-provider UI or implicit
download is added by this change. Existing reviewed provider acquisition remains
separate; no credentials, dependency installations or global paths change.

The two scope buttons show matching counts for the current catalog/package tab,
workflow, search and category, plus **Added to production** versus **Available to
add** subtitles. They are distinct lists: This production contains retained
references; My library excludes those references before counting and paging.
Adding an asset removes it from My library for this production and makes it
available under This production, including for reuse in another scene. The
underlying shared files remain in the library and are still available to other
productions. No folder move, deletion or per-production download occurs.

Catalog exclusion uses stable asset IDs, including when a production retains an
older pinned version; listing never replaces that version. Source package
exclusion includes retained/selected original references and exact-version
preparation links to catalog pins, never matching names. Selected-only switches
to This production and narrows to the current scene without redefining membership.
Removing a scene selection does not remove historical production references.
An exhausted library offers View This production, and an empty production offers
Browse My library. A failed query shows an unknown count, never a false zero, and
does not hide readable retained production references. The unscoped read-only API
retains its full-library behavior; browser requests explicitly exclude production.

Each row separates local availability/preparation from production usage. Current
or candidate presence requires that exact checkpoint's object audit. Selection,
historical pins, another scene's objects and a 3D preview never establish presence
in this scene. A saved file without an object audit remains unverified. This
production includes retained references across scenes, not just today's selection.
Prepared source packages join catalog use only through a recorded exact-version
link, never by a matching asset name.

## Prepare & add

World offers guided preparation for registered Meshes/Characters packages with an
explicit blend, glTF, GLB or FBX member. A package is already local; preparation is
not another download. Other formats, animation indexing and look assets retain
their reviewed specialist workflows.

1. Select the exact source member. The compact popup has one unchecked box:
   confirm you have the right to use and adapt this asset in your productions and
   will follow its original terms, including required credits. **Confirm & prepare**
   stays disabled until checked. There are no source URL, creator or license fields.
   Cancel, Escape and an unchecked request start no preparation or job.
   This is the user's declaration for the exact existing local version, not an
   automatically verified license. No future files, raw redistribution, model
   training, download or purchase is authorized.
2. Acquire the existing project writer semaphore and retain a run/authorization
   record. Validate registry version, package containment, at most 4096 files and
   500 MiB. A separate verified inspection copy is checked in real Blender with
   scripts disabled. Missing or non-package-local dependencies block publication.
   Relative package dependencies are preserved; no broad external-file search or
   dependency download is performed.
   A newly prepared catalog record permits production import of only the exact
   inspected member, not unchecked model members packaged beside it.
3. The existing explicit intake copies the verified original-format package into
   the shared content-addressed `incoming` catalog store, with retained evidence.
   It does not intake the disposable PREVIEW_COPY scene. Existing catalog metadata
   for identical content is preserved, including any policy refusal.
4. Verify the resulting catalog identity and original source bytes again. Record
   the source-version/catalog-version link and choose the catalog reference for
   this scene. No scene checkpoint or source-use attestation is created here.
5. Continue through production source-use review and, for blend packages, actual
   collection inspection and explicit collection selection. The existing bounded
   **Add to world** job creates a new candidate alongside previous checkpoints.
   The user reviews and keeps it; preparation never auto-imports or auto-keeps.

This deliberately separates source evidence, project-use confirmation, technical
import and creative acceptance. Cancelling the form starts no preparation/job.
Stale versions, active writers and unresolved candidates refuse preparation.

### Honest local-use confirmation

New local World intake may retain a `local-project-use-v1` declaration bound to
the original registry ID/version, selected member, confirming production and time.
The resulting immutable catalog-version metadata binds its exact intake file
hashes and inspected member. The creator, source page and license remain unrecorded
(`UNKNOWN` license), never fabricated as Creative Commons. The UI calls this
**Use confirmed by you**, not verified licensing or commercial clearance. The
user remains responsible for original terms and required credits.

This explicit local-only path does not make ordinary unknown-license catalog
records eligible, and cannot replace an existing reviewed or blocked record for
the same package. Existing evidence wins; changed/malformed confirmations fail
closed. No provider/acquisition policy or Mixamo grant is replaced. Native jobs
using a confirmed catalog model freeze its confirmation/catalog identity and
refuse changed evidence before execution. Catalog pins and job history retain
the declaration; this is not a new embedded Blender licensing/DRM system.

The previous detailed evidence API remains available for reviewed specialist and
existing integration callers, with the same validation. The new checkbox route
accepts no caller-supplied creator/license fields. Production-wide source-use and
individual import/creative decisions remain separate and are not auto-answered.

## Persistence, failure and compatibility

No catalog/project schema migration, original-folder move or production rewrite is
required. New preparation attempts and link records live under
`SystemRuntime/UserData/LibraryPreparations`; project `Runs` contains the bound
operation status. The shared library keeps the content-addressed intake files.
Other productions reuse that verified catalog version rather than copying the
package again. Inspection attempts consume additional space and are retained,
including failures; no automatic deletion is part of this update.

A failed attempt cannot publish a candidate or manufacture permission. A failed
copy/catalog transaction may leave diagnostic files, which are retained. Explicit
recovery refuses a native preparation job still recorded RUNNING; inspect its
exact retained worker evidence before releasing the project. Old runtime rollback
must preserve these new files and project history, not replace data with an empty
studio or restore obsolete manifests over newer work.

## Tests and scope

Unit coverage exercises production membership, unavailable/unknown states, the
single unchecked confirmation, stale inputs, refusal, reuse and preserved originals. The existing
guided World browser journey now prepares a generated local glTF package, then
uses the normal reviewed import to combine it with an existing saved world.
`library_preparation_fixture.py` checks an actual blend package, observed collection
import, texture dependencies and a deliberately missing dependency. It runs inside
the existing guided suite; modular workflow names and source-bound receipts remain.

All scripted rights and keep decisions are synthetic test inputs, not human or
licensed-production acceptance. Public CI and local fixture passes are separate
from exact-package staging and a backed-up live-runtime update.
