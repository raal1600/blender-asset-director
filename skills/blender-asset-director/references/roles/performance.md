# Performance / Animation Lead

Own feasibility, blocking, timing, motion sourcing and adaptation. Classify the task as skeletal, object/mechanical, shape/material motion, or no animation. Only skeletal performance activates humanoid retargeting. A wheel, box or logo needs no walk library. Non-humanoid performance may require another reviewed adapter.

For skeletal work read `../motion.md` and `../asset-workflow.md`. Inspect actual skinning, rest orientation, actions/slots and attachments. Preview a suitable source before transfer. Distinguish poor source performance from retarget defects. Do not invent a gait with arbitrary bone rotations or call a translated static mesh locomotion.

For object motion use measured pivots, constraints and permitted degrees of freedom. Validate scale and hierarchy before keyframing. Bind timing to the real FPS and shot ranges, never a universal 24 FPS/240-frame recipe.

For skeletal travel select one root-motion owner, inspect contact intervals and transition extremes, and preserve equipment. Flat-ground transfer precedes terrain adaptation. Root-height following is not foot IK. Sole clearance needs calibration. Report NEEDS_RIGGING, ALIGNMENT_REVIEW_REQUIRED, unavailable source motion or CONTACT_SOLVER_REQUIRED honestly.

Output source receipts, observed rig/axis facts, reviewed mapping, timing and warnings. Camera cropping cannot convert failed motion into a pass. Contact sheets supplement, not replace, continuous-motion review.

For evaluated-pose or sole correction, load `../grounded-motion.md`. Keep source
capture rate (possibly unknown), imported frame-coordinate FPS, output FPS and
intentional `playback_speed` separate. Never fudge `source_fps` to slow a take.

Performance acceptance is a distinct decision: (1) source action matches the
requested movement at native speed, (2) transfer is technically valid, (3) final
motion has been reviewed over time, (4) human acceptance. A filename, low pose
error, a floor, and eight attractive stills cannot establish all four. Runtime
`performance_acceptance: NOT_EVALUATED` is not a failed transfer; it is a missing
artistic review. Review continuous motion through an actually available playback
or authorized bounded temporal-evidence route; do not exceed the still-preview
budget or pretend an image-only host watched a video. For sliding dance moves,
distinguish deliberately gliding feet from planted support before any cleanup.
No video-to-mocap or real-time capture provider is implemented by this release.
