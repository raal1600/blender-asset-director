import math
import unittest
from asset_director.action_timeline_contract import validate, connection
from asset_director.motion_stitch_math import bridge, closed, pose_cost, segments, source_frame
from asset_director.core import DirectorError


def clip(name, start, delta=None, transition=None):
    result = dict(id='clip_'+name, take_id='take_'+'a'*64, start=start, frames=25,
                  speed=1, repeat_reviewed=False,
                  travel={'delta_m': delta, 'meters_per_cycle': math.hypot(*delta)} if delta else None)
    if transition is not None:
        result['transition'] = transition
    return result


def pose(angle, x=0):
    return {'arbitrary-owner': {'location': [x, 0, 0], 'q': [math.cos(angle/2), 0, 0, math.sin(angle/2)], 'scale': [1, 1, 1]}}


class MotionStitchTests(unittest.TestCase):
    def test_explicit_extra_time_and_legacy_compatibility(self):
        a = clip('a', 1)
        b = clip('b', 32, transition={'frames': 6, 'match_phase': True})
        validate(dict(performer='Anything', mode='timeline', clips=[a, b]))
        validate(dict(performer='Anything', mode='timeline', clips=[a, clip('cut', 26)]))
        for clips in ([b], [a, b | {'start': 31}], [a, b | {'transition': {'frames': True, 'match_phase': True}}],
                      [a, b | {'transition': {'frames': 6, 'match_phase': 1}}],
                      [a, b | {'transition': {'frames': 121, 'match_phase': False}}]):
            with self.assertRaises(DirectorError):
                validate(dict(performer='Anything', mode='timeline', clips=clips))

    def test_world_velocity_carries_distance_without_stretching_clips(self):
        a = clip('a', 1, [0, 2])
        b = clip('b', 32, [2, 0], {'frames': 6, 'match_phase': False})
        result = connection(a, b, {'range': [1, 25]}, {'range': [1, 25]})
        self.assertEqual(result['duration_frames'], 7)
        for value in result['delta_m']:
            self.assertAlmostEqual(value, 7/24, places=12)
        self.assertEqual(a['frames'], 25)
        self.assertEqual(b['frames'], 25)
        with self.assertRaisesRegex(DirectorError, 'turn or stop'):
            connection(a, b | {'travel': {'delta_m': [0, -2], 'meters_per_cycle': 2}}, {'range': [1, 25]}, {'range': [1, 25]})

    def test_phase_segments_preserve_duration_without_changing_source(self):
        for phase in (0, .125, .5, .96875):
            for elapsed in (2.5, 24., 36., 55.5, 2400.):
                pieces = segments(0, 24, elapsed, phase)
                self.assertLessEqual(len(pieces), 3)
                self.assertAlmostEqual(sum((b-a)*n for a, b, n in pieces), elapsed)
                self.assertTrue(all(0 <= a < b <= 24 and n >= 1 for a, b, n in pieces))
        self.assertEqual(source_frame(0, 24, 24, endpoint=True), 24)
        self.assertEqual(source_frame(0, 24, 0, .5), 12)

    def test_bridge_endpoints_and_velocity_without_semantic_names(self):
        a, b, ap, bn = pose(.2, 1), pose(.8, 2), pose(.19, .99), pose(.82, 2.02)
        self.assertLess(pose_cost(bridge(a, b, ap, bn, .1, 6, 0), a), 1e-12)
        self.assertLess(pose_cost(bridge(a, b, ap, bn, .1, 6, 1), b), 1e-12)
        eps = 1e-5
        near = bridge(a, b, ap, bn, .1, 6, eps)['arbitrary-owner']['location'][0]
        self.assertAlmostEqual((near-1)/(eps*6), .1, places=4)
        self.assertTrue(closed(a, a))
        self.assertFalse(closed(a, b))
        with self.assertRaises(DirectorError):
            bridge(pose(0), pose(math.pi), pose(0), pose(math.pi), .1, 6, .5)

    def test_native_scale_velocity_is_preserved_and_reflections_refuse(self):
        a,b,ap,bn=pose(0),pose(0),pose(0),pose(0)
        a['arbitrary-owner']['scale']=[1,1,1]
        b['arbitrary-owner']['scale']=[2,2,2]
        ap['arbitrary-owner']['scale']=[.99,.99,.99]
        bn['arbitrary-owner']['scale']=[2.02,2.02,2.02]
        eps=1e-5
        near=bridge(a,b,ap,bn,.1,6,eps)['arbitrary-owner']['scale'][0]
        self.assertAlmostEqual((near-1)/(eps*6),.1,places=4)
        b['arbitrary-owner']['scale']=[-1,1,1]
        with self.assertRaises(DirectorError):bridge(a,b,ap,bn,.1,6,1)
