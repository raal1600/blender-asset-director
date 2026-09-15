"""Diagnose synthetic FBX round-trip translation precision in Actions only.

No source mutation, tolerance change or retarget bypass. The generated metre and
centimetre files describe the same motion. Reports distinguish authored motion
from values introduced by the export/import round trip.
"""
from pathlib import Path
import json
import math
import sys
import bpy
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]
from sequence_fixture import export_take
from asset_director import blender_ops as ops
from asset_director.core import atomic_json


def main(output):
    assert bpy.app.background
    root = Path(output).resolve(); root.mkdir(parents=True, exist_ok=False)
    cases = []
    for units in (1, 100):
        path = root/f'synthetic-{units}.fbx'
        export_take(path, 1113, units, .35, 1.0)
        source = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
        before = source.animation_data.action
        authored = [c.data_path for c in ops.curves(before, source.animation_data.action_slot)
                    if c.data_path.endswith('.location')]
        bpy.ops.wm.read_factory_settings(use_empty=True)
        objects = ops.import_file(path, root)
        obj = next(o for o in objects if o.type == 'ARMATURE')
        action = obj.animation_data.action; slot = obj.animation_data.action_slot
        anchor = ops.rig_report(obj)['roles']['hips']
        rows = []
        for curve in ops.curves(action, slot):
            if not curve.data_path.endswith('.location'): continue
            vals = [float(k.co.y) for k in curve.keyframe_points]
            if not vals: continue
            rows.append({'path': curve.data_path, 'axis': curve.array_index,
                         'anchor': curve.data_path == obj.pose.bones[anchor].path_from_id('location'),
                         'min': min(vals), 'max': max(vals), 'span_scene_units': max(vals)-min(vals),
                         'span_m': (max(vals)-min(vals))/units})
        non_anchor = sorted((r for r in rows if not r['anchor']), key=lambda r:r['span_scene_units'], reverse=True)
        case = {'source_units_per_meter': units, 'authored_location_paths': sorted(set(authored)),
                'object_scale': list(obj.scale), 'anatomical_height_scene_units': ops.rig_report(obj)['anatomical_height'],
                'max_non_anchor': non_anchor[:12], 'non_anchor_curves': len(non_anchor),
                'over_existing_threshold': sum(r['span_scene_units'] >= 1e-5 for r in non_anchor)}
        cases.append(case)
        print(json.dumps(case), flush=True)
        atomic_json(root/'source_precision_report.json', {'blender': bpy.app.version_string, 'cases': cases,
                    'notice': 'Diagnostic measurements only; not a permission relaxation or source cleanup.'})


if __name__ == '__main__': main(sys.argv[sys.argv.index('--')+1])
