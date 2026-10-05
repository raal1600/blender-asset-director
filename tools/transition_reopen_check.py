"""Fresh-process evaluation/export/render of one accepted generated transition.

Run Blender with this script, passing RESULTS.json, case index, new output dir.
The accepted .blend is never resaved. Rendered frames and GLB use that same file.
"""
from pathlib import Path
import json
import math
import sys
import bpy
from mathutils import Vector
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from asset_director import action_layer, action_timeline, sequence_math as sm
from asset_director.core import atomic_json, file_hash


def evaluate(obj, f):
    scene=bpy.context.scene
    scene.frame_set(math.floor(f), subframe=f-math.floor(f)); bpy.context.view_layer.update()
    rig=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    result={'frame': f, 'root': list(rig.matrix_world.translation),
            'joints': {p.name: {'p':list(rig.matrix_world @ p.head),
                               'q':list((rig.matrix_world @ p.matrix).to_quaternion())}
                       for p in rig.pose.bones}}
    if 'Upper' in rig.pose.bones:
        upper=rig.matrix_world @ rig.pose.bones['Upper'].matrix
        result.update(p=list(upper @ Vector((0,.7,0))),q=list(upper.to_quaternion()),
                      feet=[list(rig.matrix_world @ rig.pose.bones[n].head) for n in ('Foot.L','Foot.R')])
    return result


def main():
    summary_path, index, output = sys.argv[sys.argv.index('--')+1:]
    summary=json.loads(Path(summary_path).read_text(encoding='utf-8'))
    case=summary['results'][int(index)]; out=Path(output); out.mkdir(parents=True, exist_ok=False)
    result={'status':'FAIL','input_kind':summary['input_kind'],'case':int(index),
            'blender':bpy.app.version_string,'checks':[], 'fresh_process':True}
    try:
        source=Path(case['result']); original=file_hash(source)
        assert case['status']=='PASS', 'Cannot accept a failed generation'
        assert case.get('result_sha256')==original, 'Missing generation hash or saved artifact bytes changed'
        bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
        obj=bpy.context.scene.objects[case.get('rig','Canonical native rig')]
        timeline=action_timeline.load(obj)
        assert timeline and not obj.animation_data.action
        assert any(not t.mute for t in obj.animation_data.nla_tracks)
        if case.get('acceptance_report'):
            report=json.loads(Path(case['acceptance_report']).read_text(encoding='utf-8'))
            action_timeline.verify(report)
        height=case.get('character_height_m',summary.get('character_height_m')); threshold=case['thresholds']
        assert height and height>0
        boundaries=[m['frame'] for m in case['metrics']['boundaries']]
        frames=sorted(set([f+d for f in boundaries for d in (-1,-.5,-.25,-.125,0,.125,.25,.5,1)]
                          + list(range(math.floor(min(boundaries))-2,math.ceil(max(boundaries))+3))))
        samples=[evaluate(obj,f) for f in frames]
        expected=case.get('samples',[])
        assert expected, 'Generation must record pose samples before reopening'
        for row in expected:
            actual=evaluate(obj,row['frame'])
            def compare(expected_pose,actual_pose):
                assert math.dist(actual_pose['p'],expected_pose['p']) <= threshold['position_m'], row['frame']
                angle=math.degrees(sm.norm(sm.qlog(sm.qmul(sm.inverse(expected_pose['q']),actual_pose['q']))))
                assert angle <= threshold['orientation_deg'], (row['frame'],angle)
            assert math.dist(actual['root'],row['root']) <= threshold['position_m']
            if 'joints' in row:
                assert set(actual['joints'])==set(row['joints']), 'Reopened skeleton differs'
                for name,pose in row['joints'].items(): compare(pose,actual['joints'][name])
            else:
                compare(row,actual)
                for a,b in zip(actual['feet'],row['feet']):
                    assert math.dist(a,b)<=threshold['position_m']
        result['checks'].append('fresh Blender process restores accepted Action/NLA and evaluated boundary samples')
        scene=bpy.context.scene
        scene['asset_director_preview_only']=True
        from asset_director.viewer_export import export
        exported=export(out/'accepted.glb',{'takes':[],'checkpoint':True,'preview_profile':'action-playback-v1'})
        result['checks'].append('real application GLB exporter consumes the accepted saved animation')
        assert scene.camera, 'Fixture must include a retained render camera'
        scene.render.resolution_x=320;scene.render.resolution_y=240;scene.render.resolution_percentage=100
        scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1
        scene.render.image_settings.file_format='PNG'
        render_start=math.floor(min(boundaries))-2;render_end=math.ceil(max(boundaries))+2
        rendered=[]
        for f in range(render_start,render_end+1):
            scene.frame_set(f);destination=out/('frame-'+str(f-render_start).zfill(4)+'.png')
            scene.render.filepath=str(destination);bpy.ops.render.render(write_still=True)
            assert destination.is_file();rendered.append(destination.name)
        assert file_hash(source)==original, 'Rendering/export changed accepted source bytes'
        result.update(status='PASS',source=str(source),source_sha256=original,
                      height_m=height,rig=obj.name,samples=samples,
                      frame_range=[scene.frame_start,scene.frame_end],fps=scene.render.fps/scene.render.fps_base,
                      render_range=[render_start,render_end],rendered=rendered,export=exported,
                      derivative_parity='REQUIRES_GLB_CHECK',visual_review='PENDING')
        result['checks'].append('same accepted source renders both stitch boundaries without source mutation')
    except Exception as exc:
        result['error']=repr(exc)
        raise
    finally:
        atomic_json(out/'RESULTS.json',result)


if __name__=='__main__':
    main()
