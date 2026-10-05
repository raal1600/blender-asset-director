"""Generated two-bone locomotion contact regressions through the real native path.

Authored planted intervals are explicit, nonempty and independent of bone names.
These slow analytic reference steps test contact continuity, not natural acting.
"""
from pathlib import Path
import json
import math
import sys
import bpy
from mathutils import Vector, Quaternion
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from asset_director import action_layer as layer, motion_contacts as contacts, sequence_math as sm
from asset_director.core import atomic_json,digest,DirectorError,file_hash

without_cleanup='--unannotated' in sys.argv
out=Path(sys.argv[sys.argv.index('--')+1]);out.mkdir(parents=True,exist_ok=False)
results=[];completed=False


def frame(f):
    bpy.context.scene.frame_set(math.floor(f),subframe=f-math.floor(f));bpy.context.view_layer.update()


def observed(obj):
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());world=evaluated.matrix_world
    foot_mesh_min_z=[]
    for label in ('A','B'):
        mesh=bpy.data.objects['Skin Endpoint'+label].evaluated_get(bpy.context.evaluated_depsgraph_get());data=mesh.to_mesh()
        try:foot_mesh_min_z.append(min((mesh.matrix_world@v.co).z for v in data.vertices))
        finally:mesh.to_mesh_clear()
    return {'root':list(world.translation),'foot_mesh_min_z':foot_mesh_min_z,
            'joints':{p.name:{'p':list(world@p.head),'q':list((world@p.matrix).to_quaternion())} for p in evaluated.pose.bones},
            'feet':[list(world@evaluated.pose.bones['Endpoint'+n].head) for n in ('A','B')],
            'footprints':[[list(world@evaluated.pose.bones['Endpoint'+n].head),list(world@evaluated.pose.bones['Endpoint'+n].tail)] for n in ('A','B')]}


def create_rig():
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.render.fps=30;scene.frame_end=70
    data=bpy.data.armatures.new('Authored synthetic two-bone chains');obj=bpy.data.objects.new('Contact reference performer',data);scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    root=data.edit_bones.new('Support');root.head=(0,0,1);root.tail=(0,0,2)
    chains=[]
    for label,x in (('A',-.2),('B',.2)):
        upper=data.edit_bones.new('Proximal'+label);upper.head=(x,0,1);upper.tail=(x,-math.sqrt(.11),.5);upper.parent=root
        lower=data.edit_bones.new('Distal'+label);lower.head=upper.tail;lower.tail=(x,0,0);lower.parent=upper;lower.use_connect=True
        end=data.edit_bones.new('Endpoint'+label);end.head=lower.tail;end.tail=(x,.2,0);end.parent=lower;end.use_connect=True
        chains.append({'id':'authored-'+label,'upper':upper.name,'lower':lower.name,'end':end.name,'pole_local':[0,-1,0]})
    bpy.ops.object.mode_set(mode='OBJECT')
    for p in obj.pose.bones:p.rotation_mode='QUATERNION'
    rig={'version':'native-contact-rig-v1','chains':chains,'rest_sha256':contacts.rest_identity(obj,chains),'ground_z_m':0.,'height_m':2.}
    obj[contacts.RIG_PROPERTY]=json.dumps(rig)
    material=bpy.data.materials.new('Reference blue');material.diffuse_color=(.08,.36,.7,1);material.use_nodes=True
    material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.08,.36,.7,1)
    for bone in data.bones:
        direction=bone.tail_local-bone.head_local;length=direction.length
        center=(bone.head_local+bone.tail_local)*.5
        if bone.name.startswith('Distal'):center-=direction.normalized()*.04;length-=.08
        if bone.name.startswith('Endpoint'):center.z=.04
        bpy.ops.mesh.primitive_cube_add(size=1,location=center);mesh=bpy.context.object;mesh.name='Skin '+bone.name
        mesh.rotation_euler=direction.to_track_quat('Y','Z').to_euler();mesh.dimensions=(.14,length,.08 if bone.name.startswith('Endpoint') else .14)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        mesh.parent=obj;mesh.vertex_groups.new(name=bone.name).add(list(range(8)),1,'REPLACE');mesh.modifiers.new('Authored skin','ARMATURE').object=obj;mesh.data.materials.append(material)
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,1));pelvis=bpy.context.object;pelvis.name='Skin pelvis';pelvis.dimensions=(.58,.20,.18)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);pelvis.parent=obj
    pelvis.vertex_groups.new(name='Support').add(list(range(8)),1,'REPLACE');pelvis.modifiers.new('Authored skin','ARMATURE').object=obj;pelvis.data.materials.append(material)
    bpy.ops.mesh.primitive_plane_add(size=20);bpy.context.object.name='Ground'
    bpy.ops.object.camera_add(location=(4,-6,3.5));scene.camera=bpy.context.object;scene.camera.data.type='ORTHO';scene.camera.data.ortho_scale=4
    scene.camera.rotation_euler=(Vector((0,.4,1))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.light_add(type='AREA',location=(2,-3,6));bpy.context.object.data.energy=700;bpy.context.object.data.size=5
    scene.render.engine='CYCLES';scene.cycles.samples=16;scene.render.resolution_x=640;scene.render.resolution_y=480;scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new('World');scene.world.color=(.2,.2,.2)
    return obj,rig


def case(name,va,vb,extra=6,body_yaw=0.):
    obj,rig=create_rig();duration=extra+1
    for index,velocity in enumerate((va,vb)):
        action=bpy.data.actions.new(('Outgoing ' if index==0 else 'Incoming ')+name);obj.animation_data_create().action=action
        # Both sides describe the same world support point after root alignment.
        start_offset=10*index
        planted=start_offset+24*va if index==0 else start_offset-(va+vb)*duration/2
        for step in range(193):
            f=1+step/8;t=(f-1)/24;obj.pose.bones['Support'].rotation_quaternion=Quaternion((0,1,0),index*body_yaw);obj.location=(0,start_offset+(f-1)*velocity,0)
            bpy.context.view_layer.update()
            contacts.solve(obj,rig['chains'][0],Vector((-.2,planted,0)),Quaternion((1,0,0,0)))
            # Contralateral swing has an authored zero-height/zero-vertical-speed
            # endpoint. It is never counted as a planted stance by the checker.
            lift=(.08 if velocity else 0)*math.sin(math.pi*t)**2
            target=Vector((.2,obj.location.y+.12*math.sin(2*math.pi*t) if velocity else obj.location.y,lift))
            contacts.solve(obj,rig['chains'][1],target,Quaternion((1,0,0,0)))
            obj.keyframe_insert('location',frame=f)
            for p in obj.pose.bones:p.keyframe_insert('rotation_quaternion',frame=f)
        for curve in layer.ops.curves(action):
            for key in curve.keyframe_points:key.interpolation='LINEAR'
        action[contacts.ACTION_PROPERTY]=json.dumps({'version':'native-contact-intervals-v1','rig_sha256':digest(rig),
            'intervals':[{'chain':'authored-A','start':1.,'end':25.}]})
        slot=getattr(obj.animation_data,'action_slot',None);layer.add_strip(obj,action,slot,'Retained '+str(index),1,[1,25],1).mute=True
    if without_cleanup:
        del obj[contacts.RIG_PROPERTY]
        for action in bpy.data.actions:
            if contacts.ACTION_PROPERTY in action:del action[contacts.ACTION_PROPERTY]
    obj.animation_data.action=obj.animation_data.nla_tracks[0].strips[0].action
    if hasattr(obj.animation_data,'action_slot'):obj.animation_data.action_slot=obj.animation_data.nla_tracks[0].strips[0].action_slot
    frame(1);audit=layer.audit();p=next(p for p in audit['performers'] if p['name']==obj.name)
    takes=sorted(p['takes'],key=lambda t:t['action'],reverse=True)
    assert all(t['contacts']['status']==('UNANNOTATED' if without_cleanup else 'AUTHORED') for t in takes)
    sources={a.name:digest(layer.channels(a)) for a in bpy.data.actions}
    ca={'id':'clip_a','take_id':takes[0]['id'],'start':1,'frames':25,'speed':1.,'repeat_reviewed':False,'travel':None}
    cb=ca|{'id':'clip_b','take_id':takes[1]['id'],'start':26+extra,'transition':{'frames':extra,'match_phase':False}}
    request={'version':'action-layer-v1','audit_sha256':audit['sha256'],'frame_range':[1,70],
        'changes':[{'performer':obj.name,'mode':'timeline','clips':[ca,cb]}]}
    folder=out/name;folder.mkdir();source=folder/'source.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source))
    report=layer.apply(request,'contact-'+name)
    obj=bpy.data.objects['Contact reference performer'];foot_samples=[];boundaries=[]
    # Include actual authored stance before and after BOTH boundaries. Empty masks
    # cannot pass: exactly 129 bridge/stance samples are required for this case.
    for f in [24+(cb['start']-23)*i/128 for i in range(129)]:
        frame(f);foot_samples.append({'frame':f,**observed(obj)})
    target=foot_samples[0]['footprints'][0]
    drift=max(math.dist(s['footprints'][0][i][:2],target[i][:2]) for s in foot_samples for i in range(2))
    penetration=max([max(0,-p[2]) for s in foot_samples for foot in s['footprints'] for p in foot]+[max(0,-z) for s in foot_samples for z in s['foot_mesh_min_z']])
    for f in (25,cb['start']):
        h=1/64;rows={}
        for i in (-3,-2,-1,0,1,2,3):frame(f+i*h);rows[i]=observed(obj)
        maximum=0.;position=0.;orientation=0.
        for bone in rows[0]['joints']:
            origin=rows[0]['joints'][bone];logs={i:sm.qlog(sm.qmul(sm.inverse(origin['q']),rows[i]['joints'][bone]['q'])) for i in (-3,-2,-1,1,2,3)}
            left=[(4*a-b)*(-30/(2*h)) for a,b in zip(logs[-1],logs[-2])]
            right=[(4*a-b)*(30/(2*h)) for a,b in zip(logs[1],logs[2])]
            maximum=max(maximum,math.degrees(math.dist(left,right)))
            values=[];angles=[]
            for sign in (-1,1):
                values.append([3*a-3*b+c for a,b,c in zip(rows[sign]['joints'][bone]['p'],rows[2*sign]['joints'][bone]['p'],rows[3*sign]['joints'][bone]['p'])])
                angles.append([3*a-3*b+c for a,b,c in zip(logs[sign],logs[2*sign],logs[3*sign])])
            position=max(position,math.dist(*values));orientation=max(orientation,math.degrees(math.dist(*angles)))
        velocities=[]
        for sign in (-1,1):velocities.append([sign*(-3*a+4*b-c)*30/(2*h) for a,b,c in zip(rows[0]['root'],rows[sign]['root'],rows[2*sign]['root'])])
        boundaries.append({'frame':f,'position_m':position,'orientation_deg':orientation,'angular_velocity_deg_s':maximum,'linear_velocity_m_s':math.dist(*velocities)})
    preserved=all(digest(layer.channels(bpy.data.actions[n]))==v for n,v in sources.items())
    acceptance_report=folder/'acceptance-report.json';atomic_json(acceptance_report,report)
    result=folder/'result.blend';bpy.ops.wm.save_as_mainfile(filepath=str(result));layer.verify_saved(report,result)
    thresholds={'position_m':.002,'orientation_deg':1.,'angular_velocity_deg_s':5.,'linear_velocity_m_s':.1,'foot_drift_m':.02,'penetration_m':.01}
    failures=[(b['frame'],key,b[key]) for b in boundaries for key in ('position_m','orientation_deg','angular_velocity_deg_s','linear_velocity_m_s') if b[key]>thresholds[key]]
    if drift>.02 or penetration>.01 or not preserved:failures.append(('contacts/preservation',drift,penetration,preserved))
    return {'name':name,'status':'PASS' if not failures else 'FAIL','failures':failures,'result':str(result),'result_sha256':file_hash(result),'source':str(source),
            'acceptance_report':str(acceptance_report),'rig':'Contact reference performer','character_height_m':2.,'fps':30,
            'metrics':{'boundaries':boundaries,'contacts':{'foot_drift_m':drift,'penetration_m':penetration,'sample_count':len(foot_samples),
                'provenance':'authored source planted intervals and verified two-bone mapping'}},'samples':foot_samples,'thresholds':thresholds,
            'preserved':preserved,'source_channel_hashes':sources,'stitch_timestamps':[25,cb['start']]}

def failure_checks(source, request):
    checks=[]
    for scenario in ('changed-rest','changed-ancestor','missing-side','empty-mask','false-plant','disconnected-chain','constraint','driver','nla-solo'):
        bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
        obj=bpy.data.objects['Contact reference performer'];actions=sorted([a for a,_ in layer.bindings(obj)],key=lambda a:a.name)
        if scenario=='constraint':obj.pose.bones['ProximalA'].constraints.new('COPY_LOCATION')
        elif scenario=='driver':obj.driver_add('location',0).driver.expression='0'
        elif scenario=='nla-solo':obj.animation_data.nla_tracks[0].is_solo=True
        elif scenario=='changed-ancestor':
            bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
            obj.data.edit_bones['Support'].roll+=.05;bpy.ops.object.mode_set(mode='OBJECT')
        elif scenario in {'changed-rest','disconnected-chain'}:
            rig=json.loads(obj[contacts.RIG_PROPERTY])
            if scenario=='changed-rest':rig['rest_sha256']='0'*64
            else:rig['chains'][0]['lower']=rig['chains'][1]['lower']
            obj[contacts.RIG_PROPERTY]=json.dumps(rig)
        elif scenario=='missing-side':del actions[0][contacts.ACTION_PROPERTY]
        else:
            for action in actions:
                value=json.loads(action[contacts.ACTION_PROPERTY])
                if scenario=='empty-mask':value['intervals']=[]
                else:value['intervals']=[{'chain':'authored-B','start':1.,'end':25.}]
                action[contacts.ACTION_PROPERTY]=json.dumps(value)
        frame(1);audit=layer.audit();before=layer.preserved(set());objects=len(bpy.data.objects);count=len(bpy.data.actions)
        try:layer.apply(request|{'audit_sha256':audit['sha256']},'refuse-'+scenario)
        except DirectorError as error:
            assert error.code.startswith('CONTACT_') or scenario in {'constraint','driver','nla-solo'} and error.code=='ACTION_UNSUPPORTED',(scenario,error.code,str(error))
            assert layer.preserved(set())==before and len(bpy.data.objects)==objects and len(bpy.data.actions)==count
            checks.append({'scenario':scenario,'status':'PASS','code':error.code,'message':str(error)})
        else:raise AssertionError('invalid contact case accepted: '+scenario)
    return checks


try:
    for name,va,vb in [('idle-walk',0.,.0125),('walk-idle',.0125,0.),('walk-run',.0125,.0208333333333333)]:results.append(case(name,va,vb))
    results.append(case('walk-run-body-turn',.0125,.0208333333333333,body_yaw=1.))
    failures_checked=[]
    if not without_cleanup:
        request=json.loads(Path(results[0]['acceptance_report']).read_text())['request']
        failures_checked=failure_checks(results[0]['source'],request)
    completed=True
finally:
    atomic_json(out/'RESULTS.json',{'status':'PASS' if completed and all(r['status']=='PASS' for r in results) else 'FAIL','completed':completed,
        'results':results,'failure_checks':locals().get('failures_checked',[]),'blender':bpy.app.version_string,'input_kind':'GENERATED_CC0','natural_motion_acceptance':'NOT_CLAIMED','cleanup_enabled':not without_cleanup})
assert completed and all(r['status']=='PASS' for r in results),'Contact regression: inspect RESULTS.json'
