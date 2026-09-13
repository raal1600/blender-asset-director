# Resume Asset Director after the retarget completion

The v0.5.0 preview request packages the validated completion of
`fix/evaluated-pose-retarget`. Runtime commit `7820ec9` passed all ten CI jobs in
run 34788489612 before integration into main. The release request reruns the
complete gate, then publishes a new tag and tests anonymous installers. Check
actual release status rather than assuming the request itself is publication.
Read RETARGET_ACCEPTANCE.md for exact evidence and limits.

New capabilities: explicit evaluated-pose retargeting, bounded vertical sole
correction, stage-floor, preserved glTF source frame-coordinate timebase,
separate playback_speed and integer-safe NLA endpoints. Legacy retargeting is
default; rig mapping/alignment and contact selection need actual evidence.
The floor is owned by the existing production-design `set` capability. Load the
new grounded-motion reference when relevant; no scenario is hardcoded.

Do not modify the user's installed runtime or projects merely to resume source
work. Use the managed installer for a deliberate version update, preserving its
receipt and asset library. Installation alone is not live Blender connectivity.
Do not reopen or reload over unsaved scenes. Historical local preservation gaps
remain unknown; later snapshots do not retroactively prove them.

The supplied moonwalk source has not passed human artistic acceptance. Pose
transfer, ground height and camera checks are not authentic-performance proof.
Retarget and NLA reports deliberately leave performance acceptance NOT_EVALUATED.
Temporal source/final comparison is required; still frames cannot certify motion
between samples. Foot gliding can be intentional and should not be universally
locked away. Ground correction is not IK and is unsuitable for jumps/stairs.

Next researched capability: recorded authorized human performance -> cloud mocap
-> durable take manifest -> intake -> retarget -> contact-aware temporal review.
Read CAPTURE_ROADMAP.md. It distinguishes real performance from true real-time
streaming, documents provider access/rights limits and current options, and does
not claim a capture backend has been implemented. No uploads, subscriptions,
paid calls or new devices are authorized just by reading that roadmap.
