"""Blender-only generic scene audit and scoped camera/light helpers.

No subject names, scene genres, global resets, or required armatures. Call only
inside a reviewed working-file job. Technical framing is not artistic approval.
"""
from __future__ import annotations
import math
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from .core import fields, require
from .blender_ops import restore_context, vector, flatten

GEOMETRY = {'MESH','CURVE','SURFACE','FONT','META'}


def subjects(names):
    require(isinstance(names,list) and 1 <= len(names) <= 128 and all(isinstance(n,str) for n in names)
            and len(set(names))==len(names), 'SUBJECTS_REQUIRED', 'Provide explicit observed geometry object names')
    found = [bpy.context.scene.objects.get(n) for n in names]
    require(all(o is not None and o.type in GEOMETRY for o in found),
            'SUBJECTS_REQUIRED', 'Camera/light subjects must be actual geometry in this scene, not an assumed rig or empty')
    return found


def frames_from(options):
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


def camera_check(options):
    objects=subjects(options.get('subjects'))
    camera=bpy.context.scene.objects.get(options.get('camera',''))
    require(camera and camera.type=='CAMERA','CAMERA_REQUIRED','Specify the actual camera')
    require(camera.data.type in {'PERSP','ORTHO'},'CAMERA_UNSUPPORTED','Projection check supports perspective/orthographic cameras')
    margin=options.get('margin',0.0)
    require(type(margin) in (int,float) and 0<=margin<.45,'INVALID_SCHEMA','Invalid frame margin')
    report=[]
    with restore_context():
        for frame in frames_from(options):
            bpy.context.scene.frame_set(frame)
            cam=camera.evaluated_get(bpy.context.evaluated_depsgraph_get())
            projected=[world_to_camera_view(bpy.context.scene,cam,p) for p in points_at(objects)]
            x=[p.x for p in projected];y=[p.y for p in projected];z=[p.z for p in projected]
            fits=all(margin-1e-6<=v<=1-margin+1e-6 for v in x+y)
            fits=fits and min(z)>cam.data.clip_start and max(z)<cam.data.clip_end
            report.append({'frame':frame,'bounds_ndc':[min(x),min(y),max(x),max(y)],'depth':[min(z),max(z)],
                           'whole_bounds_in_frame':fits})
    return {'camera':camera.name,'checkpoints':report,'all_fit':all(r['whole_bounds_in_frame'] for r in report),
            'visual_acceptance':'PENDING','not_measured':['occlusion','camera-path collision','focus aesthetics','between-checkpoint extrema']}


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
