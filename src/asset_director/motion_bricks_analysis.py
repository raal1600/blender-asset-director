"""Evaluated boundary support proposals and explicit in-place ambiguity.

Anatomical roles and sole weights are rig calibration. No clip labels are used
for compatibility, heading, travel, or contact decisions.
"""
import json
import math
import bpy
from mathutils import Vector
from .core import require
from .motion_bricks_feet import Soles, SIDES
from .motion_contacts import set_pose


def analyze(reader,obj,profile,motions,schedules,geometry):
    height=profile.get('reference_height_m')
    # Legacy calibration can still produce diagnostic output, but cannot pass
    # final candidate validation until the reviewed full height is supplied.
    if height is None:return {'status':'NEEDS_PREPARATION','reason':'fixed reviewed full-character height required','boundaries':{}}
    soles=Soles(obj,reader.clone,profile['roles']);result={}
    fps=bpy.context.scene.render.fps/bpy.context.scene.render.fps_base
    parent=obj.parent.matrix_world@obj.matrix_parent_inverse if obj.parent else obj.matrix_parent_inverse
    inverse=parent.to_3x3().inverted()
    try:
        for side,m in motions.items():
            schedule=schedules[side];edge=schedule['source_frames'][-1 if side=='source' else 0]
            context=schedule['source_frames'];last=m[1]['range'][1]
            def sample(f):
                pose=reader.read(m,f-m[1]['range'][0],0.,abs(f-last)<1e-7)
                dt=(f-edge)/(fps*m[0]['speed']);velocity=Vector((*geometry['velocity_in' if side=='source' else 'velocity_out'],0))*fps
                set_pose(reader,pose,inverse@velocity*dt,0.)
                return pose
            sample(edge);landmarks={};origin='evaluated-geometry-proposal'
            raw=m[2].get('bad_root_contact_preparation_v1');reviewed=json.loads(raw).get('contacts',[]) if raw else []
            for foot in SIDES:
                authored=next((c for c in reviewed if c['side']==foot and c['start']<=min(context)+1e-6 and c['end']>=max(context)-1e-6),None)
                if authored:
                    landmarks[foot]=(authored['mesh'],authored['vertex']);origin='reviewed-root-preparation-plus-evaluated-check'
                else:
                    candidates=[]
                    for skin,indices in soles.groups[foot]:
                        name=next(n for n,v in soles.source_objects.items() if v==skin)
                        e=skin.evaluated_get(bpy.context.evaluated_depsgraph_get())
                        candidates.extend(((e.matrix_world@e.data.vertices[i].co).z,name,i) for i in indices)
                    _,name,i=min(candidates,key=lambda c:c[0]);landmarks[foot]=(name,i)
            samples=[]
            for f in context:
                sample(f);low=soles.heights();e=reader.clone.evaluated_get(bpy.context.evaluated_depsgraph_get())
                samples.append({'source_frame':f,'root':list(e.matrix_world@e.pose.bones[profile['roles']['pelvis']].head),
                    'feet':{foot:{'point':list(soles.landmark(*landmarks[foot])),'low':low[foot]} for foot in SIDES}})
            feet={}
            for foot in SIDES:
                points=[s['feet'][foot]['point'] for s in samples]
                drift=max(math.dist(a[:2],b[:2]) for a in points for b in points)
                maximum_height=max(abs(s['feet'][foot]['low']-profile['ground_z']) for s in samples)
                feet[foot]={'planted':drift<=.01*height and maximum_height<=.01*height,
                    'drift_m':drift,'max_ground_distance_m':maximum_height,'mesh':landmarks[foot][0],'vertex':landmarks[foot][1]}
            root_distance=math.dist(samples[0]['root'][:2],samples[-1]['root'][:2])
            ambiguous=root_distance<.002*height and any(v['drift_m']>.01*height for v in feet.values()) and not raw and not m[0].get('root_intent')
            require(not ambiguous,'MOTION_BRICKS_ROOT_INTENT','Stationary root with moving feet is ambiguous. Choose stationary intent after review, or prepare a derived root path with reviewed contacts; direction is never inferred from its name')
            require(any(v['planted'] for v in feet.values()),'MOTION_BRICKS_BOUNDARY_CONTACT',
                    side.title()+' boundary has no grounded planted foot throughout the 0.1-second context. Review contacts or explicitly select a different trim boundary; airborne and mixed unstable contexts are unsupported')
            result[side]={'status':'SUPPORTED_GROUNDED_CONTEXT','origin':origin,'confidence':'kinematic-proposal-not-ground-truth',
                'feet':feet,'samples':samples,'root_distance_m':root_distance,'root_intent':m[0].get('root_intent','native-travel' if root_distance>=.002*height else 'observed-stationary')}
        return {'status':'EVALUATED','boundaries':result,'reference_height_m':height,'ground_z_m':profile['ground_z']}
    finally:soles.close()
