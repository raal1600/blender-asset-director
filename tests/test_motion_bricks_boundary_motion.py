import math
import unittest
from asset_director import motion_bricks_contract as c, sequence_math as q


class BoundaryMotionTests(unittest.TestCase):
    def test_physical_seconds_common_world_rotation_and_axis_conversion(self):
        # Noncommuting starting orientation catches a body/world angular-frame mixup.
        initial=q.qexp([.4,-.2,.7]);omega=[.3,.4,.5];velocity=[2.,-.6,.2]
        position=[3.,-2.,1.2];origin=[2.,-3.,.2];scale=1.7
        axes=[math.sqrt(.5),math.sqrt(.5),0.,0.]
        for side in ('source','target'):
            roots=[];rotations=[]
            for i in range(4):
                t=(i-3 if side=='source' else i)/30
                world=q.add(position,q.mul(velocity,t));relative=q.mul(q.sub(world,origin),scale)
                roots.append([relative[0],relative[2],-relative[1]])
                world_q=q.qmul(q.qexp(q.mul(omega,t)),initial)
                model=q.qmul(q.qmul(q.inverse(axes),world_q),axes)
                if i%2:model=q.mul(model,-1)  # Quaternion sign is not motion.
                rotations.append([[*model[1:],model[0]]])
            result=c.boundary_motion({'roots':roots,'local_xyzw':rotations},side,scale,origin)
            for key,expected in [('position_m',position),('linear_velocity_m_s',velocity),('angular_velocity_rad_s',omega)]:
                for a,b in zip(result[key],expected):self.assertAlmostEqual(a,b,places=11)
            self.assertAlmostEqual(abs(q.dot(result['orientation_wxyz'],initial)),1.,places=12)
            self.assertIn(0.,result['sample_seconds_from_stitch'])

    def test_heading_is_explicit_and_stationary_root_has_zero_velocity(self):
        for angle in (-90.,0.,90.):
            # World-Z yaw is model-Y yaw under the declared axes conversion.
            model=q.qexp([0.,math.radians(angle),0.])
            context={'roots':[[0.,1.,0.]]*4,'local_xyzw':[[[*model[1:],model[0]]]]*4}
            result=c.boundary_motion(context,'target',1.,[0.,0.,0.])
            self.assertAlmostEqual(result['heading_degrees'],angle)
            self.assertEqual(result['linear_velocity_m_s'],[0.,0.,0.])
            self.assertEqual(result['angular_velocity_rad_s'],[0.,0.,0.])
            self.assertEqual(result['position_m'],[0.,0.,1.])


if __name__=='__main__':unittest.main()
