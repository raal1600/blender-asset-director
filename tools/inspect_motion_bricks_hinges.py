"""Propose elbow planes from an explicitly selected native Action; never edit it.

Run in isolated Blender with --disable-autoexec. Inspect the retained evidence
and native motion before setting reviewed=true in a separate calibration file.
An inconsistent proposal cannot be accepted merely by changing that flag.
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def main():
    import bpy
    from asset_director import action_layer as layer
    from asset_director.core import atomic_json,digest,require,DirectorError
    from asset_director.motion_stitch import Sampler
    from asset_director.motion_bricks_retarget import rest_identity
    from asset_director.motion_bricks_calibration import SCHEMA,plane_summary
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rig',required=True);parser.add_argument('--mapping',type=Path,required=True)
    parser.add_argument('--action',required=True);parser.add_argument('--slot')
    parser.add_argument('--start',type=float);parser.add_argument('--end',type=float)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    require(args.output.is_absolute() and args.output.suffix=='.json' and not args.output.exists(),
            'HINGE_OUTPUT','Choose a new absolute proposal JSON; no source or earlier evidence is overwritten')
    rig=bpy.data.objects.get(args.rig)
    require(rig is not None and rig.type=='ARMATURE' and not layer.reason(rig)
            and not any(b.constraints for b in rig.pose.bones),'HINGE_RIG','Inspect an unconstrained native armature')
    roles=json.loads(args.mapping.read_text(encoding='utf-8-sig'))
    required=[side+'_'+part for side in ('left','right') for part in ('upper_arm','forearm','hand')]
    require(all(roles.get(key) in rig.data.bones for key in required),'HINGE_MAPPING','Choose the observed upper arm, forearm and hand on each side')
    bindings=[(a,s) for a,s in layer.bindings(rig) if a.name==args.action and (args.slot is None or s is not None and s.identifier==args.slot)]
    require(len(bindings)==1,'HINGE_ACTION','Select one observed native Action/slot binding')
    action,slot=bindings[0];source=layer.ops.action_range(action,slot)
    start=source[0] if args.start is None else args.start;end=source[1] if args.end is None else args.end
    require(all(math.isfinite(v) for v in (start,end)) and source[0]<=start<end<=source[1] and end-start<=3600,
            'HINGE_INTERVAL','Choose an explicit calibration interval inside the native Action, at most 3600 frames')
    signature=digest(layer.channels(action));observations={side:[] for side in ('left','right')};identity=rest_identity(rig)
    reader=Sampler(rig);samples=min(128,max(8,math.ceil(end-start)+1))
    try:
        motion=({'speed':1.},{'range':source},action,slot,{})
        for i in range(samples):
            frame=start+(end-start)*i/(samples-1)
            reader.read(motion,frame-source[0],endpoint=abs(frame-source[1])<1e-7);clone=reader.clone
            for side in observations:
                upper,forearm,hand=[clone.pose.bones[roles[side+'_'+part]] for part in ('upper_arm','forearm','hand')]
                a,b,c=[clone.matrix_world@bone.head for bone in (upper,forearm,hand)]
                u,v=(b-a).normalized(),(c-b).normalized();bend=math.degrees(u.angle(v))
                if not 10<=bend<=165:continue
                posed=(clone.matrix_world@upper.matrix).to_quaternion()
                rest=(clone.matrix_world@upper.bone.matrix_local).to_quaternion()
                normal=(rest@posed.inverted()@u.cross(v).normalized()).normalized()
                observations[side].append({'frame':frame,'bend_degrees':bend,'normal_world_rest':list(normal)})
    finally:reader.close()
    require(digest(layer.channels(action))==signature,'HINGE_SOURCE_CHANGED','Source channels changed during read-only calibration')
    value={'schema':SCHEMA,'rest_identity':identity,'mapping_sha256':digest(roles),
           'source_action_sha256':signature,'source_slot_identifier':slot.identifier if slot else 'LEGACY',
           'source_fps':bpy.context.scene.render.fps/bpy.context.scene.render.fps_base,
           'source_range':[start,end],'observations':observations,'reviewed':False}
    summaries={};valid=True
    for side,rows in observations.items():
        try:summaries[side]=plane_summary(rows)
        except DirectorError as error:summaries[side]={'status':'UNSUITABLE','reason':str(error)};valid=False
    atomic_json(args.output,value)
    print(json.dumps({'status':'PROPOSED_REQUIRES_REVIEW' if valid else 'UNSUITABLE_CALIBRATION',
                      'proposal':str(args.output),'summary':summaries,'source_preserved':True}))
    return 0 if valid else 2


if __name__=='__main__':raise SystemExit(main())
