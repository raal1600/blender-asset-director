# Offline transition review — implementation in progress

Latest reference evidence identifies application
`95234c3528bfd1c288f6670ca701c4789b0a1aff`, host SHA-256
`36a88e1ccb36492db9699a1b95b25eddcf0632fb6245478a307f223ac9f90872`.
`native-accept-95234c3/report.json` records three real candidates (two quality
passes), source-aligned comparison, explicit acceptance, exact prior-artifact
restore, restoration of the selected candidate, fresh native restart and the
same preview identity. It reached real OptiX rendering but its playback click
hit the seek rail. The retained movie was then reopened and played at rate 1
through both stitches in `native-playback-95234c3-r2/report.json`.
Fresh Blender/actual GLB parity measured maximum skin error 0.01183 mm and joint
orientation error 0.14951 degrees across every rendered integer frame and
fractional boundary samples. All 72 rendered frames were inspected separately;
human artistic approval is not claimed. Contact refinement and multi-join
reconciliation journeys remain unfinished.

Earlier native evidence identifies application
`b23e76d1e4e75f1ace63ffed8dcb058846551b8d` and host SHA-256
`b21023549902980bbd961a6b2672ec066857fd88c5974f3e087b658d0d8dbd89`.
`native-review-b23e76d/report.json` retains three real candidates, two framed
source-aligned baked previews, numerical raw/corrected diversity, input-change
staleness, and active cancellation in 0.554 seconds. Its later fault-injection
step failed a harness timing assertion. The separate corrected native procedure
`native-faults-b23e76d-r3/report.json` passed actual provider crash and restart
during generation: prior candidates and the accepted checkpoint survived, while
unpublished interrupted output was quarantined. All generated candidates failed
the fixed quality gate. Acceptance, restore, final rendering and naturalness
are not established by these tests.

The preceding `7fc75d2` native startup failed because a packaged helper was not
served; `c401b33` fixes the allowlist and tests the transitive HTTP module graph.
The first `c401b33` procedure asserted editability during transient request
admission. Its corrected procedure waits for editability while still requiring
a running native job; no application editability gate was weakened.

The accepted checkpoint and the working transition request are separate. Generate creates immutable candidate checkpoints. Acceptance verifies the current request fingerprint, runtime implementation, source checkpoint, candidate and evidence hashes, and hard quality report before atomically publishing the complete timeline. A failed candidate is inspectable but cannot be accepted. Snapshot refresh checks only existing cached edits, so acceptance/restore cannot reconstruct a discarded old working request.

Select a generated connection, set its duration, generate, inspect the candidate, refine, compare, and explicitly accept. “Generate alternatives (3)” uses the pinned ABI's Gumbel sampler at fixed temperature 1, with seeds 1234, 7 and 42. Argmax seed changes are not alternatives. The tested raw and corrected diversity evidence is described in the capability audit. Saved generated timelines also offer explicit regeneration with unchanged settings; repeated output is subject to duplicate detection. The review panel refreshes after contact edits without replacing the scene viewer.

Comparison uses one physical clock aligned at the source stitch. Duration and target-stitch time are displayed independently. No time warping is applied. Each view resolves its identified baked checkpoint. Normal scene preview and rendering resolve the accepted checkpoint. Candidate views are labeled separately and do not grant acceptance.

The foot-contact refinement panel records a user-reviewed source and target support selection and interval duration. A source interval begins at its stitch; a target interval ends at its stitch. Durations are bounded to 0.04–0.20 seconds and must leave sufficient bridge time. Left/right/both selections must be supported by evaluated native contexts; they cannot override an airborne foot into a planted one. “No support extension” disables that boundary extension. The mechanism is deterministic foot/toe orientation and positional IK with bounded release, filtering, and correction measurements. It is not a contact-label input to the neural backend. Regeneration is required. Final contact/quality checks remain authoritative.

Reviewed stationary root intent resolves an in-place ambiguity only when evaluated root travel is stationary. It does not erase moving root curves. Travelling in-place clips require a reviewed derived root preparation. `tools/prepare_root_contact_paths.py` creates separate derived Actions; preparation requires observed landmarks and intervals. Clip names are labels and do not supply direction. A complete client preparation editor is not yet implemented.

Changing motion, trim, duration, contacts, sampling plan or other request dependencies makes older candidates stale. Selecting a clip alone does not. The batch stops scheduling further seeds after a dependency edit. Discard clears the working request while preserving accepted and candidate artifacts. Prior accepted artifacts can be restored without regeneration. An early-join edit regenerates the complete requested timeline, including subsequent joins; partial inconsistent acceptance is refused by accepting complete checkpoints only.

Cancellation uses the existing native job lifecycle. Restart recovery checks both launcher ownership and native executor/Blender process evidence; it does not clear a live writer's lease. Incomplete attempts remain interrupted and excluded from valid candidates. The b23e76d native fault procedure verifies this path; B and E remain unfinished, and fault paths need final-build regression.

Historical evidence remains retained: the 9474cca native batch took 96.743 seconds and the preceding 91cb591 run exposed a comparison initialization bug. Later c401b33 and b23e76d native tests verified framing of the complete performer. These isolated observations are not benchmark percentiles or successful acceptance/render journeys.
