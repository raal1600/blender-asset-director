"""Correct only verified integer-frame samples in a disposable scene GLB.

Some bundled exporters multiply fps_base; others use fps or the correct effective
rate. Match a full sampled interval to these known rates, never guess motion or
resample values. Scene properties and source animation are not changed.
"""
import json
import math
import struct
from .core import require


def normalize(destination, start, end, fps, fps_base):
    original = destination.read_bytes()
    require(original[:4] == b'glTF' and len(original) >= 28, 'VIEWER_EXPORT_FAILED', 'Invalid GLB timing envelope')
    size, kind = struct.unpack_from('<II', original, 12)
    require(kind == 0x4e4f534a, 'VIEWER_EXPORT_FAILED', 'Expected GLB JSON')
    data = json.loads(original[20:20+size]);offset = 20+size
    count, kind = struct.unpack_from('<II', original, offset)
    require(kind == 0x004e4942 and offset+8+count == len(original), 'VIEWER_EXPORT_FAILED', 'Expected one GLB binary chunk')
    binary = bytearray(original[offset+8:]);effective = fps/fps_base;span = end-start
    samplers = [s for a in data.get('animations', []) for s in a['samplers']]
    require(all(s.get('interpolation', 'LINEAR') in {'LINEAR', 'STEP'} for s in samplers),
            'VIEWER_EXPORT_FAILED', 'Time correction requires sampled linear/step channels, not spline tangents')
    indices = {s['input'] for s in samplers}
    outputs = {s['output'] for a in data.get('animations', []) for s in a['samplers']}
    require(not indices & outputs, 'VIEWER_EXPORT_FAILED', 'Animation time/value storage is shared')
    changes = []
    for index in sorted(indices):
        accessor = data['accessors'][index];view = data['bufferViews'][accessor['bufferView']]
        require(accessor.get('componentType') == 5126 and accessor.get('type') == 'SCALAR'
                and 'sparse' not in accessor and view.get('buffer', 0) == 0 and view.get('byteStride', 4) == 4
                and 1 <= accessor['count'] <= span+1, 'VIEWER_EXPORT_FAILED', 'Unsupported sampled time accessor')
        begin = view.get('byteOffset', 0)+accessor.get('byteOffset', 0);length = accessor['count']
        require(begin >= 0 and begin+length*4 <= len(binary), 'VIEWER_EXPORT_FAILED', 'Invalid animation time storage')
        times = list(struct.unpack_from('<'+'f'*length, binary, begin))
        require(all(math.isfinite(t) for t in times) and abs(times[0]) < 1e-5 and
                all(a < b for a,b in zip(times,times[1:])), 'VIEWER_EXPORT_FAILED', 'Invalid ordered sampled times')
        if length == 1:
            require(abs(times[0]) < 1e-5, 'VIEWER_EXPORT_FAILED', 'A held channel must start at frame zero')
            continue
        candidates = [rate for rate in {effective, fps, fps*fps_base}
                      if abs(times[-1]*rate-span) < 1e-3 and
                      all(abs(t*rate-round(t*rate)) < 1e-3 for t in times)]
        require(candidates, 'VIEWER_EXPORT_FAILED', 'Unrecognized sampled GLB timebase; no approximation made')
        frames = [round(t*candidates[0]) for t in times]
        require(all(0 <= f <= span for f in frames), 'VIEWER_EXPORT_FAILED', 'Sample lies outside scene timing')
        values = [f/effective for f in frames]
        if any(abs(a-b) > 1e-7 for a,b in zip(times,values)):
            struct.pack_into('<'+'f'*length, binary, begin, *values)
            accessor['min'] = [values[0]];accessor['max'] = [values[-1]]
            changes.append({'accessor': index, 'samples': length, 'before_end': times[-1], 'after_end': values[-1]})
    if changes:
        encoded = json.dumps(data, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
        encoded += b' '*((-len(encoded)) % 4)
        raw = struct.pack('<4sII', b'glTF', 2, 12+8+len(encoded)+8+len(binary))
        raw += struct.pack('<II', len(encoded), 0x4e4f534a)+encoded+struct.pack('<II', len(binary), 0x004e4942)+binary
        destination.write_bytes(raw)
    return {'scope': 'PREVIEW_ONLY', 'effective_fps': effective, 'corrected_accessors': changes,
            'original_scene_changed': False, 'sampling': 'VERIFIED_INTEGER_FRAMES'}
