"""Bounded generated-pose smoothing with explicit endpoint/tangent constraints.

This deterministic correction minimizes displacement plus squared discrete
acceleration. It is not inference, retiming, physical simulation, or a blend
between the native clips. Every result still needs baked contact/quality checks.
"""
import copy
import math
from . import sequence_math as qm
from .core import require


def acceleration_system(count, weight):
    """Factor I + weight D2^T D2; bandwidth two, linear storage/solve cost."""
    diagonal=[1.]*count;first=[0.]*count;second=[0.]*count
    for i in range(1,count-1):
        for j,v in ((i-1,1),(i,-2),(i+1,1)):diagonal[j]+=weight*v*v
        first[i]-=2*weight;first[i+1]-=2*weight;second[i+1]+=weight
    a=[];b=[];c=[]
    for i in range(count):
        c.append(second[i]/a[i-2] if i>=2 else 0.)
        b.append((first[i]-c[i]*b[i-1])/a[i-1] if i else 0.)
        a.append(math.sqrt(diagonal[i]-b[i]*b[i]-c[i]*c[i]))
    def solve(rhs):
        y=[]
        for i,value in enumerate(rhs):y.append((value-(b[i]*y[i-1] if i else 0)-(c[i]*y[i-2] if i>=2 else 0))/a[i])
        x=[0.]*count
        for i in range(count-1,-1,-1):x[i]=(y[i]-(b[i+1]*x[i+1] if i+1<count else 0)-(c[i+2]*x[i+2] if i+2<count else 0))/a[i]
        return x
    return solve


def solve_small(matrix,rhs):
    rows=[list(row)+[value] for row,value in zip(matrix,rhs)];n=len(rows)
    for i in range(n):
        pivot=max(range(i,n),key=lambda j:abs(rows[j][i]));rows[i],rows[pivot]=rows[pivot],rows[i]
        require(abs(rows[i][i])>1e-12,'MOTION_BRICKS_REFINEMENT','Singular generated smoothing constraints')
        scale=rows[i][i];rows[i]=[v/scale for v in rows[i]]
        for j in range(n):
            if j==i:continue
            scale=rows[j][i];rows[j]=[v-scale*w for v,w in zip(rows[j],rows[i])]
    return [row[-1] for row in rows]


def constrained_solver(count, weight):
    require(count>=8,'MOTION_BRICKS_REFINEMENT','Generated smoothing needs at least eight samples')
    solve=acceleration_system(count,weight)
    constraints=[{0:1.},{count-1:1.},{0:-11/6,1:3.,2:-1.5,3:1/3},
                 {count-4:-1/3,count-3:1.5,count-2:-3.,count-1:11/6}]
    rows=[[row.get(i,0.) for i in range(count)] for row in constraints]
    inverse_rows=[solve(row) for row in rows]
    project=lambda row,x:sum(value*x[i] for i,value in row.items())
    schur=[[project(row,x) for x in inverse_rows] for row in constraints]
    def smooth(values, endpoints):
        x=solve(values);multipliers=solve_small(schur,[v-project(row,x) for row,v in zip(constraints,endpoints)])
        x=[value+sum(w*column[i] for w,column in zip(multipliers,inverse_rows)) for i,value in enumerate(x)]
        residual=max(abs(project(row,x)-v) for row,v in zip(constraints,endpoints))
        require(residual<1e-7,'MOTION_BRICKS_REFINEMENT','Generated smoothing did not satisfy endpoint constraints')
        return x,residual
    return smooth


def smooth_rotations(samples,seconds,natives,tangents,fps,*,sigma_seconds=.04,maximum_degrees=15.,acceleration_limit=None,check=lambda:None):
    from .motion_bricks_spline import continuous_system
    count=len(samples);step=seconds/(count-1);weight=(sigma_seconds/step)**4
    bound=math.radians(acceleration_limit)*step*step if acceleration_limit is not None else None
    solve=continuous_system(count,weight,acceleration_bound=bound,check=check)
    output=copy.deepcopy(samples);largest=0.;squares=[];diagnostics=[]
    for name in samples[0][1]:
        check()
        reference=qm.unit(natives[0][name]['q']);inverse=qm.inverse(reference)
        logs=[qm.qlog(qm.qmul(inverse,qm.unit(pose[name]['q']))) for _,pose in samples]
        target=qm.qlog(qm.qmul(inverse,qm.unit(natives[1][name]['q'])))
        require(all(qm.norm(v)<math.pi-.001 for v in logs+[target]),'MOTION_BRICKS_REFINEMENT',
                'This generated joint turn crosses the local smoothing chart; choose a different supported boundary')
        incoming=qm.mul(tangents[0][name]['angular'],fps)
        outgoing=qm.right_jacobian_inverse(target,qm.mul(tangents[1][name]['angular'],fps))
        values,_,report=solve(logs,[[0.,0.,0.],target,qm.mul(incoming,step),qm.mul(outgoing,step)])
        diagnostics.append({'joint':name,**report})
        for i,(_,pose) in enumerate(samples):
            q=qm.unit(qm.qmul(reference,qm.qexp(values[i])))
            change=math.degrees(qm.norm(qm.qlog(qm.qmul(qm.inverse(qm.unit(pose[name]['q'])),q))))
            largest=max(largest,change);squares.append(change*change);output[i][1][name]['q']=q
    require(largest<=maximum_degrees,'MOTION_BRICKS_EXCESSIVE_FILTER',
            'Generated motion needs more than 15 degrees of constrained smoothing; choose another duration or boundary')
    return output,{'method':'generated-only-continuous-SO3-v2','sigma_seconds':sigma_seconds,
                   'acceleration_weight':weight,'max_change_deg':largest,'rms_change_deg':math.sqrt(sum(squares)/len(squares)),
                   'constraint_residual':max(r['endpoint_constraint_residual'] for r in diagnostics),'limit_deg':maximum_degrees,'timing_changed':False,
                   'log_acceleration_limit_deg_s2':acceleration_limit,'solver':diagnostics,
                   'acceleration_scope':'rotation-log chart; evaluated baked world motion must independently pass'}


def smooth_positions(values, seconds, endpoint_velocities, *, sigma_seconds=.025, maximum_distance,check=lambda:None):
    """World-metre trajectory with fixed positions and m/s endpoint velocities."""
    count=len(values);step=seconds/(count-1);weight=(sigma_seconds/step)**4
    from .motion_bricks_spline import continuous_system
    solve=continuous_system(count,weight,check=check)
    output,_,report=solve(values,[values[0],values[-1],qm.mul(endpoint_velocities[0],step),qm.mul(endpoint_velocities[1],step)])
    largest=max(math.dist(a,b) for a,b in zip(values,output))
    require(largest<=maximum_distance,'MOTION_BRICKS_EXCESSIVE_ROOT_FILTER','Generated root smoothing exceeds its bounded correction; choose another duration or boundary')
    return output,{'method':'generated-only-continuous-position-v2','sigma_seconds':sigma_seconds,
                   'max_change_m':largest,'limit_m':maximum_distance,'constraint_residual':report['endpoint_constraint_residual'],'timing_changed':False,'solver':report}
