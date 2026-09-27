"""Portable, versioned whole-instance placement commands (Blender coordinates).

Matrices are row-major affine transforms. Only positive uniform scale and
rotation/translation are supported; no shear, reflection or rig-channel edits.
"""
import math
import re
from .core import fields, require

VERSION = 'world-transform-v1'
FIELDS = {'version', 'transforms'}
MAX_INSTANCES = 64


def matrix(value):
    require(isinstance(value, list) and len(value) == 16
            and all(type(v) in (int, float) and math.isfinite(v) for v in value),
            'INVALID_WORLD_TRANSFORM', 'Use a finite row-major 4x4 matrix')
    require(all(abs(value[12 + i] - v) <= 1e-7 for i, v in enumerate((0, 0, 0, 1))),
            'INVALID_WORLD_TRANSFORM', 'Placement must be an affine transform')
    require(all(abs(value[i]) <= 1e6 for i in (3, 7, 11)),
            'INVALID_WORLD_TRANSFORM', 'Placement translation exceeds the supported range')
    columns = [[value[r * 4 + c] for r in range(3)] for c in range(3)]
    lengths = [math.sqrt(sum(v * v for v in c)) for c in columns]
    require(all(1e-4 <= size <= 1e4 for size in lengths),
            'INVALID_WORLD_TRANSFORM', 'Placement scale must be positive and bounded')
    scale = sum(lengths) / 3
    require(max(lengths) - min(lengths) <= scale * 1e-5,
            'INVALID_WORLD_TRANSFORM', 'Use uniform scale for whole assets')
    require(all(abs(sum(a * b for a, b in zip(columns[i], columns[j]))) <= scale ** 2 * 1e-5
                for i, j in ((0, 1), (0, 2), (1, 2))),
            'INVALID_WORLD_TRANSFORM', 'Sheared placement requires detailed Blender editing')
    a, b, c = columns
    determinant = (a[0] * (b[1] * c[2] - b[2] * c[1])
                   - b[0] * (a[1] * c[2] - a[2] * c[1])
                   + c[0] * (a[1] * b[2] - a[2] * b[1]))
    require(determinant > 0, 'INVALID_WORLD_TRANSFORM', 'Mirrored placement is unsupported')
    return value


def validate(options):
    fields(options, FIELDS, FIELDS)
    require(options['version'] == VERSION, 'INVALID_WORLD_TRANSFORM', 'Unknown placement command version')
    changes = options['transforms']
    require(isinstance(changes, list) and 1 <= len(changes) <= MAX_INSTANCES,
            'INVALID_WORLD_TRANSFORM', 'Save one to 64 asset placements at a time')
    seen = set()
    for item in changes:
        fields(item, {'instance', 'expected_matrix', 'matrix'}, {'instance', 'expected_matrix', 'matrix'})
        identity = item['instance']
        require(isinstance(identity, str) and re.fullmatch(
            r'instance_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', identity)
            and identity not in seen, 'INVALID_WORLD_TRANSFORM', 'Choose distinct observed asset instances')
        seen.add(identity)
        matrix(item['expected_matrix'])
        matrix(item['matrix'])
    return options
