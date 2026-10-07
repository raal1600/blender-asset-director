"""Continuous clamped cubic smoothing, optionally bounding vector curvature.

Only generated samples are inputs. Positions and derivatives at both endpoints
are fixed. The objective combines sampled displacement with the exact integral
of squared cubic curvature; it does not use a discrete endpoint stencil.
Curvature in a rotation-log chart is not physical angular acceleration. The
evaluated baked-motion gate remains authoritative.
"""
import math
from .core import require


def clamped_key_slopes(times,values,endpoints=None):
    """C2 interpolating cubic derivatives in the supplied time units."""
    n=len(times)
    require(n==len(values) and 2<=n<=1025 and all(math.isfinite(v) for v in list(times)+list(values)),
            'MOTION_BRICKS_REFINEMENT','Invalid generated interpolation samples')
    h=[b-a for a,b in zip(times,times[1:])]
    require(all(v>0 for v in h),'MOTION_BRICKS_REFINEMENT','Generated interpolation times must increase')
    require(endpoints is None or len(endpoints)==2 and all(math.isfinite(v) for v in endpoints),
            'MOTION_BRICKS_REFINEMENT','Invalid generated endpoint slopes')
    d=[(b-a)/step for a,b,step in zip(values,values[1:],h)]
    diagonal=[1.]*n;lower=[0.]*n;upper=[0.]*n;rhs=[0.]*n
    for i in range(1,n-1):
        lower[i]=h[i-1];diagonal[i]=2*(h[i-1]+h[i]);upper[i]=h[i];rhs[i]=6*(d[i]-d[i-1])
    if endpoints is not None:
        diagonal[0]=2*h[0];upper[0]=h[0];rhs[0]=6*(d[0]-endpoints[0])
        lower[-1]=h[-1];diagonal[-1]=2*h[-1];rhs[-1]=6*(endpoints[-1]-d[-1])
    for i in range(1,n):
        factor=lower[i]/diagonal[i-1];diagonal[i]-=factor*upper[i-1];rhs[i]-=factor*rhs[i-1]
    m=[0.]*n;m[-1]=rhs[-1]/diagonal[-1]
    for i in range(n-2,-1,-1):m[i]=(rhs[i]-upper[i]*m[i+1])/diagonal[i]
    return [d[i]-h[i]*(2*m[i]+m[i+1])/6 for i in range(n-1)]+[d[-1]+h[-1]*(m[-2]+2*m[-1])/6]


def _factor(band):
    """Cholesky of a symmetric positive matrix with three lower diagonals."""
    n=len(band);lower=[[0.]*4 for _ in band]
    for i in range(n):
        for j in range(max(0,i-3),i+1):
            value=band[i][i-j]-sum(lower[i][i-k]*lower[j][j-k] for k in range(max(0,i-3,j-3),j))
            require(math.isfinite(value) and (i!=j or value>0),'MOTION_BRICKS_REFINEMENT','Invalid continuous smoothing system')
            lower[i][i-j]=math.sqrt(value) if i==j else value/lower[j][0]
    def solve(rhs):
        y=[]
        for i,v in enumerate(rhs):y.append((v-sum(lower[i][i-k]*y[k] for k in range(max(0,i-3),i)))/lower[i][0])
        x=[0.]*n
        for i in range(n-1,-1,-1):x[i]=(y[i]-sum(lower[k][k-i]*x[k] for k in range(i+1,min(n,i+4))))/lower[i][0]
        return x
    return solve


def continuous_system(count,weight,*,acceleration_bound=None,check=lambda:None):
    """Build an O(count)-storage solver reusable for scalar/vector trajectories.

    Values and endpoint positions are vectors with one to three components.
    Endpoint velocities are expressed per sample step. An optional curvature
    norm bound is likewise per squared step; callers convert physical units.
    Results retain both values and per-step derivatives of the clamped spline.
    """
    require(type(count) is int and 8<=count<=1025 and type(weight) in (int,float) and math.isfinite(weight) and weight>0,
            'MOTION_BRICKS_REFINEMENT','Choose 8–1025 generated samples and a positive finite smoothing weight')
    require(acceleration_bound is None or type(acceleration_bound) in (int,float) and math.isfinite(acceleration_bound) and acceleration_bound>0,
            'MOTION_BRICKS_REFINEMENT','Curvature bound must be positive and finite')
    check();size=2*count;rho=256. if acceleration_bound is not None else 0.
    band=[[0.]*4 for _ in range(size)]
    for i in range(count):band[2*i][0]=1.
    # Unknowns are [y_i, p_i, y_i+1, p_i+1], p=h*dy/dt.
    element=((12.,6.,-12.,6.),(6.,4.,-6.,2.),(-12.,-6.,12.,-6.),(6.,2.,-6.,4.))
    rows=[]
    for i in range(count-1):
        for j in range(4):
            for k in range(j+1):band[2*i+j][j-k]+=weight*element[j][k]
        rows.extend(({2*i:-6.,2*i+1:-4.,2*i+2:6.,2*i+3:-2.},
                     {2*i:6.,2*i+1:2.,2*i+2:-6.,2*i+3:4.}))
    if rho:
        for row in rows:
            for i,a in row.items():
                for j,b in row.items():
                    if i>=j:band[i][i-j]+=rho*a*b
    free=list(range(2,size-2));fixed=(0,1,size-2,size-1)
    factor=_factor([[band[ii][d] if ii-d>=2 else 0. for d in range(4)] for ii in free])
    def entry(i,j):return band[max(i,j)][abs(i-j)] if abs(i-j)<=3 else 0.
    def solve(rhs,prescribed):
        reduced=[rhs[ii]-sum(entry(ii,jj)*v for jj,v in zip(fixed,prescribed)) for ii in free]
        return prescribed[:2]+factor(reduced)+prescribed[2:]
    def smooth(values,endpoints):
        check();dimensions=len(values[0]) if values and isinstance(values[0],(list,tuple)) else 0
        require(len(values)==count and 1<=dimensions<=3 and len(endpoints)==4
                and all(isinstance(v,(list,tuple)) and len(v)==dimensions
                        and all(type(x) in (int,float) and math.isfinite(x) for x in v) for v in list(values)+list(endpoints)),
                'MOTION_BRICKS_REFINEMENT','Continuous smoothing needs matching finite vectors and four endpoint constraints')
        prescribed=[[endpoints[0][c],endpoints[2][c],endpoints[1][c],endpoints[3][c]] for c in range(dimensions)]
        data=[[values[j//2][c] if j%2==0 else 0. for j in range(size)] for c in range(dimensions)]
        z=[[0.]*dimensions for _ in rows];u=[[0.]*dimensions for _ in rows]
        norm=lambda v:math.sqrt(sum(x*x for x in v));primal=dual=0.
        for iteration in range(1200 if rho else 1):
            if iteration%16==0:check()
            components=[]
            for c in range(dimensions):
                rhs=data[c].copy()
                if rho:
                    for row,zz,uu in zip(rows,z,u):
                        for j,a in row.items():rhs[j]+=rho*a*(zz[c]-uu[c])
                components.append(solve(rhs,prescribed[c]))
            acceleration=[[sum(a*components[c][j] for j,a in row.items()) for c in range(dimensions)] for row in rows]
            if not rho:break
            old=z;z=[]
            for v,d in zip(acceleration,u):
                w=[a+b for a,b in zip(v,d)];length=norm(w);scale=min(1.,acceleration_bound/length) if length else 1.
                z.append([a*scale for a in w])
            u=[[d+a-b for d,a,b in zip(dual_row,v,zz)] for dual_row,v,zz in zip(u,acceleration,z)]
            primal=max(norm([a-b for a,b in zip(v,zz)]) for v,zz in zip(acceleration,z))
            dual=max(norm([a-b for a,b in zip(v,zz)]) for v,zz in zip(old,z))*rho
            if primal<1e-8 and dual<1e-6:break
        require(not rho or primal<1e-7,'MOTION_BRICKS_REFINEMENT','Bounded generated smoothing did not converge; choose another duration or boundary')
        check()
        return ([[column[2*i] for column in components] for i in range(count)],
                [[column[2*i+1] for column in components] for i in range(count)],
                {'method':'continuous-clamped-cubic-v1','iterations':iteration+1,'primal_residual':primal,'dual_residual':dual,
                 'endpoint_constraint_residual':0.,'curvature_bound_per_step2':acceleration_bound,
                 'maximum_curvature_per_step2':max(norm(v) for v in acceleration)})
    return smooth
