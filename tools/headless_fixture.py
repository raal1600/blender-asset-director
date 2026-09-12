"""Real Blender regression fixtures. Synthetic motions are NOT production assets."""
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import bpy
from mathutils import Vector
from asset_director import blender_ops as ops
from asset_director.core import Library, DirectorError, atomic_json, file_hash
from asset_director.backend import verify


def humanoid(name, prefix='', scale=1):
    bones={
        'root':((0,0,0),(0,0,.2),None), 'hips':((0,0,1),(0,0,1.2),'root'),
        'spine':((0,0,1.2),(0,0,1.6),'hips'), 'head':((0,0,1.6),(0,0,1.9),'spine')}
    for side,sign in [('l',1),('r',-1)]:
        bones.update({f'thigh_{side}':((sign*.12,0,1),(sign*.12,0,.55),'hips'),
                      f'calf_{side}':((sign*.12,0,.55),(sign*.12,0,.1),f'thigh_{side}'),
                      f'foot_{side}':((sign*.12,0,.1),(sign*.12,-.22,.1),f'calf_{side}'),
                      f'upperarm_{side}':((sign*.2,0,1.5),(sign*.5,0,1.5),'spine'),
                      f'forearm_{side}':((sign*.5,0,1.5),(sign*.8,0,1.5),f'upperarm_{side}'),
                      f'hand_{side}':((sign*.8,0,1.5),(sign*.93,0,1.5),f'forearm_{side}')})
    arm=bpy.data.armatures.new(name);obj=bpy.data.objects.new(name,arm);bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    for key,(head,tail,parent) in bones.items():
        b=arm.edit_bones.new(prefix+key);b.head=Vector(head)*scale;b.tail=Vector(tail)*scale
        if parent:b.parent=arm.edit_bones[prefix+parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    vertices=[];faces=[];groups=[]
    for key,(head,tail,parent) in bones.items():
        center=(Vector(head)+Vector(tail))*.5*scale; start=len(vertices)
        for delta in [(-.035,0,-.035),(.035,0,-.035),(0,0,.035)]:vertices.append(center+Vector(delta))
        faces.append((start,start+1,start+2));groups.append((prefix+key,[start,start+1,start+2]))
    mesh=bpy.data.meshes.new(name+'Skin');mesh.from_pydata(vertices,[],faces);mesh.update()
    skin=bpy.data.objects.new(name+'Skin',mesh);bpy.context.scene.collection.objects.link(skin)
    for name,ids in groups:skin.vertex_groups.new(name=name).add(ids,1,'REPLACE')
    mod=skin.modifiers.new('Skin','ARMATURE');mod.object=obj;skin.parent=obj
    return obj,skin


def animate(obj,prefix=''):
    for frame in range(1,25):
        for key,phase in [('thigh_l',0),('thigh_r',math.pi),('upperarm_l',math.pi),('upperarm_r',0)]:
            pb=obj.pose.bones[prefix+key];pb.rotation_mode='XYZ';pb.rotation_euler.x=.25*math.sin((frame-1)/23*2*math.pi+phase)
            pb.keyframe_insert('rotation_euler',frame=frame)
    obj.animation_data.action.name='FIXTURE_Walk_Not_For_Production'
    return obj.animation_data.action


def main(out,library):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=24
    source,skin=humanoid('FixtureSource');action=animate(source)
    report=ops.rig_report(source);assert report['readiness']=='RETARGETABLE',report
    before=report['fingerprint']
    # FBX and GLB import/export exercise actual Blender importers, not mocked bpy.
    bpy.ops.object.select_all(action='DESELECT');source.select_set(True);skin.select_set(True)
    bpy.context.view_layer.objects.active=source
    bpy.ops.export_scene.gltf(filepath=str(out/'fixture.glb'),export_format='GLB',use_selection=True,export_animations=True)
    bpy.ops.export_scene.fbx(filepath=str(out/'fixture.fbx'),use_selection=True,add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False)
    import_results={}
    for name in ('fixture.glb','fixture.fbx'):
        p=out/name
        f={'path':name,'sha256':file_hash(p),'size':p.stat().st_size}
        result=ops.index_file(p,f,{})
        assert result['clips'],result
        assert any(c['curve_count']>0 for c in result['clips'])
        import_results[name]={'clips':len(result['clips']),'rigs':len(result['rigs'])}
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=24
    source,skin=humanoid('Source');action=animate(source)
    target,target_skin=humanoid('Target','renamed:',1.2)
    with Library(library) as lib:
        result=ops.retarget(source,target,action,None,{'source_fps':24,'target_fps':30},verify(lib),'fixture')
    assert result['frames']==30,result['frames']
    assert result['qa']['limb_relative_motion_height_ratio']>.01,result['qa']
    assert ops.rig_report(source)['fingerprint']==before
    assert len(ops.curves(target.animation_data.action,target.animation_data.action_slot))>0
    assert target.animation_data.action.get('bad_in_place_horizontal') is True
    target_action=target.animation_data.action
    count_before=len(bpy.data.actions)
    # Another bake must not clear/overwrite the existing named action.
    with Library(library) as lib:
        again=ops.retarget(source,target,action,None,{'source_fps':24,'target_fps':24},verify(lib),'fixture')
    assert len(bpy.data.actions)==count_before+1
    assert target_action in bpy.data.actions[:]
    invalid=target.copy();invalid.data=target.data.copy();invalid.name='Unskinned';bpy.context.scene.collection.objects.link(invalid)
    try:ops.safe_mapping(source,invalid);raise AssertionError('Unskinned target was accepted')
    except DirectorError as exc:assert exc.code=='NEEDS_RIGGING',exc.code
    bpy.data.objects.remove(invalid,do_unlink=True)
    sequence=ops.assemble(target,{'fps':24,'clips':[{'action':again['action'],'slot':again['slot'],'start':1,'repeat':2}],
                                   'controller_speed':.5,'direction':[0,-1,0],'travel_frames':[1,40]},'fixture_sequence')
    assert sequence['controller'] and sequence['root_owner'].startswith('single')
    assert sequence['qa']['root_displacement']>.5
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'fixture_result.blend'))
    report={'status':'PASS','blender_version':bpy.app.version_string,'imports':import_results,
            'retarget':{k:result[k] for k in ('frames','fps','qa','backend')},'sequence':{k:sequence[k] for k in ('root_owner','qa')},
            'assertions':['actual GLB import','actual FBX import','renamed and resized target','FPS conversion','nontrivial limb motion','action preservation','unskinned rejection','NLA repeats','single root controller','working file save'],
            'fixture_notice':'Synthetic numerical regression fixture; does not prove natural locomotion or the user warrior rig.'}
    atomic_json(out/'fixture_report.json',report);print(json.dumps(report))

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:];main(*args)
