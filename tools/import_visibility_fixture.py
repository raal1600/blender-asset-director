"""Real import -> rig widgets -> repaired checkpoint -> GLB visibility regression.

Synthetic local inputs only. No UI, credentials, downloads or human approval.
"""
from pathlib import Path
import json,struct,sys
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from asset_director import jobs,blender_ops as ops,bone_display
from asset_director.core import Asset,Library,atomic_json,file_hash,digest,load_json
from asset_director.viewer_export import export

out=Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=False)
checks=[]
def check(value,name):checks.append({'name':name,'status':'PASS' if value else 'FAIL'})
def snapshot(rig,skin):
    return {'rest':ops.rig_report(rig)['fingerprint'],
            'refs':{p.name:p.custom_shape.name if p.custom_shape else None for p in rig.pose.bones},
            'skin':digest({'verts':[list(v.co) for v in skin.data.vertices],
                'weights':[[(g.group,g.weight) for g in v.groups] for v in skin.data.vertices]}),
            'actions':{a.name:digest([[c.data_path,c.array_index,[[list(k.co),k.interpolation] for k in c.keyframe_points]] for c in ops.curves(a)]) for a in bpy.data.actions},
            'objects':sorted((o.name,o.type,ops.flatten(o.matrix_world)) for o in bpy.data.objects)}
def exported_meshes(path):
    raw=path.read_bytes();assert raw[:4]==b'glTF'
    size,kind=struct.unpack_from('<II',raw,12);assert kind==0x4e4f534a
    data=json.loads(raw[20:20+size]);return {n.get('name') for n in data['nodes'] if 'mesh' in n}

try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.render.fps=24;scene.frame_start=1;scene.frame_end=9
    arm=bpy.data.armatures.new('SyntheticRig');rig=bpy.data.objects.new('SyntheticRig',arm)
    scene.collection.objects.link(rig);rig.select_set(True);bpy.context.view_layer.objects.active=rig
    bpy.ops.object.mode_set(mode='EDIT');bone=arm.edit_bones.new('SyntheticBone');bone.head=(0,0,0);bone.tail=(0,0,1)
    bpy.ops.object.mode_set(mode='OBJECT');bpy.ops.mesh.primitive_cube_add(size=.4,location=(0,0,.5))
    body=bpy.context.object;body.name='SyntheticBody';body.parent=rig
    group=body.vertex_groups.new(name='SyntheticBone');group.add(list(range(8)),1,'REPLACE')
    modifier=body.modifiers.new('Skin','ARMATURE');modifier.object=rig
    for frame,x in [(1,0),(5,.5),(9,0)]:
        rig.pose.bones['SyntheticBone'].location.x=x;rig.pose.bones['SyntheticBone'].keyframe_insert('location',frame=frame)
    scene.frame_set(1)
    with Library(out/'library') as lib:
        source=lib.root/'incoming/synthetic/rig.glb';source.parent.mkdir()
        bpy.ops.export_scene.gltf(filepath=str(source),export_format='GLB',export_animations=True)
        original=file_hash(source)
        asset=Asset('local','synthetic-widget-test','Generated rig','model','https://example.invalid/synthetic',
                    license_id='CC0-1.0',license_url='https://example.invalid/synthetic-license',price=0,
                    formats=['.glb'],evidence='user_attested',local_files=[{'path':source.relative_to(lib.root).as_posix(),'sha256':original,'size':source.stat().st_size}])
        lib.put(asset)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add(size=.2,location=(4,0,0));prop=bpy.context.object;prop.name='Icosphere'
        prop_matrix=ops.flatten(prop.matrix_world);seed=out/'existing-world.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(seed));seed_hash=file_hash(seed)
        def run(op,source_file=None,options=None,asset_id=None):
            j=jobs.prepare(lib,op,str(source_file) if source_file else None,asset_id=asset_id,options=options)
            done=jobs.run(lib,j['id'],bpy.app.binary_path,120);assert done['state']=='SUCCEEDED'
            folder=lib.root/'jobs'/j['id'];return folder,load_json(folder/'result.json')['data']
        folder,data=run('import',seed,{'file':asset.local_files[0]['path']},asset.id)
        checkpoint=folder/'result.blend';checkpoint_hash=file_hash(checkpoint)
        bpy.ops.wm.open_mainfile(filepath=str(checkpoint),load_ui=False,use_scripts=False)
        rig=bpy.data.objects['SyntheticRig'];body=bpy.data.objects['SyntheticBody']
        widgets={p.custom_shape for p in rig.pose.bones if p.custom_shape};assert widgets
        widget=next(iter(widgets));widget_name=widget.name
        check(all(not w.visible_get() and all(c.hide_render for c in w.users_collection) for w in widgets),'import preserves hidden widget collections')
        check(body.visible_get() and not body.hide_render,'actual skinned model remains visible')
        check(bpy.data.objects['Icosphere'].visible_get() and ops.flatten(bpy.data.objects['Icosphere'].matrix_world)==prop_matrix,'unrelated same-name world geometry is preserved')
        original_state=snapshot(rig,body)
        # Simulate a previously affected checkpoint, never rewrite job evidence.
        for collection in list(widget.users_collection):collection.objects.unlink(widget)
        bpy.context.scene.collection.objects.link(widget);widget.hide_set(False);widget.hide_render=False
        legacy=out/'legacy-visible-widget.blend';bpy.ops.wm.save_as_mainfile(filepath=str(legacy));legacy_hash=file_hash(legacy)
        audit=bone_display.inspect({'target_object':rig.name})
        options={'target_object':rig.name,'target_fingerprint':audit['target_fingerprint'],
                 'display_type':audit['display_type'],'show_custom_shapes':audit['show_custom_shapes'],
                 'show_in_front':audit['show_in_front'],'hide_widget_objects':[widget_name]}
        repaired,repair=run('bone-display',legacy,options)
        bpy.ops.wm.open_mainfile(filepath=str(repaired/'result.blend'),load_ui=False,use_scripts=False)
        rig=bpy.data.objects['SyntheticRig'];body=bpy.data.objects['SyntheticBody'];widget=bpy.data.objects[widget_name]
        check(snapshot(rig,body)==original_state,'repair preserves rest, skin, actions, transforms and widget references')
        check(widget.hide_get() and widget.hide_render,'reviewed widget-only repair hides but does not delete helper')
        positions=[]
        for frame in (1,5):
            bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
            evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
            positions.append(list(evaluated.matrix_world@evaluated.data.vertices[0].co))
        check(sum(abs(a-b) for a,b in zip(*positions))>.1,'real skinned animation still deforms after repair')
        bpy.context.scene.frame_set(1);bpy.context.scene['asset_director_preview_only']=True
        export(out/'repaired-preview.glb',{'takes':[],'checkpoint':True})
        names=exported_meshes(out/'repaired-preview.glb')
        check(widget_name not in names,'checkpoint GLB excludes render-hidden rig helper')
        check({'SyntheticBody','Icosphere'}<=names,'checkpoint GLB retains character and unrelated same-name geometry')
        check(file_hash(source)==original and file_hash(seed)==seed_hash and file_hash(checkpoint)==checkpoint_hash and file_hash(legacy)==legacy_hash,'sources and old checkpoints are byte-identical')
    report={'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','checks':checks,'blender_version':bpy.app.version_string,'human_approval':'NOT_GRANTED'}
    atomic_json(out/'report.json',report);print(json.dumps(report));assert report['status']=='PASS'
except BaseException as error:
    atomic_json(out/'failure.json',{'status':'FAIL','checks':checks,'error':str(error)});raise
