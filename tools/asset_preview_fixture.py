"""Real Blender preview-copy/animation regression; synthetic inputs only, no GUI claim."""
from pathlib import Path
import json
import sys
import bpy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from asset_director.core import atomic_json, file_hash, DirectorError
from asset_director.asset_preview import prepare
from asset_director import blender_ops as ops

out=Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=False)
source=out/'originals';source.mkdir()
checks=[]


def check(value,name):
    if not value: raise AssertionError(name)
    checks.append(name)


def preview(name,member,motion=None,embedded=False,kind='source'):
    directory=out/name;directory.mkdir()
    files=[{'path':p.relative_to(source).as_posix(),'size':p.stat().st_size,'sha256':file_hash(p)} for p in sorted(source.rglob('*')) if p.is_file()]
    request={'schema':'asset-director.asset-preview/1','id':'synthetic-native-preview','title':'Synthetic preview fixture',
             'version':'a'*64,'source_kind':kind,'root':str(source),'files':files,'file':member}
    if motion:request['motion']=motion
    atomic_json(directory/'request.json',request)
    result=prepare(directory/'request.json',bpy.app.binary_path,embedded=embedded)
    check(result['state']=='READY' and not result['selection_changed'] and not result['production_use_approved'],name+' isolated receipt')
    check(all(file_hash(source/f['path'])==f['sha256'] for f in files),name+' originals unchanged')
    return result,directory


try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.render.fps=24;scene.frame_start=1;scene.frame_end=25
    arm=bpy.data.armatures.new('SyntheticRig');rig=bpy.data.objects.new('SyntheticRig',arm)
    scene.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig;rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT');bone=arm.edit_bones.new('SyntheticBone');bone.head=(0,0,0);bone.tail=(0,0,1)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.mesh.primitive_cube_add(size=.5,location=(0,0,.5));mesh=bpy.context.object;mesh.name='SyntheticPreviewSubject'
    group=mesh.vertex_groups.new(name='SyntheticBone');group.add(list(range(len(mesh.data.vertices))),1,'REPLACE')
    modifier=mesh.modifiers.new('SyntheticSkin','ARMATURE');modifier.object=rig;mesh.parent=rig
    pb=rig.pose.bones['SyntheticBone']
    for frame,x in [(1,0),(13,1),(25,0)]:
        pb.location.x=x;pb.keyframe_insert('location',frame=frame)
    rig.animation_data.action.name='SyntheticNativeTake'
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(source/'scene.blend'))
    bpy.ops.export_scene.gltf(filepath=str(source/'scene.glb'),export_format='GLB',export_animations=True)
    blend,directory=preview('blend-preview','scene.blend')
    check(any(o['name']=='SyntheticPreviewSubject' for o in blend['data']['objects']),'actual Blender objects in preview')
    check(len(blend['data']['takes'])>=1,'observed binding offered for playback')
    glb,directory=preview('glb-preview','scene.glb')
    check(len(glb['data']['objects'])>=2,'real GLB imported into isolated scene')
    f={'path':'scene.glb','size':(source/'scene.glb').stat().st_size,'sha256':file_hash(source/'scene.glb')}
    index=ops.index_file(source/'scene.glb',f,{},source)
    check(bool(index['clips']),'native source indexed from real imported channels')
    clip=index['clips'][0];motion={k:clip[k] for k in ('file','action','slot','source_object','fps','frame_start','frame_end')}
    native,directory=preview('native-preview','scene.glb',motion)
    info=native['data']['native_clip']
    check(info['action']==clip['action'] and info['fps']==clip['fps'] and not info['retargeted'],'exact native action and timebase, not retargeted')
    bpy.ops.wm.open_mainfile(filepath=str(directory/native['blend']['path']),load_ui=False,use_scripts=False)
    animated=bpy.data.objects[info['source_object']];start,end=info['frame_range']
    scene=bpy.context.scene;positions=[]
    for frame in (start,(start+end)/2,end):
        scene.frame_set(int(frame));bpy.context.view_layer.update()
        positions.append(list(animated.pose.bones['SyntheticBone'].head))
    check(sum(abs(a-b) for a,b in zip(positions[0],positions[1]))>.1,'pose changes during genuine native playback')
    embedded,directory=preview('embedded-asset','scene.blend',embedded=True)
    model=directory/embedded['model']['path']
    check(model.read_bytes()[:4]==b'glTF','real Blender exported a GLB for local WebGL')
    check(file_hash(model)==embedded['model']['sha256'],'embedded derivative exact identity')
    checkpoint,directory=preview('embedded-checkpoint','scene.blend',embedded=True,kind='checkpoint')
    check(checkpoint['data']['checkpoint'] and checkpoint['data']['embedded_viewer']['kind']=='READ_ONLY_3D_INSPECTION','saved checkpoint uses scene playback, not a render camera')
    # Checkpoint files are flattened only in the disposable inspection bundle.
    # Relative textures must rebind to exact verified copies, not disappear or
    # silently read the original source after that path shortening.
    bpy.ops.wm.open_mainfile(filepath=str(source/'scene.blend'),load_ui=False,use_scripts=False)
    texture_dir=source/'textures';texture_dir.mkdir()
    texture=bpy.data.images.new('RecordedPreviewColor',width=2,height=2)
    texture.pixels[:]=[.1,.6,.9,1]*4;texture.file_format='PNG'
    texture.filepath_raw=str(texture_dir/'color.png');texture.save()
    texture.filepath='//textures/color.png'
    material=bpy.data.materials.new('SyntheticRecordedTexture');material.use_nodes=True
    node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=texture
    material.node_tree.links.new(node.outputs['Color'],material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    bpy.data.objects['SyntheticPreviewSubject'].data.materials.append(material)
    bpy.ops.wm.save_as_mainfile(filepath=str(source/'textured.blend'))
    textured,directory=preview('embedded-textured-checkpoint','textured.blend',embedded=True,kind='checkpoint')
    bpy.ops.wm.open_mainfile(filepath=str(directory/textured['blend']['path']),load_ui=False,use_scripts=False)
    copied=Path(bpy.data.images['RecordedPreviewColor'].filepath).resolve()
    check(copied.is_relative_to((directory/'library/incoming/package').resolve()),'relative checkpoint texture resolves inside the verified short-path copy')
    check(file_hash(copied)==file_hash(texture_dir/'color.png'),'short-path texture copy preserves exact source bytes')
    sys.path.insert(0, str(ROOT/'tools'))
    from viewer_texture_fixture import run as check_preview_textures
    check_preview_textures(source, preview, check)
    # Standalone copy cannot quietly adopt external source textures.
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.mesh.primitive_cube_add()
    image=bpy.data.images.new('Unrecorded',width=1,height=1);image.source='FILE';image.filepath=str(out/'unrecorded.png');image.use_fake_user=True
    bpy.ops.wm.save_as_mainfile(filepath=str(source/'external.blend'))
    try:preview('external-refusal','external.blend');raise AssertionError('Unrecorded external reference was accepted')
    except DirectorError as e:check(e.code=='EXTERNAL_REFERENCE','unrecorded external dependency refuses GUI launch')
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.mesh.primitive_cube_add()
    image=bpy.data.images.new('UnrecordedRelative',width=1,height=1);image.source='FILE';image.filepath='//textures/unrecorded.png';image.use_fake_user=True
    bpy.ops.wm.save_as_mainfile(filepath=str(source/'external-relative.blend'))
    try:preview('compact-relative-refusal','external-relative.blend',embedded=True,kind='checkpoint');raise AssertionError('Unrecorded relative checkpoint dependency was accepted')
    except DirectorError as e:check(e.code=='EXTERNAL_REFERENCE','short-path checkpoint refuses an unrecorded relative dependency')
    atomic_json(out/'asset_preview_report.json',{'status':'PASS','checks':checks,'blender':bpy.app.version_string,
        'not_tested':['native window UI','human temporal approval','private assets']})
except Exception as error:
    atomic_json(out/'asset_preview_failure.json',{'status':'FAIL','checks':checks,'error':str(error)})
    raise
