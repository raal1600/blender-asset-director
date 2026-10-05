import math
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from asset_director import sequence_math as sm, motion_bricks_stitch_math as seam

class GeneratedSeamTests(unittest.TestCase):
    def test_noncommuting_angular_velocity_and_exact_interior(self):
        duration, window = 2., .35
        initial=sm.qexp([.1, -.2, .05]); velocity=[.6, .2, -.3]
        raw=lambda t:sm.qmul(initial, sm.qexp(sm.mul(velocity,t)))
        native=[sm.qexp([.7,.1,-.4]),sm.qexp([-.2,.8,.1])]
        speeds=[[.2,-.3,.7],[-.4,.1,.2]]
        residuals=[seam.rotation_residual(raw(t),q,velocity,w) for t,q,w in zip([0.,duration],native,speeds)]
        corrected=lambda t:seam.correct_rotation(raw(t),residuals,t,duration,window)
        h=1e-6
        for i,t in enumerate([0.,duration]):
            self.assertLess(sm.norm(sm.qlog(sm.qmul(sm.inverse(native[i]),corrected(t)))),1e-10)
            measured=sm.angular_velocity(corrected(t),corrected(t+h),h) if i==0 else sm.angular_velocity(corrected(t-h),corrected(t),h)
            self.assertLess(sm.norm(sm.sub(measured,speeds[i])),1e-4)
        for t in [.35,.5,1.,1.65]:
            self.assertLess(sm.norm(sm.qlog(sm.qmul(sm.inverse(raw(t)),corrected(t)))),1e-12)

    def test_translation_residual_has_native_derivative_and_compact_support(self):
        residual=seam.edge_residual([2.,-1.,.5],[.4,.6,-.1],0.,2.,.4,0)
        self.assertEqual(residual,[2.,-1.,.5])
        for side in [0,1]:
            self.assertEqual(seam.edge_residual([2.],[.3],1.,2.,.4,side),[0.])

class GroundClearanceTests(unittest.TestCase):
    def test_height_noise_is_removed_without_changing_clear_lifts(self):
        for value in [-.04,0.,.01,.02]:self.assertEqual(seam.ground_clearance(value,1.),0.)
        for value in [.05,.1,.8]:self.assertEqual(seam.ground_clearance(value,1.),value)
        self.assertAlmostEqual(seam.ground_clearance(.03,1.)*2,seam.ground_clearance(.06,2.))

    def test_release_has_continuous_position_and_first_two_derivatives(self):
        h=1e-7
        for point,derivative in [(.02,0.),(.05,1.)]:
            f=lambda x:seam.ground_clearance(x,1.)
            self.assertAlmostEqual(f(point-h),f(point+h),delta=3*h)
            self.assertAlmostEqual((f(point+h)-f(point-h))/(2*h),derivative,delta=1e-6)
            self.assertAlmostEqual((f(point+h)-2*f(point)+f(point-h))/(h*h),0.,delta=.03)
        from asset_director.core import DirectorError
        with self.assertRaises(DirectorError):seam.ground_clearance(float('nan'),1.)
        with self.assertRaises(DirectorError):seam.ground_clearance(.01,0.)

if __name__=='__main__':unittest.main()
