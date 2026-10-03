import math
import unittest
from asset_director.gait_profile import estimate
from asset_director.action_timeline_contract import validate, timing
from asset_director.core import DirectorError


def paths(scale=1, angle=0):
    result = {}
    for name, offset, x in [('Support A', 0, -.2), ('Support B', .5, .2)]:
        points = []
        for index in range(65):
            phase = (index / 64 + offset) % 1
            y = .5 - 2 * phase if phase < .5 else -.5 + 2 * (phase - .5)
            z = 0 if phase < .5 else .16 * math.sin(2 * math.pi * (phase - .5))
            points.append([scale * (x * math.cos(angle) - y * math.sin(angle)),
                           scale * (x * math.sin(angle) + y * math.cos(angle)), scale * z])
        result[name] = points
    return result


class GaitTests(unittest.TestCase):
    def test_observed_stance_infers_pace_not_label(self):
        g = estimate(paths(), 2)
        self.assertEqual(g['status'], 'estimated')
        self.assertAlmostEqual(g['meters_per_cycle'], 2)
        self.assertEqual(g['direction'], [0, 1])
        self.assertEqual(g['stance_residual_ratio'], 0)
        self.assertNotIn('approved', g)

    def test_rotated_scaled_coordinates(self):
        g = estimate(paths(3, math.pi / 2), 6)
        self.assertEqual(g['status'], 'estimated')
        self.assertAlmostEqual(g['meters_per_cycle'], 6)
        self.assertAlmostEqual(g['direction'][0], -1)
        self.assertAlmostEqual(g['direction'][1], 0)

    def test_refuse_static_hopping_nonclosing_or_ambiguous(self):
        traces = paths()
        for bad in [{}, {'Only': traces['Support A']},
                    {k: [p[0]] * 65 for k, p in traces.items()},
                    {k: traces['Support A'] for k in traces},
                    {k: p[:-1] + [[0, 3, 0]] for k, p in traces.items()},
                    {k: p[:-1] + [[0, float('nan'), 0]] for k, p in traces.items()}]:
            self.assertEqual(estimate(bad, 2)['status'], 'unavailable')

    def test_backend_binds_automatic_profile_and_retains_review(self):
        g = estimate(paths(), 2) | {'id': 'a' * 64}
        take = {'range': [0, 24], 'gait': g}
        clip = {'id': 'clip_test', 'take_id': 'take_' + 'b' * 64, 'start': 1, 'frames': 61,
                'speed': 1, 'repeat_reviewed': False,
                'travel': {'delta_m': [0, 5], 'meters_per_cycle': 2, 'gait_id': g['id']}}
        validate({'performer': 'Rig', 'mode': 'timeline', 'clips': [clip]})
        with self.assertRaises(DirectorError): timing(clip, take)
        clip['repeat_reviewed'] = True  # Synthetic contract fixture only.
        self.assertEqual(timing(clip, take)['cycles'], 2.5)
        for patch in [{'gait_id': 'c' * 64}, {'meters_per_cycle': 5}, {'delta_m': [5, 0]}]:
            with self.assertRaises(DirectorError): timing(clip | {'travel': clip['travel'] | patch}, take)
        self.assertEqual(timing(clip | {'speed': 2, 'frames': 31}, take)['native_end'], 31)
