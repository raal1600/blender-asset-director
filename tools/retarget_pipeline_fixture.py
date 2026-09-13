"""Job-level, synthetic retarget/ground/floor/preview regression; NOT human motion.

Generated fixture geometry/motion is dedicated to CC0 solely for this test.
No production files, provider requests or local model inference are used.
"""
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Matrix
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]
from asset_director import blender_ops as ops, jobs
from asset_director.core import Asset, DirectorError, Library, atomic_json, file_hash, load_json
from headless_fixture import humanoid


def main(out, library):
    assert bpy.app.background
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    checks=[]
    def passed(name, **data):checks.append({'name':name,'status':'PASS',**data})
    with Library(library) as lib:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene=bpy.context.scene;scene.render.fps=24
        source, skin=humanoid('CaptureFixture')
        for f in range(1,26):
            source.pose.bones['hips'].location=(.02*(f-1),0,.02*math.sin(f/5))
            source.pose.bones['hips'].keyframe_insert('location',frame=f)
            source.pose.bones['spine'].rotation_mode='XYZ'
            source.pose.bones['spine'].rotation_euler.y=.15*math.sin(f/4)
            source.pose.bones['spine'].keyframe_insert('rotation_euler',frame=f)
        source.animation_data.action.name='Synthetic_One_Second_Travel'
        for c in ops.curves(source.animation_data.action,source.animation_data.action_slot):
            for k in c.keyframe_points:k.interpolation='LINEAR'
        file=lib.root/'incoming'/'pipeline-synthetic.glb'
        file.parent.mkdir(parents=True,exist_ok=True)
        bpy.ops.object.select_all(action='DESELECT');source.select_set(True);skin.select_set(True)
        bpy.ops.export_scene.gltf(filepath=str(file),export_format='GLB',use_selection=True,export_animations=True)
        rec={'path':file.relative_to(lib.root).as_posix(),'size':file.stat().st_size,'sha256':file_hash(file)}
        asset=Asset('local','pipeline-synthetic','Synthetic CI motion, not production','pack',
                    'https://github.com/raal1600/blender-asset-director', 'CC0-1.0',
                    'https://creativecommons.org/publicdomain/zero/1.0/','Synthetic fixture generator',0,True,
                    ['.glb'],['fixture'],'user_attested',[rec])
        lib.put(asset)
        def run(operation, input_path=None, asset_id=None, options=None):
            job=jobs.prepare(lib,operation,str(input_path) if input_path else None,asset_id,options)
            result=jobs.run(lib,job['id'],bpy.app.binary_path,180)
            return lib.root/'jobs'/job['id']/'result.blend',load_json(lib.root/'jobs'/job['id']/'result.json'),job
        _,report,j=run('index',asset_id=asset.id)
        indexed=jobs.index_result(lib,asset.id,j['id']); assert indexed['ids']
        clip=lib.get(indexed['ids'][0]);assert abs(clip.metadata['duration_seconds']-1)<1e-5
        assert clip.metadata['fps']==24
        passed('glTF indexed as seconds at 24 FPS')
        bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=30
        target,skin=humanoid('Recipient_019','other:',1.25)
        target.rotation_euler.z=.3;target.location=(4,-2,0)
        bpy.context.view_layer.update()
        target_name,skin_name=target.name,skin.name
        baseline=out/'target-baseline.blend';bpy.ops.wm.save_as_mainfile(filepath=str(baseline))
        original_hash=file_hash(baseline)
        # Changing target FPS must not rescale the source frame coordinates.
        # Identity target basis is a reviewed fixture alignment, not a general default.
        names=clip.metadata['roles'];target_roles=ops.rig_report(target)['roles']
        mapping={s:target_roles[r] for r,s in names.items() if r in target_roles}
        rotation=Matrix.Rotation(.3,3,'Z')
        pose=dict(rotation=[v for row in rotation for v in row],translation_bone=target_roles['hips'],
                  translation_scale=1.25,target_origin=list(target.matrix_world@target.pose.bones[target_roles['hips']].head),
                  ground_contact=dict(mesh=skin_name,vertex_groups=[target_roles['foot_l'],target_roles['foot_r']],height=0,max_correction=.25))
        options={'target_object':target_name,'target_fps':30,'mapping':mapping,
                 'alignment':{t:[v for row in Matrix.Identity(4) for v in row] for t in mapping.values()},'pose_space':pose}
        retargeted,report,_=run('retarget',baseline,clip.id,options)
        data=report['data'];assert abs(data['duration_seconds']-1)<1e-5,data
        assert data['source_frame_coordinate_fps']==24 and abs(data['frame_range'][1]-31)<1e-4
        assert data['ground_contact']['frames']>=30
        passed('different-FPS glTF retarget plus bounded sole correction',duration=data['duration_seconds'])
        action,slot=data['action'],data['slot']
        assembled,report,j=run('assemble',retargeted,options={'target_object':target_name,'fps':25,
                           'clips':[{'action':action,'slot':slot,'start':1,'playback_speed':.8}]})
        sequence=report['data'];end=sequence['strips'][0]['end']
        assert abs(sequence['strips'][0]['duration_seconds']-1.25)<1e-5
        assert sequence['frame_range'][1]==math.floor(end) and end>math.floor(end)
        bpy.ops.wm.open_mainfile(filepath=str(assembled),load_ui=False,use_scripts=False)
        rig=bpy.data.objects[target_name]
        bpy.context.scene.frame_set(bpy.context.scene.frame_end)
        moved=rig.pose.bones[target_roles['hips']].matrix.translation.copy()
        bpy.context.scene.frame_set(math.ceil(end))
        outside=rig.pose.bones[target_roles['hips']].matrix.translation.copy()
        assert (moved-outside).length>.01, (moved,outside)
        passed('fractional NLA end excludes the uncovered rest frame',strip_end=end,retained=sequence['frame_range'])
        # Real source has stationary root but traveling hips: no extra controller.
        try:
            ops.assemble(rig,{'fps':25,'clips':[{'action':action,'slot':slot,'start':1,'playback_speed':.8}],
                             'controller_speed':.1,'direction':[0,1,0],'travel_frames':[1,20]},'must-refuse')
            raise AssertionError('Traveling hips accepted external root controller')
        except DirectorError as e:assert e.code=='DOUBLE_ROOT_MOTION',e.code
        passed('hips-only travel rejects a second motion owner')
        floor,report,_=run('stage-floor',assembled,options=dict(size=[8,8],location=[4,-2,0],color=[.2]*3,
                                    grid_color=[.22]*3,tile_size=1,roughness=.8))
        assert report['data']['existing_geometry_materials_preserved']
        camera,_,_=run('camera-fit',floor,options={'subjects':[skin_name],'frames':[1,16,32],
                         'lens_mm':50,'direction':[.4,-1,.2],'margin':.2})
        lit,_,_=run('light-rig',camera,options={'subjects':[skin_name],
                         'lights':[{'type':'AREA','energy':150,'offset':[1,-1,2],'color':[1,1,1],'size_ratio':2}]})
        _,preview,preview_job=run('preview',lit,options={'frames':[32],'width':64,'height':64,'samples':1})
        assert preview['data']['production_settings_restored']
        assert file_hash(baseline)==original_hash and file_hash(file)==rec['sha256']
        repeated=jobs.run(lib,preview_job['id'],bpy.app.binary_path,180)
        assert repeated['state']=='SUCCEEDED'
        passed('job chain floor/camera/light/CPU preview/reuse with original hashes unchanged')
        # Timed import must restore caller FPS even when a glTF import fails.
        bpy.context.scene.render.fps=30
        created=ops.import_file(file,file.parent,frame_fps=24)
        assert bpy.context.scene.render.fps==30
        rigs=[o for o in created if o.type=='ARMATURE'];assert len(rigs)==1
        bindings,_=ops.clip_bindings(created)
        relevant=[b for b in bindings if b[0] in rigs];assert relevant
        assert abs((relevant[0][4]-relevant[0][3])/24-1)<1e-5
        passed('import coordinate-FPS selection restores caller scene FPS')
    result={'status':'PASS','blender_version':bpy.app.version_string,'checks':checks,
            'notice':'Synthetic geometry and motion only; no natural dance, full foot IK, or live capture claim.'}
    atomic_json(out/'retarget_pipeline_report.json',result);print(json.dumps(result))


if __name__=='__main__':main(*sys.argv[sys.argv.index('--')+1:])
