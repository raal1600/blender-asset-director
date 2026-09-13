# Real-performance capture roadmap

Research checked 2026-09-14. This is a design recommendation, NOT an implemented
capture integration or a measured comparison of provider motion quality. The
v0.5.0 runtime stabilizes downstream retargeting; it does not reconstruct video.
No credentials, paid services, recordings or user projects were used here.

## Decision

First integrate **recorded real-human performance -> cloud reconstruction ->
reviewed local intake -> retarget -> temporal quality review**. This fits the
existing no-local-AI/no-local-GPU-inference policy and lets us evaluate dance
quality before investing in live hardware. Keep true real-time streaming as a
separate later mode, not a marketing name for an asynchronous video-upload job.
A source performance is not improved just because its retarget is more accurate.

Two modes need different acceptance:

- Recorded take: upload an authorized video; receive completed skeletal motion;
  review the whole take, then retarget. Latency is job turnaround.
- Live capture: a performer drives a character as they move. This needs capture
  hardware or an actual streaming inference service, clocked pose packets,
  calibration and a persistent low-latency receiver. Latency is capture-to-display.

A good existing licensed mocap take remains a valid cheaper source. Reuse first.
For performer-specific movement, record a skilled consenting performer or use
footage whose source, upload and output-use permissions are actually established.
Do not label reconstructed concert footage as original optical mocap or assume
that an online video grants commercial performance/likeness/music rights.

## Current source options, with their real boundaries

| Route | Verified capability | Decision for this harness |
|---|---|---|
| DeepMotion Animate 3D | Documented REST API converts video into FBX/BVH and other outputs; API access is requested separately [1]. Foot-lock controls distinguish auto, always, never and grounding [2]. | Preferred API prototype, conditional on actual API approval, commercial entitlement and an explicit spend/upload budget. This is batch video processing, not verified live streaming. |
| Rokoko Create / Vision | Cloud single-camera video workflow. Current pricing lists 30 seconds/month for Starter; verify quota/export/use rights in the actual account [3]. Legacy webcam and dual-camera Vision workflows were retired August 16, 2026 [4]. | Low-friction short-take trial via official UI and exported-file intake. A public supported automated Create submission API was not established in this research; do not invent one. |
| Rokoko hardware + Studio + Blender plugin | Official Blender integration streams performance from Smartsuit/Smartgloves/face tools [5]. | A genuine later live route, requiring hardware, appropriate streaming entitlement and compatibility testing. The plugin is not a substitute for a capture device. Do not install another addon until this mode is selected. |
| Move API rt1 | Documented Enterprise-only real-time, calibrated multi-camera model; minimum four synchronized cameras and real-time processing infrastructure [6]. | Valid professional live option, not the free single-webcam/no-setup path. Infrastructure cost and deployment need vendor confirmation. |
| FreeMoCap | Free/open source, two or more cameras, calibrated capture, local reconstruction, animation exports; documentation says CPU operation is supported [7]. | Credible community alternative. It need not require a GPU, but stock operation is local processing and therefore outside this project's present no-local-AI policy. A remote worker would be new engineering plus hosting cost, not an existing free hosted API. Review code/dependency licenses before redistribution. |

DeepMotion's web FAQ distinguishes non-commercial Freemium from premium
commercial licensing and describes one base credit per animation second, with
additional hand/face costs [8]. These are web-plan facts, not an API price quote.
API access/entitlements and usable quotas must be checked in the account before
submission. Do not map a custom provider output license to CC0 merely to pass the
existing conservative asset policy. Extend rights evidence deliberately when a
commercially permitted custom license is needed.

Rokoko product documentation changed recently. Older tutorials that show a free
Vision webcam/dual-camera workflow should not drive a new integration [4].
No claimed quality ranking below is based on a provider benchmark; the pilot must
measure actual source and output motion.

## What to implement next

### 1. Capture/take manifest before another model

Add a versioned, model-independent take record with:

- immutable source video/hash; frame timestamps, dimensions, variable/constant
  frame-rate information, any known edit or slow-motion multiplier;
- performer/source provenance, permitted use and consent to upload; no credentials;
- source skeleton and rest pose, axis/up convention, units, calibration identity,
  source motion hash, duration in seconds and actual sample times;
- provider/model/version, request options, remote job ID, costs and entitlement
  evidence, output file hashes, and explicit gaps/unknowns;
- imported frame-coordinate FPS, native capture rate when known, destination FPS
  and artistic playback speed as DIFFERENT values;
- raw, cleaned and retargeted output lineage. Never overwrite the raw take.

This release's glTF coordinate-FPS and playback-speed corrections are downstream
prerequisites. They are not proof of a capture device's clock or original rate.

### 2. Capture provider adapter and durable jobs

Proposed commands (not current CLI): probe, plan, submit, status, fetch and intake.
Use a small capability contract: recorded/live, formats, body/hand/face support,
auth state, entitlement, quota and verified upload/download host set. Credentials
are local-only. Authenticate to documented services; never scrape private APIs.

Before submit, require a specific approved video, provider, features, maximum cost,
and privacy/use approval. Paid execution remains blocked by default. A general
request to research capture is NOT approval to spend or upload recordings/models.
Use provider-supported idempotency or a local submission ledger to avoid duplicate
paid takes. After a network timeout, inspect job status rather than blindly
resubmitting. Persist resumable state and poll within documented limits.

Cache by source hash + segment/timestamps + model/version/options. A failed
retarget does not justify another capture charge. Strip expiring signed URLs from
permanent model-facing logs. Fetch bounded files, validate/hash them, retain
license evidence, then use ordinary catalog/intake and isolated Blender jobs.

Keep recordings and full poses out of chat history. The model receives compact
receipts, failure summaries and selected small crops. This avoids reproducing the
previous oversized multimodal request failure. No provider-specific request-byte
limit is assumed by this design.

### 3. Source performance acceptance BEFORE retargeting

The Performance role must separately judge:

1. Is the source actually the requested action at its original speed?
2. Does reconstruction preserve its rhythm, pauses, weight shift and travel?
3. Does retargeting preserve it on the chosen character?
4. Does any cleanup improve it without erasing intentional motion?

For the moonwalk example, distinguish support on a raised heel/toe from a sliding
flat foot, the support exchange, backward body travel and torso/arm accents.
This is an example-specific review rubric, not a runtime preset or a claim of
identifying a named performer. Keep general contact modes: PLANTED, GLIDING,
AIRBORNE, UNKNOWN. Low confidence must stay unknown rather than fabricated.

Measure per-foot heel/toe positions and velocities relative to the ground and
root, vertical clearance, segment-length stability, trajectory continuity,
phase changes and acceleration spikes at matched timestamps. Ground height alone
does not establish good footwork. Blanket zero-foot-velocity constraints would
ruin intentional slides. The current vertical sole correction should remain
opt-in for a compatible grounded take, not be silently enabled for every dancer.

DeepMotion documents a grounding mode that permits intentional gliding and warns
that stronger smoothing can lose accuracy [2,9]. Compare settings on an approved
short take instead of assuming auto-locking or heavy smoothing is always better.
Mode availability is plan-dependent; do not promise free access to every setting.

### 4. Temporal evidence, not eight flattering stills

Current bounded still previews test geometry, composition and basic contacts;
they cannot establish continuity between samples. Add an explicitly authorized
low-cost temporal-preview mode (for example, short low-resolution Workbench or
CPU sequences) with its own duration/frame/time limits. Do not evade the existing
eight-frame policy by silently rendering a video. Preserve production settings.

Compare synchronized source / raw reconstructed skeleton / retarget / cleanup
at normal speed, with optional slowed diagnostic playback. A host without actual
video/motion access cannot claim it watched a clip. Mark temporal review pending
and provide the artifact for a human when necessary. Use source-relative metrics
and a human verdict, not a universal numerical "realism score."

### 5. True live mode later

Prefer an established supported Studio/Blender streaming plugin over inventing a
per-frame agent loop. Codex/MCP should orchestrate setup, capture start/stop,
selection and inspection. They should NOT issue one language-model tool call per
pose frame. The streaming data path belongs in a deterministic receiver.

A future receiver needs versioned skeleton/calibration, timestamped sequence IDs,
unit/axis conversion, bounded buffers, stale/out-of-order packet handling,
disconnection policy, raw recording, dropout markers and measured latency.
Measure capture-to-preview latency and jitter rather than claiming "real time"
from a marketing phrase. Recording/post-processing and a low-latency preview may
legitimately have different quality. Preserve the user's original scene; live
preview mutations require an explicitly selected disposable target and consent.

## Pilot and decision gates

Start with a 5-10 second authorized recording of a skilled dancer: neutral lead-in,
a few clear sliding/support exchanges, and a stop. Use a fixed camera, visible
feet and full body, adequate light and limited occlusion; follow the selected
provider's actual guidelines [10]. Do not begin with an edited concert montage.
Keep shoes distinguishable from the ground; do not obscure knees/ankles with
loose clothing. A second reference angle helps human review even if the selected
service accepts only one video; do not claim multi-view reconstruction in that case.

Reuse the current known rig/mannequin first to isolate motion quality. Choose one
provider and one approved capture job. Review its raw skeleton before retargeting.
Keep original speed initially, then use explicit playback_speed only for an
approved artistic timing change. Compare the new captured take against the old
Sketchfab take at normal speed; do not demand that the new result win.

Accept separately: provenance/upload permission, completed source processing,
correct timebase and unit/axis normalization, technically valid transfer,
performance/temporal review, final look and human acceptance. If raw capture is
poor, adjust capture conditions/provider settings rather than indefinitely
patching the target rig. No pipeline can recover an occluded foot with certainty
from an otherwise ambiguous single-view clip.

## Sources (primary, checked 2026-09-14)

1. DeepMotion API access and outputs: https://www.deepmotion.com/animate-3d-api
2. Foot-lock modes and entitlements: https://www.deepmotion.com/article/foot-locking-saymotion
3. Rokoko software quota/exports: https://www.rokoko.com/pricing
4. Vision/Create transition and retirement dates: https://support.rokoko.com/hc/en-us/articles/48823033216017-Rokoko-Vision-and-Rokoko-Create-What-you-need-to-know
5. Rokoko live Blender integration: https://www.rokoko.com/integrations/blender
6. Move rt1 capabilities/requirements: https://developers.move.ai/docs/models/rt1/
7. FreeMoCap architecture/hardware/CPU statement: https://freemocap.org/
8. DeepMotion plan licensing and credits: https://www.deepmotion.com/pricing-animate3d
9. DeepMotion maintained REST parameters: https://github.com/DeepMotion/Animate-3D-REST-API
10. Capture guidance: https://www.deepmotion.com/article/single-person-capture-guidelines-for-animate-3d
