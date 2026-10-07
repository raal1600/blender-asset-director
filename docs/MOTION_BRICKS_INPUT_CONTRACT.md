# Transition input and provenance contract (in development)

`motion_bricks_contract.py` owns `motion-bricks.upright-grounded.v1` numerical
restrictions and `asset-director.transition-input.v1`. `motion_bricks_timeline`
emits one request ID with a dependency fingerprint, distinct from its low-level
`asset-director.motion-bricks.request.v1` C ABI payload. Names label observed
Action/slot and anatomical bindings; they do not select direction or motion.

Current dependencies include actual source channel content, selected clip and
interval, source-frame rate, four exact sample timestamps per side, evaluated
model contexts, native-basis/rest/mapping hashes, object linear and parent
transforms, unit scale, source preparation/contact properties, requested timing,
sampling settings, provider configuration and pinned source/GGML/model revisions.
Project/checkpoint identity is additionally bound by the existing job input hash
and launcher transaction. `transition-review.mjs` separately binds accepted,
working and candidate checkpoints. Atomic acceptance rechecks the request,
runtime, source checkpoint and every candidate artifact hash. Complete native
acceptance/recovery journeys remain a separate runtime evidence gate.

Each boundary covers 0.1 seconds (four samples at 30 FPS). Sampling cannot wrap,
extrapolate or reach outside the selected single native interval. Repeated cycles
must first be split explicitly for this domain. Output N=24,28,…,64 includes both
contexts; bridge indices are 3…N−4 and duration is (N−7)/30 seconds. Only this
bridge may retime within 0.85–1.15. Actual supported duration range is
0.481666…–2.185 seconds. Source clocks are not altered to satisfy it.

`argmax` is the backward-compatible mode and ignores seed for sampling.
`gumbel-temperature-1` sets the real ABI argmax flag false. It has no configurable
temperature. All settings are retained. Real repeated-seed experiments justify
the bounded alternatives control for this backend; they do not establish quality.
Final corrected diversity must be rerun after cleanup changes.

Sparse masks remain GLOBAL_ROOT 11110000, LOCAL_ROOT 11101111, POSE 11111111,
applied after both boundary setters. Destination XY is predicted; heading and
height remain conditioned by native motion. Target-position placeholders are
not target locks. All constraints are soft model conditioning.

Per join the existing job folder retains `motion-bricks-<clip>-input.json`,
`-raw.json`, `-retargeted.json`, `-corrected.json` and the combined provenance
receipt. Raw output is saved before correction so a failed retarget does not erase
the prediction. Corrected samples include their original scene-frame timestamps
and a single composed object delta path. Head/finger/toe endpoint interpolation
is deterministic bridge processing.

Raw duplicate comparison uses common-time interior root RMS normalized by fixed
reviewed height and quaternion-geodesic RMS (in degrees), ignoring filenames,
metadata and quaternion sign. Both ≤0.0001H and ≤0.1° means near duplicate.
Different durations remain distinct timebases; playback must not time-warp them.
This is candidate distinction, not a quality or physical-validity test.

The worker refuses to load the model when `bpy` is present. On Windows it queries
the loaded module path with GetModuleFileNameW and hashes the actual DLL; the
parent compares it with the verified installation. Each model file is size/hash
checked before loading. Provider events and separate native inference, request
conversion, output conversion and loading durations distinguish model compute
from application latency. This is sampled resource monitoring, not an allocator
cap or proof against unrelated whole-device interference.

Generated joins optionally carry `contacts` with `origin: user-reviewed` and
`source`/`target` records `{support, seconds}`. Support is auto, left, right,
both, or none; intervals are 0.04–0.20 seconds, additionally bounded by bridge
duration. Auto means the evaluated proposal, not ground truth. Selected explicit
feet must pass native-context support checks before model loading. The plan is
included in the dependency fingerprint and correction provenance. It drives
bridge-only positional/orientation support processing, not backend conditioning.

Clips optionally carry `root_intent: stationary-reviewed`. This is valid only
for evaluated stationary root travel and does not remove native root curves.
Changing the selected Action clears this intent and its contact correction
metadata. Missing intent on ambiguous in-place motion produces an actionable
preparation refusal. Direction is never derived from an Action label.

Seam reporting uses cubic one-sided extrapolation from four samples at h,2h,3h,
4h from the shared boundary, with h=1/1536 second. Derivatives are per second;
both angular estimates use quaternion logs in the same near-left reference
frame. The retained convergence experiment documents why the former three-point
estimate over-reported velocity differences on high-curvature baked segments.
This does not excuse excessive acceleration or establish physical feasibility.

Candidates also retain `applicationIdentity`: the isolated installation's source
commit, whether clean HEAD was checked when it was created, the content-manifest
hash, source-file count and actual native-host hash. Runtime verification hashes
the copied source files. Acceptance refuses an absent/unverified or changed build
identity even if the Python implementation hash happens to remain unchanged.
Source provenance does not claim GUI, motion-quality or human approval.

`workbench-job-trace-v1` links the launcher request to its native job receipt;
`blender-job-trace-v1` records process-local stages, while each transition retains
provider loading/inference timings. Wall-clock startup estimates are explicitly
labeled and are not confused with monotonic stage duration. Pre-bake raw-retargeted
and corrected world-space kinematics use identical timestamps; baked validation
is separate and denser. Missing stage contact measurements remain unavailable.

Each generated Action operation now carries `generation_attempt`, the validated
UUID request ID. It belongs to the durable job specification, not the motion
dependency fingerprint. Repeating unchanged inputs therefore creates a fresh
isolated native attempt; it neither reuses a failed job nor rewrites its files.
Resubmitting the same attempt remains idempotent. Ordinary native clip operations
retain their existing job identity policy.

Corrected artifacts include `motion-bricks.comparison.v1`: the fixed reviewed
height, physical duration, raw model rotations/root positions converted to
metres, and corrected evaluated world rotations/root positions before baking.
Publication verifies artifact hashes before comparing candidates with the same
dependency fingerprint. Near duplicates require both interior rotation RMS
at most 0.1 degrees and root RMS at most 0.0001 of reviewed height. Quaternion
sign and metadata are irrelevant. Raw and corrected differences are reported
separately so correction-erased diversity is visible. Different durations are
reported separately without time warping. This is not a baked quality pass.

Straight rest elbows have no observable bend plane. Anatomical profile v2 can
now retain `motion-bricks.hinge-calibration.v1` evidence proposed by
`tools/inspect_motion_bricks_hinges.py` from an explicitly selected Action/slot
and interval. Each side needs 8–128 non-singular measured bends (10–165 degrees),
with signed rest-space normals agreeing within 5 degrees. The proposal starts
unreviewed. `prepare_motion_bricks_rig.py --hinge-calibration` requires a separate
reviewed record, matching rest/mapping identities, and planes perpendicular to
the actual rest arm segments. Non-singular rest geometry must also agree.
The evidence retains source content, slot, FPS and exact sample frames and is
included in the profile/dependency hash. It does not alter rest geometry or
native curves. This is rig calibration, not animation-name logic or a quality
exception. No client calibration editor or automatic approval is implied.

The per-context encode/decode guard measures position in world metres: less
than 0.00001 m, with orientation less than 0.05 degrees. Rig-unit error is also
retained as a diagnostic, but is not compared to a metre threshold. This matters
for supported positive uniform scale, including imported centimetre rigs at
object scale 0.01. No seam, quality or correction threshold changes with scale.

The real sequence fixture accepts an explicit `source_ranges` array, one
native-frame interval per clip. Omission means the complete native interval.
Selections are checked against the observed Action ranges and recorded in
`RESULTS.json`; the runner never searches for a different boundary. An explicit
short-context case must be refused rather than sampling beyond its selection.
