# Shared library and production usage

The browser separates **This production** from **My library**. Both retain the
existing catalog/package tabs, workflow categories, search and 24-result paging.
My library means locally recorded catalog assets and registered original packages,
not a claim that a remote listing is downloaded. No online-provider UI or implicit
download is added by this change. Existing reviewed provider acquisition remains
separate; no credentials, dependency installations or global paths change.

The two scope buttons show matching counts for the current catalog/package tab,
workflow, search and category, plus **Production references** versus **All shared
assets/packages** subtitles. They are overlapping filters of shared files, not
separate folders or per-production downloads. Selected-only remains a scene filter;
the scope counts still describe all matches. A matching-view explanation is shown
only when both complete bounded result sets have the same exact asset IDs and
versions. Equal counts, matching names or one equal page of a larger result do not
prove identical membership. A failed comparison shows an unknown count, never a
false zero, and does not hide readable retained production references.

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
not another download. Other formats, animation indexing, custom rights and look
assets retain their reviewed specialist workflows.

1. Select the exact source member. Supply the actual creator, HTTPS source/terms
   references and verified license, and explicitly confirm zero-cost source
   evidence. No license or attestation is preselected. Unsupported/custom rights
   fail closed; the form is not a way to assign a more permissive license.
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

Unit coverage exercises production membership, unavailable/unknown states, empty
rights forms, stale inputs, refusal, reuse and preserved originals. The existing
guided World browser journey now prepares a generated local glTF package, then
uses the normal reviewed import to combine it with an existing saved world.
`library_preparation_fixture.py` checks an actual blend package, observed collection
import, texture dependencies and a deliberately missing dependency. It runs inside
the existing guided suite; modular workflow names and source-bound receipts remain.

All scripted rights and keep decisions are synthetic test inputs, not human or
licensed-production acceptance. Public CI and local fixture passes are separate
from exact-package staging and a backed-up live-runtime update.
