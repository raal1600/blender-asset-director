"""Real Blender C1/contact regression using generated, CC0 native rig fixtures.

Run: blender --background --factory-startup --python tools/stitch_continuity_fixture.py -- OUTPUT
No model, licensed assets, anatomically inferred contacts or retargeting claims.
"""
from pathlib import Path
import json
import math
import sys
import bpy
from mathutils import Vector, Quaternion
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from asset_director import action_layer as layer, motion_stitch, sequence_math as sm, action_timeline_contract
from asset_director.core import atomic_json, digest, file_hash

OUT = Path(sys.argv[sys.argv.index('--')+1]); OUT.mkdir(parents=True, exist_ok=False)
HEIGHT = 2.0
THRESHOLDS = {'position_m': .001*HEIGHT, 'orientation_deg': 1.,
              'linear_velocity_m_s': .05*HEIGHT, 'angular_velocity_deg_s': 5.,
              'foot_drift_m': .01*HEIGHT, 'penetration_m': .005*HEIGHT}


def frame(f):
    bpy.context.scene.frame_set(math.floor(f), subframe=f-math.floor(f))
    bpy.context.view_layer.update()


def observed(obj):
    rig = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    matrix = rig.matrix_world @ rig.pose.bones['Upper'].matrix
    return {'root': list(rig.matrix_world.translation), 'p': list(matrix @ Vector((0., .7, 0.))),
            'q': list(matrix.to_quaternion()),
            'feet': [list(rig.matrix_world @ rig.pose.bones[n].head) for n in ('Foot.L', 'Foot.R')]}


def derivative(center, near, far, dt, sign):
    # Three-point one-sided derivative at the SAME boundary timestamp.
    v = [(sign*(-3*c+4*n-f)/(2*dt)) for c,n,f in zip(center['root'],near['root'],far['root'])]
    # Body-space quaternion logarithms anchored to the boundary orientation.
    a = sm.qlog(sm.qmul(sm.inverse(center['q']), near['q']))
    b = sm.qlog(sm.qmul(sm.inverse(center['q']), far['q']))
    w = [sign*(4*x-y)/(2*dt) for x,y in zip(a,b)]
    return v,w


def add_stage(rig):
    """Visible skinned segments, authored camera and floor for evidence renders."""
    scene=bpy.context.scene
    material=bpy.data.materials.new('Synthetic teal');material.diffuse_color=(.055,.5,.4,1)
    for bone in rig.data.bones:
        head,tail=bone.head_local,bone.tail_local
        center=(head+tail)*.5;length=(tail-head).length
        if bone.name.startswith('Foot'):center.z=.05
        bpy.ops.mesh.primitive_cube_add(size=1, location=center)
        mesh=bpy.context.object;mesh.name='Skin '+bone.name
        mesh.rotation_euler=(tail-head).to_track_quat('Y','Z').to_euler()
        mesh.dimensions=(.15,length,.1 if bone.name.startswith('Foot') else .15)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        mesh.parent=rig
        mesh.vertex_groups.new(name=bone.name).add(list(range(len(mesh.data.vertices))),1,'REPLACE')
        mesh.modifiers.new('Native skin','ARMATURE').object=rig
        mesh.data.materials.append(material)
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.001));bpy.context.object.name='Ground'
    bpy.ops.object.camera_add(location=(4,-7,4));camera=bpy.context.object;camera.name='Evidence camera'
    camera.rotation_euler=(Vector((.5,0,1))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=5;scene.camera=camera
    bpy.ops.object.light_add(type='AREA',location=(2,-3,6));bpy.context.object.data.energy=700;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=5
    scene.render.engine='CYCLES';scene.cycles.samples=16
    scene.render.resolution_x=640;scene.render.resolution_y=480;scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new('Neutral world');scene.world.color=(.2,.2,.2)


def fixture(fps, extra, turn=False, native_root=False, speeds=(1., 1.), multi=False, rotation_mode='XYZ', zero_boundary=False, euler_branch=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene; scene.render.fps=fps; scene.frame_end=100
    data=bpy.data.armatures.new('CC0 synthetic hierarchy')
    obj=bpy.data.objects.new('Canonical native rig',data); scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active=obj; obj.select_set(True); bpy.ops.object.mode_set(mode='EDIT')
    for name,head,tail in [('Root',(0,0,1),(0,0,1.3)),('Upper',(0,0,1.3),(0,0,2)),
                           ('Foot.L',(-.2,0,0),(-.2,.25,0)),('Foot.R',(.2,0,0),(.2,.25,0))]:
        bone=data.edit_bones.new(name);bone.head=head;bone.tail=tail
        if name=='Upper':bone.parent=data.edit_bones['Root']
    for name,head,tail,parent in [('Head',(0,0,1.8),(0,0,2),'Upper'),
        ('Arm.L',(-.15,0,1.8),(-.8,0,1.5),'Upper'),('Arm.R',(.15,0,1.8),(.8,0,1.5),'Upper'),
        ('Leg.L',(-.2,0,1),(-.2,0,.05),'Root'),('Leg.R',(.2,0,1),(.2,0,.05),'Root')]:
        bone=data.edit_bones.new(name);bone.head=head;bone.tail=tail;bone.parent=data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in obj.pose.bones: bone.rotation_mode=rotation_mode
    add_stage(obj)
    for idx in range(2):
        action=bpy.data.actions.new('Idle' if idx==0 else 'Arm reach')
        obj.animation_data_create().action=action
        for name in ('Upper','Foot.L','Foot.R'):
            owner=obj.pose.bones[name]
            for f in (1,13,25):
                angle = ((0 if zero_boundary and idx else .9*idx) + .007*(f-1)) if name=='Upper' else 0
                q=Quaternion((0,0,1),angle)
                if rotation_mode=='QUATERNION':
                    if idx:q.negate()
                    owner.rotation_quaternion=q;prop='rotation_quaternion'
                elif rotation_mode=='AXIS_ANGLE':
                    owner.rotation_axis_angle=(angle,0,0,1);prop='rotation_axis_angle'
                else:
                    owner.rotation_euler=(.2,math.radians(100)+.1*idx+.007*(f-1),.3) if euler_branch and name=='Upper' else q.to_euler(rotation_mode)
                    prop='rotation_euler'
                owner.keyframe_insert(prop,frame=f)
        if native_root:
            for f in (1,13,25):
                obj.location=(10*idx+(f-1)*(.04+.03*idx),0,0)
                obj.keyframe_insert('location',frame=f)
        for c in layer.ops.curves(action):
            for k in c.keyframe_points:k.interpolation='LINEAR'
        slot=getattr(obj.animation_data,'action_slot',None)
        layer.add_strip(obj,action,slot,'Retained '+str(idx),1,[1,25],1).mute=True
    obj.animation_data.action=obj.animation_data.nla_tracks[0].strips[0].action
    if hasattr(obj.animation_data, 'action_slot'):obj.animation_data.action_slot=obj.animation_data.nla_tracks[0].strips[0].action_slot
    frame(1)
    inspection=layer.audit();p=next(p for p in inspection['performers'] if p['name']==obj.name)
    takes={t['action']:t for t in p['takes']}
    ca={'id':'clip_first','take_id':takes['Idle']['id'],'start':1,'frames':round(24/speeds[0])+1,'speed':speeds[0],'repeat_reviewed':False,'travel':None}
    cb=ca|{'id':'clip_second','take_id':takes['Arm reach']['id'],'start':ca['frames']+1+extra,'frames':round(24/speeds[1])+1,'speed':speeds[1],
           'transition':{'frames':extra,'match_phase':False}}
    if turn:
        ca['travel']={'delta_m':[0.,1.], 'meters_per_cycle':1.}
        cb['travel']={'delta_m':[-1.,0.], 'meters_per_cycle':1.}
        cb['heading_deg']=90.;cb['transition']['mode']='turn'
    clips=[ca,cb]
    if multi:clips.append(ca|{'id':'clip_third','start':cb['start']+cb['frames']+extra,'transition':{'frames':extra,'match_phase':False}})
    take_by_id={t['id']:t for t in takes.values()}
    stitch_times=[value for a,b in zip(clips,clips[1:]) for value in (action_timeline_contract.timing(a,take_by_id[a['take_id']])['native_end'],b['start'])]
    sources={a.name:digest(layer.channels(a)) for a in bpy.data.actions}
    request={'version':'action-layer-v1','audit_sha256':inspection['sha256'],'frame_range':[1,100],
             'changes':[{'performer':obj.name,'mode':'timeline','clips':clips}]}
    report=layer.apply(request,'continuity-'+str(fps)+'-'+str(extra))
    obj=bpy.data.objects['Canonical native rig']
    boundaries=[]
    for f in stitch_times:
        # h=1/64 frame: small versus 1/4 bake grid, large enough for Blender floats.
        h=1/64; rows={}
        for i in (-2,-1,0,1,2):frame(f+i*h);rows[i]=observed(obj)
        lv,lw=derivative(rows[0],rows[-1],rows[-2],h/fps,-1)
        rv,rw=derivative(rows[0],rows[1],rows[2],h/fps,1)
        # Extrapolate each side back to the same stitch timestamp, not adjacent frames.
        def extrap(key,sign):
            return [3*a-3*b+c for a,b,c in zip(rows[sign][key],rows[2*sign][key],sample(3*sign)[key])]
        def sample(i):frame(f+i*h);return observed(obj)
        position_error=math.dist(extrap('p',-1),extrap('p',1))
        logs={i:sm.qlog(sm.qmul(sm.inverse(rows[0]['q']), sample(i)['q'])) for i in (-3,-2,-1,1,2,3)}
        orient_a=[3*a-3*b+c for a,b,c in zip(logs[-1],logs[-2],logs[-3])]
        orient_b=[3*a-3*b+c for a,b,c in zip(logs[1],logs[2],logs[3])]
        boundaries.append({'frame':f,'position_m':position_error,'orientation_deg':math.degrees(math.dist(orient_a,orient_b)),
                           'linear_velocity_m_s':math.dist(lv,rv),
                           'angular_velocity_deg_s':math.degrees(math.dist(lw,rw))})
    contacts=[]
    # Known planted feet, keyed constant at ground in the two source Actions.
    # Travel cases intentionally have NO contact claim: source feet are stationary
    # in rig space, so an added path would slide them. This must never false-pass.
    if not turn and not native_root:
        for f in [a+(b-a)*i/64 for a,b in zip(stitch_times[::2],stitch_times[1::2]) for i in range(65)]:
            frame(f);contacts.append(observed(obj)['feet'])
    metrics={'boundaries':boundaries,'contacts':{'status':'MEASURED' if contacts else 'NOT_APPLICABLE',
             'provenance':'authored constant ground-level feet, full bridge interval' if contacts else 'travelling synthetic pose has no planted-foot annotations',
             'sample_count':len(contacts),
             'foot_drift_m':max((math.dist(row[j][:2],contacts[0][j][:2]) for row in contacts for j in range(2)),default=None),
             'penetration_m':max((max(0,-foot[2]) for row in contacts for foot in row),default=None)}}
    root_preservation=[]
    if native_root:
        for index,c in enumerate(clips):
            frame(c['start']);begin=observed(obj)['root']
            frame(c['start']+c['frames']-1);end=observed(obj)['root']
            expected=24*(.04+.03*(index%2))
            error=math.dist([end[i]-begin[i] for i in range(3)],[expected,0.,0.])
            root_preservation.append({'clip_id':c['id'],'expected_displacement_m':[expected,0.,0.],'error_m':error})
    preserved=all(digest(layer.channels(bpy.data.actions[n]))==s for n,s in sources.items())
    folder=OUT/(str(fps)+'fps-'+str(extra)+'frames'+('-turn' if turn else '-native-root' if native_root else '')+('-speed-'+str(speeds[0])+'-'+str(speeds[1]) if speeds!=(1.,1.) else '')+('-multi' if multi else '')+('-'+rotation_mode if rotation_mode!='XYZ' else '')+('-euler-branch' if euler_branch else ''));folder.mkdir()
    samples=[]
    for f in sorted(set([f for c in clips for f in (c['start'],c['start']+(c['frames']-1)/2,c['start']+c['frames']-1)]+[b+v for b in stitch_times for v in (-1,-.25,0,.25,1)])):
        frame(f); samples.append({'frame':f,**observed(obj)})
    acceptance_report=folder/'acceptance-report.json'; atomic_json(acceptance_report,report)
    result=folder/'result.blend';bpy.ops.wm.save_as_mainfile(filepath=str(result));layer.verify_saved(report,result)
    # verify_saved reloads in this process; the acceptance runner also uses a NEW
    # Blender process to reopen every artifact via --verify in this same script.
    failures=[(m,k,m[k]) for m in boundaries for k in ('position_m','orientation_deg','linear_velocity_m_s','angular_velocity_deg_s') if m[k]>THRESHOLDS[k]]
    failures += [('native-root-preservation','position_m',row['error_m']) for row in root_preservation if row['error_m']>THRESHOLDS['position_m']]
    if contacts:
        failures += [('contacts',k,metrics['contacts'][k]) for k in ('foot_drift_m','penetration_m') if metrics['contacts'][k]>THRESHOLDS[k]]
    return {'fps':fps,'fps_base':bpy.context.scene.render.fps_base,'extra_frames':extra,'turn':turn,'native_root':native_root,
            'result':str(result),'result_sha256':file_hash(result),'acceptance_report':str(acceptance_report),'metrics':metrics,'samples':samples,
            'rig':'Canonical native rig','character_height_m':HEIGHT,'stitch_timestamps':stitch_times,'source_fps':[fps*s for s in speeds],'clip_timing':clips,
            'source_channel_hashes':sources,'rotation_mode':rotation_mode,'root_preservation':root_preservation,
            'preserved':preserved,'reopened':report['reopened'],'status':'PASS' if not failures and preserved else 'FAIL',
            'failures':failures,'thresholds':THRESHOLDS}

results=[]
completed=False
try:
    for fps in (24,30,60):
        for extra in (2,12):results.append(fixture(fps,extra))
    results.append(fixture(60,2,True))
    results.append(fixture(30,12,True))
    results.append(fixture(30,6,native_root=True))
    results.append(fixture(30,6,speeds=(.8,2.)))
    results.append(fixture(30,6,native_root=True,multi=True))
    results.append(fixture(60,2,rotation_mode='QUATERNION'))
    results.append(fixture(60,2,rotation_mode='AXIS_ANGLE',zero_boundary=True))
    results.append(fixture(30,6,speeds=(1.1,1.1)))
    results.append(fixture(60,2,euler_branch=True))
    completed=True
finally:
    atomic_json(OUT/'RESULTS.json',{'status':'PASS' if completed and results and all(r['status']=='PASS' for r in results) else 'FAIL',
        'input_kind':'GENERATED_CC0','character_height_m':HEIGHT,
        'derivative_method':'second-order one-sided at same timestamp; h=1/64 scene frame; quaternion logarithms in boundary body frame',
        'completed':completed,'results':results,'blender':bpy.app.version_string})
assert results and all(r['status']=='PASS' for r in results), 'Continuity regression: inspect RESULTS.json'
