# World: add, draft, save

The normal World path is Browse / View 3D → Add to scene → Save changes.
Source selection, single-collection inspection and native import are coordinated
by the existing bounded APIs. A selected reference is still not an imported
instance; the displayed draft must have real Blender output and object evidence.

## Drafts and recovery

World imports can extend the current unsaved World candidate. Every import writes
a separate immutable checkpoint whose parent is the actual input checkpoint.
`current` stays at the last user-saved version; `candidate` is the working draft.
No schema rewrite or historical receipt migration is required. A failed addition
retains the prior draft, attempted job and error evidence.

Save changes explicitly invokes the existing KEEP_WORKING decision. It does not
approve World as finished, advance to Action or approve renders/films. Undo moves
the candidate pointer back one verified parent, recording a new undo receipt and
retaining all checkpoint files. It never deletes assets or old outputs. A changed
input hash, unrelated activity, active writer or stale revision still refuses.

The Save / Undo bar is visible in both World and its asset browser. Continue to
Action remains a separate human creative decision after saving.

## Add and permission

Each Add click is an explicit intent for one exact asset version/member and scene.
The client serializes at most twelve intents, de-duplicates repeated pending
clicks, and stops the remaining queue on failure, cancellation or context change.
The queue is window-local, not an autonomous service: closing/reloading cancels
unstarted intentions. Started native jobs and saved drafts retain their normal
durable recovery records. While additions remain, the browser's standard
before-unload warning asks before leaving; its wording is browser-controlled.

A missing production source-use confirmation pauses the same addition at one
unchecked checkbox; confirmation resumes it, while cancel starts no dependent
job. Already confirmed identical scope does not prompt again. No approval is
fabricated and no native rights gate is bypassed.

For an unprepared local package, the new explicit `projectUse` checkbox request
covers preparation and use in the named production. It is accepted only if all
previously pinned sources already have their required review. The backend binds
the actual package confirmation to the verified source-to-catalog mapping and
checks that the resulting scope contains only the previous sources plus that
exact prepared version. Its source-use receipt references the preparation run;
it is a real launcher-checkbox transport, never an MCP response or creative
approval. Older preparation callers retain preparation-only behavior.

Blender files with one observed collection continue automatically. Files with
multiple collections require an explicit collection choice (or Add all); no
guessed collection names or retarget mappings are introduced. Unsupported
members, missing dependencies, blocked rights or changed versions still stop.

## Verification

Launcher tests cover serial draft imports, parent hashes, undo/save separation,
failure preservation, changed versions, denied permission, collection ambiguity,
scope binding and queue cancellation. The existing installed-studio workbench
journey exercises the new visible controls with actual Blender. Scripted choices
on generated fixtures are test input, not acceptance of user assets or films.
