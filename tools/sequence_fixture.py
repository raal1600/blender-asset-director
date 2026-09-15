"""Real synthetic export/index/plan/retarget/sequence workflow, for Actions only.

No private or downloaded animation bytes. Two generated FBXs deliberately share
one generic source Action label. A full 1113-frame take is transferred at 24 FPS,
then sequenced at 30 FPS on a translated/rotated, opaque-named existing target.
Run background/factory Blender -- OUTPUT_DIRECTORY DISPOSABLE_LIBRARY.
"""
from pathlib import Path
import copy
import json
import math
import os
import sys
import time
import bpy
from mathutils import Matrix, Quaternion, Vector
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from transfer_planning_fixture import make_rig, skin_signature
from asset_director import jobs, local_motion as lm, license_policy as lp, blender_ops as ops
from asset_director import transfer_review as tr, sequence_review as sr, sequence_blender as sb
from asset_director.core import Library, DirectorError, atomic_json, load_json, file_hash


def export_take(path, frames, scale, travel, phase, root_axis='X'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rig,skin,n=make_rig('GeneratedSource','source',scale)
    # FBX reconstructs tails and auto-connects coincident children. Use a
    # horizontal floor control; retain the collinear case as a negative test.
    if root_axis == 'X':
        bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
        root=rig.data.edit_bones[n['root']];root.tail=root.head+Vector((.15*scale,0,0))
        bpy.ops.object.mode_set(mode='OBJECT')
    else:
        assert root_axis == 'Z'
    scene=bpy.context.scene;scene.render.fps=30;scene.frame_start=1;scene.frame_end=frames
    for f in sorted({1,frames,*range(2,frames, max(1,frames//24))}):
        scene.frame_set(f)
        u=(f-1)/(frames-1)
        hips=rig.pose.bones[n['hips']];hips.location=(travel*scale*u,0,0)
        hips.keyframe_insert('location',frame=f)
        for name,sign in [('upperarm_l',1),('upperarm_r',-1),('index_1_l',1),('index_1_r',-1)]:
            pb=rig.pose.bones[n[name]];pb.rotation_mode='QUATERNION'
            pb.rotation_quaternion=Quaternion((1,0,0),sign*(.12*math.sin(u*math.pi*2+phase)))
            pb.keyframe_insert('rotation_quaternion',frame=f)
    action=rig.animation_data.action;action.name='Armature|mixamo.com|Layer0'
    for c in ops.curves(action,rig.animation_data.action_slot):
        for k in c.keyframe_points:k.interpolation='LINEAR'
    samples=[]
    for f in (1,frames):
        scene.frame_set(f);bpy.context.view_layer.update()
        ev=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        samples.append((ev.matrix_world@ev.pose.bones[n['hips']].matrix).translation.copy())
    expected=Vector((travel*scale,0,0))
    assert ((samples[1]-samples[0])-expected).length/scale < 1e-5, {
        'stage':'authored synthetic source','measured':[list(v) for v in samples],
        'expected_displacement':list(expected)}
    scene.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);skin.select_set(True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,add_leaf_bones=False,bake_anim=True,
                            bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False)
    old=time.time()-10;os.utime(path,(old,old))


def pose(target,f):
    bpy.context.scene.frame_set(math.floor(f),subframe=f-math.floor(f))
    bpy.context.view_layer.update();ev=target.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return {b.name:(ev.matrix_world@b.matrix).copy() for b in ev.pose.bones}


def original_pose(target,action,slot, f):
    """Independent oracle: direct original Action, no sequence helper transform."""
    ad=target.animation_data;prior=ad.action;prior_slot=ad.action_slot
    tracks=[(t,t.mute) for t in ad.nla_tracks]
    basis={p.name:p.matrix_basis.copy() for p in target.pose.bones}
    oldframe=bpy.context.scene.frame_current+bpy.context.scene.frame_subframe
    for t,_ in tracks:t.mute=True
    try:
        ops.assign(target,action,slot)
        return pose(target,f)
    finally:
        ad.action=prior
        if prior:ad.action_slot=prior_slot
        for p in target.pose.bones:p.matrix_basis=basis[p.name]
        for t,mute in tracks:t.mute=mute
        pose(target,oldframe)


def main(out,library):
    assert bpy.app.background
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    inbox=out/'generated-inbox';inbox.mkdir();checks=[]
    def passed(name,**data):
        checks.append({'name':name,'status':'PASS',**data})
        atomic_json(out/'sequence_progress.json',{'status':'INCOMPLETE','checks':checks})
    def fail(call,code):
        try:call();raise AssertionError('Expected '+code)
        except DirectorError as e:assert e.code==code,(e.code,code)
    export_take(inbox/'A.fbx',32,1,.92,.2)
    export_take(inbox/'B.fbx',1113,100,.35,1.0)
    source_hashes={p.name:(file_hash(p),p.stat().st_mtime_ns) for p in inbox.iterdir()}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    target,skin,n=make_rig('ExistingTarget','target',1.18)
    for i,(role,old) in enumerate(list(n.items())):
        new=f'Joint_{i:03d}_CUSTOM';target.data.bones[old].name=new;n[role]=new
    roles={r:b for r,b in n.items() if r!='root'}
    target.location=(2.3,-1.1,.2);target.rotation_euler.z=math.radians(17)
    for p in target.pose.bones:p.rotation_mode='QUATERNION'
    assert ops.rig_report(target)['anatomical_height'] is None
    head=target.pose.bones[n['head']]
    for f,a in [(1,0),(32,.02)]:
        head.rotation_quaternion=Quaternion((1,0,0),a);head.keyframe_insert('rotation_quaternion',frame=f)
    prior=target.animation_data.action;prior.use_fake_user=True
    target.animation_data.action=None
    for p in target.pose.bones:p.matrix_basis=Matrix.Identity(4)
    target.data.bones[n['root']].hide=True;target.data.show_bone_custom_shapes=False
    bpy.context.scene.render.fps=30;bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    target_name,skin_name=target.name,skin.name;fingerprint=ops.rig_report(target,roles)['fingerprint']
    skin_hash=skin_signature(skin);prior_name=prior.name;prior_signature=sb.signature(prior,None)
    base=out/'existing-target.blend';bpy.ops.wm.save_as_mainfile(filepath=str(base));base_hash=file_hash(base)
    foot_ids=[v.index for v in skin.data.vertices if any(g.group==skin.vertex_groups[n['foot_l']].index for g in v.groups)]
    ground=min((skin.matrix_world@skin.data.vertices[i].co).z for i in foot_ids)
    with Library(library) as lib:
        def run(op,path=None,aid=None,options=None):
            j=jobs.prepare(lib,op,str(path) if path else None,aid,options)
            jobs.run(lib,j['id'],bpy.app.binary_path,600)
            d=lib.root/'jobs'/j['id'];return j,load_json(d/'result.json')['data'],d
        root=lm.add_root(lib,str(inbox),'mixamo')['root'];lm.sync(lib,root['id'])
        evidence=[]
        for name,url in [('faq',lp.FAQ),('terms',lp.TERMS)]:
            p=lib.root/'licenses'/('sequence-synthetic-'+name+'.txt')
            p.write_text('Synthetic fixture evidence only, NOT Adobe terms, acquisition or license permission.')
            evidence.append({'url':url,'file':lp.file_ref(lib,p.relative_to(lib.root).as_posix())})
        review=lm.review_root(lib,root['id'],dict(policy=lp.POLICY,reviewer='synthetic-fixture',reviewed_at='2026-09-15T00:00:00Z',
                      official_downloads_attested=True,terms_reviewed=True,include_future_files=False,evidence=evidence))
        synced=lm.sync(lib,root['id'],index=True,blender=bpy.app.binary_path)
        assert synced['status']=='COMPLETE',synced
        clips={}
        for item in synced['roots'][0]['assets']:
            parent=lib.get(item['asset_id']);clips[parent.title]=lib.get(parent.metadata['indexed_clips'][0])
        assert len(clips)==2,clips.keys()
        clips=[clips[k] for k in sorted(clips)]
        assert clips[0].metadata['action']==clips[1].metadata['action']
        assert clips[0].local_files[0]['sha256']!=clips[1].local_files[0]['sha256']
        assert abs(clips[1].metadata['duration_seconds']-1112/30)<1e-5
        indexed_displacements=[]
        for clip,units,wanted in zip(clips,(1,100),(.92,.35)):
            samples=clip.metadata['samples']
            displacement=(Vector(samples[-1]['hips'])-Vector(samples[0]['hips']))/units
            assert (displacement-Vector((wanted,0,0))).length < 1e-5, {
                'stage':'indexed FBX','measured_m':list(displacement),'expected_m':wanted}
            indexed_displacements.append(list(displacement))
        passed('real generated FBX intake: same label, distinct bytes, full 37-second take',
               indexed_anchor_displacements_m=indexed_displacements)
        transfers=[];plans=[]
        for i,clip in enumerate(clips):
            opts=dict(target_object=target_name,target_roles=roles,source_meters_per_unit=1 if i==0 else .01,
                      target_meters_per_unit=1,target_fps=30 if i==0 else 24,root_mode='morphology_scaled',
                      facing={'mode':'anatomical'},check_count=33)
            if i==1:
                fail(lambda:jobs.prepare(lib,'transfer-plan',str(base),clip.id,opts),'RESOURCE_LIMIT')
                opts['max_output_intervals']=1200
            j,p,d=run('transfer-plan',base,clip.id,opts);plans.append(p)
            approved=tr.prepare(lib,dict(plan_job_id=j['id'],plan_id=p['id'],reviewer='synthetic-fixture',
                                         reviewed_at='2026-09-15T00:00:00Z',approved=True))
            jobs.run(lib,approved['id'],bpy.app.binary_path,600)
            td=lib.root/'jobs'/approved['id'];data=load_json(td/'result.json')['data']
            assert data['qa_roles']==roles and data['target_fingerprint']==fingerprint
            assert abs(data['duration_seconds']-clip.metadata['duration_seconds'])<1e-6
            displacement=Vector(data['samples'][-1]['hips'])-Vector(data['samples'][0]['hips'])
            rotation=Matrix([p['retarget_options']['pose_space']['rotation'][k:k+3] for k in (0,3,6)])
            native=Vector(clip.metadata['samples'][-1]['hips'])-Vector(clip.metadata['samples'][0]['hips'])
            expected=rotation@native*p['units']['runtime_translation_scale']
            assert (displacement-expected).length < 1e-4, {
                'stage':'retargeted anchor','measured':list(displacement),'expected':list(expected)}
            transfers.append((approved,data,td))
        assert abs(transfers[1][1]['frame_range'][1]-(1+1112*24/30))<1e-5
        assert transfers[1][1]['scene_frame_range'][1]==891
        assert file_hash(base)==base_hash
        passed('actual reviewed long retarget, separate units, opaque roles, 30-to-24 FPS and fractional endpoint',
               long_seconds=transfers[1][1]['duration_seconds'],long_end=transfers[1][1]['frame_range'][1])
        contact={'mesh':skin_name,'feet':{'left':[n['foot_l']],'right':[n['foot_r']]},'ground_z':ground,
                 'tolerance_m':.001,'near_ground_m':.02,'glide_speed_m_s':.001}
        request=dict(target_object=target_name,clips=[{'job_id':x[0]['id']} for x in transfers],fps=30,meters_per_unit=1,
                     joins=[{'duration_seconds':.413,'yaw_degrees':25,'placement':'continue_velocity','subdivisions':4}],
                     budget={'max_duration_seconds':60,'max_pose_samples':4096,'max_created_keys':1500000,
                             'max_contact_samples':512,'max_mesh_evaluations':1000000},contact=contact)
        j,p,d=run('sequence-plan',base,options=request)
        assert p['full_clips'] and not p['source_time_warp']
        assert p['roles']==roles and p['anchor']==n['hips'] and not (d/'result.blend').exists()
        assert p['joins'][0]['unaligned_anchor_gap_m']>.75,p['joins'][0]
        assert abs(p['duration_seconds']-(31/30+1112/30+.413))<1e-5
        assert p['timeline'][1]['source_range']==transfers[1][1]['frame_range']
        hashes={x.name:file_hash(x) for x in d.iterdir() if x.is_file()}
        jobs.run(lib,j['id'],bpy.app.binary_path,600)
        assert hashes=={x.name:file_hash(x) for x in d.iterdir() if x.is_file()}
        passed('read-only plan binds full ranges/permissions and exposes naive snap-back',gap_m=p['joins'][0]['unaligned_anchor_gap_m'])
        approval=dict(plan_job_id=j['id'],plan_id=p['id'],reviewer='synthetic-fixture',reviewed_at='2026-09-15T00:00:00Z',approved=True)
        fail(lambda:sr.prepare(lib,approval|{'plan_id':'sq_'+'0'*64}),'STALE_SEQUENCE_BINDING')
        ej=sr.prepare(lib,approval);jobs.run(lib,ej['id'],bpy.app.binary_path,600)
        ed=lib.root/'jobs'/ej['id'];result=load_json(ed/'result.json')['data'];manifest=load_json(ed/'sequence.json');output=ed/'result.blend'
        bpy.ops.wm.open_mainfile(filepath=str(output),load_ui=False,use_scripts=False)
        target=bpy.data.objects[target_name];skin=bpy.data.objects[skin_name]
        assert ops.rig_report(target,roles)['fingerprint']==fingerprint and skin_signature(skin)==skin_hash
        assert sb.signature(bpy.data.actions[prior_name],None)==prior_signature
        assert target.data.bones[n['root']].hide and len(result['strips'])==3
        assert result['performance']=='PENDING' and result['human']=='NOT_ESTABLISHED'
        grants=sorted({lib.get(c.id).metadata['license_grant'] for c in clips})
        assert lp.derivation(lib,file_hash(output))==grants
        worst=0.;rot_worst=0.
        for i,t in enumerate(manifest['timeline']):
            original=manifest['source_original_signatures'][i];action=bpy.data.actions[original['imported_action']]
            matrix=Matrix([t['alignment'][k:k+4] for k in (0,4,8,12)])
            for u in (0,.001,.25,.5,.999,1):
                native=t['source_range'][0]+u*(t['source_range'][1]-t['source_range'][0])
                oracle=original_pose(target,action,original['slot'],native)
                actual=pose(target,t['start']+u*(t['end']-t['start']))
                for role,name in roles.items():
                    expected=matrix@oracle[name]
                    worst=max(worst,(expected.translation-actual[name].translation).length)
                    rot_worst=max(rot_worst,1-abs(expected.to_quaternion().normalized().dot(actual[name].to_quaternion().normalized())))
        assert worst<.0001,(worst,rot_worst)
        assert rot_worst<1e-6,(worst,rot_worst)
        passed('saved sequence matches full original clips after reviewed planar placement, including fractional last key',
               max_position_error_m=worst,max_quaternion_one_minus_abs_dot=rot_worst)
        cj,check,cd=run('sequence-check',output,options={'sequence_job_id':ej['id']})
        assert check['qa_roles']==roles and len(check['endpoint_errors'])==2
        assert all(e['status']=='PASS' for e in check['endpoint_errors']) and len(check['seams'])==2
        assert check['contact_batches'] and all(c['repair_applied'] is False for c in check['contact_batches'])
        states={row[foot]['state'] for c in check['contact_batches'] for row in c['samples'] for foot in ('left','right')}
        assert 'GLIDE_CANDIDATE' in states,states
        assert check['scene_frame_end']==math.ceil(manifest['final_key_frame'])
        passed('bound reviewed roles and dense transition contact diagnostics never lock deliberate gliding',
               endpoints=check['endpoint_errors'],seams=check['seams'],contact_states=sorted(states))
        track=target.animation_data.nla_tracks.get(manifest['strips'][0]['track']);track.strips[0].influence=.5
        fail(lambda:sb.check(target,manifest),'SEQUENCE_STATE_CHANGED');track.strips[0].influence=1
        track.is_solo=True;fail(lambda:sb.check(target,manifest),'SEQUENCE_STATE_CHANGED');track.is_solo=False
        bpy.context.scene.frame_end-=1;fail(lambda:sb.check(target,manifest),'SEQUENCE_STATE_CHANGED')
        bpy.context.scene.frame_end+=1
        passed('muted/influence/solo/range drift and stale review are not accepted')
        alternate=copy.deepcopy(request);alternate['joins'][0].update(placement='match_endpoint',yaw_degrees=-15,duration_seconds=.35)
        aj,ap,ad=run('sequence-plan',base,options=alternate)
        ae=sr.prepare(lib,approval|{'plan_job_id':aj['id'],'plan_id':ap['id']});jobs.run(lib,ae['id'],bpy.app.binary_path,600)
        qa=load_json(lib.root/'jobs'/ae['id']/'result.json')['data']['qa']
        assert all(x['position_error_m']<.0001 for x in qa['endpoint_errors'])
        passed('alternative explicit yaw and endpoint placement retain evaluated pose boundaries')
        hashes={x.name:file_hash(x) for x in ed.iterdir() if x.is_file()};jobs.run(lib,ej['id'],bpy.app.binary_path,600)
        assert hashes=={x.name:file_hash(x) for x in ed.iterdir() if x.is_file()}
        assert source_hashes=={x.name:(file_hash(x),x.stat().st_mtime_ns) for x in inbox.iterdir()}
        assert file_hash(base)==base_hash
        lp.revoke(lib,review['review_id'],'synthetic-fixture-completed')
        fail(lambda:jobs.read_job(lib,ej['id']),'LICENSE_REVOKED')
        passed('idempotence, original-file/action/skin preservation and both-source license revocation')
    result={'status':'PASS','blender_version':bpy.app.version_string,'checks':checks,
            'performance':'PENDING','human':'NOT_ESTABLISHED','private_assets':'NOT_USED',
            'notice':'Generated FBXs only. Numeric continuity is not natural dancing or user playback acceptance.'}
    atomic_json(out/'sequence_report.json',result);print(json.dumps({'status':'PASS','checks':len(checks)}))

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    try:main(*args)
    except Exception:
        import traceback
        atomic_json(Path(args[0])/'sequence_failure.json',{'status':'FAIL','traceback':traceback.format_exc()[-12000:]})
        raise
