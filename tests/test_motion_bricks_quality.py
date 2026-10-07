import unittest
import math
from asset_director.motion_bricks_quality import thresholds,gate,contact_runs,correction_metrics


class QualityTests(unittest.TestCase):
    def test_stage_metrics_use_seconds_world_rotation_and_ignore_quaternion_sign(self):
        from asset_director.motion_bricks_quality import trajectory_metrics
        from asset_director.sequence_math import qexp
        rotations=[{'joint':[v*(-1 if i%2 else 1) for v in qexp([0,0,math.radians(30)*i/60])]} for i in range(61)]
        result=trajectory_metrics(rotations,[[2*i/60,0,0] for i in range(61)],1.)
        self.assertAlmostEqual(result['root_speed_m_s'],2.)
        self.assertAlmostEqual(result['joint_speed_deg_s'],30.)
        self.assertLess(result['joint_acceleration_deg_s2'],1e-8)
        self.assertLess(result['root_acceleration_m_s2'],1e-8)
    def test_missing_or_failed_hard_metric_cannot_be_ranked_away(self):
        limits=thresholds(2.)
        self.assertEqual(gate({'position_m':0.,'orientation_deg':0.},limits,['position_m','orientation_deg']),[])
        self.assertEqual(len(gate({'position_m':.003,'orientation_deg':0.},limits,['position_m'])),1)
        self.assertEqual(gate({},limits,['planted_drift_m'])[0]['reason'],'unavailable')
        for invalid in (0,None,float('nan'),True):
            with self.assertRaises(Exception):thresholds(invalid)

    def test_airborne_and_sliding_intervals_are_not_planted_successes(self):
        def rows(z,speed):return [{s:{'point':[speed*i/60,0,z],'low':z} for s in ('left','right')} for i in range(61)]
        self.assertEqual(contact_runs(rows(.2,0),60,2.,0),[])
        self.assertEqual(contact_runs(rows(0,1),60,2.,0),[])
        lifted_landmark=rows(.2,0)
        for row in lifted_landmark:
            for foot in row.values():foot['low']=0.
        self.assertEqual(contact_runs(lifted_landmark,60,2.,0),[],'Another vertex on the ground does not plant this measured landmark')
        runs=contact_runs(rows(.001,0),60,2.,0)
        self.assertEqual(len(runs),2);self.assertEqual(runs[0]['end_index'],60)
        self.assertEqual(runs[0]['drift_m'],0.)

    def test_correction_measures_motion_not_metadata_or_quaternion_sign(self):
        raw=[{'hip':{'q':[1,0,0,0]}}]*3;corrected=[{'hip':{'q':[-1,0,0,0]}}]*3
        result=correction_metrics(raw,corrected,[[0,0,0]]*3,[[0,.2,0]]*3)
        self.assertEqual(result['rotation_correction_max_deg'],0.)
        self.assertAlmostEqual(result['root_correction_m'],.2)

    def test_generated_filter_preserves_constant_motion_and_rejects_excessive_repair(self):
        from asset_director.motion_bricks_stitch_math import smooth_rotations
        from asset_director.sequence_math import qexp, qlog, qmul, inverse, norm
        samples=[(i,{'hip':{'q':qexp([0,0,i*.01])}}) for i in range(101)]
        corrected,report=smooth_rotations(samples,1.)
        self.assertFalse(report['timing_changed'])
        self.assertLess(norm(qlog(qmul(inverse(samples[50][1]['hip']['q']),corrected[50][1]['hip']['q']))),1e-12)
        self.assertEqual([s[0] for s in corrected],list(range(101)))
        samples[50][1]['hip']['q']=qexp([math.radians(150),0,0])
        with self.assertRaisesRegex(Exception,'more than 15 degrees'):smooth_rotations(samples,1.)

    def test_contact_provenance_and_duration_are_bounded(self):
        from asset_director.motion_bricks_contract import contact_plan
        self.assertEqual(contact_plan()['origin'],'evaluated-proposal')
        valid={'origin':'user-reviewed','source':{'support':'right','seconds':.12},'target':{'support':'auto','seconds':.08}}
        self.assertEqual(contact_plan(valid),valid)
        for patch in ({'support':'airborne','seconds':.12},{'support':'right','seconds':True},{'support':'right','seconds':.201}):
            with self.assertRaises(Exception):contact_plan({**valid,'source':patch})
        with self.assertRaises(Exception):contact_plan({**valid,'origin':'ground-truth'})

    def test_cubic_boundary_derivatives_use_the_stitch_and_physical_seconds(self):
        from asset_director.motion_bricks_stitch_math import boundary_estimate
        h=1/1536
        for side,sign in (('left',-1),('right',1)):
            values=[[2+3*t+400*t*t+100000*t*t*t] for t in [sign*i*h for i in (1,2,3,4)]]
            p,v=boundary_estimate(values,h,side)
            self.assertAlmostEqual(p[0],2,places=11);self.assertAlmostEqual(v[0],3,places=8)
