import math
import unittest
from asset_director.motion_bricks_spline import continuous_system,clamped_key_slopes
from asset_director.core import DirectorError


class ContinuousSplineTests(unittest.TestCase):
    def test_clamped_nonuniform_cubic_interpolation_reproduces_derivatives(self):
        times=[0.,.07,.21,.4,.71,1.];values=[x**3-2*x*x+.4*x for x in times]
        slopes=clamped_key_slopes(times,values,[.4,-.6])
        for x,v in zip(times,slopes):self.assertAlmostEqual(v,3*x*x-4*x+.4,places=10)
        with self.assertRaises(DirectorError):clamped_key_slopes([0.,0.],[0.,1.],[0.,0.])

    def test_exact_affine_motion_and_clamped_derivatives(self):
        values=[[i*.02,-i*.03,1.] for i in range(50)];velocity=[.02,-.03,0.]
        result,slopes,report=continuous_system(50,256.)(values,[values[0],values[-1],velocity,velocity])
        for a,b in zip(result,values):
            for x,y in zip(a,b):self.assertAlmostEqual(x,y,places=9)
        for row in slopes:
            for x,y in zip(row,velocity):self.assertAlmostEqual(x,y,places=9)
        self.assertEqual(report['endpoint_constraint_residual'],0)

    def test_vector_bound_applies_to_continuous_segments_not_only_sample_differences(self):
        values=[[i*.02+.035*math.sin(i*.7),.02*math.sin(i*.6),0.] for i in range(40)]
        ends=[[0.,0.,0.],[.78,0.,0.],[.02,0.,0.],[.02,0.,0.]];bound=.003
        result,slopes,report=continuous_system(40,100.,acceleration_bound=bound)(values,ends)
        self.assertEqual(result[0],ends[0]);self.assertEqual(result[-1],ends[1])
        self.assertEqual(slopes[0],ends[2]);self.assertEqual(slopes[-1],ends[3])
        for a,b,p,q in zip(result,result[1:],slopes,slopes[1:]):
            left=[6*(y-x)-4*v-2*w for x,y,v,w in zip(a,b,p,q)]
            right=[-6*(y-x)+2*v+4*w for x,y,v,w in zip(a,b,p,q)]
            for acceleration in (left,right):self.assertLessEqual(math.sqrt(sum(v*v for v in acceleration)),bound+1e-7)
        self.assertLess(report['primal_residual'],1e-7)
        self.assertGreater(result[-1][0]-result[0][0],.77)

    def test_invalid_inputs_and_cancellation_are_not_success(self):
        for count,weight,bound in [(7,1,None),(30,0,None),(30,1,float('nan'))]:
            with self.assertRaises(DirectorError):continuous_system(count,weight,acceleration_bound=bound)
        values=[[0.] for _ in range(20)];values[4]=[float('nan')]
        with self.assertRaises(DirectorError):continuous_system(20,1.)(values,[[0.]]*4)
        calls=[]
        def check():
            calls.append(1)
            if len(calls)>=3:raise RuntimeError('cancelled')
        solve=continuous_system(20,100.,acceleration_bound=.001,check=check)
        with self.assertRaisesRegex(RuntimeError,'cancelled'):solve([[i*.03] for i in range(20)],[[0.],[.57],[0.],[0.]])

    def test_finer_grid_converges_without_weakening_continuous_bound(self):
        count=69;bound=.004
        values=[[.5*math.sin(i*.08)+.06*math.sin(i*.7),.03*math.sin(i*.6)] for i in range(count)]
        ends=[values[0],values[-1],[.04,0.],[.025,0.]]
        result,slopes,report=continuous_system(count,1296.,acceleration_bound=bound)(values,ends)
        self.assertLess(report['primal_residual'],1e-8)
        self.assertLess(report['dual_residual'],1e-6)
        for a,b,p,q in zip(result,result[1:],slopes,slopes[1:]):
            for row in ([6*(y-x)-4*v-2*w for x,y,v,w in zip(a,b,p,q)],
                        [-6*(y-x)+2*v+4*w for x,y,v,w in zip(a,b,p,q)]):
                self.assertLessEqual(math.hypot(*row),bound+1e-8)
