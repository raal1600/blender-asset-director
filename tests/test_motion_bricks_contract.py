import copy
import math
import unittest
from asset_director.core import DirectorError
from asset_director import motion_bricks_contract as c


class TransitionInputTests(unittest.TestCase):
    def test_all_native_durations_and_exact_retime_limits(self):
        for n in range(24, 65, 4):
            seconds=(n-7)/30
            plan=c.duration_plan(seconds)
            self.assertEqual(plan['model_frames'],n)
            self.assertEqual(plan['bridge_indices'],[3,n-4])
            self.assertEqual(plan['generated_retime_ratio'],1)
            for factor in (.85,1.15):
                bounded=c.duration_plan(seconds*factor)
                self.assertGreaterEqual(bounded['generated_retime_ratio'],.85-1e-12)
                self.assertLessEqual(bounded['generated_retime_ratio'],1.15+1e-12)
        for seconds in (True,0,math.nan,math.inf,.4816,2.18501):
            with self.assertRaises(DirectorError):c.duration_plan(seconds)

    def test_context_has_no_fabricated_or_unrelated_frames(self):
        for fps in (24,30,60):
            for side in ('source','target'):
                schedule=c.context_schedule([13.,13.+fps],fps,side)
                expected=13.+fps if side=='source' else 13.
                self.assertEqual(schedule['source_frames'][3 if side=='source' else 0],expected)
                for a,b in zip(schedule['source_frames'],schedule['source_frames'][1:]):
                    self.assertAlmostEqual((b-a)/fps,1/30)
                self.assertEqual(schedule['context_horizon_seconds'],.1)
                with self.assertRaises(DirectorError):c.context_schedule([13.,13.+.09*fps],fps,side)
                with self.assertRaises(DirectorError):c.context_schedule([13.,13.+fps],fps,side,elapsed=2*fps)
        self.assertEqual(c.context_schedule([10,40],30,'source',elapsed=9)['source_frames'],[16,17,18,19])

    def test_sampling_explicitly_discloses_ineffective_argmax_seed(self):
        self.assertFalse(c.sampling_settings('argmax',1234)['seed_affects_output'])
        self.assertEqual(c.sampling_settings('gumbel-temperature-1',7)['temperature'],1)
        for mode,seed in [('temperature-.5',7),('argmax',True),('argmax',2**32)]:
            with self.assertRaises(DirectorError):c.sampling_settings(mode,seed)

    def test_metadata_sign_and_small_numerical_noise_are_not_diversity(self):
        a={'roots':[[0,1,0] for _ in range(24)],'local_xyzw':[[[0,0,0,1]] for _ in range(24)]}
        b=copy.deepcopy(a);b['filename']='different';b['local_xyzw'][5][0]=[0,0,0,-1]
        b['roots'][6][0]=1e-7
        self.assertTrue(c.motion_difference(a,b,2.)['near_duplicate'])
        for frame in b['local_xyzw']:frame[0]=[math.sin(.1),0,0,math.cos(.1)]
        self.assertFalse(c.motion_difference(a,b,2.)['near_duplicate'])
        b['roots'].append([0,1,0])
        self.assertEqual(c.motion_difference(a,b,2.)['status'],'DIFFERENT_DURATIONS')
