"""Real Blender planning/approval/transfer with generated data, never user assets.

Run factory background Blender: -- OUTPUT_DIRECTORY DISPOSABLE_LIBRARY.
Existing pinned retarget backend required; no downloads inside this fixture.
"""
from pathlib import Path
import json
import math
import os
import sys
import time
import bpy
from mathutils import Matrix, Vector
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from headless_fixture import humanoid
from asset_director import jobs, blender_ops as ops, local_motion as lm, license_policy as lp
from asset_director import transfer_review as review, transfer_blender as tb
from asset_director.core import Library, atomic_json, file_hash, load_json, DirectorError, digest


def make_rig(label, flavor, scale=1):
    rig,skin=humanoid(label,scale=scale)
    bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT');b=rig.data.edit_bones
    mid=b.new('spine_mid');mid.head=(0,0,1.34*scale);mid.tail=(0,0,1.48*scale);mid.parent=b['spine']
    chest=b.new('chest');chest.head=mid.tail;chest.tail=(0,0,1.59*scale);chest.parent=mid
    neck=b.new('neck');neck.head=(0,0,1.59*scale);neck.tail=(0,0,1.65*scale);neck.parent=chest
    b['head'].head=(0,0,1.65*scale);b['head'].parent=neck
    for side,sgn in [('l',1),('r',-1)]:
        toe=b.new('toe_'+side);toe.head=(sgn*.12*scale,-.16*scale,.1*scale);toe.tail=(sgn*.12*scale,-.23*scale,.1*scale);toe.parent=b['foot_'+side]
        sh=b.new('shoulder_'+side);sh.head=(sgn*.08*scale,0,1.5*scale);sh.tail=b['upperarm_'+side].head;sh.parent=chest;b['upperarm_'+side].parent=sh
        for j,finger in enumerate(('thumb','index','middle','ring','pinky')):
            parent=b['hand_'+side]
            for i in (1,2,3):
                p=b.new(f'{finger}_{i}_{side}')
                p.head=(sgn*(.88+i*.03)*scale,(j-2)*.012*scale,1.5*scale)
                p.tail=(p.head.x+sgn*.03*scale,p.head.y,p.head.z);p.parent=parent;parent=p
    bpy.ops.object.mode_set(mode='OBJECT')
    rename={}
    for bone in rig.data.bones:
        name=bone.name
        if flavor=='source':
            table={'root':'Root','hips':'Hips','spine':'Spine','spine_mid':'Spine1','chest':'Spine2','neck':'Neck','head':'Head'}
            if name in table:n='mixamorig:'+table[name]
            elif any(name.startswith(f+'_') for f in ('thumb','index','middle','ring','pinky')):
                finger,i,side=name.split('_');n=f'mixamorig:{"Left" if side=="l" else "Right"}Hand{finger.title()}{i}'
            else:n='mixamorig:'+name
        else:
            table={'spine':'spine.001','spine_mid':'spine.002','chest':'spine.003'}
            if any(name.startswith(f+'_') for f in ('thumb','index','middle','ring','pinky')):
                finger,i,side=name.split('_');n=f'DEF-f_{finger}.{int(i):02d}.{side.upper()}'
            else:n='DEF-'+table.get(name,name)
        rename[name]=n
    for old,new in rename.items():rig.data.bones[old].name=new
    return rig,skin,rename


def skin_signature(obj):
    return digest({'vertices':[list(v.co) for v in obj.data.vertices],
                   'weights':[[(g.group,g.weight) for g in v.groups] for v in obj.data.vertices],
                   'groups':[g.name for g in obj.vertex_groups]})


def main(out,library):
    assert bpy.app.background
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);checks=[]
    def passed(name,**data):
        checks.append({'name':name,'status':'PASS',**data})
        atomic_json(out/'transfer_planning_progress.json',{'status':'INCOMPLETE','checks':checks})
    def fails(call,expected):
        try:call();raise AssertionError('Expected '+expected)
        except DirectorError as e:assert e.code==expected,(e.code,expected)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source,skin,sn=make_rig('Synthetic_Performer','source');scene=bpy.context.scene
    scene.render.fps=30;scene.frame_start=1;scene.frame_end=32
    for f in range(1,33):
        h=source.pose.bones[sn['hips']];h.location.x=(f-1)*.011;h.keyframe_insert('location',frame=f)
        for name,phase in [('thigh_l',0),('thigh_r',math.pi),('index_1_l',.8),('index_1_r',-.8)]:
            p=source.pose.bones[sn[name]];p.rotation_mode='XYZ';p.rotation_euler.x=.15*math.sin(f/6+phase);p.keyframe_insert('rotation_euler',frame=f)
    action=source.animation_data.action;action.name='SYNTHETIC_WALK_NOT_MOCAP'
    for c in ops.curves(action,source.animation_data.action_slot):
        for k in c.keyframe_points:k.interpolation='LINEAR'
    inbox=out/'inbox';inbox.mkdir();source_path=inbox/'Test Take.fbx'
    bpy.ops.object.select_all(action='DESELECT');source.select_set(True);skin.select_set(True)
    bpy.ops.export_scene.fbx(filepath=str(source_path),use_selection=True,add_leaf_bones=False,bake_anim=True,
                           bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False)
    t=time.time()-10;os.utime(source_path,(t,t));source_hash=file_hash(source_path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    target,target_skin,tn=make_rig('Other_Character','target',1.18)
    target_name,skin_name=target.name,target_skin.name
    target.rotation_euler.z=math.radians(67);target.location=(3,2,0)
    target.pose.bones[tn['head']].rotation_mode='XYZ'
    for f,a in [(1,0),(32,.05)]:
        target.pose.bones[tn['head']].rotation_euler.x=a;target.pose.bones[tn['head']].keyframe_insert('rotation_euler',frame=f)
    original_action_name=target.animation_data.action.name
    scene=bpy.context.scene;scene.render.fps=30;scene.frame_set(1)
    target_path=out/'existing-character.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target_path))
    target_hash=file_hash(target_path);target_fingerprint=ops.rig_report(target)['fingerprint'];skin_hash=skin_signature(target_skin)
    with Library(library) as lib:
        def run(op,path=None,aid=None,options=None):
            j=jobs.prepare(lib,op,str(path) if path else None,aid,options)
            done=jobs.run(lib,j['id'],bpy.app.binary_path,180);d=lib.root/'jobs'/j['id']
            return done,load_json(d/'result.json')['data'],d
        root=lm.add_root(lib,str(inbox),'mixamo')['root'];lm.sync(lib,root['id'])
        ev=[]
        for label,url in [('faq',lp.FAQ),('terms',lp.TERMS)]:
            p=lib.root/'licenses'/('transfer-synthetic-'+label+'.txt');p.write_text('Synthetic test evidence, NOT provider terms or an actual acquisition.')
            ev.append({'url':url,'file':lp.file_ref(lib,p.relative_to(lib.root).as_posix())})
        lm.review_root(lib,root['id'],dict(policy=lp.POLICY,reviewer='synthetic-fixture',reviewed_at='2026-09-14T00:00:00Z',
            official_downloads_attested=True,terms_reviewed=True,include_future_files=False,evidence=ev))
        synced=lm.sync(lib,root['id'],index=True,blender=bpy.app.binary_path)
        parent=lib.get(synced['roots'][0]['assets'][0]['asset_id']);clip=lib.get(parent.metadata['indexed_clips'][0])
        plan_options=dict(target_object=target_name,source_meters_per_unit=1,target_meters_per_unit=1,
                          target_fps=30,root_mode='morphology_scaled',facing={'mode':'anatomical'},check_count=65)
        planned,p,pdir=run('transfer-plan',target_path,clip.id,plan_options)
        assert p['status']=='REVIEW_REQUIRED' and len(p['mapping'])==52,p['mapping']
        assert p['retarget_options']['pose_space']['translation_bone']==tn['hips']
        assert abs(p['facing']['yaw_degrees']-67)<.01,p['facing']
        assert abs(p['units']['morphology_ratio']-1.18)<1e-4,p['units']
        assert not (pdir/'result.blend').exists() and file_hash(target_path)==target_hash
        assert not p['target_character']['inherited_grants'], 'Source grant was incorrectly attributed to target'
        assert p['id']=='tp_'+digest({k:v for k,v in p.items() if k!='id'})
        passed('52 mappings, measured yaw/scale, separate provenance and read-only proposal',pairs=len(p['mapping']),yaw=p['facing']['yaw_degrees'])
        hashes={x.name:file_hash(x) for x in pdir.iterdir() if x.is_file()}
        jobs.run(lib,planned['id'],bpy.app.binary_path,180)
        assert hashes=={x.name:file_hash(x) for x in pdir.iterdir() if x.is_file()}
        passed('completed plan reuse without another worker')
        approval=dict(plan_job_id=planned['id'],plan_id=p['id'],reviewer='synthetic-fixture',reviewed_at='2026-09-14T00:00:00Z',approved=True)
        fails(lambda:review.prepare(lib,approval|{'approved':False}),'TRANSFER_REVIEW_REQUIRED')
        approved=review.prepare(lib,approval)
        fails(lambda:review.checked_binding(lib,{**p['retarget_options'],'transfer_binding':approval,'target_fps':24}),'STALE_TRANSFER_BINDING')
        passed('approval binds exact options and inherited license evidence')
        done=jobs.run(lib,approved['id'],bpy.app.binary_path,180);result=lib.root/'jobs'/done['id']/'result.blend'
        data=load_json(result.parent/'result.json')['data']
        assert abs(data['duration_seconds']-31/30)<1e-5
        assert lp.derivation(lib,file_hash(result))==[clip.metadata['license_grant']]
        bpy.ops.wm.open_mainfile(filepath=str(result),load_ui=False,use_scripts=False)
        target=bpy.data.objects[data['target']];skin=bpy.data.objects[skin_name]
        assert ops.rig_report(target)['fingerprint']==target_fingerprint and skin_hash==skin_signature(skin)
        assert original_action_name in bpy.data.actions
        assert all(max(abs(v-1) for v in pb.scale)<1e-5 for pb in target.pose.bones)
        assert not any(c.keyframe_points for c in ops.curves(target.animation_data.action,target.animation_data.action_slot) if tn['root'] in c.data_path)
        passed('existing mesh/weights/rest/action, unit scales, timing, root and grants preserved')
        asset,src,act=tb.import_source(lib,planned['specification']);ops.assign(src,act,clip.metadata.get('slot'))
        source_rest={n:(src.matrix_world@src.data.bones[n].matrix_local).to_quaternion() for n in p['mapping']}
        actual_action=target.animation_data.action;actual_slot=target.animation_data.action_slot.identifier;target.animation_data.action=None
        for pb in target.pose.bones:pb.matrix_basis=Matrix.Identity(4)
        for n,v in p['retarget_options']['alignment'].items():target.pose.bones[n].matrix_basis=Matrix([v[i:i+4] for i in range(0,16,4)])
        bpy.context.view_layer.update();ref={n:(target.matrix_world@target.pose.bones[n].matrix).to_quaternion() for n in p['mapping'].values()}
        direction_error=0.
        for e in p['alignment_evidence']:
            end=tb.successor(e['role'],p['target_roles'])
            if end:
                delta=target.matrix_world.to_3x3()@(target.pose.bones[p['target_roles'][end]].head-target.pose.bones[e['target']].head)
                expected_direction=Vector(e['aligned_source_direction'])
                direction_error=max(direction_error,1-delta.normalized().dot(expected_direction.normalized()))
        assert direction_error<2e-5,direction_error
        passed('reference agrees with measured semantic head paths',max_direction_error=direction_error)
        ops.assign(target,actual_action,actual_slot)
        vals=p['retarget_options']['pose_space']['rotation'];w=Matrix([vals[i:i+3] for i in (0,3,6)]).to_quaternion();error=0.
        # FBX import may offset the first key. Match elapsed seconds, not equal
        # scene frame labels: the retargeted action always begins at frame one.
        output_start, output_end = data['frame_range']
        sfps=p['retarget_options']['source_fps'];tfps=data['fps']
        for i in range(32):
            out_frame=output_start+(output_end-output_start)*i/31
            src_frame=p['retarget_options']['start']+(out_frame-output_start)*sfps/tfps
            bpy.context.scene.frame_set(math.floor(src_frame),subframe=src_frame-math.floor(src_frame))
            bpy.context.view_layer.update()
            expected={}
            for s,t in p['mapping'].items():
                sq=(src.matrix_world@src.pose.bones[s].matrix).to_quaternion()
                expected[t]=w@sq@source_rest[s].inverted()@w.inverted()@ref[t]
            bpy.context.scene.frame_set(math.floor(out_frame),subframe=out_frame-math.floor(out_frame))
            bpy.context.view_layer.update()
            for t,q in expected.items():
                observed=(target.matrix_world@target.pose.bones[t].matrix).to_quaternion()
                error=max(error,1-abs(q.normalized().dot(observed.normalized())))
        assert error<2e-6,error
        passed('independent mapped world-rotation relation at matched times',
               max_quaternion_one_minus_dot=error,checkpoints=32,
               source_start=p['retarget_options']['start'],output_start=output_start)
        target.rotation_euler.z+=.02;bpy.context.view_layer.update()
        fails(lambda:tb.verify_execution(lib,src,target,act,clip.metadata.get('slot'),approved['specification']['options']),'STALE_TRANSFER_BINDING')
        passed('world-binding change rejected despite unchanged rest fingerprint')
        _,other,odir=run('transfer-plan',target_path,clip.id,plan_options|{'target_fps':24,'source_meters_per_unit':.5})
        assert abs(other['units']['unit_conversion']-.5)<1e-7 and abs(other['units']['morphology_ratio']-2.36)<1e-4
        alt_job=review.prepare(lib,approval|{'plan_job_id':odir.name,'plan_id':other['id']});jobs.run(lib,alt_job['id'],bpy.app.binary_path,180)
        alt=load_json(lib.root/'jobs'/alt_job['id']/'result.json')['data']
        assert abs(alt['duration_seconds']-31/30)<1e-5 and abs(alt['frame_range'][1]-25.8)<1e-5 and alt['scene_frame_range'][1]==26,alt
        passed('separate units/anatomy and changed FPS with final-key coverage')
        bpy.ops.wm.read_factory_settings(use_empty=True);probe,pskin,n=make_rig('ContactBody','target');scene=bpy.context.scene;scene.render.fps=30
        for f,x in [(1,0),(2,.05),(3,.1)]:
            pb=probe.pose.bones[n['hips']];pb.location=(x,0,0);pb.keyframe_insert('location',frame=f)
        # Pose-bone location channels are bone-local, not world coordinates.
        # Derive the downward handle offset from the actual unposed fixture basis.
        local_down=(probe.matrix_world@probe.data.bones[n['hips']].matrix_local).to_3x3().inverted()@Vector((0,0,-.04))
        for c in ops.curves(probe.animation_data.action,probe.animation_data.action_slot):
            for k in c.keyframe_points:k.interpolation='LINEAR'
            component=local_down[c.array_index]
            if abs(component)>1e-8:
                for k in c.keyframe_points:
                    k.interpolation='BEZIER';k.handle_left_type='FREE';k.handle_right_type='FREE'
                    k.handle_left=(k.co.x-1/3,k.co.y+component)
                    k.handle_right=(k.co.x+1/3,k.co.y+component)
        scene.frame_set(1);scene.frame_start=1;scene.frame_end=3;bpy.context.view_layer.update()
        deps=pskin.evaluated_get(bpy.context.evaluated_depsgraph_get());m=deps.to_mesh()
        ids=[v.index for v in pskin.data.vertices if any(g.group==pskin.vertex_groups[n['foot_l']].index for g in v.groups)]
        floor=min((deps.matrix_world@m.vertices[i].co).z for i in ids);deps.to_mesh_clear()
        # Independently establish that the TEST DATA really penetrates between
        # keys before asking contact-check to diagnose it. Do not reuse the
        # runtime reducer or inferred contact states to establish this oracle.
        frames=[1,1.5,2,2.5,3];expected={}
        foot_ids={side:[v.index for v in pskin.data.vertices if any(
            g.group==pskin.vertex_groups[n['foot_'+suffix]].index for g in v.groups)]
            for side,suffix in [('left','l'),('right','r')]}
        for f in frames:
            scene.frame_set(math.floor(f),subframe=f-math.floor(f))
            evaluated=pskin.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
            try:
                expected[f]={side:min((evaluated.matrix_world@mesh.vertices[i].co).z for i in selected)
                             for side,selected in foot_ids.items()}
            finally:evaluated.to_mesh_clear()
        for f in (1,2,3):
            assert all(abs(h-floor)<2e-6 for h in expected[f].values()),expected
        for f in (1.5,2.5):
            assert all(abs((h-floor)+.03)<2e-5 for h in expected[f].values()),expected
        passed('fixture independently contains world-vertical subframe penetration',
               measured_clearance={str(f):{side:h-floor for side,h in row.items()} for f,row in expected.items()})
        scene.frame_set(1)
        contact_path=out/'contact-original.blend';bpy.ops.wm.save_as_mainfile(filepath=str(contact_path));h=file_hash(contact_path)
        opts={'target_object':probe.name,'mesh':pskin.name,'feet':{'left':[n['foot_l']],'right':[n['foot_r']]},
              'ground_z':floor,'meters_per_unit':1,'tolerance_m':.001,'near_ground_m':.02,'glide_speed_m_s':.01,
              'frames':frames}
        _,contact,cdir=run('contact-check',contact_path,options=opts)
        for sample in contact['samples']:
            for side in ('left','right'):
                assert abs(sample[side]['minimum_z']-expected[sample['frame']][side])<2e-6,sample
        assert any(sample['left']['state']=='GLIDE_CANDIDATE' for sample in contact['samples'])
        assert contact['extrema']['integer_frames']['penetration_within_tolerance']
        assert not contact['extrema']['subframes']['penetration_within_tolerance'],contact
        assert contact['repair_applied'] is False and contact['channels_changed']==[] and contact['performance']=='PENDING'
        assert file_hash(contact_path)==h and not (cdir/'result.blend').exists()
        passed('evaluated subframe sole penetration measured without locking glide',extrema=contact['extrema'])
        assert source_hash==file_hash(source_path) and target_hash==file_hash(target_path)
        passed('source and target input preservation')
        report={'status':'PASS','blender_version':bpy.app.version_string,'checks':checks,'performance':'PENDING',
                'real_user_source':'NOT_RUN','live_ui_control':'NOT_RUN',
                'notice':'Synthetic transfer/contact evidence, not Mixamo/Quaternius acceptance, foot IK or continuous viewing.'}
        atomic_json(out/'transfer_planning_report.json',report);print(json.dumps(report))

if __name__=='__main__':main(*sys.argv[sys.argv.index('--')+1:])
