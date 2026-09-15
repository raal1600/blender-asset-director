"""Actual FBX owner/action collision, generated source only; no private assets."""
from pathlib import Path
import json,sys
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from headless_fixture import humanoid
from asset_director import blender_ops as ops
from asset_director.worker import re_original
from asset_director.core import file_hash,atomic_json

def main(directory):
    out=Path(directory);out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rig,skin=humanoid('Armature',prefix='mixamorig:')
    bpy.context.scene.render.fps=30;bpy.context.scene.frame_end=32
    for frame in (1,32):
        p=rig.pose.bones['mixamorig:hips'];p.location.x=frame*.001;p.keyframe_insert('location',frame=frame)
    rig.animation_data.action.name='mixamo.com|Layer0'
    bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);skin.select_set(True);bpy.context.view_layer.objects.active=rig
    f=out/'synthetic.fbx'
    bpy.ops.export_scene.fbx(filepath=str(f),use_selection=True,add_leaf_bones=False,bake_anim=True,
        bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False)
    expected=file_hash(f)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    first=ops.import_file(f,out);bindings,_=ops.clip_bindings(first)
    assert len(bindings)==1
    first_rig,first_action,first_slot,start,end,_=bindings[0]
    indexed=first_action.name;fingerprint=ops.rig_report(first_rig)['fingerprint']
    before=set(bpy.data.actions);second=ops.import_file(f,out);new=set(bpy.data.actions)-before
    matches=[a for a in new if a.name==indexed]
    if not matches:matches=[a for a in new if re_original(a.name)==re_original(indexed)]
    assert len(matches)==1,([a.name for a in new],indexed)
    second_rig=next(o for o in second if o.type=='ARMATURE')
    assert second_rig.animation_data.action==matches[0]
    assert ops.rig_report(second_rig)['fingerprint']==fingerprint
    assert ops.action_range(matches[0],second_rig.animation_data.action_slot)==(start,end)
    assert file_hash(f)==expected
    report={'status':'PASS','blender':bpy.app.version_string,'original_action':indexed,
            'imported_action':matches[0].name,'new_owner':second_rig.name,'first_owner':first_rig.name,
            'original_bytes_unchanged':True,'rig_and_timebase_preserved':True}
    atomic_json(out/'action_collision_report.json',report);print(json.dumps(report))

if __name__=='__main__':main(sys.argv[sys.argv.index('--')+1])
