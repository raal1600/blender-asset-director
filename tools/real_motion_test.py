"""Real retrieved motion, renamed/resized target and numerical Blender evaluation."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import bpy
from asset_director.core import Library,load_json,atomic_json
from asset_director import blender_ops as ops,backend


def main(selection,out):
    selected=load_json(Path(selection));out=Path(out)
    with Library(selected['library']) as lib:
        a=lib.get(selected['asset_id']);meta=a.metadata;f=meta['file'];p=lib.verify_file(f)
        ops.load_input(p)
        source=bpy.data.objects[meta['source_object']];action=bpy.data.actions[meta['action']]
        ops.assign(source,action,meta.get('slot'))
        # Duplicate actual skin/rig for a controlled different-name/scale fixture.
        # This is not a substitute for testing a structurally different user warrior.
        target=source.copy();target.data=source.data.copy();target.animation_data_clear();target.name='RealMotionTarget'
        bpy.context.scene.collection.objects.link(target)
        for b in target.data.bones:b.name='target:'+b.name
        copied=[]
        for original in list(bpy.data.objects):
            if original.type=='MESH' and any(m.type=='ARMATURE' and m.object==source for m in original.modifiers):
                mesh=original.copy();mesh.data=original.data.copy();mesh.animation_data_clear();bpy.context.scene.collection.objects.link(mesh)
                world=mesh.matrix_world.copy();mesh.parent=target;mesh.matrix_world=world
                for m in mesh.modifiers:
                    if m.type=='ARMATURE' and m.object==source:m.object=target
                for group in mesh.vertex_groups:
                    if group.name in source.data.bones:group.name='target:'+group.name
                copied.append(mesh)
        assert copied,'Source package has no skinned mesh; choose another real clip fixture'
        target.scale=tuple(x*1.1 for x in target.scale)
        bpy.context.view_layer.update()
        pairs={b.name:'target:'+b.name for b in source.data.bones}
        result=ops.retarget(source,target,action,meta.get('slot'),{'mapping':pairs,'source_fps':meta['fps'],'target_fps':24},backend.verify(lib),'real_motion')
        assert result['qa']['limb_relative_motion_height_ratio']>.001,result['qa']
        assert result['frames']>2
        # The original source remains in this private CI fixture solely for comparison.
        source.hide_render=True
        for obj in list(bpy.data.objects):
            if obj.type=='MESH' and any(m.type=='ARMATURE' and m.object==source for m in obj.modifiers):obj.hide_render=True
        from asset_director.worker import stage
        stage(target)
        preview=ops.render_previews(out,{'frames':[1,result['frames']//2,result['frames']], 'width':480,'height':270,'samples':4})
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'real_motion_result.blend'))
        report={'status':'PASS','blender_version':bpy.app.version_string,'source_asset':a.id,'source_url':a.source_url,'license':a.license_id,
                'actual_clip_name':action.name,'frames':result['frames'],'qa':result['qa'],'preview':preview,
                'scope':'Actual downloaded motion evaluated and baked to renamed/scaled duplicate skeleton. Not proof of arbitrary-rig compatibility.',
                'visual_acceptance':'REQUIRES_HUMAN_CONFIRMATION'}
        atomic_json(out/'real_motion_report.json',report);print(json.dumps(report))

if __name__=='__main__':main(*sys.argv[sys.argv.index('--')+1:])
