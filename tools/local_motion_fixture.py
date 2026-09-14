"""Actual Blender local-inbox integration; generated FBX, not Adobe source data.

Run in factory/background Blender -- OUTPUT_DIRECTORY DISPOSABLE_LIBRARY.
The library needs the existing verified retarget backend; no new downloads here.
"""
from pathlib import Path
import json
import math
import os
import sys
import time
import bpy
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from headless_fixture import humanoid
from asset_director import jobs, local_motion as lm, license_policy as lp, motion_assets as ma, blender_ops as ops
from asset_director.core import Library, DirectorError, atomic_json, file_hash, load_json
from asset_director.motion_scout import search


def main(out,library):
    assert bpy.app.background
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    inbox=out/'manual-downloads'/'Mixamo';inbox.mkdir(parents=True,exist_ok=True);checks=[]
    def passed(name,**values):checks.append({'name':name,'status':'PASS',**values})
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source,skin=humanoid('SYNTHETIC_Source',prefix='mixamorig:')
    bpy.context.view_layer.objects.active=source;bpy.ops.object.mode_set(mode='EDIT')
    bones=source.data.edit_bones
    b=bones.new('mixamorig:Spine1');b.head=(0,0,1.32);b.tail=(0,0,1.44);b.parent=bones['mixamorig:spine']
    c=bones.new('mixamorig:Spine2');c.head=(0,0,1.44);c.tail=(0,0,1.6);c.parent=b
    bones['mixamorig:head'].parent=c;bpy.ops.object.mode_set(mode='OBJECT')
    sc=bpy.context.scene;sc.render.fps=30;sc.frame_start=1;sc.frame_end=32
    for frame in range(1,33):
        hips=source.pose.bones['mixamorig:hips'];hips.location.x=(frame-1)*.002;hips.keyframe_insert('location',frame=frame)
        for name,phase in [('thigh_l',0),('thigh_r',math.pi)]:
            pb=source.pose.bones['mixamorig:'+name];pb.rotation_mode='XYZ';pb.rotation_euler.x=.15*math.sin(frame/6+phase)
            pb.keyframe_insert('rotation_euler',frame=frame)
    action=source.animation_data.action;action.name='Armature|mixamo.com|Layer0'
    for c in ops.curves(action,source.animation_data.action_slot):
        for k in c.keyframe_points:k.interpolation='LINEAR'
    bpy.ops.object.select_all(action='DESELECT');source.select_set(True);skin.select_set(True);bpy.context.view_layer.objects.active=source
    fbx=inbox/'Synthetic Moonwalk Claim.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,add_leaf_bones=False,bake_anim=True,
                           bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False)
    old=time.time()-10;os.utime(fbx,(old,old));original=file_hash(fbx),fbx.stat().st_mtime_ns
    with Library(library) as lib:
        def run(op,path=None,aid=None,options=None):
            j=jobs.prepare(lib,op,str(path) if path else None,aid,options)
            done=jobs.run(lib,j['id'],bpy.app.binary_path,180);d=lib.root/'jobs'/j['id']
            return d/'result.blend',load_json(d/'result.json')['data'],done
        root=lm.add_root(lib,str(inbox),'mixamo')['root'];first=lm.sync(lib,root['id'])
        pid=first['roots'][0]['assets'][0]['asset_id'];assert lm.preflight(lib,pid)['import']=='BLOCKED'
        try:jobs.prepare(lib,'import',asset_id=pid);raise AssertionError('Folder name granted import permission')
        except DirectorError as e:assert e.code=='BLOCKED_POLICY'
        passed('manual folder copied without implicit license permission')
        evidence=[]
        for name,url in [('faq',lp.FAQ),('terms',lp.TERMS)]:
            p=lib.root/'licenses'/('local-motion-fixture-'+name+'.txt')
            p.write_text('Synthetic fixture evidence; not real Adobe terms, an acquisition or legal permission.')
            evidence.append({'url':url,'file':lp.file_ref(lib,p.relative_to(lib.root).as_posix())})
        review=lm.review_root(lib,root['id'],{'policy':lp.POLICY,'reviewer':'synthetic-ci-user',
            'reviewed_at':'2026-09-14T00:00:00Z','official_downloads_attested':True,'terms_reviewed':True,
            'include_future_files':False,'evidence':evidence})
        synced=lm.sync(lib,root['id'],index=True,blender=bpy.app.binary_path);assert synced['status']=='COMPLETE',synced
        parent=lib.get(pid);assert len(parent.metadata['indexed_clips'])==1,parent.metadata
        clip=lib.get(parent.metadata['indexed_clips'][0]);gid=clip.metadata['license_grant']
        for r,n in [('spine','spine'),('spine_mid','Spine1'),('chest','Spine2')]:assert clip.metadata['roles'][r]=='mixamorig:'+n,clip.metadata['roles']
        assert clip.metadata['fps']==30 and abs(clip.metadata['duration_seconds']-31/30)<1e-5,clip.metadata
        assert 'Synthetic Moonwalk Claim' in clip.title and clip.metadata['semantic_evidence']=='FILENAME_CLAIM_ONLY'
        assert any(r['id']==clip.id for r in search(lib,'moonwalk','commercial')['results'])
        assert lm.preflight(lib,clip.id)['native_playback']=='READY'
        assert not lm.preflight(lib,clip.id,'raw_redistribution')['policy']['eligible']
        passed('reviewed FBX index, filename search, spine chain and derived clip permissions',clip_id=clip.id)
        job_files=lambda:{p.relative_to(lib.root).as_posix():(file_hash(p),p.stat().st_mtime_ns) for p in (lib.root/'jobs').rglob('*') if p.is_file()}
        before=job_files();manifests={p.name:p.read_bytes() for p in (lib.root/'manifests').glob('*.json')}
        again=lm.sync(lib,root['id'],index=True,blender=bpy.app.binary_path)
        assert again['roots'][0]['assets'][0]['index']=='REUSED_INDEX',again
        assert before==job_files() and manifests=={p.name:p.read_bytes() for p in (lib.root/'manifests').glob('*.json')}
        passed('second sync reuses copied bytes and completed index without worker or manifest writes')
        native,native_report,native_job=run('native-clip',aid=clip.id)
        bpy.ops.wm.open_mainfile(filepath=str(native),load_ui=False,use_scripts=False)
        rig=bpy.data.objects[native_report['source_object']];worst=0.
        for sample in clip.metadata['samples']:
            frame=sample['frame'];bpy.context.scene.frame_set(math.floor(frame),subframe=frame-math.floor(frame))
            ev=rig.evaluated_get(bpy.context.evaluated_depsgraph_get());actual=ev.matrix_world@ev.pose.bones['mixamorig:hips'].head
            worst=max(worst,max(abs(a-b) for a,b in zip(actual,sample['hips'])))
        assert worst<2e-5,worst
        assert not native_report['retargeted'] and not native_report['motion_edited']
        assert json.loads(bpy.context.scene[lp.SCENE_KEY])==[gid] and bpy.context.scene.frame_end==32
        assert abs(native_report['duration_seconds']-31/30)<1e-5
        passed('native character/action pairing preserves timing, final frame and indexed trajectory',max_pose_error=worst)
        native_hash=file_hash(native);names=[o.name for o in bpy.data.objects if o.type=='MESH']
        floor,_,_=run('stage-floor',native,options={'size':[4,4],'location':[0,0,0],'color':[.3]*3,'grid_color':[.2]*3,'tile_size':.5,'roughness':.7})
        assert lp.derivation(lib,file_hash(floor))==[gid]
        camera,_,_=run('camera-fit',floor,options={'subjects':names,'frames':[1,16,32],'lens_mm':50,'direction':[.4,-1,.2],'margin':.15})
        lit,_,_=run('light-rig',camera,options={'subjects':names,'lights':[{'type':'AREA','energy':150,'offset':[1,-1,2],'color':[1,1,1],'size_ratio':2}]})
        preview,prev,_=run('preview',lit,options={'frames':[16],'width':64,'height':64,'samples':1})
        assert prev['production_settings_restored'] and lp.derivation(lib,file_hash(preview))==[gid]
        passed('floor/camera/light/CPU preview preserve inherited project restrictions and production settings')
        export_opts={'target_object':native_report['source_object'],'action':native_report['action'],
            'start':native_report['frame_range'][0],'end':native_report['frame_range'][1],'sample_fps':30,
            'meters_per_unit':1,'source_to_canonical':[1,0,0,0,1,0,0,0,1],'roles':native_report['rig']['roles'],'project_use':'commercial',
            'source':{'provider':'mixamo','source_id':'synthetic-local-test','source_url':'https://www.mixamo.com/',
                      'capture_method':'generated','capture_evidence':'Synthetic generator, not human capture or Adobe data'},
            'rights':{'license_id':'CC0-1.0','license_url':'https://creativecommons.org/publicdomain/zero/1.0/',
                      'evidence':[evidence[0]['file']],'commercial':'allowed','adaptation':'allowed','raw_redistribution':'allowed',
                      'attribution':'Contradictory synthetic caller claim must not erase inherited scope'},
            'semantics':{'title':'Synthetic canonical motion','labels':['test'],'description':'Not performance acceptance'}}
        _,_,export_job=run('motion-export',native,options=export_opts)
        stored=ma.collect(lib,export_job['id']);record,_=ma.load(lib,stored['motion_id'])
        assert record['rights']['license_id']==lp.LICENSE and record['rights']['raw_redistribution']=='denied'
        assert record['rights']['review_grants']==[gid]
        passed('canonical export inherits scope rather than contradictory caller CC0 label',motion_id=stored['motion_id'])
        bpy.ops.wm.read_factory_settings(use_empty=True);target,_=humanoid('Target','target:')
        target_path=out/'disposable-target.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target_path));target_hash=file_hash(target_path)
        tr=ops.rig_report(target);common=sorted(set(clip.metadata['roles'])&set(tr['roles']))
        mapping={clip.metadata['roles'][r]:tr['roles'][r] for r in common}
        opts={'target_object':target.name,'target_fps':30,'mapping':mapping,
              'alignment':{n:[v for row in Matrix.Identity(4) for v in row] for n in mapping.values()},
              'pose_space':{'rotation':[1,0,0,0,1,0,0,0,1],'translation_bone':clip.metadata['roles']['hips'],
                            'translation_scale':1,'target_origin':list(target.pose.bones['target:hips'].head)}}
        retargeted,transfer,_=run('retarget',target_path,clip.id,opts)
        assert lp.derivation(lib,file_hash(retargeted))==[gid] and file_hash(target_path)==target_hash
        assert abs(transfer['duration_seconds']-31/30)<1e-4,transfer['duration_seconds']
        passed('indexed local motion retarget preserves timebase and scoped grants')
        assert file_hash(native)==native_hash and (file_hash(fbx),fbx.stat().st_mtime_ns)==original
        lp.revoke(lib,review['review_id'],'synthetic fixture complete')
        try:jobs.read_job(lib,native_job['id']);raise AssertionError('Revocation not enforced')
        except DirectorError as e:assert e.code=='LICENSE_REVOKED',e.code
        passed('revocation blocks future job reuse; original and prior working files unchanged')
        report={'status':'PASS','blender_version':bpy.app.version_string,'checks':checks,'performance':'PENDING',
                'human':'NOT_ESTABLISHED','original_source_unchanged':True,
                'notice':'Generated FBX and synthetic review evidence only; not actual Adobe origin/license or convincing dancing.'}
        atomic_json(out/'local_motion_report.json',report);print(json.dumps(report))

if __name__=='__main__':main(*sys.argv[sys.argv.index('--')+1:])
