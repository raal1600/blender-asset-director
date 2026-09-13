"""Blender-only generic scene audit and scoped camera/light helpers.

No subject names, scene genres, global resets, or required armatures. Call only
inside a reviewed working-file job. Technical framing is not artistic approval.
"""
from __future__ import annotations
import math
import bpy
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
from .core import fields, require
from .blender_ops import curves, restore_context, vector, flatten
from . import camera_plan as plan_contract

GEOMETRY = {'MESH','CURVE','SURFACE','FONT','META'}
OCCLUSION_MAX_TRIANGLES = 4_000_000
OCCLUSION_MAX_RAYS = 400
SCREEN_TARGET_TOLERANCE = 5e-3
SCREEN_TARGET_FAILURE = 2e-2


def subjects(names):
    require(isinstance(names,list) and 1 <= len(names) <= 128 and all(isinstance(n,str) for n in names)
            and len(set(names))==len(names), 'SUBJECTS_REQUIRED', 'Provide explicit observed geometry object names')
    found = [bpy.context.scene.objects.get(n) for n in names]
    require(all(o is not None and o.type in GEOMETRY for o in found),
            'SUBJECTS_REQUIRED', 'Camera/light subjects must be actual geometry in this scene, not an assumed rig or empty')
    return found


def frames_from(options):
    samples=options.get('sample')
    if samples is not None:
        require(options.get('frames') is None,'INVALID_SCHEMA','Use either frames or sample, never both')
        fields(samples,{'start','end','count'},{'start','end','count'})
        start,end,count=samples['start'],samples['end'],samples['count']
        require(all(type(v) is int for v in (start,end,count)) and -100000<=start<=end<=100000 and 1<=count<=32,
                'RESOURCE_LIMIT','Sample one to 32 integer frames across an ordered range')
        if count==1: return [start]
        span=end-start
        return sorted({start+int(round(span*i/(count-1))) for i in range(count)})
    frames=options.get('frames',[bpy.context.scene.frame_current])
    require(isinstance(frames,list) and 1 <= len(frames) <= 32
            and all(type(f) is int and -100000 <= f <= 100000 for f in frames),
            'RESOURCE_LIMIT','Use one to 32 explicit frame checkpoints')
    return sorted(set(frames))


def points_at(objects):
    deps=bpy.context.evaluated_depsgraph_get()
    points=[]
    for obj in objects:
        evaluated=obj.evaluated_get(deps)
        bounds=list(evaluated.bound_box)
        require(bounds and not all(all(v==-1 for v in p) for p in bounds), 'BOUNDS_UNKNOWN', 'Evaluated geometry has no bounds')
        points.extend(evaluated.matrix_world @ Vector(p) for p in bounds)
    require(points and all(math.isfinite(v) for p in points for v in p), 'INVALID_BOUNDS','Nonfinite geometry bounds')
    return points


def bounding_box(points):
    low=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    extent=max(high-low)
    require(extent>1e-9,'EMPTY_SUBJECT','Subject extent is zero')
    return (low+high)/2,extent


def scene_audit():
    scene=bpy.context.scene
    require(len(scene.objects)<=10000,'RESOURCE_LIMIT','Scene exceeds bounded audit size')
    objects=[]
    for obj in sorted(scene.objects,key=lambda o:o.name):
        item={'name':obj.name,'type':obj.type,'parent':obj.parent.name if obj.parent else None,
              'matrix_world':flatten(obj.matrix_world),'dimensions':vector(obj.dimensions),
              'hide_render':obj.hide_render,'semantic_role':'UNKNOWN',
              'materials':[s.material.name if s.material else None for s in obj.material_slots]}
        if obj.type in GEOMETRY:
            try:
                points=points_at([obj]);center,extent=bounding_box(points)
                item['bounds_world']=[vector(p) for p in points]; item['center_world']=vector(center);item['extent']=extent
            except Exception as exc:
                item['bounds_status']=type(exc).__name__
        if obj.type=='MESH':
            item['vertices']=len(obj.data.vertices);item['polygons']=len(obj.data.polygons)
            item['uv_layers']=[u.name for u in obj.data.uv_layers]
        if obj.type=='CAMERA':
            item['camera']={'projection':obj.data.type,'lens_mm':obj.data.lens,'sensor_width_mm':obj.data.sensor_width,
                            'sensor_fit':obj.data.sensor_fit,'focus_distance':obj.data.dof.focus_distance,
                            'focus_object':obj.data.dof.focus_object.name if obj.data.dof.focus_object else None,
                            'dof_enabled':obj.data.dof.use_dof}
        if obj.type=='LIGHT':
            item['light']={'type':obj.data.type,'energy':obj.data.energy,'color':vector(obj.data.color)}
        objects.append(item)
    materials=[]
    for mat in sorted(bpy.data.materials,key=lambda m:m.name):
        images=[]
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type=='TEX_IMAGE' and node.image:
                    images.append({'image':node.image.name,'size':list(node.image.size),
                                   'colorspace':node.image.colorspace_settings.name})
        materials.append({'name':mat.name,'uses_nodes':mat.use_nodes,'images':images,
                          'node_types':sorted(n.bl_idname for n in mat.node_tree.nodes) if mat.use_nodes else []})
    return {'objects':objects,'materials':materials,'fps':scene.render.fps/scene.render.fps_base,
            'frame_range':[scene.frame_start,scene.frame_end], 'frame_current':scene.frame_current,
            'resolution':[scene.render.resolution_x,scene.render.resolution_y],
            'pixel_aspect':[scene.render.pixel_aspect_x,scene.render.pixel_aspect_y],
            'units':{'system':scene.unit_settings.system,'scale_length':scene.unit_settings.scale_length},
            'camera':scene.camera.name if scene.camera else None,'world':scene.world.name if scene.world else None,
            'color_management':{'view_transform':scene.view_settings.view_transform,'look':scene.view_settings.look,
                                'exposure':scene.view_settings.exposure,'gamma':scene.view_settings.gamma},
            'blender_version':bpy.app.version_string,'semantic_analysis':'NOT_PERFORMED',
            'not_measured':['asset suitability','historical authenticity','visual realism','complete scene identity hash']}


def aim_point(objects,aim):
    """Evaluated world point for an aim definition at the current frame."""
    if 'point' in aim:
        return Vector(aim['point'])
    target=next((o for o in objects if o.name==aim['subject']),None)
    require(target is not None,'SUBJECTS_REQUIRED','Aim subject must be one of the checked subjects')
    points=points_at([target])
    low=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    fraction=aim.get('bounds',[0.5,0.5,0.5])
    return Vector(tuple(low[i]+(high[i]-low[i])*fraction[i] for i in range(3)))


def orientation_report(cam):
    matrix=cam.matrix_world.to_3x3()
    forward=(matrix @ Vector((0,0,-1))).normalized()
    up=(matrix @ Vector((0,1,0))).normalized()
    pitch=math.degrees(math.asin(max(-1.0,min(1.0,forward.z))))
    right=forward.cross(Vector((0,0,1)))
    if right.length<1e-6:
        roll=0.0
    else:
        right.normalize(); level_up=right.cross(forward)
        roll=math.degrees(math.atan2(up.dot(right),up.dot(level_up)))
    return {'forward':vector(forward),'up':vector(up),'pitch_deg':pitch,'roll_deg':roll}


def occluder_trees(excluded):
    """One BVH per renderable mesh that could block a sight line, bounded by triangles.

    BVHTree.FromObject returns geometry in the object's local space (verified on
    Blender 5.2.1), so each tree is paired with the matrix its rays are cast in.
    Transforming rays is exact under affine transforms and avoids copying large
    evaluated meshes into world space.
    """
    deps=bpy.context.evaluated_depsgraph_get(); trees=[]; triangles=0
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or obj.name in excluded or obj.hide_render: continue
        evaluated=obj.evaluated_get(deps); mesh=evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles(); count=len(mesh.loop_triangles)
        finally:
            evaluated.to_mesh_clear()
        require(triangles+count<=OCCLUSION_MAX_TRIANGLES,'RESOURCE_LIMIT',
                'Scene exceeds the bounded occlusion ray-test budget')
        triangles+=count
        trees.append({'name':obj.name,'tree':BVHTree.FromObject(obj,deps),'matrix':evaluated.matrix_world.copy()})
    return trees


def occlusion_sample(cam,trees,points):
    origin=cam.matrix_world.translation; blocked=[]
    for index,point in enumerate(points):
        offset=point-origin; distance=offset.length
        if distance<=1e-6: continue
        direction=offset/distance; nearest=None
        for entry in trees:
            try:
                inverse=entry['matrix'].inverted()
            except ValueError:
                continue
            local_origin=inverse @ origin
            local_direction=inverse.to_3x3() @ direction
            scale=local_direction.length
            if scale<=1e-12: continue
            hit=entry['tree'].ray_cast(local_origin,local_direction/scale,distance*scale)
            if hit[0] is None: continue
            world_distance=hit[3]/scale
            if nearest is None or world_distance<nearest: nearest=world_distance
        if nearest is not None and nearest<distance-max(0.005,distance*0.002): blocked.append(index)
    return blocked


def bound_points(objects):
    """Eight evaluated bounds corners plus the centre, per subject."""
    points=[]
    for obj in objects:
        corners=points_at([obj]); points.extend(corners)
        points.append(sum(corners,Vector())/len(corners))
    return points


def check_targets(options):
    raw=options.get('targets')
    if raw is None: return {}
    require(isinstance(raw,list) and 1<=len(raw)<=32,'RESOURCE_LIMIT','Provide one to 32 screen targets')
    targets={}
    for entry in raw:
        fields(entry,{'frame','subject','bounds','screen'},{'frame','subject','screen'})
        frame=entry['frame']
        require(type(frame) is int and -100000<=frame<=100000,'INVALID_SCHEMA','Target frame must be a bounded integer')
        require(frame not in targets,'INVALID_SCHEMA','Duplicate target frame')
        aim={'subject':entry['subject']}
        if 'bounds' in entry: aim['bounds']=entry['bounds']
        targets[frame]={'aim':plan_contract.resolve_aim(aim),'screen':plan_contract.screen_target(entry['screen']),
                        'subject':entry['subject']}
    return targets


def camera_check(options):
    objects=subjects(options.get('subjects'))
    camera=bpy.context.scene.objects.get(options.get('camera',''))
    require(camera and camera.type=='CAMERA','CAMERA_REQUIRED','Specify the actual camera')
    require(camera.data.type in {'PERSP','ORTHO'},'CAMERA_UNSUPPORTED','Projection check supports perspective/orthographic cameras')
    margin=options.get('margin',0.0)
    require(type(margin) in (int,float) and 0<=margin<.45,'INVALID_SCHEMA','Invalid frame margin')
    targets=check_targets(options); occlusion=bool(options.get('occlusion')); frames=frames_from(options)
    require(not occlusion or len(frames)*len(objects)*9<=OCCLUSION_MAX_RAYS,'RESOURCE_LIMIT',
            'Occlusion sampling exceeds the bounded ray budget')
    scene=bpy.context.scene; report=[]
    with restore_context():
        trees=occluder_trees({o.name for o in objects}) if occlusion else []
        for frame in frames:
            scene.frame_set(frame)
            cam=camera.evaluated_get(bpy.context.evaluated_depsgraph_get())
            projected=[world_to_camera_view(scene,cam,p) for p in points_at(objects)]
            x=[p.x for p in projected];y=[p.y for p in projected];z=[p.z for p in projected]
            fits=all(margin-1e-6<=v<=1-margin+1e-6 for v in x+y)
            fits=fits and min(z)>cam.data.clip_start and max(z)<cam.data.clip_end
            entry={'frame':frame,'bounds_ndc':[min(x),min(y),max(x),max(y)],'depth':[min(z),max(z)],
                   'whole_bounds_in_frame':fits,'camera_location':vector(cam.matrix_world.translation),
                   'lens_mm':cam.data.lens,'sensor_width_mm':cam.data.sensor_width,'sensor_fit':cam.data.sensor_fit,
                   'clip_planes':[cam.data.clip_start,cam.data.clip_end],'resolution':[scene.render.resolution_x,scene.render.resolution_y],
                   **orientation_report(cam)}
            target=targets.get(frame)
            if target:
                point=aim_point(objects,target['aim']); projection=world_to_camera_view(scene,cam,point)
                error_x=abs(projection.x-target['screen'][0]); error_y=abs(projection.y-target['screen'][1])
                entry['screen_target']={'subject':target['subject'],'requested':list(target['screen']),
                                        'achieved':[projection.x,projection.y],
                                        'error_normalized':[error_x,error_y],'error_max':max(error_x,error_y),
                                        'error_pixels':[error_x*scene.render.resolution_x,error_y*scene.render.resolution_y],
                                        'distance':(point-cam.matrix_world.translation).length,
                                        'within_tolerance':max(error_x,error_y)<=SCREEN_TARGET_TOLERANCE}
            if occlusion:
                points=bound_points(objects); blocked=occlusion_sample(cam,trees,points)
                entry['occlusion']={'rays':len(points),'blocked':len(blocked),'blocked_indices':blocked,
                                    'note':'obvious external occluders only; subject geometry excluded'}
            report.append(entry)
    measured=[] if not targets else [r['screen_target']['error_max'] for r in report if 'screen_target' in r]
    return {'camera':camera.name,'checkpoints':report,'all_fit':all(r['whole_bounds_in_frame'] for r in report),
            'occlusion_checked':occlusion,'max_screen_error':max(measured) if measured else None,
            'screen_targets_within_tolerance':all(r['screen_target']['within_tolerance'] for r in report if 'screen_target' in r),
            'visual_acceptance':'PENDING',
            'not_measured':['artistic composition','camera-path collision','focus aesthetics',
                            'between-checkpoint extrema','motion blur']+([] if occlusion else ['subject occlusion'])}


def camera_fit(options,owner):
    objects=subjects(options.get('subjects'));frames=frames_from(options)
    direction=options.get('direction')
    require(isinstance(direction,list) and len(direction)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in direction),
            'DIRECTION_REQUIRED','Provide a world-space subject-to-camera direction')
    direction=Vector(direction);require(direction.length>1e-9,'DIRECTION_REQUIRED','Zero camera direction')
    direction.normalize()
    lens=options.get('lens_mm');sensor=options.get('sensor_width_mm',36.0);margin=options.get('margin',.1)
    require(type(lens) in (int,float) and 1<=lens<=1000,'LENS_REQUIRED','Choose an explicit lens, not a genre default')
    require(type(sensor) in (int,float) and 1<=sensor<=100,'INVALID_SCHEMA','Invalid sensor width')
    require(type(margin) in (int,float) and 0<=margin<.45,'INVALID_SCHEMA','Invalid margin')
    projection=options.get('projection','PERSP')
    require(projection in {'PERSP','ORTHO'},'CAMERA_UNSUPPORTED','Unsupported projection')
    scene=bpy.context.scene
    with restore_context():
        points=[]
        for f in frames:
            scene.frame_set(f);points.extend(points_at(objects))
        center,extent=bounding_box(points)
        data=bpy.data.cameras.new('BAD_CAM_'+owner);data.type=projection;data.lens=lens;data.sensor_width=sensor
        camera=bpy.data.objects.new(data.name,data);scene.collection.objects.link(camera)
        camera.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
        data.clip_start=max(1e-6,extent*1e-5);data.clip_end=max(100,extent*10000)
        def fits(value):
            camera.location=center+direction*(value if projection=='PERSP' else extent*10)
            if projection=='ORTHO':data.ortho_scale=value
            bpy.context.view_layer.update()
            for point in points:
                p=world_to_camera_view(scene,camera,point)
                if not (margin<=p.x<=1-margin and margin<=p.y<=1-margin and data.clip_start<p.z<data.clip_end):return False
            return True
        lo,hi=0.0,extent
        for _ in range(24):
            if fits(hi):break
            hi*=2
        else:
            bpy.data.objects.remove(camera,do_unlink=True);bpy.data.cameras.remove(data)
            raise RuntimeError('Cannot fit bounded subject with these lens/sensor settings')
        for _ in range(32):
            mid=(lo+hi)/2
            if fits(mid):hi=mid
            else:lo=mid
        fits(hi*1.001)
        # Focus on observed bounds, never a possibly offset object origin. Disabled
        # until a shot-specific focal plane/aperture has been selected by the host.
        data.dof.focus_distance=(center-camera.location).length;data.dof.use_dof=False
        scene.camera=camera
        result=camera_check({'subjects':options['subjects'],'camera':camera.name,'frames':frames,'margin':margin})
        result.update({'center':vector(center),'extent':extent,'lens_mm':lens,'projection':projection,
                       'notice':'Technical full-bounds fit, not an artistic composition or collision clearance'})
        return result


def light_rig(options,owner):
    objects=subjects(options.get('subjects'));center,extent=bounding_box(points_at(objects))
    specs=options.get('lights')
    require(isinstance(specs,list) and 1<=len(specs)<=8,'RESOURCE_LIMIT','Specify one to eight motivated lights')
    # Validate the complete request before creating any datablock.
    for spec in specs:
        fields(spec,{'type','energy','offset','color','size_ratio'}, {'type','energy','offset','color'})
        require(spec['type'] in {'SUN','AREA','POINT','SPOT'},'INVALID_SCHEMA','Unsupported light type')
        require(type(spec['energy']) in (int,float) and 0<=spec['energy']<=1e6,'RESOURCE_LIMIT','Invalid light energy')
        for key in ('offset','color'):
            require(isinstance(spec[key],list) and len(spec[key])==3
                    and all(type(v) in (int,float) and math.isfinite(v) for v in spec[key]),'INVALID_SCHEMA','Invalid light vector')
        require(Vector(spec['offset']).length>1e-6 and max(abs(v) for v in spec['offset'])<=1000,'INVALID_SCHEMA','Invalid light offset')
        require(all(0<=v<=1 for v in spec['color']),'INVALID_SCHEMA','Invalid light color')
        size=spec.get('size_ratio',1.0)
        require(type(size) in (int,float) and 0<size<=100,'INVALID_SCHEMA','Invalid relative light size')
    created=[]
    for i,spec in enumerate(specs):
        data=bpy.data.lights.new('BAD_LIGHT_'+owner+'_'+str(i),spec['type'])
        data.energy=spec['energy'];data.color=spec['color']
        if data.type=='AREA':data.size=extent*spec.get('size_ratio',1.0)
        obj=bpy.data.objects.new(data.name,data);bpy.context.scene.collection.objects.link(obj)
        obj.location=center+extent*Vector(spec['offset'])
        obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
        created.append(obj.name)
    return {'created_lights':created,'subject_center':vector(center),'subject_extent':extent,
            'existing_world_preserved':True,'existing_lights_preserved':True,'visual_acceptance':'PENDING',
            'notice':'Explicit additive light plan; powers/colors are caller choices, not automatic physical calibration'}


def merged_dof(plan,entry):
    """Plan-level DOF with per-checkpoint overrides; absent values are not authored."""
    merged=dict(plan.get('dof') or {})
    merged.update(entry.get('dof') or {})
    return merged


def camera_plan(options,owner):
    """Author an explicit, host-decided camera move.

    Every creative value is caller-supplied: checkpoints, placement, aim, lens,
    screen position, roll, interpolation and focus. This function solves and
    keyframes those values, then verifies them with real projection. It never
    invents a framing, a lens, a frame rate or a duration.
    """
    plan=plan_contract.validate(options)
    scene=bpy.context.scene
    found=subjects(plan['subjects']); by_name={o.name:o for o in found}
    for entry in plan['keyframes']:
        if 'subject' in entry['aim']:
            require(entry['aim']['subject'] in by_name,'SUBJECTS_REQUIRED','Aim subjects must be listed in subjects')
    all_points=[]
    with restore_context():
        for entry in plan['keyframes']:
            scene.frame_set(entry['frame']); all_points.extend(points_at(found))
    _,extent=bounding_box(all_points)
    preserved_actions=[]; preserved_animation=[]; muted_constraints=[]
    if plan['mode']=='adapt':
        camera=scene.objects.get(plan['camera'])
        require(camera is not None,'CAMERA_REQUIRED','Adapt needs the observed camera object name')
        require(camera.type=='CAMERA','CAMERA_REQUIRED','Adapt target must be a camera object')
        require(camera.data.type=='PERSP','CAMERA_UNSUPPORTED',
                'camera-plan authors perspective moves; adapt a perspective camera or use camera-fit')
        data=camera.data
        if camera.animation_data and camera.animation_data.action:
            existing=camera.animation_data.action
            if plan['existing_animation']=='preserve':
                track=camera.animation_data.nla_tracks.new(); track.name='BAD_PRESERVED_'+existing.name
                strip=track.strips.new(existing.name,int(existing.frame_range[0]),existing)
                strip.name=existing.name; track.mute=True
                preserved_animation.append({'action':existing.name,'nla_track':track.name,'muted':True})
            else:
                existing.use_fake_user=True
                preserved_animation.append({'action':existing.name,'nla_track':None,'fake_user':True})
            camera.animation_data.action=None; preserved_actions.append(existing.name)
        if plan['constraints']=='mute':
            for constraint in camera.constraints:
                if not constraint.mute:
                    constraint.mute=True; muted_constraints.append(constraint.name)
        rotation_mode=plan['rotation_mode'] or camera.rotation_mode
    else:
        require((plan['name'] or '') not in bpy.data.objects,'NAME_TAKEN',
                'Choose a camera name that does not already exist; the runtime does not rename silently')
        data=bpy.data.cameras.new('BAD_CAM_'+owner)
        camera=bpy.data.objects.new(plan['name'] or data.name,data)
        scene.collection.objects.link(camera)
        data.type='PERSP'; data.clip_start=max(1e-4,extent*1e-5); data.clip_end=max(100.0,extent*10000.0)
        rotation_mode=plan['rotation_mode'] or 'QUATERNION'
    data.sensor_width=plan['sensor_width_mm']; data.sensor_fit=plan['sensor_fit']
    data.sensor_height=plan['sensor_height_mm']
    focus_name=(plan.get('dof') or {}).get('focus_object')
    if focus_name:
        focus=bpy.data.objects.get(focus_name)
        require(focus is not None,'INVALID_SCHEMA','focus_object must be an existing object')
        data.dof.focus_object=focus
    computed=[]
    with restore_context():
        for entry in plan['keyframes']:
            scene.frame_set(entry['frame'])
            aim=aim_point(found,entry['aim'])
            lens=entry.get('lens_mm',plan['lens_mm'])
            data.lens=lens
            sensor_w,sensor_h=plan_contract.sensor_extents(plan['sensor_width_mm'],plan['sensor_height_mm'],
                plan['sensor_fit'],
                (scene.render.resolution_x,scene.render.resolution_y),
                (scene.render.pixel_aspect_x,scene.render.pixel_aspect_y))
            yaw,pitch=plan_contract.screen_angles(*plan_contract.half_angles(lens,sensor_w,sensor_h),entry['screen'])
            roll=math.radians(entry.get('roll_deg',plan['roll_deg'] or 0.0))
            def orient():
                base=(aim-camera.location).to_track_quat('-Z','Y')
                camera.rotation_mode='QUATERNION'
                camera.rotation_quaternion=(base@Quaternion((0,0,1),roll)
                                            @Quaternion((0,1,0),yaw)@Quaternion((1,0,0),pitch))
                bpy.context.view_layer.update()
            def projected_of(point):
                # Judge the evaluated camera so a kept constraint cannot silently
                # defeat the authored aim; the check must see what will render.
                evaluated=camera.evaluated_get(bpy.context.evaluated_depsgraph_get())
                return world_to_camera_view(scene,evaluated,point)
            if 'position' in entry:
                camera.location=Vector(entry['position']); orient()
                distance=(camera.location-aim).length
            else:
                direction=Vector(entry['direction']).normalized()
                if 'distance' in entry:
                    camera.location=aim+direction*entry['distance']; orient(); distance=entry['distance']
                else:
                    margin=entry['fit']['margin']
                    def fits(value):
                        camera.location=aim+direction*value; orient()
                        for point in points_at(found):
                            projected=projected_of(point)
                            if not (margin<=projected.x<=1-margin and margin<=projected.y<=1-margin
                                    and data.clip_start<projected.z<data.clip_end): return False
                        return True
                    solved=plan_contract.bisect_threshold(fits,max(extent*1e-3,1e-4),max(extent,1.0),limit=extent*1e6)
                    distance=solved*1.001; camera.location=aim+direction*distance; orient()
            projected=projected_of(aim)
            error_x=abs(projected.x-entry['screen'][0]); error_y=abs(projected.y-entry['screen'][1])
            require(max(error_x,error_y)<=SCREEN_TARGET_FAILURE,'SCREEN_TARGET_MISSED',
                    'Authored orientation cannot place the aim point at the requested screen position; '
                    'check camera shift or kept constraints')
            computed.append({'frame':entry['frame'],'location':list(camera.location),
                             'rotation':list(camera.rotation_quaternion),'lens_mm':lens,'aim':list(aim),
                             'screen':entry['screen'],'achieved':[projected.x,projected.y],
                             'error':[error_x,error_y],'distance':distance,'roll_deg':math.degrees(roll),
                             'dof':merged_dof(plan,entry)})
    with restore_context():
        for item in computed:
            frame=item['frame']
            camera.location=Vector(item['location'])
            if rotation_mode=='QUATERNION':
                camera.rotation_mode='QUATERNION'; camera.rotation_quaternion=Quaternion(item['rotation'])
                camera.keyframe_insert('rotation_quaternion',frame=frame)
            else:
                camera.rotation_mode=rotation_mode
                camera.rotation_euler=Quaternion(item['rotation']).to_euler(rotation_mode)
                camera.keyframe_insert('rotation_euler',frame=frame)
            camera.keyframe_insert('location',frame=frame)
            if item['lens_mm'] is not None:
                data.lens=item['lens_mm']; data.keyframe_insert('lens',frame=frame)
            dof=item['dof']
            if dof.get('use_dof') is not None:
                data.dof.use_dof=dof['use_dof']; data.dof.keyframe_insert('use_dof',frame=frame)
            if dof.get('focus_distance') is not None:
                data.dof.focus_distance=dof['focus_distance']; data.dof.keyframe_insert('focus_distance',frame=frame)
    action=camera.animation_data.action if camera.animation_data else None
    require(action is not None,'ACTION_REQUIRED','Camera animation was not created')
    interpolation=plan['interpolation']
    for curve in curves(action):
        for point in curve.keyframe_points:
            point.interpolation=interpolation['type']; point.easing=interpolation['easing']
            point.handle_left_type=interpolation['handle_left']; point.handle_right_type=interpolation['handle_right']
        curve.extrapolation=interpolation['extrapolation']
    if plan['frame_range']:
        scene.frame_start,scene.frame_end=plan['frame_range']
    if plan['fps']:
        exact=float(plan['fps']); whole=int(exact)
        scene.render.fps=whole; scene.render.fps_base=1.0 if abs(exact-whole)<1e-9 else whole/exact
    if plan['set_scene_camera']: scene.camera=camera
    targets=[{'frame':k['frame'],'subject':k['aim']['subject'],'screen':k['screen'],'bounds':k['aim']['bounds']}
             for k in plan['keyframes'] if 'subject' in k['aim']]
    verification=camera_check({'subjects':plan['subjects'],'camera':camera.name,
                               'frames':[k['frame'] for k in plan['keyframes']],'targets':targets,
                               'occlusion':True,'margin':0.0})
    return {'camera':camera.name,'mode':plan['mode'],'action':action.name,'rotation_mode':rotation_mode,
            'projection':data.type,'lens_mm':plan['lens_mm'],
            'sensor':{'width_mm':plan['sensor_width_mm'],'height_mm':plan['sensor_height_mm'],
                      'fit':plan['sensor_fit']},
            'keyframes':[{'frame':c['frame'],'camera_location':c['location'],'aim_point':c['aim'],
                          'screen_requested':c['screen'],'screen_achieved':c['achieved'],
                          'screen_error_normalized':c['error'],'distance':c['distance'],
                          'lens_mm':c['lens_mm'],'roll_deg':c['roll_deg']} for c in computed],
            'scene_camera':scene.camera.name if scene.camera else None,
            'frame_range':[scene.frame_start,scene.frame_end],
            'fps':scene.render.fps/scene.render.fps_base,'interpolation':interpolation,
            'clip_planes':[data.clip_start,data.clip_end],'preserved_actions':preserved_actions,
            'preserved_animation':preserved_animation,'muted_constraints':muted_constraints,
            'max_screen_error':max(max(c['error']) for c in computed),'verification':verification,
            'visual_acceptance':'PENDING',
            'limitations':['Perspective cameras only; an orthographic plan is rejected rather than approximated.',
                           'Occlusion evidence comes from bounded ray tests, not collision or clearance safety.',
                           'Camera-path collision between checkpoints is not evaluated.',
                           'focus_object is a static assignment because object pointers are not keyframable; key focus distances or animate the target object.',
                           'Numeric framing evidence is not artistic acceptance.']}
