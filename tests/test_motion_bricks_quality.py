import unittest
from asset_director.motion_bricks_quality import thresholds,gate,contact_runs,correction_metrics


class QualityTests(unittest.TestCase):
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
        runs=contact_runs(rows(.001,0),60,2.,0)
        self.assertEqual(len(runs),2);self.assertEqual(runs[0]['end_index'],60)
        self.assertEqual(runs[0]['drift_m'],0.)

    def test_correction_measures_motion_not_metadata_or_quaternion_sign(self):
        raw=[{'hip':{'q':[1,0,0,0]}}]*3;corrected=[{'hip':{'q':[-1,0,0,0]}}]*3
        result=correction_metrics(raw,corrected,[[0,0,0]]*3,[[0,.2,0]]*3)
        self.assertEqual(result['rotation_correction_max_deg'],0.)
        self.assertAlmostEqual(result['root_correction_m'],.2)
