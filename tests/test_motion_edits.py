import math
import unittest
from asset_director.action_timeline_contract import validate, timing, source_range, connection
from asset_director.core import DirectorError


def clip(**extra):
    return dict(id='clip_a', take_id='take_'+'a'*64, start=1, frames=25,
                speed=1., repeat_reviewed=False, travel=None, **extra)


class MotionEditTests(unittest.TestCase):
    def test_explicit_source_range_is_single_pass_and_preserves_native_identity(self):
        c = clip(source_range=[7., 19.]); c['frames'] = 13
        take = {'range': [1., 25.]}
        validate(dict(performer='Observed', mode='timeline', clips=[c]))
        self.assertEqual(source_range(c, take), [7., 19.])
        self.assertEqual(timing(c, take)['native_end'], 13)
        self.assertEqual(take['range'], [1., 25.])
        for bad in (c | {'source_range': [0., 19.]}, c | {'frames': 30, 'repeat_reviewed': True},
                    c | {'travel': {'delta_m': [1., 0.], 'meters_per_cycle': 1.}},
                    c | {'transition': {'frames': 6, 'match_phase': True}}):
            with self.assertRaises(DirectorError):
                timing(bad, take)

    def test_turn_requires_explicit_interval_and_has_distinct_brake_geometry(self):
        a = clip(); a['travel'] = {'delta_m': [0., -1.], 'meters_per_cycle': 1.}
        b = a | {'id': 'clip_b', 'start': 38, 'heading_deg': 90.,
                 'travel': {'delta_m': [-1., 0.], 'meters_per_cycle': 1.},
                 'transition': {'frames': 12, 'match_phase': False, 'mode': 'turn'}}
        validate(dict(performer='Observed', mode='timeline', clips=[a, b]))
        plan = connection(a, b, {'range': [1., 25.]}, {'range': [1., 25.]})
        self.assertEqual(plan['turn_delta_deg'], 90.)
        self.assertEqual(plan['mode'], 'turn')
        self.assertEqual(plan['delta_m'], [-13/192, -13/192])
        for bad in (b | {'transition': {'frames': 12, 'match_phase': False}}, b | {'heading_deg': 180.}):
            with self.assertRaises(DirectorError):
                connection(a, bad, {'range': [1., 25.]}, {'range': [1., 25.]})
        with self.assertRaises(DirectorError):
            validate(dict(performer='Observed', mode='timeline', clips=[a, b | {'transition': None}]))

    def test_automatic_gait_rotates_with_explicit_heading_not_strides(self):
        take = {'range': [1., 25.], 'gait': {'status': 'estimated', 'id': 'b'*64,
                                          'direction': [0., -1.], 'meters_per_cycle': 1.}}
        c = clip(heading_deg=90.)
        c['travel'] = {'delta_m': [1., 0.], 'meters_per_cycle': 1., 'gait_id': 'b'*64}
        self.assertEqual(timing(c, take)['cycles'], 1)
        with self.assertRaises(DirectorError):
            timing(c | {'travel': c['travel'] | {'delta_m': [0., -1.]}}, take)


if __name__ == '__main__':
    unittest.main()
