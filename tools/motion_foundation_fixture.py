"""Real job-chain regression of canonical motion and frozen clay anatomy.

Synthetic motion only; no performer assets, production files or live MCP. Run
with -- OUTPUT_DIRECTORY BACKEND_LIBRARY in a factory/background Blender.
"""
from pathlib import Path
import json
import math
import sys
import bpy
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from asset_director import jobs, blender_ops as ops, motion_assets as ma
from asset_director.core import Library, atomic_json, file_hash, load_json, DirectorError
from asset_director.motion_body import build_profile
from asset_director.motion_review import diagnostics
from asset_director.motion_scout import search
from headless_fixture import humanoid


def main(out,backend_library):
    assert bpy.app.background
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);checks=[]
    def passed(name,**v):checks.append({'name':name,'status':'PASS',**v})
    with Library(backend_library) as lib:
        terms=lib.root/'licenses/foundation-fixture.txt'
        terms.write_text('Synthetic fixture created by motion_foundation_fixture.py dedicated to CC0. Not human capture.')
        evidence={'path':terms.relative_to(lib.root).as_posix(),'sha256':file_hash(terms),'size':terms.stat().st_size}
        rights={'license_id':'CC0-1.0','license_url':'https://creativecommons.org/publicdomain/zero/1.0/',
          'evidence':[evidence],'commercial':'allowed','adaptation':'allowed','raw_redistribution':'allowed','attribution':'Synthetic CI fixture'}
        bpy.ops.wm.read_factory_settings(use_empty=True);sc=bpy.context.scene;sc.render.fps=24
        source,skin=humanoid('Source_Morphology');roles=ops.rig_report(source)['roles'];name=source.name
        for f in range(1,26):
            source.pose.bones['hips'].location=(.02*(f-1),0,0)
            source.pose.bones['hips'].keyframe_insert('location',frame=f)
            source.pose.bones['spine'].rotation_mode='XYZ';source.pose.bones['spine'].rotation_euler.y=.15*math.sin(f/4)
            source.pose.bones['spine'].keyframe_insert('rotation_euler',frame=f)
        action=source.animation_data.action;action_name=action.name
        for c in ops.curves(action,source.animation_data.action_slot):
            for k in c.keyframe_points:k.interpolation='LINEAR'
        sc.frame_start=1;sc.frame_end=25;sc.frame_set(7)
        original=out/'synthetic-source.blend';bpy.ops.wm.save_as_mainfile(filepath=str(original));baseline=file_hash(original)
        expected=[]
        for f in (1,13,25):sc.frame_set(f);expected.append(list(source.matrix_world@source.pose.bones['hips'].head))
        def run(op,path=None,options=None):
            job=jobs.prepare(lib,op,str(path) if path else None,options=options)
            done=jobs.run(lib,job['id'],bpy.app.binary_path,180);directory=lib.root/'jobs'/job['id']
            return directory/'result.blend',load_json(directory/'result.json')['data'],done
        export_opts={'target_object':name,'action':action_name,'start':1,'end':25,'sample_fps':24,
          'meters_per_unit':1,'source_to_canonical':[1,0,0,0,1,0,0,0,1],'roles':roles,
          'source':{'provider':'local','source_id':'synthetic-foundation','source_url':'https://github.com/raal1600/blender-asset-director',
                    'capture_method':'generated','capture_evidence':'Synthetic regression generator; not mocap'},
          'rights':rights,'semantics':{'title':'Synthetic Backslide','labels':['backslide'],'description':'CI fixture, not a convincing moonwalk'},
          'project_use':'commercial'}
        _,report,job=run('motion-export',original,export_opts)
        stored=ma.collect(lib,job['id']);mid=stored['motion_id'];record,samples=ma.load(lib,mid,samples=True)
        assert len(samples)==25 and abs(samples[-1]['time']-1)<1e-8
        hi=next(i for i,j in enumerate(record['skeleton']['joints']) if j['name']=='hips')
        for sample,exp in zip((samples[0],samples[12],samples[24]),expected):
            assert max(abs(a-b) for a,b in zip(sample['positions'][hi],exp))<2e-6
        assert ma.collect(lib,job['id'])['status']=='REUSED' and file_hash(original)==baseline
        passed('export evaluated source to immutable numeric record and reuse',motion_id=mid)
        assert any(x['id']==mid for x in search(lib,'moonwalking','commercial')['results'])
        passed('local metadata rediscovery without provider calls')
        imported,report,_=run('motion-source',options={'motion_id':mid,'project_use':'commercial','fps':30})
        bpy.ops.wm.open_mainfile(filepath=str(imported),load_ui=False,use_scripts=False)
        imported_rig=bpy.data.objects[report['source_object']]
        for frame,exp in zip((1,16,31),expected):
            bpy.context.scene.frame_set(frame)
            assert max(abs(a-b) for a,b in zip(imported_rig.pose.bones['hips'].head,exp))<2e-5
        passed('canonical source roundtrip preserves matched-time trajectory at 30 FPS')
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add(location=(10,4,1));bpy.context.object.name='KEEP_THIS_PROP'
        staging=out/'staging.blend';bpy.ops.wm.save_as_mainfile(filepath=str(staging));staging_hash=file_hash(staging)
        neutral,clay0,_=run('clay-proxy',staging,{'motion_id':mid,'project_use':'commercial'})
        altered,clay1,_=run('clay-proxy',staging,{'motion_id':mid,'project_use':'commercial',
          'length_scales':{'thigh_l':.7,'thigh_r':.7,'calf_l':.7,'calf_r':.7,
                           'upperarm_l':1.25,'upperarm_r':1.25,'forearm_l':1.25,'forearm_r':1.25}})
        profile0=build_profile(record['skeleton'],clay0['skeleton']);profile=build_profile(record['skeleton'],clay1['skeleton'])
        assert abs(profile0['chain_ratios']['leg_l']-1)<1e-5,profile0
        assert abs(profile['chain_ratios']['leg_l']-.7)<1e-4,profile
        assert abs(profile['chain_ratios']['arm_l']-1.25)<1e-4,profile
        assert file_hash(staging)==staging_hash
        bpy.ops.wm.open_mainfile(filepath=str(altered),load_ui=False,use_scripts=False)
        target=bpy.data.objects[clay1['armature']]
        assert 'KEEP_THIS_PROP' in bpy.data.objects and target.get('bad_morphology_locked') and not target.animation_data
        assert all(tuple(b.scale)==(1,1,1) for b in target.pose.bones) and clay1['rig']['skinned_vertices']>0
        passed('source-shaped and short-leg/long-arm proxies with frozen rest anatomy',leg_ratio=profile['chain_ratios']['leg_l'])
        origin=list(target.matrix_world@target.pose.bones[roles['hips']].head)
        options={'motion_id':mid,'project_use':'commercial','target_object':target.name,'target_fps':30,'target_meters_per_unit':1,
          'expected_source_fingerprint':record['skeleton']['source_fingerprint'],'expected_target_fingerprint':clay1['rig']['fingerprint'],
          'mapping':profile['mapping'],'alignment':{n:[v for row in Matrix.Identity(4) for v in row] for n in profile['mapping'].values()},
          'pose_space':{'rotation':[1,0,0,0,1,0,0,0,1],'translation_bone':roles['hips'],'translation_scale':1,
                        'translation_scale_xyz':profile['suggested_translation_scale_xyz'],'target_origin':origin}}
        retargeted,transfer,job=run('motion-retarget',altered,options)
        assert abs(transfer['duration_seconds']-1)<1e-5 and transfer['source_motion_id']==mid
        bpy.ops.wm.open_mainfile(filepath=str(retargeted),load_ui=False,use_scripts=False)
        target=bpy.data.objects[clay1['armature']];positions=[]
        for f in (1,31):bpy.context.scene.frame_set(f);positions.append(target.pose.bones[roles['hips']].head.copy())
        assert abs((positions[1]-positions[0]).x-.48*.7)<1e-4,positions
        assert ops.rig_report(target)['fingerprint']==clay1['rig']['fingerprint']
        passed('canonical bridge uses v0.5 transfer and measured root scaling',root_travel=(positions[1]-positions[0]).x)
        try:run('motion-retarget',altered,dict(options,expected_target_fingerprint='b'*64));raise AssertionError('Stale profile accepted')
        except DirectorError as e:assert e.code=='STALE_RETARGET_PROFILE',e.code
        passed('stale target fingerprint refused')
        _,audited,_=run('body-audit',retargeted,{'target_object':clay1['armature'],'meters_per_unit':1,
                         'source_to_canonical':[1,0,0,0,1,0,0,0,1],'roles':roles})
        assert audited['body_profile']['chains']['leg_l']['length_m']>0
        checked=diagnostics(record,samples);assert checked['performance']=='NOT_EVALUATED' and checked['contacts']=={}
        assert jobs.run(lib,job['id'],bpy.app.binary_path)['state']=='SUCCEEDED'
        passed('body audit and technical/performance separation; completed-job reuse')
        camera,_,_=run('camera-fit',retargeted,{'subjects':[clay1['mesh']],'frames':[1,16,31],
                           'lens_mm':50,'direction':[.4,-1,.2],'margin':.15})
        lit,_,_=run('light-rig',camera,{'subjects':[clay1['mesh']],
                   'lights':[{'type':'AREA','energy':150,'offset':[1,-1,2],'color':[1,1,1],'size_ratio':2}]})
        _,preview,_=run('preview',lit,{'frames':[16],'width':64,'height':64,'samples':1})
        assert preview['production_settings_restored'] and file_hash(original)==baseline and file_hash(staging)==staging_hash
        passed('actual clay/retarget/camera/light CPU preview and original-hash preservation')
        result={'status':'PASS','blender_version':bpy.app.version_string,'checks':checks,
          'notice':'Synthetic poses/segmented proxy; not authentic dance, IK, video inference or workstation acceptance.'}
        atomic_json(out/'motion_foundation_report.json',result);print(json.dumps(result))

if __name__=='__main__':main(*sys.argv[sys.argv.index('--')+1:])
