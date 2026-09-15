"""Synthetic FBX tail reconstruction/connected-anchor regression, CI only.

The positive source uses a horizontal floor control; the negative uses a collinear
parent, which Blender's importer reconnects despite meaningful hip location keys.
No importer defaults or imported rig properties are changed to force a pass.
"""
from pathlib import Path
import sys
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from sequence_fixture import export_take
from asset_director import blender_ops as ops, transfer_blender as tb
from asset_director.core import atomic_json, file_hash, DirectorError


def main(output):
    assert bpy.app.background
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    checks=[]
    for axis in ('Z','X'):
        path=root/('generated-'+axis+'.fbx')
        export_take(path,32,1,.92,.2,root_axis=axis)
        source_hash=file_hash(path)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        objects=ops.import_file(path,root)
        source=next(o for o in objects if o.type=='ARMATURE')
        action=source.animation_data.action;slot=source.animation_data.action_slot
        roles=ops.rig_report(source)['roles'];anchor=roles['hips']
        start,end=ops.action_range(action,slot)
        samples=ops.samples_for(source,ops.rig_report(source),start,end,max_samples=3)
        travel=(Vector(samples[-1]['hips'])-Vector(samples[0]['hips'])).length
        location=next(c for c in ops.curves(action,slot)
                      if c.data_path==source.pose.bones[anchor].path_from_id('location') and c.array_index==0)
        channel_span=max(k.co.y for k in location.keyframe_points)-min(k.co.y for k in location.keyframe_points)
        assert channel_span>.9,channel_span
        signature=tb.action_signature(action,slot)
        connected=source.data.bones[anchor].use_connect
        if axis=='Z':
            assert connected and travel<1e-5,(connected,travel)
            try:
                tb.source_checks(source,action,anchor,start,end,3,1)
                raise AssertionError('Ignored connected-anchor motion accepted')
            except DirectorError as exc:assert exc.code=='CONNECTED_ANCHOR_TRANSLATION',exc.code
        else:
            assert not connected and abs(travel-.92)<1e-5,(connected,travel)
            tb.source_checks(source,action,anchor,start,end,3,1)
        assert signature==tb.action_signature(action,slot) and file_hash(path)==source_hash
        checks.append({'root_axis':axis,'hip_connected_after_import':connected,
                       'keyed_translation_span':channel_span,'evaluated_travel':travel,
                       'source_and_curves_preserved':True})
    atomic_json(root/'fbx_anchor_report.json',{'status':'PASS','blender':bpy.app.version_string,'checks':checks})


if __name__=='__main__':main(sys.argv[sys.argv.index('--')+1])
