# Offline transition review

The working request and accepted scene are independent. Generate creates a
reviewable candidate; only explicit acceptance replaces the complete accepted
timeline. Failure, cancellation and pending generation preserve its checkpoint.
The tested native workflows and exact revisions are in
[the research handoff](MOTION_BRICKS_RESEARCH_HANDOFF.md); historical failures are
retained in [the capability audit](MOTION_BRICKS_CAPABILITY_AUDIT.md).

## Normal workflow

1. Select the intended performer, native clips and explicit intervals in Action.
   Generated mode preserves those intervals and their clocks. An interruption is
   a new request with an explicit trim, not a hidden shortening of either clip.
2. Complete reviewed mapping/rest/root preparation if needed. A stationary root
   does not establish intended travel. The root-intent selector permits reviewed
   stationary intent only when evaluated root travel is stationary; it cannot
   erase native curves. Travelling in-place motion requires reviewed derived
   preparation. Import its copied checkpoint from More, inspect the unaccepted
   preview, then choose Keep & continue building or Reject prepared checkpoint.
   Keeping preparation does not accept a generated transition or approve Action.
3. Select a generated connection and its duration, then Generate candidate or
   Generate alternatives (3). Alternatives use verified fixed-temperature Gumbel
   samples with seeds 1234, 7 and 42. Argmax seed changes are not alternatives.
   Model lengths and generated-only retiming limit the offered timing; invalid
   durations are refused. No native clip is retimed to make the bridge fit.
4. Inspect the validation result and compare candidates. Quality review order
   includes only current, verified, nonduplicate candidates with all joins passing
   all hard gates. It averages normalized per-join error scores; tied scores share
   a rank. Failed, missing, stale, incomplete and unknown-preset evidence is
   unranked. Ranking is a review aid, not naturalness or physical certification.
5. Refine contacts or try a supported duration/sample and regenerate. The contact
   panel records reviewed left/right/both support and interval durations. Source
   support begins at its stitch inside the bridge; target support ends at its
   stitch. Extensions are 0.04–0.20 seconds with room required inside the bridge.
   No support extension disables that side's extension. Evaluated native support
   must still qualify: a correction cannot declare an airborne foot planted.
6. Explicitly accept a hard-valid current candidate. Dependency and file hashes
   are rechecked before atomic acceptance. A whole consistent checkpoint is
   accepted, including all affected downstream joins. No downstream result is
   silently accepted. Accepted history / restore selects exact prior artifacts.
7. Save/reopen and render the accepted scene. Candidate previews are labeled
   unaccepted; normal rendering uses the accepted checkpoint. Preview and render
   identities are hash-bound to the same baked source.

## What refinement actually changes

Contact editing changes deterministic bridge foot/toe orientation, IK, release
and bounded smoothing. It is not a contact-label input to the neural model. In
the actual native refinement test, 0.16 → 0.08 second support windows reduced
seed42 drift from 31.09 to 5.68 mm while leaving the neural request and raw arrays
exactly equal. Original Actions remain intact. Correction magnitude, acceleration,
penetration and planted support still have to pass fixed quality limits.

Comparison uses one physical clock aligned at the selected source stitch. Choose
which join to review, scrub either stitch or play both at full speed. Each view
labels its bridge duration, target-stitch time and baked artifact. Different
durations are not time-warped. A missing join is labeled absent and synchronized
playback is disabled; the first join is not silently substituted.

Native root travel uses explicit timeline composition placement, with no second
manual travel path. Generated heading overrides, arbitrary target locks,
waypoints, pose editing, subinterval regeneration, text prompts, precision knobs
and decorative sliding sliders are not offered. A full graphical root-preparation
editor is not implemented; reviewed preparation tools plus checkpoint import are
the supported workflow. Optional viewing overlays must not change baked motion.

## Working states and recovery

Needs preparation and actionable refusal messages identify missing mapping,
ambiguous root intent, unavailable context, unsupported transforms or contact
boundaries. Ready, queued/generating, validating, ready for review, failed quality,
failed execution, cancelled, stale and accepted states retain distinct meanings.
Validation progress comes from the owned job, including fresh Blender reopening.
Detailed provider settings, provenance and metrics are expandable.

Changing a relevant input makes older candidates stale; merely selecting a clip
does not. A batch stops scheduling more seeds when its request becomes stale.
An early-join edit identifies downstream labels and target frames affected by
timing/placement. The previous complete accepted revision remains usable while
the replacement is pending. A new candidate never overwrites a newer request.

Cancellation reaches the owned job/process lifecycle. Restart checks ownership,
quarantines interrupted unpublished outputs and retains accepted revisions plus
valid candidates. Corrupt candidate artifacts cannot be accepted. Repeating the
same acceptance event is idempotent; a distinct repeated event is refused.
Discard clears the working draft after cancellation; it does not delete the
accepted scene. The native exit safeguard may wait for active preview work;
finish that operation and refresh status rather than force-closing unrelated work.

Real Windows evidence: final alternatives/ranking/acceptance/render at 5d4a7ba;
contact refinement and stale/cancel/provider-crash/restart at 5f1b8b8; native
multi-join comparison and exact restoration at 2cd8ed9. The final motion and
persistence code trees match 5f1b8b8 exactly. These are finite reviewed fixtures,
not a guarantee that every candidate passes or every humanoid generalizes.
