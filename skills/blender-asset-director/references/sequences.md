# Reviewed full-clip animation sequences

Use for joining two to four distinct reviewed retarget results on the SAME existing
character. Read the repository's docs/REVIEWED_SEQUENCES.md and current session
handoff. Do not replace a working character, merge meshes or retarget mixed source
rigs together. Keep each source's identity and the target's independent provenance.

1. Verify completed reviewed retarget JOB IDs, output hashes, native ranges/FPS,
   owner/slot, QA roles, units, target rest/world and license grants. Old completed
   jobs are reusable data, not jobs to rerun under changed code. Generic Mixamo
   action names and filenames are not identity or performance evidence.
2. For long new takes, transfer-plan accepts explicit max_output_intervals; default
   360 stays. Inspect work before increasing it, preserve native seconds and the
   full range, and respect retained key/mesh/deadline caps. No quiet crop/speed-up.
3. sequence-plan is read-only and takes a saved target, clip job IDs, fps, units,
   joins, full budget and contact calibration/null. Choose duration_seconds,
   yaw_degrees, placement match_endpoint/continue_velocity and subdivisions from
   observed target-space endpoint evidence. There are no scene/provider presets.
4. Review the returned sq_ proposal, alignment, endpoint poses, velocity mismatch,
   semantic context and work. sequence-prepare --review binds actual plan_job_id,
   plan_id, named host reviewer, offset-aware time and approved=true. Do not forge
   human approval. Changed fields/inputs/code require another exact plan/review.
5. Execute the prepared sequence job. It creates derived aligned and bridge Actions
   in a new file while preserving originals, rig/skin/rest/display and lineage.
   This is full A + extra pose/velocity-aware bridge + full B, not hidden overlap.
   One existing target pose anchor owns travel; never add a second root owner.
6. sequence-check uses the exact result and sequence_job_id before presentation
   derivatives. Inspect endpoint/native timing, stored-frame rounding, seam motion,
   and integer/subframe contact. No foot locking or full IK is supplied; glide
   candidates require interpretation. Contact null is unmeasured, not PASS.
7. Reuse or create a separate bounded presentation copy. Respect the session's
   render budget. Use bone-display audit for actual widgets and retain references.
   Present only in a correctly bound review window using available host control;
   do not overwrite unsaved windows, change preferences/ports or add services.

Connected anchors whose location is ignored, unsupported channels/constraints,
changed fingerprints, missing roles, near-pi joint differences and exceeded budgets
must stay explicit blockers. Never flatten source channels or alter a rig merely
for a pass. The bridge is an offline quintic/log-quaternion approximation, not a
full inertialization system, physically plausible choreography or contact guarantee.

Keep TECHNICAL, CONTINUITY, PERFORMANCE and HUMAN separate. Still frames and CI
cannot certify continuous motion. Preserve the original input as rollback; there
is no automatic sequence-revert or live playback controller in this milestone.
