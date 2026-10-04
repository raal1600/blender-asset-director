# Lightweight native-clip stitching — development

No model, inference service, training data, downloaded dependency or animation-name
classifier is used. Codex can plan and inspect; bounded Blender operations execute
and verify. This does not reproduce a learned generative motion model.

The first supported scope is same-performer native transform animation with
compatible channel ownership. Original Actions, chosen clip durations, World
placement, skin/rest data and previous checkpoints remain intact. Explicit added
transition frames connect clips; they are not hidden crossfades or source trims.
Unsupported native root travel, constraints or ambiguous ownership require the
existing reviewed/manual workflow, not a second movement controller.

## User flow

In Action, append an observed take to the selected performer's motion timeline.
When both clips have inspected, matching transform ownership, **Smooth connection**
starts enabled with a quarter-second suggestion (six added frames at 24 fps).
This is an editable starting value, not a detected optimal transition length.
An amber connection occupies its own timeline space. Timing and path exposes
2–120 added frames, and turning Smooth connection off restores a hard cut.

Changing a distance, transition length or earlier clip ripples connected following
clips. Independent clips keep the existing explicit ripple operation. Undo and
Discard remain local; Save creates a separate checkpoint and rebuilds the actual
combined preview. Saving is not performance approval. Old saved timelines without
connections retain their previous behavior and are not rewritten just for display.

The clip's metre distance remains its own distance. A velocity-preserving bridge
can carry additional movement between clips; that extra distance is displayed.
The red path starts from the preceding clips **and** their connection displacements.
Facing stays unchanged. A direction reversal sharper than 135 degrees requests an
intermediate turn/stop clip or Blender review instead of inventing a turn.

## Native execution

`action-timeline-v1` gains an optional clip member:

```json
"transition": {"frames": 6, "match_phase": true}
```

Absent/null means the original hard cut. The first clip cannot have a connection.
The next start must equal the previous inclusive end + 1 + the added frames.
For example, 1–25, connection 26–31, next clip 32–56 preserves both 25-frame clips.
The mathematical bridge spans native endpoint 25 to start 32 (seven intervals).
A fractional native endpoint is retained even when its occupied frame is rounded.
The matching `native-stitch-v1` inspection is required by UI, API and native worker.
Source, action/slot, channel coverage, implementation and checkpoint identities
remain bound to the existing inspected request. Foreign/stale inputs refuse.

The worker samples native transform channels on a disposable, unskinned copy and
restores the original frame/state. It requires matching animated owners/channels,
supported rotation modes, positive scale and static unconstrained ancestry.
It preserves original Actions and creates separate connection Actions, retaining
Euler, quaternion or axis-angle ownership. No bone names imply human roles.

A quintic bridge matches sampled endpoint poses and velocities. Rotations use the
existing SO(3) endpoint bridge, refusing near-180-degree ambiguity. Quarter-frame
keys are a bounded approximation between measured endpoints, not a dynamics solve.
Maximums are 4,096 sampled poses per performer, 256 bones, 200,000 connection keys
per performer and 500,000 existing/generated scalar keys across the saved scene.

When phase matching is requested **and** the user has reviewed the take as a loop,
32 observed phases are compared using pose and velocity difference at the beginning
of the connection. The incoming cycle advances through the added time instead of
returning to that identical pose at the connection's end. Numerical cycle closure
is additionally required. Otherwise the original opening is retained;
the harness never creates loop approval. Phase-shifted clips use at most three NLA
pieces referencing the original Action, preserving selected total duration. The
saved connection records its matched start phase, actual incoming phase,
before/after start-match costs and method. Lower matching cost is not a claim
of lower foot sliding or better human-rated movement.

The existing delta-location path remains the only added travel owner. A short
quintic connector matches both adjacent world-space velocities through the extra
time. Native root travel is not cancelled, relocated or given a second controller.
Stride calibration is unchanged: reliable observed pace is automatic; ambiguous
pace still needs explicit calibration or a native clip without added travel.

## Verification and acceptance

### Correctable paths and compact clip controls

The Action editor keeps the saved-scene viewer and timeline together, beside a
compact selected-clip inspector on wide screens. Narrow layouts put the viewer
before the inspector. Required manual calibration remains visible; advanced
timing and clip operations stay collapsed until requested or a field there needs
correction. Changing a checkbox preserves an explicitly opened timing panel.

A missing calibration or refused connection must not hide the red correction
handle. Its provisional origin includes known preceding path/bridge displacement
but omits any unresolved connection displacement, visibly labelled as pending.
This is draft geometry, not an executable or approved motion prediction. Save
still requires valid pace, timing, connection and source evidence. Resizing the
viewer reprojects the keyboard/pointer handle with the 3D endpoint.

The isolated browser journey covers missing pace, pointer/keyboard corrections,
refusal without mutation jobs, responsive placement, calibration, actual Blender
Save and saved playback. Screenshots and real-image inspection are separate from
assertion results; a passing DOM test alone does not certify the visual layout.

### Required evidence

Portable Python and launcher tests cover the contract, bounds, explicit added
distance, source-independent pose math, connected ripple/undo, native-channel
preflight and old-timeline compatibility. Generated-only native coverage is in
`tools/motion_stitch_fixture.py`: actual Blender sampling, source/channel refusal,
phase selection, original action/rest/skin preservation, scaled parent and scene
units, save/reopen, Euler/quaternion/axis-angle ownership and separate revisions.
`tools/motion_stitch_glb_check.mjs` independently compares saved exported geometry
at scene-frame endpoints and inside a connection. The existing preview exporter
samples whole frames; between-frame differences are separately recorded, not
claimed as exact native subframe agreement. Blender remains the detailed surface.

`tools/motion_stitch_browser_check.mjs` exercises the authenticated browser, real
Blender Save, added time/distance, refusal, Undo, connected ripple, reload and saved
GLB playback in an isolated generated studio. It does not use a user's projects
or answer a human approval request. The existing hard-cut/ripple and automatic
pace browser journeys remain separate regressions.

The native fixture is required in the existing motion/version matrix; the browser
and GLB checks join the existing embedded-viewer suite. No workflow/evidence
partition is renamed or made optional. These are test definitions, not a claim
that the current commit's remote checks have run.

Exact-commit public/private CI, packaging, staging, reversible installation and
licensed-character temporal/contact review remain separate acceptance gates.
This development contract does not authorize or certify a live runtime update.

Technical endpoint agreement and sampled support diagnostics do not establish
natural movement or continuous contact. No IK, collision/terrain solver, arbitrary
rig retargeter or procedural replacement gait is introduced. Original clips remain
available when a connection requires an intermediate motion or Blender adjustment.
