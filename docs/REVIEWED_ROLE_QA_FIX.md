# Reviewed roles survive transfer QA

A character whose bone names are not recognized can have a valid explicit
transfer-plan mapping. Previously execution discarded that semantic review:
post-transfer `rig_report` repeated name inference, returned no anatomical
height, and `quality` raised a Python TypeError before publishing the result.

The worker now passes semantic roles from the exact checked proposal into
retarget preflight, rig reports, evaluated sampling and final QA. The existing
world, skeleton, action and immutable proposal binding checks run first. There
is no new public role override or approval bypass. Source/target bone names,
rest data and asset metadata are not rewritten. Result evidence records the
roles and height actually used for QA.

Unreviewed targets lacking measurable QA anatomy fail before action creation
with `MAPPING_REVIEW_REQUIRED`. Invalid quality height/FPS inputs produce the
structured `INVALID_SCALE` error instead of a TypeError.

Validation:

- `tools/run_checks.py --offline` covers units and isolated installer checks.
- Run the normal `tools/transfer_planning_fixture.py` in background Blender.
- Repeat in fresh disposable outputs/library with an additional `custom`
  argument. This renames target joints to opaque identifiers, verifies automatic
  anatomy is unavailable, proposes explicit roles, executes the approved job,
  and independently checks evaluated QA coordinates after reopening. It also
  checks missing/duplicate role rejection, unchanged skin/rest/actions, stale
  binding rejection and fractional final-key coverage.

The local real-character retry completed with the same 50 mapped joints and
unchanged source/target proposal values. The existing mesh/weights, rest rig and
21 old actions were unchanged; one new 30 FPS action covers frames 1–32.
Private assets and detailed acceptance evidence remain outside the repository.

Scope: this repairs reviewed-transfer QA. It does not establish artistic motion
quality, universal rig compatibility or a general persistent semantic-tagging
workflow for unrelated later operations. Standalone QA on a rig with no stored
semantic metadata still needs its own reviewed semantic context.
