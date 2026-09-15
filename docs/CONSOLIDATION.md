# Current development handoff — September 15, 2026

## Source of truth

`main` is the consolidated development branch. Runtime `0.6.0-dev.4` is not a
release: the published installer remains v0.5.0. Use full Git commit identities.
This consolidation does not change installed skills, user projects, preferences,
agent providers, MCP connections or repository protections.

The current user requested consolidation, fresh Actions validation, contributor
documentation and cleanup. This supersedes older handoffs' temporary “do not
merge” instructions. Preserve those handoffs as records of their sessions, not as
current branch-selection instructions.

## What was reconciled

Most development branches already form a single chain. The combined source also
preserves three divergent histories: the synthetic Transition Lab, main's earlier
deployment wrapper, and the imported-reference identity fix. No feature branch is
blindly copied over main and no history is rewritten. Original branch tips are
recorded in [the cleanup inventory](consolidation/branches.json).

The public read-only audit is [Actions run 35027452229](https://github.com/raal1600/blender-asset-director/actions/runs/35027452229).
Its `consolidation-audit-*` artifact retains a Git bundle, branch graph, exact
branch tips, run inventory and pull-request inventory for 30 days. Branch deletion
does not remove commits that are ancestors of main; the inventory and merge
history remain the long-term recovery pointers.

### Defect found during consolidation

The action/reference workflow at `d61f56f90aad0c604b03720464f7d057bc987112`
failed on Blender 4.5.3 in [run 34938877417](https://github.com/raal1600/blender-asset-director/actions/runs/34938877417),
although the ordinary ten-job CI passed. The importer can rename both an owner
and its action slot after an object-name collision. Action-name handling alone
therefore did not make the stored slot identifier valid at runtime.

`action_identity.imported_slot` accepts only an observed, already-bound, unique
OBJECT-slot rename matching the imported owner. Exact slot matches and legacy
non-slot actions keep their existing behavior. Ambiguous, unrelated and unbound
slots are refused. The catalog and immutable reviewed options are not edited.
The same guarded resolution is used in planning and reviewed execution.

The identical-reference shortcut is retained alongside the newer physical-metre
alignment tolerance; it does not restore the superseded local-unit tolerance.
Portable rejection tests and actual Blender planning **and execution** regressions
are now in the normal three-version CI matrix. Failed historical runs remain
visible rather than being represented as successful.

### Workflow cleanup

The branch-only action/reference workflow is replaced by normal CI coverage.
The sequence investigation remains available as a manually dispatched diagnostic.
The synthetic Pages workflow builds from the tested source, validates media and
browser behavior, and deploys only main. Its obsolete hardcoded download of an
expiring earlier run is removed; its history is preserved by the merge.
No raw licensed assets or private reports enter public Pages.

## Required gates before accepting a revision

| Gate | Required evidence |
|---|---|
| Asset Director Tests | All ten jobs: three portable OS/Python configurations, three real Blender versions, four bootstrap configurations. |
| Blender regression coverage | Normal/custom roles, display, grounding, precision, source/action identity, long full-take sequencing and existing production fixtures. |
| Transition Lab | Actual synthetic pipeline/render, H.264 validation and Chrome desktop/mobile playback. Main additionally requires successful deployment. |
| Source package | Source-only package bound to the full commit; not a release or installation update. |
| Private integration | Private repository pins this exact public SHA and runs real licensed inputs plus bounded comparison recording; evidence stays private. |

A PR must cite its final Actions runs. The merge is authorized only after the
integrated public and private gates pass; main then runs its own post-merge gates.
This document defines the gates, **not a claim that an in-progress run passed**.
The PR conversation and Actions records carry the exact final run/commit pairs.
Artifacts have explicit retention periods; JSON provenance and original commit
identities must be retained in docs or PR records when accepting results.

## Cleanup safeguards and future contributions

Cleanup is a one-time, named-branch operation. The cleanup workflow waits for all
required main workflows for the same SHA. It verifies the target is still current
main, branches are unprotected, old tips match the inventory, all tips are already
ancestors of main, and no open PR needs them. The temporary integration branch
also needs a merged PR matching its current tip. Unknown, moved or divergent
branches are preserved. Deletions use expected-ref leases and are reported in
Actions. No protection or repository setting is relaxed.

New contributors start a focused branch from main and follow
[CONTRIBUTING.md](../CONTRIBUTING.md). Do not recreate old long-lived development
branches or edit a historical evidence file to turn a failure into a pass.

## Acceptance scope and limitations

Synthetic and private numeric checks are not a proof of universal natural motion.
The private recording's retained user review covers a particular four-second
video, not the full 38.5-second sequence or future recordings. Bounded sampled
contact does not establish continuous contact or full IK. Preserve these limits
when reporting results. No release, broad private publication, desktop test or
production runtime replacement is implied by this cleanup.
