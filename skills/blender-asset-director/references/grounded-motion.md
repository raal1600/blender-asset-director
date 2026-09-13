# Explicit floor and grounded motion (development)

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
the explicit cap fail. Stable evaluated vertex indices are required.

Do not use this correction for jumps, steps, uneven terrain or arbitrary motion.
It does not implement pressure, horizontal foot locking or IK. Subsequent NLA
retiming interpolates the baked poses, so recheck contact on the final timebase.
Keep ground-preserving source alignment level: a tilted world rotation also tilts
root travel. A world-yaw alignment is appropriate only when supported by the rigs.

Check the final integer frame range against the NLA strip end. An extra frame can
fall outside the strip and expose the rest pose. Preview and camera checks must
include the last retained frame. Playback looping still resets traveling motion;
this is not a seamless-loop operation.
