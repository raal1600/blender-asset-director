"""Synthetic evaluated-surface regression. No user assets or backend download.

Run background factory Blender --python this_file -- UNUSED_OUTPUT_DIRECTORY.
"""
import bpy,sys,math,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from asset_director import blender_ops as ops
from asset_director.ground_contact import GroundContact
from asset_director.core import atomic_json,DirectorError,digest


def main(out):
    assert bpy.app.background
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    data=bpy.data.armatures.new('SyntheticRig');rig=bpy.data.objects.new('SyntheticActor',data)
    bpy.context.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig;rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    root=data.edit_bones.new('root');root.head=(0,0,0);root.tail=(0,0,.1)
    hips=data.edit_bones.new('hips');hips.head=(0,0,1);hips.tail=(0,0,1.2);hips.parent=root
    foot=data.edit_bones.new('sole');foot.head=(0,0,.4);foot.tail=(0,0,.6);foot.parent=hips
    bpy.ops.object.mode_set(mode='OBJECT')
    mesh=bpy.data.meshes.new('SoleSurface');mesh.from_pydata([(-.02,-.03,0),(.02,-.03,0),(.02,.03,0),(-.02,.03,0)],[],[(0,1,2,3)]);mesh.update()
    skin=bpy.data.objects.new('SyntheticSkin',mesh);bpy.context.collection.objects.link(skin)
    skin.vertex_groups.new(name='sole').add(list(range(4)),1,'REPLACE')
    modifier=skin.modifiers.new('Skin','ARMATURE');modifier.object=rig
    for f,angle,x in [(1,-.8,0),(2,.8,.6),(2.4,.8,.84)]:
        rig.pose.bones['sole'].rotation_mode='XYZ';rig.pose.bones['sole'].rotation_euler.z=angle
        rig.pose.bones['sole'].keyframe_insert('rotation_euler',frame=f)
        rig.pose.bones['hips'].location.x=x;rig.pose.bones['hips'].keyframe_insert('location',frame=f)
    original=rig.animation_data.action;original.use_fake_user=True;slot=rig.animation_data.action_slot.identifier
    for c in ops.curves(original,rig.animation_data.action_slot):
        for k in c.keyframe_points:k.interpolation='LINEAR'
    scene=bpy.context.scene
    def evaluate(f):
        scene.frame_set(math.floor(f),subframe=f-math.floor(f));bpy.context.view_layer.update()
        obj=skin.evaluated_get(bpy.context.evaluated_depsgraph_get());m=obj.to_mesh()
        try:return min((obj.matrix_world@v.co).z for v in m.vertices)
        finally:obj.to_mesh_clear()
    ground=evaluate(1)
    original_middle=evaluate(1.5)-ground
    assert original_middle<-.05,original_middle
    fingerprint=ops.rig_report(rig)['fingerprint']
    raw_rot=[(c.data_path,c.array_index,[(list(k.co),k.interpolation) for k in c.keyframe_points]) for c in ops.curves(original,rig.animation_data.action_slot) if 'rotation' in c.data_path]
    def reset():
        action=original.copy();ops.assign(rig,action,slot)
        return action
    reset();plain=GroundContact(rig,'hips',dict(mesh=skin.name,vertex_groups=['sole'],height=ground,max_correction=.2))
    plain.correct([1,2,2.4]);integer_only=evaluate(1.5)-ground
    assert integer_only<-.05,integer_only
    action=reset();dense=GroundContact(rig,'hips',dict(mesh=skin.name,vertex_groups=['sole'],height=ground,max_correction=.2,subdivisions=4))
    dense.correct([1,2,2.4]);measurements={str(f):evaluate(f)-ground for f in (1,1.25,1.5,1.75,2,2.1,2.2,2.3,2.4)}
    assert max(abs(v) for v in measurements.values())<1e-4,measurements
    actual_rot=[(c.data_path,c.array_index,[(list(k.co),k.interpolation) for k in c.keyframe_points]) for c in ops.curves(action,rig.animation_data.action_slot) if 'rotation' in c.data_path]
    assert actual_rot==raw_rot
    assert ops.rig_report(rig)['fingerprint']==fingerprint
    last=max(k.co.x for c in ops.curves(action,rig.animation_data.action_slot) for k in c.keyframe_points)
    assert abs(last-2.4)<1e-6
    for f in (1,1.25,1.5,1.75,2,2.1,2.2,2.3,2.4):
        evaluate(f);assert abs((rig.matrix_world@rig.pose.bones['hips'].head).x-.6*(f-1))<1e-5
    reset()
    try:
        GroundContact(rig,'hips',dict(mesh=skin.name,vertex_groups=['sole'],height=ground+.1,max_correction=.12,subdivisions=2)).correct([1,2,2.4])
        raise AssertionError('Total correction cap should reject midpoint')
    except DirectorError as e:assert e.code=='GROUND_CORRECTION_LIMIT',e.code
    report={'status':'PASS','blender_version':bpy.app.version_string,'original_midpoint_clearance':original_middle,'integer_only_midpoint_clearance':integer_only,'subdivided_clearance':measurements,'rotation_curves_unchanged':True,'horizontal_travel_preserved':True,'fingerprint_preserved':True,'fractional_endpoint':last,'total_cap_rejection':'PASS','ground_report':dense.report(),'performance':'PENDING'}
    atomic_json(out/'ground_contact_report.json',report);print(json.dumps(report))


if __name__=='__main__':main(sys.argv[sys.argv.index('--')+1])
