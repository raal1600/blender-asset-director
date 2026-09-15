"""Identical imported centimeter-scale references need no reference deformation.

Synthetic FBX and local CC0 declaration only. Real project files are not used.
Run factory background Blender -- OUTPUT_DIRECTORY VERIFIED_BACKEND_LIBRARY.
"""
from pathlib import Path
import json,sys,shutil
import bpy
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from transfer_planning_fixture import make_rig
from asset_director import jobs,blender_ops as ops
from asset_director.core import Library,Asset,atomic_json,file_hash,load_json


def main(directory, backend_library):
    assert bpy.app.background
    out=Path(directory).resolve();out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rig,skin,names=make_rig('Armature','source',100)
    rig.scale=(.01,.01,.01)
    bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
    b=rig.data.edit_bones[names['root']];b.tail=b.head+__import__('mathutils').Vector((15,0,0))
    bpy.ops.object.mode_set(mode='OBJECT')
    scene=bpy.context.scene;scene.render.fps=30;scene.frame_start=1;scene.frame_end=32
    for f in (1,32):
        pb=rig.pose.bones[names['hips']];pb.location.x=f*.02;pb.keyframe_insert('location',frame=f)
    rig.animation_data.action.name='mixamo.com|Layer0'
    bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);skin.select_set(True)
    fbx=out/'synthetic-centimeter-rig.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,add_leaf_bones=False,bake_anim=True,
        bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False)
    original=file_hash(fbx)
    with Library(out/'library') as lib:
        # Reuse the independently checksum-verified backend from this CI job.
        from asset_director import backend, transfer_review
        with Library(backend_library) as source_library:
            verified = backend.verify(source_library)
            shutil.copytree(verified, backend.location(lib), dirs_exist_ok=True)
        backend.verify(lib)
        dest=lib.root/'incoming'/'synthetic.fbx';shutil.copy2(fbx,dest)
        item=Asset('local','reference-identity-synthetic','Synthetic centimeter reference','model',
            'https://example.com/synthetic','CC0-1.0','https://creativecommons.org/publicdomain/zero/1.0/',
            'synthetic fixture',0,True,['.fbx'],['test'],'user_attested',
            [{'path':'incoming/synthetic.fbx','sha256':file_hash(dest),'size':dest.stat().st_size}])
        lib.put(item)
        def run(op,path=None,aid=None,options=None):
            j=jobs.prepare(lib,op,str(path) if path else None,aid,options)
            jobs.run(lib,j['id'],bpy.app.binary_path,180);d=lib.root/'jobs'/j['id']
            return j,load_json(d/'result.json')['data'],d
        indexed,_,_=run('index',aid=item.id)
        cid=jobs.index_result(lib,item.id,indexed['id'])['ids'][0]
        _,native,d=run('native-clip',aid=cid)
        bpy.ops.wm.open_mainfile(filepath=str(d/'result.blend'),load_ui=False,use_scripts=False)
        target=bpy.data.objects[native['source_object']];target_name=target.name
        if target.animation_data.action:target.animation_data.action.use_fake_user=True
        target.animation_data.action=None
        for track in target.animation_data.nla_tracks:track.mute=True
        for pb in target.pose.bones:pb.rotation_mode='QUATERNION';pb.matrix_basis=Matrix.Identity(4)
        bpy.context.view_layer.update()
        target_file=out/'new-working-reference.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(target_file),check_existing=False)
        untouched=file_hash(target_file)
        planned,proposal,_=run('transfer-plan',target_file,cid,{'target_object':target_name,
            'source_meters_per_unit':1,'target_meters_per_unit':1,'target_fps':30,
            'root_mode':'preserve_world','facing':{'mode':'anatomical'},'check_count':9})
        assert proposal['source_fingerprint']==proposal['target_fingerprint']
        assert proposal['alignment_method']=='exact identity for identical observed references'
        identity=[float(i==j) for i in range(4) for j in range(4)]
        assert all(m==identity for m in proposal['retarget_options']['alignment'].values())
        assert file_hash(target_file)==untouched and file_hash(fbx)==original
        approved=transfer_review.prepare(lib,dict(plan_job_id=planned['id'],
            plan_id=proposal['id'],reviewer='synthetic-fixture',
            reviewed_at='2026-09-15T00:00:00Z',approved=True))
        done=jobs.run(lib,approved['id'],bpy.app.binary_path,180)
        result_dir=lib.root/'jobs'/approved['id']
        data=load_json(result_dir/'result.json')['data']
        assert done['state']=='SUCCEEDED' and data['qa_roles']==proposal['target_roles']
        assert (result_dir/'result.blend').is_file()
        assert file_hash(target_file)==untouched and file_hash(fbx)==original
        assert approved['specification']['options']['slot']==lib.get(cid).metadata['slot']
        report={'reviewed_execution':'PASS','status':'PASS' ,'blender':bpy.app.version_string,'same_reference':True,
            'identity_alignment_count':len(proposal['retarget_options']['alignment']),
            'source_and_target_unchanged':True,'source_geometry':'generated centimeter-scale FBX, not user data'}
        atomic_json(out/'reference_identity_report.json',report);print(json.dumps(report))

if __name__=='__main__':main(*sys.argv[sys.argv.index('--')+1:])
