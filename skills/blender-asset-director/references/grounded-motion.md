# Explicit floor and grounded motion (v0.5.0)

Use only when the observed motion stays grounded. These operations do not author
human footwork or establish artistic acceptance.

`stage-floor` adds one horizontal mesh and two new alternating matte materials.
Supply `size` [x,y], `location` [x,y,z], `color`, `grid_color`, `tile_size`, and
`roughness`. Size, coordinates, colours and cell count are bounded. Existing
geometry and materials are preserved; the result is a new working file.

Evaluated retarget `pose_space` optionally accepts `ground_contact` with `mesh`,
`vertex_groups`, `height`, and `max_correction`. The selected mesh must be skinned
to the target. Vertices with weights above 0.1 in the named groups measure the
lowest sole point. A bounded world-Z correction is keyed on the translation
anchor. Joint rotations and horizontal travel are preserved. Corrections beyond
the explicit cap fail. Stable evaluated vertex indices are required. Exactly one enabled target
Armature modifier is supported; extra viewport/render modifiers are refused.
Base and evaluated edge/loop connectivity are fingerprinted, not merely counted.
Ground correction also rejects source alignment that tilts world Z. These are
conservative supported-case checks, not a general topology-identity proof.

Do not use this correction for jumps, steps, uneven terrain or arbitrary motion.
It does not implement pressure, horizontal foot locking or IK. Subsequent NLA
retiming interpolates the baked poses, so recheck contact on the final timebase.
Keep ground-preserving source alignment level: a tilted world rotation also tilts
root travel. A world-yaw alignment is appropriate only when supported by the rigs.

Check the final integer frame range against the NLA strip end. An extra frame can
fall outside the strip and expose the rest pose. Preview and camera checks must
include the last retained frame. Playback looping still resets traveling motion;
this is not a seamless-loop operation.

## Timing and endpoints

Use the indexed `source_fps` as a frame-coordinate convention, not as a playback
speed dial. glTF retarget imports now use that same coordinate FPS and restore
the target scene's FPS afterwards. Native recording FPS remains unknown unless
a trustworthy source supplies it. Baking retains a fractional last key when
needed to preserve the source duration in seconds.

For intentional retiming, an assembly clip accepts `playback_speed` in 0.1..4
(default 1). At 0.8 speed a one-second take lasts 1.25 seconds. The NLA scale is
`target_fps / (baked_fps * playback_speed)`. A conflicting legacy `source_fps`
override is refused.

Assembly retains only integer frames actually covered by strips, from the ceil
of the first start to the floor of the last end. Integer-frame gaps are refused;
subframe gaps and interpolation extrema still require temporal review. A strip
ending at 32.25 retains frame 32, not frame 33 in the rest pose. The fractional
endpoint is kept in the action/strip even when it is not an integer output frame.
Travel in either root or hips blocks an additional path controller.
