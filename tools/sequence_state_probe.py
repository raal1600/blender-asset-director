"""Bounded diagnostic of indexed, retargeted and sampled synthetic root motion.

Invoked in Actions only. Reports measurements, not a passing sequence fixture.
No source assets are uploaded. The original assertion remains in the CI gate.
"""
from pathlib import Path
import sys
import json
import traceback
import math
import bpy
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from asset_director import blender_ops as ops, sequence_blender as sb
from asset_director.core import atomic_json, load_json
import sequence_fixture


def main(out, library):
    assert bpy.app.background
    out=Path(out);library=Path(library)
    failure=None
    try:sequence_fixture.main(out/'fixture',library)
    except Exception:failure=traceback.format_exc()[-6000:]
    results=[]
    for path in sorted((library/'jobs').glob('*/job.json')):
        j=load_json(path)
        if j['state']!='SUCCEEDED':continue
        op=j['specification']['operation']
        if op not in ('index','retarget','sequence-plan'):continue
        d=load_json(path.parent/'result.json')['data']
        entry={'job_id':j['id'],'operation':op}
        if op=='index':
            entry['clips']=[{'range':[c['frame_start'],c['frame_end']],
                'hips':[s.get('hips') for s in (c['samples'][0],c['samples'][-1])]} for c in d['clips']]
        elif op=='retarget':
            entry['recorded_hips']=[s.get('hips') for s in (d['samples'][0],d['samples'][-1])]
            bpy.ops.wm.open_mainfile(filepath=str(path.parent/'result.blend'),load_ui=False,use_scripts=False)
            target=bpy.data.objects[d['target']];anchor=d['qa_roles']['hips']
            action=bpy.data.actions[d['action']];slot=d['slot']
            ops.assign(target,action,slot)
            times=[d['frame_range'][0],(sum(d['frame_range'])/2),d['frame_range'][1]]
            observed=[]
            for f in times:
                bpy.context.scene.frame_set(math.floor(f),subframe=f-math.floor(f));bpy.context.view_layer.update()
                ev=target.evaluated_get(bpy.context.evaluated_depsgraph_get())
                observed.append({'frame':f,'local':list(target.pose.bones[anchor].location),
                    'world':list((ev.matrix_world@ev.pose.bones[anchor].matrix).translation)})
            entry['direct']=observed
            # Reopen to avoid drawing conclusions from a probe-mutated state.
            bpy.ops.wm.open_mainfile(filepath=str(path.parent/'result.blend'),load_ui=False,use_scripts=False)
            target=bpy.data.objects[d['target']];action=bpy.data.actions[d['action']]
            slots=[s for s in action.slots if s.identifier==slot];reader=sb.Reader(target,20)
            entry['reader']=[{'frame':f,'world':list(reader.read(action,slots[0],f)[anchor]['world'].translation)} for f in times]
            entry['anchor_curves']=[{'axis':c.array_index,'first':list(c.keyframe_points[0].co),
                'last':list(c.keyframe_points[-1].co)} for c in ops.curves(action,slots[0])
                if c.data_path==target.pose.bones[anchor].path_from_id('location')]
        else:entry['join_metrics']=[{k:v for k,v in x.items() if k in ('unaligned_anchor_gap_m','planar_bridge_displacement_m','anchor_velocity_difference_m_s')} for x in d['joins']]
        results.append(entry)
    atomic_json(out/'state_probe.json',{'status':'DIAGNOSTIC','original_failure':failure,'results':results})
    print('Diagnostic saved; this does not override the sequence acceptance failure.')


if __name__=='__main__':main(*sys.argv[sys.argv.index('--')+1:])
