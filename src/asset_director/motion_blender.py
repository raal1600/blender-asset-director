"""Blender-only canonical bridge and source-shaped segmented diagnostic bodies.

No user mesh is reshaped. The generated rest morphology is fitted once and frozen.
The proxy is not a skin/anatomy model and does not solve contact or performance.
"""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import bpy
from mathutils import Matrix, Quaternion, Vector
from .core import atomic_json, require
from . import motion_assets as ma
from .motion_body import body_profile
from .motion_morph import inclusive_scene_end, morph_skeleton
from . import blender_ops as ops


def guard():
    require(bpy.app.background,'BACKGROUND_REQUIRED','Use isolated background motion jobs')


def rotation(values):
    return Matrix([values[i:i+3] for i in (0,3,6)])


def values(v):
    return [float(x) for x in v]


def rig(name):
    obj=bpy.data.objects.get(name)
    require(obj and obj.type=='ARMATURE','TARGET_REQUIRED','Name an observed armature')
    require(len(obj.data.bones)<=ma.MAX_JOINTS,'RESOURCE_LIMIT','Rig exceeds canonical joint budget')
    scale=obj.matrix_world.to_scale()
    require(min(scale)>0 and max(scale)/min(scale)<1.00001 and obj.matrix_world.determinant()>0,
            'SCALE_REVIEW_REQUIRED','Canonical bridge needs positive uniform armature scale')
    return obj


def skeleton(obj,meters,axes,roles):
    pending=list(obj.data.bones);ordered=[];names=set()
    while pending:
        ready=[b for b in pending if not b.parent or b.parent.name in names]
        require(ready,'INVALID_SKELETON','Cannot order hierarchy')
        for b in ready:
            ordered.append(b);names.add(b.name);pending.remove(b)
    joints=[]
    for b in ordered:
        world=obj.matrix_world@b.matrix_local
        joints.append({'name':b.name,'parent':b.parent.name if b.parent else None,
          'head':values(meters*(axes@(obj.matrix_world@b.head_local))),
          'tail':values(meters*(axes@(obj.matrix_world@b.tail_local))),
          'rotation':values((axes@world.to_quaternion().to_matrix()).to_quaternion().normalized())})
    result={'joints':joints,'roles':roles,'source_fingerprint':ops.rig_report(obj)['fingerprint']}
    ma.validate_skeleton(result)
    return result


def audit(options):
    guard();obj=rig(options['target_object'])
    sk=skeleton(obj,options['meters_per_unit'],rotation(options['source_to_canonical']),options['roles'])
    return {'object':obj.name,'skeleton':sk,'body_profile':body_profile(sk),
            'read_only':True,'unit_evidence':'explicit caller-supplied conversion, not inferred from a label'}


def export(job,directory):
    guard();o=job['specification']['options'];obj=rig(o['target_object'])
    action=bpy.data.actions.get(o['action']);require(action is not None,'ACTION_NOT_FOUND','Observed action not found')
    gate=ma.rights_gate(o['source'],o['rights'],o['project_use'])
    require(gate['eligible'],'MOTION_RIGHTS_BLOCKED','; '.join(gate['reasons']))
    sk=skeleton(obj,o['meters_per_unit'],rotation(o['source_to_canonical']),o['roles'])
    axes=rotation(o['source_to_canonical']);meters=o['meters_per_unit']
    fps=bpy.context.scene.render.fps/bpy.context.scene.render.fps_base
    duration=(o['end']-o['start'])/fps;ma.finite(duration,1e-7,600)
    n=math.ceil(duration*o['sample_fps'])
    require(n+1<=ma.MAX_FRAMES and (n+1)*len(sk['joints'])<=ma.MAX_JOINT_FRAMES,'RESOURCE_LIMIT','Export sample budget exceeded')
    times=[i/o['sample_fps'] for i in range(n)]+[duration]
    ops.assign(obj,action,o.get('slot'))
    for track in obj.animation_data.nla_tracks:track.mute=True
    start,end=ops.action_range(action,getattr(obj.animation_data,'action_slot',None))
    require(o['start']>=start-1e-5 and o['end']<=end+1e-5,'SOURCE_RANGE_REVIEW','Interval leaves the selected action')
    samples=[];previous={}
    with ops.restore_context():
        for t in times:
            frame=o['start']+t*fps;bpy.context.scene.frame_set(math.floor(frame),subframe=frame-math.floor(frame))
            evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());positions=[];rotations=[]
            for j in sk['joints']:
                pb=evaluated.pose.bones[j['name']];world=evaluated.matrix_world@pb.matrix
                scale=world.to_scale();expected=obj.matrix_world.to_scale()
                require(max(abs(a-b) for a,b in zip(scale,expected))<1e-4 and world.determinant()>0,
                        'POSE_SCALE_UNSUPPORTED','Canonical rigid-pose export refuses stretch/reflection')
                positions.append(values(meters*(axes@world.translation)))
                q=(axes@world.to_quaternion().to_matrix()).to_quaternion().normalized()
                if j['name'] in previous and q.dot(previous[j['name']])<0:q.negate()
                previous[j['name']]=q.copy();rotations.append(values(q))
            samples.append({'time':t,'positions':positions,'rotations':rotations})
    payload=ma.write_payload(Path(directory)/'motion.bin',samples,len(sk['joints']))
    source=copy.deepcopy(o['source'])
    source['raw_files']=[{k:f[k] for k in ('sha256','size')} for f in job['specification']['inputs']]
    record={'schema':ma.SCHEMA,'source':source,'rights':o['rights'],
       'timing':{'duration_seconds':duration,'sample_count':len(samples),'source_frame_fps':fps,
                 'native_capture_fps':o.get('native_capture_fps'),'sampling':'explicit_timestamps'},
       'coordinates':{'unit':'meter','up':'+Z','handedness':'right','source_to_canonical':o['source_to_canonical'],'meters_per_source_unit':meters},
       'skeleton':sk,'payload':payload,'semantics':o['semantics'],'lineage':[],
       'contact_annotations':o.get('contact_annotations',[])}
    record['id']=ma.validate_record(record);ma.read_payload(Path(directory)/'motion.bin',record)
    atomic_json(Path(directory)/'motion.record.json',record)
    return {'motion_id':record['id'],'sample_count':len(samples),'duration_seconds':duration,
            'body_profile':body_profile(sk),'performance':'NOT_EVALUATED','next':'motion-collect the successful job'}


def create_rig(sk,name):
    ma.validate_skeleton(sk)
    data=bpy.data.armatures.new(name);obj=bpy.data.objects.new(name,data)
    bpy.context.scene.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.ops.object.mode_set(mode='EDIT')
    try:
        for j in sk['joints']:
            b=data.edit_bones.new(j['name']);b.head=j['head'];b.tail=j['tail']
            if j['parent']:b.parent=data.edit_bones[j['parent']]
            b.align_roll(Quaternion(j['rotation'])@Vector((0,0,1)))
    finally:bpy.ops.object.mode_set(mode='OBJECT')
    obj['bad_semantic_roles']=json.dumps(sk['roles'],sort_keys=True)
    for p in obj.pose.bones:p.rotation_mode='QUATERNION'
    return obj


def load_source(record,samples,fps,owner):
    obj=create_rig(record['skeleton'],'BAD_MOTION_SOURCE_'+owner)
    action=bpy.data.actions.new('BAD_CAPTURE_'+owner);ops.assign(obj,action)
    previous={}
    for sample in samples:
        solved={}
        for index,j in enumerate(record['skeleton']['joints']):
            bone=obj.data.bones[j['name']];desired=Quaternion(sample['rotations'][index]).to_matrix().to_4x4()
            desired.translation=Vector(sample['positions'][index]);solved[j['name']]=desired
            basis=(bone.convert_local_to_pose(desired,bone.matrix_local,parent_matrix=solved[j['parent']],
                   parent_matrix_local=obj.data.bones[j['parent']].matrix_local,invert=True)
                   if j['parent'] else bone.convert_local_to_pose(desired,bone.matrix_local,invert=True))
            location,q,scale=basis.decompose();pb=obj.pose.bones[j['name']]
            require(max(abs(v-1) for v in scale)<1e-4,'POSE_SCALE_UNSUPPORTED','Canonical import requires rigid bones')
            if pb.name in previous and q.dot(previous[pb.name])<0:q.negate()
            previous[pb.name]=q.copy();pb.location=location;pb.rotation_quaternion=q;pb.scale=(1,1,1)
            frame=1+sample['time']*fps
            pb.keyframe_insert('location',frame=frame);pb.keyframe_insert('rotation_quaternion',frame=frame)
    for c in ops.curves(action,getattr(obj.animation_data,'action_slot',None)):
        for k in c.keyframe_points:k.interpolation='LINEAR'
    action.use_fake_user=True;obj['bad_motion_id']=record['id']
    return obj,action


def allowed_motion(lib,options):
    record,samples=ma.load(lib,options['motion_id'],samples=True)
    gate=ma.rights_gate(record['source'],record['rights'],options['project_use'])
    require(gate['eligible'],'MOTION_RIGHTS_BLOCKED','; '.join(gate['reasons']))
    return record,samples,gate


def source_import(lib,options,owner):
    guard();record,samples,_=allowed_motion(lib,options)
    fps=options['fps'];obj,action=load_source(record,samples,fps,owner)
    scene=bpy.context.scene;scene.render.fps=int(fps);scene.render.fps_base=int(fps)/fps
    scene.frame_start=1;scene.frame_end,exact_end=inclusive_scene_end(1,samples[-1]['time'],fps);scene.frame_set(1)
    return {'source_object':obj.name,'action':action.name,'slot':getattr(obj.animation_data.action_slot,'identifier',None),
            'motion_id':record['id'],'fps':fps,'duration_seconds':samples[-1]['time'],
            'final_key_frame':exact_end,'scene_frame_end':scene.frame_end,
            'rig':ops.rig_report(obj),'performance':'NOT_EVALUATED','source_only':True}


def _capsule(vertices,faces,weights,start,end,weight_name,radius_ratio):
    start=Vector(start);end=Vector(end);axis=end-start;length=axis.length
    if length<=1e-6:return
    radius=min(.08,max(.008,length*radius_ratio));base=len(vertices);sides=10
    q=Vector((0,1,0)).rotation_difference(axis.normalized())
    frame=Matrix.Translation(start)@q.to_matrix().to_4x4()
    rings=[(-radius*.99,radius*.14),(-radius*.7,radius*.714),(0,radius),
           (length,radius),(length+radius*.7,radius*.714),(length+radius*.99,radius*.14)]
    for y,r in rings:
        for k in range(sides):
            theta=2*math.pi*k/sides
            vertices.append(values(frame@Vector((r*math.cos(theta),y,r*math.sin(theta)))))
    weights.append((weight_name,list(range(base,base+len(rings)*sides))))
    for row in range(len(rings)-1):
        for k in range(sides):
            a=base+row*sides+k;b=base+row*sides+(k+1)%sides;faces.append((a,b,b+sides,a+sides))
    faces.append(tuple(base+k for k in reversed(range(sides))))
    faces.append(tuple(base+(len(rings)-1)*sides+k for k in range(sides)))


def clay(lib,options,owner):
    guard();record,_,_=allowed_motion(lib,options)
    scales=options.get('length_scales',{})
    sk=morph_skeleton(record['skeleton'],scales)
    before={o.name:(o.data.as_pointer() if o.data else 0,ops.flatten(o.matrix_world)) for o in bpy.data.objects}
    materials={m.name:m.as_pointer() for m in bpy.data.materials}
    obj=create_rig(sk,'BAD_CLAY_'+owner);vertices=[];faces=[];weights=[]
    byname={j['name']:j for j in sk['joints']};children={j['name']:[] for j in sk['joints']}
    for j in sk['joints']:
        if j['parent']:children[j['parent']].append(j['name'])
    # Render the same joint-head hierarchy that body_profile measures. Display
    # tails are used only for terminal visualization, never as chain landmarks.
    for j in sk['joints']:
        if children[j['name']]:
            for child in children[j['name']]:
                _capsule(vertices,faces,weights,j['head'],byname[child]['head'],j['name'],options.get('radius_ratio',.1))
        else:
            _capsule(vertices,faces,weights,j['head'],j['tail'],j['name'],options.get('radius_ratio',.1))
    mesh=bpy.data.meshes.new(obj.name+'_skin');mesh.from_pydata(vertices,[],faces);mesh.update()
    skin=bpy.data.objects.new(mesh.name,mesh);bpy.context.scene.collection.objects.link(skin)
    for name,ids in weights:
        group=skin.vertex_groups.get(name) or skin.vertex_groups.new(name=name);group.add(ids,1.0,'REPLACE')
    modifier=skin.modifiers.new('CanonicalSkin','ARMATURE');modifier.object=obj;skin.parent=obj
    material=bpy.data.materials.new(obj.name+'_matte');material.use_nodes=True
    bsdf=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value=(*options.get('color',[.45]*3),1)
    bsdf.inputs['Roughness'].default_value=.7;mesh.materials.append(material)
    for poly in mesh.polygons:poly.use_smooth=True
    obj['bad_morphology_locked']=True;obj['bad_source_motion']=record['id']
    require(all(n in bpy.data.objects and (bpy.data.objects[n].data.as_pointer() if bpy.data.objects[n].data else 0,
            ops.flatten(bpy.data.objects[n].matrix_world))==v for n,v in before.items()),'CLAY_ISOLATION_FAILED','Existing objects changed')
    require(all(n in bpy.data.materials and bpy.data.materials[n].as_pointer()==v for n,v in materials.items()),
            'CLAY_ISOLATION_FAILED','Existing material identities changed')
    actual=skeleton(obj,1,Matrix.Identity(3),sk['roles'])
    return {'armature':obj.name,'mesh':skin.name,'skeleton':actual,'body_profile':body_profile(actual),
            'classification':'CREATE_DIAGNOSTIC_PROXY','length_scales':scales,'morphology_locked':True,
            'existing_object_transforms_and_data_ids_preserved':True,'rig':ops.rig_report(obj),
            'visual_geometry_basis':'joint-head hierarchy; terminal display tails only',
            'limitations':['segmented rigid-weight capsule proxy, not production skin',
              'girth is a visualization setting, not measured anatomy','existing characters are never reshaped',
              'fixed rest lengths, not animated bone scales'],'performance':'NOT_EVALUATED'}


def retarget(lib,options,owner):
    guard();record,samples,gate=allowed_motion(lib,options);target=rig(options['target_object'])
    require(record['skeleton']['source_fingerprint']==options['expected_source_fingerprint'] and
            ops.rig_report(target)['fingerprint']==options['expected_target_fingerprint'],
            'STALE_RETARGET_PROFILE','Source/target fingerprint no longer matches reviewed plan')
    # Source arrays are meters; reconstruct the temporary rig in TARGET scene units.
    # Morphological ratios must never accidentally also serve as unit conversion.
    unit_factor=1/options['target_meters_per_unit']
    converted=copy.deepcopy(record);converted_samples=copy.deepcopy(samples)
    for joint in converted['skeleton']['joints']:
        for key in ('head','tail'):joint[key]=[v*unit_factor for v in joint[key]]
    for sample in converted_samples:
        sample['positions']=[[v*unit_factor for v in p] for p in sample['positions']]
    fps=options['target_fps'];source,action=load_source(converted,converted_samples,fps,owner)
    transfer={k:options[k] for k in ('target_object','target_fps','mapping','alignment','pose_space')}
    transfer['source_fps']=fps
    from .backend import verify
    try:
        result=ops.retarget(source,target,action,getattr(source.animation_data.action_slot,'identifier',None),transfer,verify(lib),owner)
    finally:
        bpy.data.objects.remove(source,do_unlink=True)
        if action.name in bpy.data.actions:bpy.data.actions.remove(action)
    result['source_motion_id']=record['id'];result['source_rights']=gate
    return result
