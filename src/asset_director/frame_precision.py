"""Declared time is double precision; Blender frame fields store binary32.

Compare direct stored fields to their exact representable value. For arithmetic
on several frame fields, account for rounding at each known operation, not a
scene-sized tolerance. Never change source FPS to hide storage quantization.
"""
import math
import struct
from .core import require


def stored(value):
    require(type(value) in (int, float) and math.isfinite(value) and abs(value) <= 100000,
            'INVALID_TIMING', 'Frame coordinate exceeds the supported precision domain')
    return struct.unpack('<f', struct.pack('<f', value))[0]


def ulp(value):
    value = abs(stored(value))
    if value < 2**-126: return 2**-149
    return 2**(math.frexp(value)[1]-24)


def action_range(observed, intended):
    require(len(observed) == len(intended) == 2 and
            all(a == stored(b) for a,b in zip(observed,intended)),
            'SEQUENCE_CLIP_INVALID', 'Action range differs from the representable reviewed receipt')
    return {'intended':list(intended), 'stored':list(observed),
            'error_frames':[a-b for a,b in zip(observed,intended)], 'format':'IEEE754-binary32'}


def strip_error_bound(start, source_range, scale):
    span = source_range[1]-source_range[0]
    end = start+span*scale
    return (ulp(start)+abs(scale)*(ulp(source_range[0])+ulp(source_range[1])+ulp(span))
            +abs(span)*ulp(scale)+ulp(span*scale)+ulp(end))
