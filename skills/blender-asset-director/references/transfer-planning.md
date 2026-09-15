# Reviewed transfer planning (development)

Load for indexed motion -> existing skinned character. Preserve source motion and
target character provenance separately. The local-folder/license/native-clip paths
already exist; do not rebuild them or introduce a new mannequin unnecessarily.

1. Inspect a saved target COPY and an eligible indexed clip, including owner,
   action/slot/range/FPS, rig, units and license state. Preserve originals.
2. `job-prepare transfer-plan` takes the target copy and indexed asset ID, with
   target_object, source_meters_per_unit, target_meters_per_unit, target_fps,
   root_mode and facing. Optional reviewed roles must name real bones. Numbered
   torso/finger names are only proposals until actual hierarchy is checked.
3. Run the read-only job and inspect result.json. It contains REVIEW_REQUIRED,
   an exact proposal ID, mapping, fingerprint/world/action binding, units, body
   ratios, facing evidence, target translation anchor and reference matrices.
   Do not insert a previous scene's 180-degree yaw, ratio, names or repair cap.
   Terminal axes/antiparallel or ambiguous directions require review.
4. Use `transfer-prepare --review FILE` only after host review. The review needs
   actual plan_job_id, plan_id, reviewer, offset-aware reviewed_at and approved=true.
   Never invent user approval. Changed values or inputs require a new proposal.
5. Run the returned retarget job to a new result. Preserve source files, existing
   mesh/skin/rest proportions, original actions, license restrictions and failures.
   The translation anchor names a mapped TARGET bone, not a source alias.
6. For contact evidence, use read-only `contact-check` with target_object, mesh,
   feet.left/right group lists, ground_z, meters_per_unit, tolerance_m,
   near_ground_m, glide_speed_m_s, and frames OR sample. Fractional frames allowed;
   integer and subframe extrema are separate. No subframe evidence means unknown.
7. Diagnose before proposing repair. GLIDE_CANDIDATE is not an error or authority
   to lock a foot. Above ground is not proof of a jump or unwanted floating.
   Keep the initial result and measured failure, then use only a separately
   justified bounded vertical correction and compare the corrected result.

Planning needs fixed positive uniform object transforms and supported unconstrained
chains. Minimal anatomical swing/nearest-rest twist is not full IK or universal
human fitting. Review the proposal instead of writing task-local alignment scripts
or treating generated matrices as unquestionable.

camera-check requires camera and subjects; frames and sample are exclusive.
The portable validators reject malformed requests before Blender or job creation.

No safe multi-window UI controller is provided in this milestone. Use only actual
approved host tools with explicit process/window/file binding. Never switch an
unrelated unsaved scene, add a command watcher/service, or save preferences to
make playback convenient. A floor-level root is an existing control, not stray
mesh; filtering its display must not delete it. Restore your own display changes.

Keep TECHNICAL, PERFORMANCE and HUMAN separate. Stills, numeric checks and frame
advancement are not continuous-viewing evidence. Bind real feedback to an output
hash/viewing scope and preserve historical PENDING/preservation-failure records.
Local handoff budget: at most 8 CPU stills at 640x360/16 samples, not a full-video
render. Realistic skin, choreography, GPU reconstruction and full IK stay out of
scope. Full contract: docs/REVIEWED_TRANSFER_PLANNING.md in the source repository.
