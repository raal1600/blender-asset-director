"""Actions-only visualisation of the actual, tested sequence result.

No production assets accepted. Run the existing synthetic sequence_fixture first.
We sample real evaluated Blender Actions/NLA, including honest native crossfade
baselines, then render identical display-only joint geometry for every method.
No retargeting/sequence algorithm is reimplemented by the renderer.
"""
from pathlib import Path
import json
import math
import os
import sys
import bpy
from mathutils import Matrix, Vector
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]
from asset_director import blender_ops as ops, sequence_blender as sb
from asset_director.core import load_json, atomic_json, file_hash

FPS = 30
FRAME_COUNT = 120
WIDTH, HEIGHT, SAMPLES = 480, 360, 8
METHODS = ('cut', 'nla', 'aligned', 'director')
SEGMENTS = [('hips','spine'),('spine','spine_mid'),('spine_mid','chest'),('chest','neck'),('neck','head')]
for side in ('l','r'):
    SEGMENTS += [('chest','upperarm_'+side),('upperarm_'+side,'forearm_'+side),
                 ('forearm_'+side,'hand_'+side),('hips','thigh_'+side),
                 ('thigh_'+side,'calf_'+side),('calf_'+side,'foot_'+side),('foot_'+side,'toe_'+side)]
ROLES = sorted({r for pair in SEGMENTS for r in pair})


def bounded_path(raw):
    path = Path(raw).resolve()
    root = Path(os.environ['RUNNER_TEMP']).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Showcase inputs/outputs must be inside the isolated Actions temporary directory')
    return path


def source_result(library, fixture):
    report = load_json(fixture/'sequence_report.json')
    assert report['status']=='PASS' and report['private_assets']=='NOT_USED'
    matches=[]
    for path in (library/'jobs').glob('*/sequence.json'):
        m=load_json(path)
        if len(m['joins'])==1 and abs(m['joins'][0]['duration_seconds']-.413)<1e-9:
            job=load_json(path.parent/'job.json')
            result=load_json(path.parent/'result.json')
            if job['state']=='SUCCEEDED' and result['status']=='OK':
                for name in ('result.blend','sequence.json','result.json'):
                    file=path.parent/name
                    receipt=next(f for f in job['outputs'] if f['path']==file.relative_to(library).as_posix())
                    assert receipt['size']==file.stat().st_size and receipt['sha256']==file_hash(file)
                matches.append((path,m,result['data']))
    assert len(matches)==1, 'Expected exactly the positively tested synthetic sequence'
    return matches[0]


def capture(target, roles, origin):
    bpy.context.view_layer.update()
    ev=target.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return {role:list(origin @ (ev.matrix_world @ ev.pose.bones[roles[role]].matrix).translation)
            for role in ROLES if role in roles}


def read_method(blend, manifest, method):
    bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False,use_scripts=False)
    target=bpy.data.objects[manifest['request']['target_object']]
    roles=manifest['roles']; fps=manifest['fps']; assert abs(fps-FPS)<1e-9
    # One constant normalisation for ALL views. Do not recenter each method.
    origin=target.matrix_world.inverted()
    if method=='director':
        checked=sb.check(target,manifest)
        assert all(e['status']=='PASS' for e in checked['endpoint_errors'])
        transition=[(manifest['joins'][0][k]-1)/fps for k in ('start','end')]
    else:
        originals=[]
        for descriptor in manifest['source_original_signatures']:
            action=bpy.data.actions[descriptor['imported_action']]
            slot=next(s for s in action.slots if s.identifier==descriptor['slot'])
            assert sb.signature(action,slot)==descriptor['curve_signature']
            originals.append((action,slot))
        a,sa=originals[0]; b,sbslot=originals[1]
        da,db=manifest['clips']; overlap=manifest['joins'][0]['duration_seconds']*fps
        incoming=manifest['timeline'][0]['end'] if method=='cut' else manifest['timeline'][0]['end']-overlap
        if method=='aligned':
            # Give NLA a fair positional control: match B to A at the START of
            # its overlap, not to A's later endpoint. Same explicit yaw as Director.
            reader=sb.Reader(target,4096)
            native=da['range'][0]+(incoming-1)*da['fps']/fps
            A=reader.read(a,sa,native); B=reader.read(b,sbslot,db['range'][0])
            anchor=manifest['anchor']
            yaw=Matrix.Rotation(math.radians(manifest['joins'][0]['yaw_degrees']),4,'Z')
            delta=A[anchor]['world'].translation-yaw@B[anchor]['world'].translation
            delta.z=0
            b,sbslot=sb.align_action(reader,b,sbslot,db,anchor,Matrix.Translation(delta)@yaw,'SHOWCASE_ALIGNED_CONTROL')
        for track in target.animation_data.nla_tracks:
            track.mute=True;track.is_solo=False
        target.animation_data.action=None;target.animation_data.use_nla=True
        for pb in target.pose.bones:pb.matrix_basis=Matrix.Identity(4)
        sb.nla(target,a,sa,da['range'],da['fps'],fps,1,'SHOWCASE_A')
        item=sb.nla(target,b,sbslot,db['range'],db['fps'],fps,incoming,'SHOWCASE_B')
        if method!='cut':
            strip=target.animation_data.nla_tracks[item['track']].strips[0]
            strip.blend_in=overlap
            assert abs(strip.blend_in-overlap)<1e-5 and strip.blend_type=='REPLACE'
        transition=[(incoming-1)/fps, (incoming-1)/fps+(0 if method=='cut' else overlap/fps)]
    samples=[]
    for index in range(FRAME_COUNT):
        sb.frame(1+index)
        samples.append(capture(target,roles,origin))
    assert len(samples)==FRAME_COUNT and all('hips' in row for row in samples)
    return {'transition_seconds':transition,'poses':samples}


def material(name,color):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1)
    m.use_nodes=True;m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*color,1)
    m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8
    return m


def sphere(name,radius,mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=radius)
    obj=bpy.context.object;obj.name=name;obj.data.materials.append(mat)
    for polygon in obj.data.polygons:polygon.use_smooth=True
    return obj


def line(name,radius,mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=10,radius=radius,depth=1)
    obj=bpy.context.object;obj.name=name;obj.data.materials.append(mat)
    for p in obj.data.polygons:p.use_smooth=True
    return obj


def point_line(obj,start,end):
    a,b=Vector(start),Vector(end);d=b-a
    obj.location=(a+b)/2;obj.rotation_mode='QUATERNION'
    if d.length>1e-8:obj.rotation_quaternion=d.to_track_quat('Z','Y')
    obj.scale.z=max(d.length,1e-8)


def render_all(data,output):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=SAMPLES
    sc.cycles.max_bounces=2;sc.cycles.use_denoising=False
    sc.render.threads_mode='FIXED';sc.render.threads=2
    sc.render.resolution_x=WIDTH;sc.render.resolution_y=HEIGHT;sc.render.resolution_percentage=100
    sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGB'
    sc.render.film_transparent=False;sc.view_settings.view_transform='Standard'
    sc.world=bpy.data.worlds.new('Showcase World');sc.world.use_nodes=True
    sc.world.node_tree.nodes['Background'].inputs[0].default_value=(.16,.18,.21,1)
    sc.world.node_tree.nodes['Background'].inputs[1].default_value=.6
    body=material('Identical body in all four views',(.58,.68,.76))
    joints_mat=material('Joint landmarks',(.86,.9,.91))
    floor_mat=material('Floor',(.10,.125,.155));grid_mat=material('Grid',(.24,.28,.32))
    marker_mat=material('Projected hips',(.35,.84,.67))
    floor_z=min(data['director']['poses'][0][f][2] for f in ('foot_l','foot_r'))-.042
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,floor_z))
    bpy.context.object.data.materials.append(floor_mat)
    for i in range(-8,11):
        g=line('Floor grid X',.004,grid_mat);point_line(g,(i*.5,-4,floor_z+.005),(i*.5,4,floor_z+.005))
        g=line('Floor grid Y',.004,grid_mat);point_line(g,(-4,i*.5,floor_z+.005),(5,i*.5,floor_z+.005))
    light_data=bpy.data.lights.new('Softbox','AREA');light_data.energy=650;light_data.size=5
    light=bpy.data.objects.new('Softbox',light_data);sc.collection.objects.link(light);light.location=(1,-3,5)
    light.rotation_euler=(Vector((.4,0,1))-light.location).to_track_quat('-Z','Y').to_euler()
    cam_data=bpy.data.cameras.new('Identical locked camera');cam=bpy.data.objects.new('Camera',cam_data)
    sc.collection.objects.link(cam);cam.location=(2.8,-7,3.1)
    cam.rotation_euler=(Vector((.58,0,1.0))-cam.location).to_track_quat('-Z','Y').to_euler()
    cam_data.type='ORTHO';cam_data.ortho_scale=3.8;sc.camera=cam
    shared=set.intersection(*(set(d['poses'][0]) for d in data.values()))
    edges=[(a,b,line(a+' → '+b,.047 if a in ('hips','spine','spine_mid','chest') else .032,body))
           for a,b in SEGMENTS if a in shared and b in shared]
    nodes={role:sphere(role,.115 if role=='head' else .042,joints_mat) for role in shared}
    marker=sphere('Projected anchor (not physical contact)',.04,marker_mat)
    trail=bpy.data.curves.new('Observed projected hips path','CURVE');trail.dimensions='3D';trail.bevel_depth=.011;trail.bevel_resolution=1
    spline=trail.splines.new('POLY');spline.points.add(FRAME_COUNT-1)
    trail_obj=bpy.data.objects.new('Observed projected hips path',trail);sc.collection.objects.link(trail_obj);trail.materials.append(marker_mat)
    for method in METHODS:
        folder=output/method;folder.mkdir()
        for index,row in enumerate(data[method]['poses']):
            for a,b,obj in edges:point_line(obj,row[a],row[b])
            for role,obj in nodes.items():obj.location=row[role]
            marker.location=(row['hips'][0],row['hips'][1],floor_z+.018)
            for j,p in enumerate(spline.points):
                h=data[method]['poses'][min(j,index)]['hips'];p.co=(h[0],h[1],floor_z+.009,1)
            sc.render.filepath=str(folder/f'{index:04d}.png')
            bpy.ops.render.render(write_still=True)
        print('SHOWCASE_RENDERED',method,FRAME_COUNT,flush=True)


def main(library_raw,fixture_raw,output_raw):
    assert bpy.app.background and os.environ.get('GITHUB_ACTIONS')=='true','Run only in disposable Actions workspace'
    library,fixture,output=map(bounded_path,(library_raw,fixture_raw,output_raw));output.mkdir(parents=True,exist_ok=False)
    path,manifest,result=source_result(library,fixture);blend=path.parent/'result.blend';before=file_hash(blend)
    data={name:read_method(blend,manifest,name) for name in METHODS}
    for name in METHODS:
        for i in range(15):
            for role in data['director']['poses'][i]:
                assert (Vector(data[name]['poses'][i][role])-Vector(data['director']['poses'][i][role])).length<1e-5
    assert file_hash(blend)==before,'Sampling mutated authoritative result bytes'
    # Whitelist public numbers; never publish library manifests or permissions.
    metrics={'schema':'asset-director.transition-showcase/1','synthetic':True,'private_assets_used':False,
      'runtime':'0.6.0-dev.4','commit':os.environ['GITHUB_SHA'],'engine_base_commit':'389e8f28689e228370334b7cf4c529bead87a7d3',
      'actions_run':f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}',
      'blender':bpy.app.version_string,'fixture_status':'PASS','frames_per_method':FRAME_COUNT,'fps':FPS,
      'rendered_seconds':FRAME_COUNT/FPS,'last_observed_seconds':(FRAME_COUNT-1)/FPS,
      'render':{'width_per_method':WIDTH,'height_per_method':HEIGHT,'samples':SAMPLES,'engine':'CYCLES','device':'CPU','total_frames':FRAME_COUNT*len(METHODS)},
      'source_seconds':[d['duration_seconds'] for d in manifest['clips']],
      'director_sequence_seconds':manifest['duration_seconds'],'bridge_seconds':manifest['joins'][0]['duration_seconds'],
      'yaw_degrees':manifest['joins'][0]['yaw_degrees'],'placement':manifest['request']['joins'][0]['placement'],
      'unaligned_gap_m':manifest['joins'][0]['unaligned_anchor_gap_m'],
      'endpoint_errors':result['qa']['endpoint_errors'],'seams':result['qa']['seams'],
      'source_result_sha256':before,'original_result_unchanged':True,
      'performance':'PENDING','human':'NOT_ESTABLISHED',
      'methodology':'Original Actions/NLA evaluated in Blender. Identical display-only joint geometry and fixed camera for all four methods. NLA overlaps the source clips; Director adds bridge time and retains both complete clips. No claim of equal source phase after the transition.',
      'methods':{k:{'transition_seconds':v['transition_seconds'],'anchor_positions':[row['hips'] for row in v['poses']]} for k,v in data.items()}}
    atomic_json(output/'metrics.json',metrics)
    render_all(data,output)
    assert file_hash(blend)==before
    print('SHOWCASE_COMPLETE',json.dumps({'frames':FRAME_COUNT*4,'source_unchanged':True}),flush=True)


if __name__=='__main__':main(*sys.argv[sys.argv.index('--')+1:])
