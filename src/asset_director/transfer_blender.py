"""Read-only background transfer proposals and measured subframe contact diagnostics.

All inference here is geometric and exposed for review. Minimal swing preserves
nearest target-rest twist; it is not a muscle model, universal rig mapper or IK.
"""
from __future__ import annotations
import copy
import math
from pathlib import Path
import bpy
from mathutils import Matrix, Vector
from .core import digest, require, DirectorError, rights
from . import blender_ops as ops, transfer_contract as contract
from .motion import REQUIRED
from .motion_blender import skeleton
from .motion_body import body_profile, build_profile

SCHEMA = 'asset-director.transfer-proposal/1'


def flat(m):
    return [float(x) for row in m for x in row]


def guard():
    require(bpy.app.background, 'BACKGROUND_REQUIRED', 'Use an isolated planning/diagnostic worker')


def import_source(lib, spec):
    """Resolve the same indexed owner/action/slot as the existing retarget route."""
    asset = lib.get(spec['asset_id'])
    require(asset.kind == 'animation' and asset.metadata.get('file') and asset.metadata.get('action'),
            'INDEX_REQUIRED', 'Choose one actual indexed animation clip')
    require(rights(asset, lib=lib)['eligible'], 'BLOCKED_POLICY', 'Source project use is not eligible')
    f = asset.metadata['file']; options = spec['options']
    from .worker import package_root, re_original
    before = set(bpy.data.actions)
    created = ops.import_file(lib.verify_file(f), package_root(lib, f), frame_fps=asset.metadata['fps'])
    rigs = [o for o in created if o.type == 'ARMATURE']
    selected = [o for o in rigs if o.name == asset.metadata['source_object']]
    if not selected and len(rigs) == 1: selected = rigs
    require(len(selected) == 1, 'SOURCE_AMBIGUOUS', 'Indexed source rig cannot be selected uniquely')
    actions = list(set(bpy.data.actions)-before)
    matches = [a for a in actions if a.name == asset.metadata['action']]
    if not matches:
        matches = [a for a in actions if re_original(a.name) == re_original(asset.metadata['action'])]
    require(len(matches) == 1, 'ACTION_AMBIGUOUS', 'Indexed source action cannot be selected uniquely')
    obj = selected[0]; action = matches[0]
    ops.assign(obj, action, asset.metadata.get('slot'))
    for track in obj.animation_data.nla_tracks: track.mute = True
    return asset, obj, action


def rigid_object(obj):
    require(obj and obj.type == 'ARMATURE', 'TARGET_REQUIRED', 'Choose an observed armature')
    require(len(obj.data.bones) <= 256, 'RESOURCE_LIMIT', 'Rig joint budget exceeded')
    current = obj
    while current:
        require(not current.constraints and not (current.animation_data and current.animation_data.drivers),
                'TRANSFER_CONTROLS_UNSUPPORTED', 'Object/ancestor constraints or drivers require a baked review path')
        if current != obj:
            require(not current.animation_data, 'TRANSFER_CONTROLS_UNSUPPORTED', 'Animated rig ancestor requires explicit baking')
        current = current.parent
    require(not any(pb.constraints for pb in obj.pose.bones), 'TRANSFER_CONTROLS_UNSUPPORTED', 'Pose constraints require baked deform rigs')
    m = obj.matrix_world; scale = m.to_scale()
    require(m.determinant() > 0 and min(scale)>0 and max(scale)/min(scale)<1.00001,
            'SCALE_REVIEW_REQUIRED', 'Positive uniform rig object scale is required')
    basis = m.to_3x3().normalized()
    require(max(abs(basis.col[i].dot(basis.col[j]) - (i==j)) for i in range(3) for j in range(3))<1e-5,
            'SCALE_REVIEW_REQUIRED', 'Rig object shear is not supported')


def roles(obj, override):
    report = ops.rig_report(obj)
    selected = override if override is not None else report['roles']
    contract.role_map(selected)
    require(all(n in obj.data.bones for n in selected.values()), 'MAPPING_REVIEW_REQUIRED', 'Role names an absent bone')
    require(REQUIRED <= selected.keys(), 'MAPPING_REVIEW_REQUIRED', 'Required body roles remain unresolved')
    require(override is not None or not report['ambiguous'], 'MAPPING_REVIEW_REQUIRED', 'Ambiguous chains require explicit reviewed roles')
    return report, dict(selected)


def head(obj, role, r):
    return obj.matrix_world @ obj.data.bones[r[role]].head_local


def facing(obj, r):
    require(all(k in r for k in ('foot_l','foot_r','toe_l','toe_r','hips','head','thigh_l','thigh_r')),
            'FACING_REVIEW_REQUIRED', 'Automatic facing needs bilateral ankle/toe and torso landmarks; supply explicit evidence otherwise')
    up = head(obj,'head',r)-head(obj,'hips',r)
    require(up.length > 1e-6 and up.normalized().z > .8,
            'FACING_REVIEW_REQUIRED', 'Automatic facing requires an upright world-Z reference')
    vectors = []
    for side in ('l','r'):
        v = head(obj,'toe_'+side,r)-head(obj,'foot_'+side,r); v.z = 0
        require(v.length > 1e-6, 'FACING_REVIEW_REQUIRED', 'Degenerate foot direction')
        vectors.append(v.normalized())
    require(vectors[0].dot(vectors[1]) > .5, 'FACING_REVIEW_REQUIRED', 'Toe directions disagree; do not average ambiguous feet')
    f = (vectors[0]+vectors[1]).normalized()
    lateral = head(obj,'thigh_l',r)-head(obj,'thigh_r',r); lateral.z = 0
    require(lateral.length>1e-6 and abs(lateral.normalized().dot(f))<.35,
            'FACING_REVIEW_REQUIRED', 'Foot direction disagrees with hip lateral axis')
    return f


def successor(role, r):
    fixed = {'hips':'spine', 'spine':'spine_mid' if 'spine_mid' in r else 'chest' if 'chest' in r else 'neck' if 'neck' in r else 'head',
             'spine_mid':'chest', 'chest':'neck' if 'neck' in r else 'head', 'neck':'head'}
    for side in ('l','r'):
        fixed.update({f'{a}_{side}':f'{b}_{side}' for a,b in
                      [('shoulder','upperarm'),('upperarm','forearm'),('forearm','hand'),('thigh','calf'),('calf','foot'),('foot','toe')]})
        fixed['hand_'+side] = 'middle_1_'+side
        for finger in ('thumb','index','middle','ring','pinky'):
            for i in (1,2): fixed[f'{finger}_{i}_{side}']=f'{finger}_{i+1}_{side}'
    value = fixed.get(role)
    return value if value in r else None


def direction(obj, role, r):
    name = r[role]; end = successor(role,r)
    if end:
        b = obj.data.bones[r[end]].parent
        while b and b.name != name: b = b.parent
        require(b is not None, 'ALIGNMENT_REVIEW_REQUIRED', 'Semantic successor is outside its chain')
        v = head(obj,end,r)-head(obj,role,r); evidence = 'semantic joint heads: '+role+' -> '+end
    else:
        b = obj.data.bones[name]; v = obj.matrix_world.to_3x3() @ (b.tail_local-b.head_local)
        evidence = 'terminal rest-bone axis; anatomical endpoint not independently measured'
    require(v.length>1e-6, 'ALIGNMENT_REVIEW_REQUIRED', 'Degenerate anatomical direction')
    return v.normalized(), evidence


def action_signature(action, slot):
    curves = ops.curves(action,slot)
    require(len(curves)<=4096 and sum(len(c.keyframe_points) for c in curves)<=500000,
            'RESOURCE_LIMIT', 'Planning curve/key budget exceeded')
    return digest([{'path':c.data_path,'index':c.array_index,
                    'keys':[[float(k.co.x),float(k.co.y),k.interpolation,
                             list(k.handle_left),list(k.handle_right)] for k in c.keyframe_points]}
                   for c in curves])


def source_checks(source, action, anchor, start, end, count, meters_per_unit=1):
    slot=source.animation_data.action_slot
    signature=action_signature(action,slot)
    from .translation_precision import precision, check_span
    policy = precision(meters_per_unit, max(source.matrix_world.to_scale()))
    largest_non_anchor_span_m = 0.0
    for c in ops.curves(action,slot):
        require(not c.modifiers, 'TRANSFER_CURVE_MODIFIERS_UNSUPPORTED', 'Curve modifiers need a separately baked source')
        values = [float(k.co.y) for k in c.keyframe_points]
        require(all(math.isfinite(v) for v in values),'INVALID_MOTION','Nonfinite animation key')
        if c.data_path in {'location','rotation_euler','rotation_quaternion','scale'}:
            require(not values or max(values)-min(values)<1e-6,'SOURCE_OBJECT_MOTION_REVIEW','Animated object motion requires baking')
        if c.data_path.endswith('.scale'):
            require(all(abs(v-1)<1e-5 for v in values),'ANIMATED_SCALE_UNSUPPORTED','Source bone scales must remain one')
        if c.data_path == source.pose.bones[anchor].path_from_id('location') and values:
            require(not source.data.bones[anchor].use_connect or
                    (max(values)-min(values))*policy['meters_per_local_unit'] <= policy['tolerance_m_per_component'],
                    'CONNECTED_ANCHOR_TRANSLATION',
                    'Imported translation anchor is connected to its parent; Blender ignores its location channels. Review the source, do not disconnect silently.')
        if c.data_path.endswith('.location') and c.data_path != source.pose.bones[anchor].path_from_id('location'):
            if values:
                largest_non_anchor_span_m = max(largest_non_anchor_span_m,
                    check_span(values, policy, f'{c.data_path}[{c.array_index}]'))
    original_world=source.matrix_world.copy(); origin=None; maximum=0.
    for i in range(count):
        f = start+(end-start)*i/(count-1)
        bpy.context.scene.frame_set(math.floor(f),subframe=f-math.floor(f))
        require(max(abs(source.matrix_world[r][c]-original_world[r][c]) for r in range(4) for c in range(4))<1e-5,
                'OBJECT_TRANSFORM_CHANGED','Source rig world transform varies')
        require(all(max(abs(v-1) for v in b.scale)<1e-5 for b in source.pose.bones),
                'ANIMATED_SCALE_UNSUPPORTED','Source pose scale varies at a sampled time')
        p = source.matrix_world @ source.pose.bones[anchor].head
        if origin is None: origin=p.copy()
        maximum=max(maximum,(p-origin).length)
    return {'curve_signature':signature,'checkpoints':count,'max_anchor_displacement_source_units':maximum,
            'non_anchor_translation_precision': policy, 'max_non_anchor_span_m': largest_non_anchor_span_m,
            'scope':'all key values/channel restrictions plus bounded evaluated times; no swept-extrema guarantee'}


def propose(lib, spec):
    guard(); o=spec['options']; contract.plan(o)
    target=bpy.data.objects.get(o['target_object']);rigid_object(target)
    if target.animation_data and target.animation_data.action:
        for c in ops.curves(target.animation_data.action,getattr(target.animation_data,'action_slot',None)):
            if c.data_path in {'location','rotation_euler','rotation_quaternion','scale'}:
                vals=[float(k.co.y) for k in c.keyframe_points]
                require(not c.modifiers and all(math.isfinite(v) for v in vals) and
                        (not vals or max(vals)-min(vals)<1e-6),
                        'TARGET_OBJECT_MOTION_REVIEW','Animated target object transforms require a separate bake/placement decision')
    tr, t_roles=roles(target,o.get('target_roles'))
    require(tr['skinned_vertices']>0,'NEEDS_RIGGING','Target must have existing verified skinning')
    asset,source,action=import_source(lib,spec);rigid_object(source)
    sr,s_roles=roles(source,o.get('source_roles'))
    slot=source.animation_data.action_slot
    start,end=ops.action_range(action,slot);sfps=asset.metadata['fps']
    require(abs(start-asset.metadata['frame_start'])<1e-5 and abs(end-asset.metadata['frame_end'])<1e-5
            and sr['fingerprint']==asset.metadata['skeleton_fingerprint'],
            'STALE_SOURCE_INDEX','Reimported action/rig differs from indexed evidence')
    start, end = o.get('start', start), o.get('end', end)
    from .motion_timing import bake_samples
    bake_samples(start, end, sfps, o['target_fps'], o.get('max_output_intervals', 360))
    bpy.context.scene.frame_set(math.floor(start),subframe=start-math.floor(start))
    if target.animation_data:
        target.animation_data.action=None
        for track in target.animation_data.nla_tracks:track.mute=True
    for pb in target.pose.bones: pb.matrix_basis=Matrix.Identity(4)
    bpy.context.view_layer.update()
    src_sk=skeleton(source,o['source_meters_per_unit'],Matrix.Identity(3),s_roles)
    tgt_sk=skeleton(target,o['target_meters_per_unit'],Matrix.Identity(3),t_roles)
    profile=build_profile(src_sk,tgt_sk,o['root_mode'])
    common=sorted(set(s_roles)&set(t_roles)-{'root'})
    pairs={s_roles[r]:t_roles[r] for r in common}
    require(REQUIRED <= set(common),'MAPPING_REVIEW_REQUIRED','Both bodies need the required semantic roles')
    if o['facing']['mode']=='anatomical':
        sf,tf=facing(source,s_roles),facing(target,t_roles)
        facing_evidence='bilateral ankle-to-toe directions checked against upright torso and hip lateral axis'
    else:
        sf=Vector(o['facing']['source_forward']).normalized();tf=Vector(o['facing']['target_forward']).normalized()
        facing_evidence=o['facing']['evidence']
    yaw=math.atan2(sf.cross(tf).z,sf.dot(tf)); world=Matrix.Rotation(yaw,3,'Z')
    source_world=flat(source.matrix_world);target_world=flat(target.matrix_world)
    evidence=source_checks(source,action,s_roles['hips'],start,end,o.get('check_count',65),o['source_meters_per_unit'])
    role_for={t_roles[r]:r for r in common};alignment={}; alignment_evidence=[];solved={}
    inv_rotation=target.matrix_world.to_quaternion().to_matrix().inverted()
    ordered=[];remaining=list(target.data.bones)
    while remaining:
        ready=[b for b in remaining if not b.parent or b.parent.name in solved or b.parent in ordered]
        require(ready,'INVALID_SKELETON','Cannot order target hierarchy')
        ordered.extend(ready)
        for b in ready:remaining.remove(b)
    for b in ordered:
        parent=b.parent
        inherited=(b.convert_local_to_pose(Matrix.Identity(4),b.matrix_local,parent_matrix=solved[parent.name],parent_matrix_local=parent.matrix_local)
                   if parent else b.matrix_local.copy())
        desired=inherited.copy()
        if b.name in role_for:
            role=role_for[b.name];sd,se=direction(source,role,s_roles);td,te=direction(target,role,t_roles)
            wanted=(world@sd).normalized(); dot=td.dot(wanted)
            require(dot>-.9999,'ALIGNMENT_REVIEW_REQUIRED','Antiparallel anatomical directions need explicit twist review')
            swing=td.rotation_difference(wanted)
            reference=swing.to_matrix() @ (target.matrix_world@b.matrix_local).to_quaternion().to_matrix()
            desired=(inv_rotation@reference).to_4x4();desired.translation=inherited.translation
            local=(b.convert_local_to_pose(desired,b.matrix_local,parent_matrix=solved[parent.name],parent_matrix_local=parent.matrix_local,invert=True)
                   if parent else b.convert_local_to_pose(desired,b.matrix_local,invert=True))
            loc,q,scale=local.decompose()
            require(max(abs(v-1) for v in scale)<1e-5 and loc.length<1e-5,
                    'ALIGNMENT_REVIEW_REQUIRED','Reference would stretch/translate target bones')
            local=q.normalized().to_matrix().to_4x4();alignment[b.name]=flat(local)
            alignment_evidence.append({'role':role,'source':s_roles[role],'target':b.name,
                'source_direction':list(sd),'target_direction':list(td),'aligned_source_direction':list(wanted),
                'swing_degrees':math.degrees(swing.angle),'source_basis':se,'target_basis':te})
        solved[b.name]=desired
    morphology=profile['suggested_translation_scale_xyz'][0]
    unit_conversion=o['source_meters_per_unit']/o['target_meters_per_unit']
    scale=morphology*unit_conversion
    origin=head(target,'hips',t_roles)
    retarget={'target_object':target.name,'source_object':asset.metadata['source_object'],
        'action':asset.metadata['action'],'source_fps':sfps,'target_fps':o['target_fps'],
        'start':start,'end':end,'mapping':pairs,'alignment':alignment,
        'max_output_intervals':o.get('max_output_intervals', 360),
        'pose_space':{'rotation':flat(world),'translation_bone':t_roles['hips'],
                      'translation_scale':scale,'target_origin':list(origin),
                      'source_meters_per_unit':o['source_meters_per_unit']}}
    ground_evidence = None
    if 'ground_contact' in o:
        from .ground_contact import GroundContact
        probe = GroundContact(target, t_roles['hips'], o['ground_contact'])
        ground_evidence = {'request':o['ground_contact'], 'selected_vertices':len(probe.indices),
                           'topology':probe.topology, 'repair_applied':False,
                           'scope':'vertical anchor correction only; no jumping or horizontal lock'}
        retarget['pose_space']['ground_contact'] = copy.deepcopy(o['ground_contact'])
    if asset.metadata.get('slot') is not None:retarget['slot']=asset.metadata['slot']
    from .pose_contract import validate_binding
    validate_binding(retarget['pose_space'],pairs)
    from .license_policy import derivation
    target_grants=derivation(lib, spec['inputs'][0]['sha256'])
    result={'schema':SCHEMA,'status':'REVIEW_REQUIRED','source_asset_id':asset.id,
        'source_character':{'provider':asset.provider,'provider_hint':asset.metadata.get('local_motion',{}).get('provider_hint'),
                            'title':asset.title,'object':source.name,
                            'license':rights(asset,lib=lib),'source_url':asset.source_url},
        'target_character':{'object':target.name,'meshes':tr['meshes'],
                            'provider':'UNKNOWN_UNLESS_LINKED_CATALOG_EVIDENCE',
                            'inherited_grants':target_grants,'project_use':'HOST_REVIEW_REQUIRED_UNLESS_LINKED_EVIDENCE',
                            'provenance':'keep separate from animation provider'},
        'source_fingerprint':sr['fingerprint'],'target_fingerprint':tr['fingerprint'],
        'source_world':source_world,'target_world':target_world,'source_checks':evidence,
        'source_roles':s_roles,'target_roles':t_roles,'mapping':pairs,
        'unmapped_source_bones':sorted(set(source.data.bones.keys())-set(pairs)),
        'unmapped_target_bones':sorted(set(target.data.bones.keys())-set(pairs.values())),
        'source_chain_notes':sr.get('chain_notes',[]),'target_chain_notes':tr.get('chain_notes',[]),
        'body_profile':profile,'units':{'source_meters_per_unit':o['source_meters_per_unit'],
            'target_meters_per_unit':o['target_meters_per_unit'],'unit_conversion':unit_conversion,
            'morphology_ratio':morphology,'runtime_translation_scale':scale},
        'facing':{'yaw_degrees':math.degrees(yaw),'source_forward':list(sf),'target_forward':list(tf),'evidence':facing_evidence},
        'alignment_method':'minimal anatomical swing; nearest target-rest twist; host must review terminal axes',
        'alignment_evidence':alignment_evidence,'retarget_options':retarget,'grounding':ground_evidence,
        'duration_seconds':(end-start)/sfps,'performance':'PENDING',
        'limitations':['not full IK, retiming, foot locking or volume fitting','terminal bone axes require review',
                       'no universal finger/control-rig support','review does not establish source quality or target licensing']}
    result['id']='tp_'+digest(result)
    return result


def verify_execution(lib, source, target, action, slot_id, options):
    if 'transfer_binding' not in options:return
    from .transfer_review import checked_binding
    proposal,_=checked_binding(lib,options)
    for obj,key in ((source,'source'),(target,'target')):
        rigid_object(obj)
        require(ops.rig_report(obj)['fingerprint']==proposal[key+'_fingerprint'],
                'STALE_TRANSFER_BINDING','Rig fingerprint changed since the reviewed proposal')
        expected=proposal[key+'_world'];actual=flat(obj.matrix_world)
        require(max(abs(a-b) for a,b in zip(actual,expected))<1e-5,
                'STALE_TRANSFER_BINDING','Rig placement/orientation changed since review')
    ops.assign(source,action,slot_id)
    require(action_signature(action,source.animation_data.action_slot)==proposal['source_checks']['curve_signature'],
            'STALE_TRANSFER_BINDING','Selected action curves/slot changed since review')
    return {key: dict(proposal[key+'_roles']) for key in ('source', 'target')}


def contact_check(options):
    guard();contract.contact(options)
    from .ground_contact import GroundContact,topology
    from .contact_diagnostics import summarize
    target=bpy.data.objects.get(options['target_object']);rigid_object(target)
    frames=contract.checkpoints(options)
    probes={side:GroundContact(target,None,{'mesh':options['mesh'],'vertex_groups':groups,
                'height':options['ground_z'],'max_correction':1}) for side,groups in options['feet'].items()}
    mesh_obj=probes['left'].mesh
    require(len(frames)*len(mesh_obj.data.vertices)<=50_000_000,'RESOURCE_LIMIT','Evaluated vertex/sample budget exceeded')
    require(not set(probes['left'].indices)&set(probes['right'].indices),'INVALID_GROUND_CONTACT','Left/right selections overlap; review weights')
    scene=bpy.context.scene; fps=scene.render.fps/scene.render.fps_base;samples=[]
    with ops.restore_context():
        for f in frames:
            scene.frame_set(math.floor(f),subframe=f-math.floor(f));bpy.context.view_layer.update()
            for probe in probes.values():
                probe.check_modifiers();require(topology(mesh_obj.data)==probe.topology,'CONTACT_TOPOLOGY_CHANGED','Base mesh topology changed')
            evaluated=mesh_obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
            try:
                require(topology(mesh)==probes['left'].topology,'CONTACT_TOPOLOGY_CHANGED','Evaluated vertex correspondence changed')
                sample={'frame':f,'time':f/fps}
                for side,probe in probes.items():
                    points=[evaluated.matrix_world@mesh.vertices[i].co for i in probe.indices]
                    sample[side]={'minimum_z':min(p.z for p in points),'centroid':list(sum(points,Vector())/len(points))}
                samples.append(sample)
            finally:evaluated.to_mesh_clear()
    return summarize(samples,options)|{'read_only':True,'fps':scene.render.fps/scene.render.fps_base,'target_fingerprint':ops.rig_report(target)['fingerprint'],
        'meters_per_unit':options['meters_per_unit'],'ground_z_scene_units':options['ground_z'],
        'selected_vertices':{s:len(p.indices) for s,p in probes.items()},'topology':probes['left'].topology}
