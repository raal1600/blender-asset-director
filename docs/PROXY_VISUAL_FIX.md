# Diagnostic proxy: visible anatomy is not the controller graph

This is a focused correction on `feature/motion-foundation`, development runtime
`0.6.0-dev.1`. Use an exact commit, not the version label, to identify the patch.
Main, published releases and user installations are not changed.

## Evidence and root cause

The user-reported retest of b3c1578 passed timing and anatomical scaling (0.8 legs,
1.15 arms), but still rendered a 1.316 m root-to-hips capsule weighted to a stationary
root. Decorative upper-body geometry remained. The full local report and source
are not in this repository; the pasted findings are the reproduction basis, not
an independently executed local-source acceptance by the repository maintainer.

`motion_blender.clay` previously visualized every parent-child edge, plus a tail
for every leaf. Changing those from display tails to heads repaired main limbs
but did not distinguish rig controls from anatomical landmarks. Assigning a whole
link to its parent also could not guarantee that its far end followed a child
moving through intermediate helper transforms. Passing skeleton tests missed the
visible-surface error.

## Correction

* `motion_proxy.anatomy_graph` uses only explicit, reviewed anatomical roles below
  hips. It connects each to its nearest anatomical ancestor. It never draws a
  root-to-hips link, unlabelled helper, decorative leaf, or arbitrary terminal tail.
* All original rig bones remain. The geometry omission does not delete motion
  channels, rename rigs, or change transfer mappings. Missing/contradictory anatomy
  fails with PROXY_ANATOMY_REVIEW_REQUIRED rather than guessing from controller names.
* `proxy_geometry.create_skin` creates bounded capsule links and landmark markers.
  Each end ring binds fully to its own semantic joint; intermediate rings blend
  those endpoint bones. Marker geometry binds to its own joint. No root/helper
  vertex group is created. Linear vertex-group skinning is explicit; envelopes
  and dual-quaternion volume preservation are disabled for this diagnostic mesh.
* The result persists a v2 geometry manifest (segments, excluded bones, ring/marker
  membership, topology hash). `check_attachments` measures their actual evaluated
  mesh centres against evaluated anatomical heads, verifies skin groups and
  topology, and restores the frame/subframe after sampling.
* Creation checks the rest mesh. Canonical retarget checks nine timestamps,
  including its exact endpoints. Detachment fails with PROXY_ATTACHMENT_FAILED;
  a skeletal TECHNICAL PASS alone no longer passes this geometry gate. Legacy
  proxies are explicitly NOT_CHECKED and must be regenerated, never retroactively
  approved by this patch.

The original timing/semantic length fixes are left unchanged. Source records and
old output files remain immutable; changed code causes new downstream job IDs.

## Added tests

Twelve portable graph regressions cover roots, decorative leaves, helpers between
landmarks, arbitrary names, long/misleading tails, coincident landmarks, missing
hips, inconsistent anatomy and nonmutation. `tools/proxy_visual_fixture.py` runs
real background jobs using generated source data with a 1.316 m root-to-pelvis
offset, long decorative tails, intermediate upper-body helpers, a stationary root,
moving hips, and articulated limbs. It tests source-shaped and 0.8-leg/1.15-arm
proxies, reopens saved results, checks evaluated attachments at 25 timestamps,
checks two deliberate corruptions (displaced skin and extra root weights), and
produces two 480x480/8-sample CPU previews. No performer asset is redistributed.

CI executes this fixture on all supported Blender versions. Execution results
must be reported separately from this description of the tests.

## Focused local retest

Use a new worktree/output folder and the same immutable motion record:
`m_7998ee55d7767d3c9c3b333006d778b39b13b2e07d7f05cca83d8994d59eedf6`.
Do not download or re-export it. Preserve both previous failed proxy outputs.
Run offline checks and both the foundation and proxy-visual Blender fixtures first.
Then regenerate source-shaped and previously specified 0.8-leg/1.15-arm proxies,
build fresh target profiles/fingerprints, and retarget with the audited alignment.

Inspect `proxy_geometry.graph.excluded_bones`, actual skin vertex groups and
`proxy_attachment_check`. The stationary controller and nonanatomical decorative
bones must have zero direct surface weights and zero rendered segments. Inspect
rendered deformed surfaces at the same representative timestamps as the previous
test; do not infer visual success from armature lines alone. Report any unwanted
piece even if the numerical attachment check passes. Timing and measured ratios
should retain the preceding pass, with ordinary numerical tolerance.

Keep TECHNICAL, proxy VISUAL, PERFORMANCE and HUMAN acceptance separate. Stills
and attachment metrics do not establish continuous motion or choreography quality.
No global install, main merge, release, source mutation, sculpting, new provider,
GPU model or paid call is part of this fix.

## Boundaries

These are overlapping segmented links/markers, not a watertight clay human.
Blended links may shear or self-intersect; girth and endpoint markers are diagnostic
display choices, not measured anatomy. The attachment gate does not certify skin
quality, body volume, floor contact, or human-performance realism. Only explicit
anatomical roles are shown; unknown anatomy is omitted/reported, not inferred.

Blender's documented vertex-group binding behavior is the implementation basis:
https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/armature.html
