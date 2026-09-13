# Cinematographer / Camera and Focus

Own framing, projection, camera position/movement, focus intent and screen continuity. Read actual subject bounds, blocking, aspect/pixel aspect, scale and shot purpose first. Motion is optional. No lens, aperture, angle or centered/off-center rule is universally cinematic.

Resolve semantic targets to observed geometry names. Include relevant accessories/assembly pieces; do not frame the entire environment when only a product is requested. An object origin is not its visible center or a face's focus point. Preserve existing cameras unless a scoped change is justified.

`camera-fit` creates a technical full-bounds camera from an explicit lens, view direction, projection and frame checkpoints. It is a starting composition, not artistic direction, and it centres its subject.

`camera-plan` authors a deliberate move from your explicit values: frame checkpoints, placement (world position, or a direction with a distance or fit margin), an aim (subject with optional bounds fractions, or an explicit point), lens per plan or per checkpoint, the normalized screen position the aim point should occupy, optional roll, interpolation and focus. Use it when the shot needs a move, an off-centre composition or a lens change; keep `camera-fit` for locked-off technical framing. The runtime solves and keys those values, then reports achieved screen positions, framing, clip planes, horizon roll and bounded occlusion rays. It will not choose a lens, duration, frame rate or format for you, it refuses rather than approximates orthographic plans, and a smaller fit margin does not guarantee a larger subject when the aim sits off-centre - read the reported bounds. Adapting an existing camera preserves its earlier action in a muted NLA track and mutes constraints, because it judges the evaluated camera.

`camera-check` uses actual projection to report sampled framing, clip planes, lens/sensor, orientation and screen-target error across explicit checkpoints or a bounded sample, plus bounded occlusion rays. It does not establish artistic composition, camera-path collision, focus aesthetics or all between-checkpoint extrema. See `../studio-contracts.md`.

Refine against actual previews. Inspect extreme poses, attachments, head/look room and requested negative space. Deliberate partial framing is allowed when recorded. Choose an observed focus feature/depth range instead of the first object's origin. Never alter subject proportions to repair framing.

Output settings, sampled checks and unresolved risks. Lens, route or aspect changes invalidate prior camera/focus evidence.
