"""Background Blender regression: -- NEW_OUTPUT_DIRECTORY DISPOSABLE_LIBRARY.

No downloads/backend/live window needed. Does not claim visual acceptance.
"""
import bpy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from headless_fixture import humanoid,animate
from asset_director import jobs,bone_display,blender_ops as ops
from asset_director.core import Library,atomic_json,file_hash,load_json,digest,DirectorError


def snapshot(rig,skin):
    return {'fingerprint':ops.rig_report(rig)['fingerprint'],
            'shape_refs':{p.name:p.custom_shape.name if p.custom_shape else None for p in rig.pose.bones},
            'skin':digest({'verts':[list(v.co) for v in skin.data.vertices],'groups':[g.name for g in skin.vertex_groups],
                           'weights':[[(g.group,g.weight) for g in v.groups] for v in skin.data.vertices]}),
            'objects':sorted((o.name,o.type,ops.flatten(o.matrix_world)) for o in bpy.data.objects),
            'actions':{a.name:digest([[c.data_path,c.array_index,[[list(k.co),list(k.handle_left),list(k.handle_right),k.interpolation] for k in c.keyframe_points]] for c in ops.curves(a)]) for a in bpy.data.actions},
            'poses':{p.name:list(p.scale) for p in rig.pose.bones}}


def main(out,library):
    assert bpy.app.background
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rig,skin=humanoid('ReviewRig');animate(rig);scene=bpy.context.scene;scene.frame_set(1)
    bpy.ops.mesh.primitive_ico_sphere_add();widget=bpy.context.object;widget.name='ObservedWidget'
    for p in rig.pose.bones:p.custom_shape=widget
    rig.data.display_type='OCTAHEDRAL';rig.data.show_bone_custom_shapes=True
    rig.data.bones['head'].display_type='ENVELOPE'
    rig.data.bones['root'].hide=True
    source=out/'source.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source));sha=file_hash(source)
    before=snapshot(rig,skin);names=(rig.name,skin.name,widget.name);checks=[]
    def passed(name):checks.append(name);atomic_json(out/'progress.json',{'checks':checks})
    options={'target_object':rig.name,'target_fingerprint':before['fingerprint'],'display_type':'OCTAHEDRAL','show_custom_shapes':False,'show_in_front':True}
    def fails(patch,code):
        state=bone_display.audit(rig)
        try:bone_display.apply(options|patch);raise AssertionError('Expected '+code)
        except DirectorError as e:assert e.code==code,(e.code,code)
        assert bone_display.audit(rig)==state
    fails({'target_fingerprint':'0'*64},'STALE_TARGET')
    fails({'visible_bones':['absent']},'UNKNOWN_BONE')
    fails({'hide_widget_objects':[skin.name]},'NOT_TARGET_WIDGET')
    # Even an assigned shape must not be hidden if it is a skinned character.
    rig.pose.bones['head'].custom_shape=skin
    fails({'hide_widget_objects':[skin.name]},'SKINNED_WIDGET_REVIEW')
    rig.pose.bones['head'].custom_shape=widget
    other=rig.copy();bpy.context.scene.collection.objects.link(other)
    fails({},'SHARED_ARMATURE_DATA')
    other.data=rig.data.copy()
    fails({'hide_widget_objects':[widget.name]},'SHARED_WIDGET_REVIEW')
    bpy.data.objects.remove(other,do_unlink=True)
    passed('stale, absent, unrelated, skinned and shared targets rejected before mutation')
    with Library(library) as lib:
        def run(op,opts):
            j=jobs.prepare(lib,op,str(source),options=opts);jobs.run(lib,j['id'],bpy.app.binary_path,120)
            folder=lib.root/'jobs'/j['id'];return j,load_json(folder/'result.json')['data'],folder
        j,a,folder=run('bone-display-audit',{'target_object':rig.name})
        assert a['custom_shapes_override_standard_style'] and a['custom_shape_assignments']
        assert a['per_bone_display_overrides']=={'head':'ENVELOPE'}
        assert not (folder/'result.blend').exists() and file_hash(source)==sha
        passed('read-only audit detects spherical custom shape and per-bone overrides')
        j,d,folder=run('bone-display',options)
        bpy.ops.wm.open_mainfile(filepath=str(folder/'result.blend'),load_ui=False,use_scripts=False)
        rig,skin,widget=(bpy.data.objects[n] for n in names)
        assert snapshot(rig,skin)==before
        assert not rig.data.show_bone_custom_shapes and rig.show_in_front
        assert all(b.display_type=='ARMATURE_DEFINED' for b in rig.data.bones)
        assert rig.data.bones['root'].hide and not widget.hide_render and not widget.hide_get()
        passed('reopened standard display preserves references, skin, rest, actions, transforms and default visibility')
        hashes={p.name:file_hash(p) for p in folder.iterdir() if p.is_file()}
        jobs.run(lib,j['id'],bpy.app.binary_path,120)
        assert hashes=={p.name:file_hash(p) for p in folder.iterdir() if p.is_file()}
        passed('completed display job reused without another worker or output rewrite')
        visible=['hips','spine','head']
        _,d,folder=run('bone-display',options|{'display_type':'STICK','visible_bones':visible,'hide_widget_objects':[widget.name]})
        bpy.ops.wm.open_mainfile(filepath=str(folder/'result.blend'),load_ui=False,use_scripts=False)
        rig,skin,widget=(bpy.data.objects[n] for n in names)
        assert snapshot(rig,skin)==before
        assert set(b.name for b in rig.data.bones if not b.hide)==set(visible)
        assert rig.data.display_type=='STICK' and widget.hide_render and widget.hide_get()
        assert d['after']['visual_acceptance']=='PENDING' and file_hash(source)==sha
        passed('explicit bone subset and verified widget hiding persist without deleting objects')
    report={'status':'PASS','blender_version':bpy.app.version_string,'checks':checks,'visual_acceptance':'PENDING','live_ui_control':'NOT_RUN'}
    atomic_json(out/'REPORT.json',report);print(json.dumps(report))


if __name__=='__main__':main(*sys.argv[sys.argv.index('--')+1:])
