import unittest
from asset_director.motion_bricks_refinement import acceleration_system, constrained_solver, smooth_positions


class RefinementTests(unittest.TestCase):
    def test_position_filter_preserves_physical_motion_and_bounds_its_correction(self):
        values=[[i/25,2*i/25,0.] for i in range(26)]
        result,report=smooth_positions(values,.5,[[2.,4.,0.],[2.,4.,0.]],maximum_distance=.0001)
        for actual,expected in zip(result,values):
            for a,b in zip(actual,expected):self.assertAlmostEqual(a,b,places=10)
        self.assertFalse(report['timing_changed'])
        values[12][2]=1.
        with self.assertRaisesRegex(Exception,'bounded correction'):
            smooth_positions(values,.5,[[2.,4.,0.],[2.,4.,0.]],maximum_distance=.01)
    def test_banded_solver_inverts_the_acceleration_objective(self):
        values=[.2,-.4,1.3,2.1,-.5,.3,1.4,2.]
        weight=123.;rhs=values.copy()
        for i in range(1,len(values)-1):
            acceleration=values[i-1]-2*values[i]+values[i+1]
            for j,c in ((i-1,1),(i,-2),(i+1,1)):rhs[j]+=weight*c*acceleration
        result=acceleration_system(len(values),weight)(rhs)
        for actual,expected in zip(result,values):self.assertAlmostEqual(actual,expected,places=10)

    def test_constraints_preserve_motion_endpoints_and_tangents_while_reducing_noise(self):
        solve=constrained_solver(50,256.)
        values=[i*.02+(.03 if i%2 else -.03) for i in range(50)]
        result,residual=solve(values,[0.,.98,.02,.02])
        self.assertLess(residual,1e-10)
        self.assertAlmostEqual(result[0],0);self.assertAlmostEqual(result[-1],.98)
        self.assertAlmostEqual(-11/6*result[0]+3*result[1]-1.5*result[2]+result[3]/3,.02)
        self.assertAlmostEqual(-result[-4]/3+1.5*result[-3]-3*result[-2]+11/6*result[-1],.02)
        energy=lambda x:sum((x[i-1]-2*x[i]+x[i+1])**2 for i in range(1,len(x)-1))
        self.assertLess(energy(result),energy(values)*.01)
        self.assertGreater(max(result)-min(result),.97,'Smoothing must preserve the trajectory, not freeze it')
