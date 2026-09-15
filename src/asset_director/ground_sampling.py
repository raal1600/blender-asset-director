"""Portable, bounded contact checkpoints; no claim of continuous collision safety."""
import math
from .core import require


def validate_subdivisions(value):
    require(type(value) is int and 1 <= value <= 8, 'INVALID_GROUND_CONTACT',
            'Ground-contact subdivisions must be an integer in 1..8')


def correction_frames(frames, subdivisions=1, max_frames=361):
    validate_subdivisions(subdivisions)
    require(type(max_frames) is int and 2 <= max_frames <= 7201, 'RESOURCE_LIMIT',
            'Invalid explicitly bounded grounding input count')
    require(isinstance(frames, list) and 2 <= len(frames) <= max_frames and
            all(type(f) in (int, float) and math.isfinite(f) for f in frames) and
            all(b > a for a, b in zip(frames, frames[1:])),
            'INVALID_GROUND_CONTACT', 'Need bounded increasing baked frame coordinates')
    require((len(frames)-1)*subdivisions+1 <= 2881, 'RESOURCE_LIMIT',
            'Grounding exceeds the retained 2881-checkpoint budget; diagnose a bounded interval instead')
    # Subdivide each actual interval, including a shorter fractional final interval.
    # Retain the supplied endpoint exactly once; never extend the action duration.
    return [a + (b-a)*i/subdivisions for a,b in zip(frames, frames[1:])
            for i in range(subdivisions)] + [frames[-1]]
