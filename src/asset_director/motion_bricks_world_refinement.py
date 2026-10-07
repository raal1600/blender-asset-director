"""Bounded bridge-only world-rotation refinement after foot support projection."""
import copy
import math
from mathutils import Quaternion
from . import motion_bricks_retarget as ret, sequence_math as qm
from .motion_bricks_refinement import smooth_rotations
from .motion_bricks_quality import thresholds
from .motion_contacts import set_pose
from .motion_heading import rotation
from .core import require


def refine(reader,profile,samples,path,native_context,seconds,fps,check):
    clone=reader.clone
    def world(pose,delta):
        check();set_pose(reader,pose,delta,0.)
        return {name:{'q':list((clone.matrix_world@clone.pose.bones[name].matrix if name else clone.matrix_world).to_quaternion().normalized())} for name in pose}
    values=[(f,world(pose,delta)) for (f,pose),(_,delta) in zip(samples,path)]
    a,b,ap,app,bn,bnn,h=native_context
    endpoints=[world(a,path[0][1]),world(b,path[-1][1])]
    contexts=[world(pose,path[edge][1]) for pose,edge in ((ap,0),(app,0),(bn,-1),(bnn,-1))]
    tangents=[]
    for edge,sign in ((0,-1),(1,1)):
        row={}
        for name in endpoints[edge]:
            inverse=qm.inverse(endpoints[edge][name]['q'])
            near=qm.qlog(qm.qmul(inverse,contexts[2*edge][name]['q']));far=qm.qlog(qm.qmul(inverse,contexts[2*edge+1][name]['q']))
            row[name]={'angular':qm.mul(qm.sub(qm.mul(near,4),far),sign/(2*h))}
        tangents.append(row)
    # A fixed 20% margin reserves room for chart curvature, hierarchy conversion
    # and actual Blender interpolation. It does not change the hard quality gate.
    limit=.8*thresholds(profile['reference_height_m'])['joint_acceleration_deg_s2']
    filtered,report=smooth_rotations(values,seconds,endpoints,tangents,fps,sigma_seconds=.05,acceleration_limit=limit,check=check)
    output=copy.deepcopy(samples);largest=0.
    for i,((_,pose),(_,goals)) in enumerate(zip(output,filtered)):
        check();set_pose(reader,pose,path[i][1],0.)
        if '' in pose:
            parent=clone.matrix_world.to_quaternion()@Quaternion(pose['']['q']).inverted()
            pose['']['q']=list((parent.inverted()@Quaternion(goals['']['q'])).normalized())
            set_pose(reader,pose,path[i][1],0.)
        inverse=clone.matrix_world.to_quaternion().inverted()
        ret.apply_rotations(clone,{name:(inverse@Quaternion(value['q'])).normalized() for name,value in goals.items() if name})
        for name in pose:
            q=list(rotation(clone.pose.bones[name] if name else clone))
            change=math.degrees(qm.norm(qm.qlog(qm.qmul(qm.inverse(samples[i][1][name]['q']),q))))
            largest=max(largest,change);pose[name]['q']=q
    require(largest<=15.,'MOTION_BRICKS_EXCESSIVE_FILTER','World smoothing requires more than 15 degrees of local correction; choose another duration or boundary')
    report.update(coordinate_frame='evaluated world rotations',max_local_change_deg=largest,
                  mechanism='deterministic bounded bridge processing, including unmodeled joints; not neural generation')
    return output,report
