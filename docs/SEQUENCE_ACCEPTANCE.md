# Reviewed sequences: executed repository acceptance

Runtime: `0.6.0-dev.4`.
Branch: `feature/reviewed-sequence-integration-20260915`.
Tested code: `cc92cd557933b68d06826922b30d7c399db54357`.
Actions: https://github.com/raal1600/blender-asset-director/actions/runs/34923625714

All ten jobs completed successfully. This record and accompanying documentation/
skill-routing changes follow that tested code; they do not change runtime Python,
fixtures or workflows. No merge, release or workstation installation was performed.

## Executed gates

| Gate | Result |
| --- | --- |
| Unit/policy + isolated installation, Ubuntu Python 3.11 | PASS |
| Unit/policy + isolated installation, Ubuntu Python 3.13 | PASS |
| Unit/policy + isolated installation, Windows Python 3.11 | PASS |
| Windows PowerShell 5.1 and 7 bootstrap | PASS |
| Ubuntu/macOS shell bootstrap | PASS |
| Full Blender fixtures, 4.5.3 / 5.0.0 / 5.2.1 | PASS |
| Existing live free-provider/source-motion check, Blender 5.0.0 | PASS |
| Private Moonwalk/Thriller/Adventurer and live windows | NOT RUN |

Platform-specific skips remain described in individual logs. A passing job is not
proof that a skipped test ran. All automated development testing in this iteration
ran in GitHub Actions; the editing container was used for source/evidence reading
and isolated text editing only. No local Blender or unittest execution.

The matrix now invokes the previously missing custom-role transfer variant and
bone-display fixture, plus physical-translation precision, FBX connection/travel,
and the full long-take sequence workflow. Existing tests were not removed.

## Concrete Blender 5.2.1 evidence

Downloaded `blender-5.2.1-evidence`, artifact `10378629631`.
Archive SHA256:
`3365f02610d0660b990cc7135d225aa80682d9c33b1aef6f2a48fb76d05c7572`.
The inspected archive includes sequence_report.json, fbx_anchor_report.json and
other bounded diagnostic reports; no private assets.

Eight sequence gate groups passed. The generated source clips have different
bytes but the same generic Mixamo-style action label. Source A travels 0.920000017 m;
source B travels 0.349999994 m after its centimetre-to-metre conversion. These are
independently checked after actual FBX import, not assumed from authored keys.

The full B take contains 1113 source frames at 30 FPS: 1112/30 = 37.0666666667 seconds.
A reviewed 24 FPS target bake retains the intended last key at 890.6, represented
as 890.5999755859375 in Blender storage, with scene endpoint 891. It is then sequenced
at 30 FPS without source-speed change, cropping or dropping the opening of B.

The target has opaque custom bone names, a stationary control root, moving hips,
a translated/rotated object, different proportions, finger channels and an existing
action/display setup. All 52 reviewed role mappings survive into sequence QA.
The plan exposes a naive unaligned anchor gap of 1.085600080 m. The test uses an
explicit 0.413-second extra bridge and 25-degree yaw; these are fixture choices,
not runtime defaults or recommendations for the real scene.

Measured after saving/reopening:

- Full-clip poses compared at twelve selected matched-time positions, including
  both endpoints: maximum world-position error 1.018524616e-6 m; maximum quaternion
  one-minus-absolute-dot error 1.192092896e-7. Rotation error is dimensionless.
- Bridge entry frame 32: endpoint error 3.371747881e-7 m.
- Bridge exit frame 44.39: endpoint error 6.336060651e-7 m.
- Finite anchor velocity changes across +/-1/32-frame probes: approximately
  0.0002861023 and 0.0000572205 m/s. These are finite probes, not a proof of C1
  continuity everywhere or preservation of source acceleration.
- Maximum joint angular-velocity changes at those probes: approximately
  0.00046044 and 0.00030245 rad/s.
- Contact states include GLIDE_CANDIDATE and UNKNOWN_INITIAL_SAMPLE. No foot lock
  or contact repair was applied. The fixture is not an anatomical dance capture.
- Alternative match_endpoint placement with -15-degree yaw and a 0.35-second
  bridge also passed evaluated endpoint checks.
- Source files, target mesh/weights/rest, old action curves and display settings
  remained unchanged. Repeated execution reused the completed job with unchanged
  outputs; revoking the shared synthetic source review blocked subsequent reuse.

The progress JSON deliberately says INCOMPLETE after each intermediate gate;
sequence_report.json is the final result. Do not treat a progress receipt alone
as success. No continuous visual viewing or artistic verdict was performed here.

## Defects found and fixed

### Physical units in source translation checks

The first sequence fixture failed source planning because the old 1e-5 local-unit
threshold applied a hundred-times tighter physical tolerance to centimetre FBXs.
A dedicated actual-export probe measured about 0.15 micrometres of numerical noise.
`968d4bb` applies the same fixed 10-micrometre/component physical budget using the
reviewed source conversion and fixed uniform world scale. It records the policy
and measured span. Source channels are not normalized or flattened. Independent
fixtures verify that a genuine 1 mm extra-bone translation is rejected by BOTH
planning and execution in metre and centimetre units.

### Fractional frame storage

The intended endpoint 890.6 is not exactly representable in Blender's binary32
frame fields. `d3b1e59` checks the exact stored representation, records the error,
and accounts for NLA arithmetic rounding without changing FPS. It also uses
forward holds plus later full-channel REPLACE ownership so microscopic rounding
gaps cannot expose a rest frame. Unit regressions reject even a one-storage-step
changed action endpoint; this is not a blanket relaxed time tolerance.

### Source keys did not imply evaluated travel

The first naive-gap assertion found zero travel. Diagnostics compared indexing,
saved retarget playback and planner sampling: all agreed. A pre-export oracle then
proved the authored source DID travel, but FBX reimport lost that travel.

The official importer reconstructs a tail and can auto-connect a child whose head
coincides with it. Our old synthetic vertical root produced connected hips; Blender
then ignored the hips' location keys. `44f8b25` adds a structured refusal for a
connected source anchor with meaningful location variation. It does not edit the
source or disconnect a production bone. The positive synthetic fixture now has
a horizontal floor-control root; the original collinear case remains a negative
round-trip test. `cc92cd5` applies the same source-fixture correction and an
independent imported-travel check to the older transfer fixture.

Actual negative/positive round-trip measurements in Blender 5.2.1:

| Source | Keyed translation span | Evaluated travel | Result |
| --- | ---: | ---: | --- |
| Collinear root; hips auto-connected | 0.920000017 | 0 | Explicit refusal |
| Horizontal root; hips unconnected | 0.920000017 | 0.920000012 | Accepted |

The source bytes and action curves remained unchanged in both checks. The earlier
attempt to set the fixture's authoring time alone did not solve the importer issue;
that failed attempt/evidence was not reclassified as success.

Primary importer reference:
https://github.com/blender/blender/blob/v5.0.0/scripts/addons_core/io_scene_fbx/import_fbx.py

## Scope and handoff

Repository TECHNICAL: PASS for the executed supported cases.
Local complete Moonwalk -> Thriller on Adventurer: NOT RUN.
PERFORMANCE: PENDING. HUMAN: NOT ESTABLISHED for this sequence implementation.

Use docs/SEQUENCE_LOCAL_ACCEPTANCE.md. Record Thriller's own file-specific reviewed
permission; the user attested official Mixamo acquisition but that is not an
existing blanket grant. Reuse authorized/indexed motion and the existing Adventurer.
No new mannequin, source download, rig replacement or arbitrary-code endpoint.

The method is a reviewed planar alignment plus a reversible exact-endpoint
quintic/log-quaternion bridge, not full inertialization or contact-aware IK.
The two-clip workflow was exercised with both placement modes. More complicated
multi-clip choreography, hard turns, physical support, collision extrema, distinct
mixed-license combinations and natural human dance remain separate acceptance
cases. Full B timing is represented; its appearance still needs local playback.

Old unexplained shared configuration/recent-files differences remain unresolved.
No attribution, restoration or retroactive preservation claim was made.
