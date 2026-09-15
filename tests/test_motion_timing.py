import copy
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from asset_director.core import DirectorError, Library
from asset_director import jobs, motion_timing as t
from asset_director.pose_contract import validate as pose


class MotionTimingTests(unittest.TestCase):
    def test_integral_bake(self):
        points=t.bake_samples(1,25,24,30)
        self.assertEqual(len(points),31); self.assertEqual(points[0],(1,1));self.assertEqual(points[-1],(31,25))
    def test_fractional_bake_preserves_seconds_and_endpoint(self):
        points=t.bake_samples(1,24,24,30)
        self.assertEqual(len(points),30);self.assertEqual(points[-1],(29.75,24))
        self.assertAlmostEqual((points[-1][0]-points[0][0])/30,23/24)
    def test_roundoff_does_not_drop_first_sample(self):
        points=t.bake_samples(0,.999999999999,1,1)
        self.assertEqual(len(points),2);self.assertEqual(points[0],(1,0))
    def test_bake_bounds(self):
        for args in ((0,400,1,1),(0,0,24,24),(0,1,True,24),(0,float('nan'),24,24)):
            with self.subTest(args=args),self.assertRaises(DirectorError):t.bake_samples(*args)
    def test_speed_separate_from_fps(self):
        self.assertAlmostEqual(t.strip_scale(24,30,.8),1.5625)
        self.assertAlmostEqual(24*t.strip_scale(24,30,.8)/30,1.25)
    def test_speed_invalid(self):
        for speed in (0,True,float('inf'),5):
            with self.subTest(speed=speed),self.assertRaises(DirectorError):t.strip_scale(24,30,speed)
    def test_fractional_endpoint_not_rounded_outside_strip(self):
        self.assertEqual(t.retained_range([{'start':1,'end':187.25}]),(1,187))
    def test_nonfirst_start_not_padded_with_rest(self):
        self.assertEqual(t.retained_range([{'start':7,'end':20}]),(7,20))
    def test_integer_gap_refused(self):
        with self.assertRaises(DirectorError) as c:t.retained_range([{'start':1,'end':3.5},{'start':5,'end':9}])
        self.assertEqual(c.exception.code,'SEQUENCE_GAP_REVIEW')
    def test_subframe_gap_has_no_integer_rest_frame(self):
        self.assertEqual(t.retained_range([{'start':1,'end':3.5},{'start':4,'end':9}]),(1,9))
    def test_invalid_span_or_budget(self):
        for strips in ([],[{'start':1,'end':1.5}],[{'start':1,'end':362}]):
            with self.subTest(strips=strips),self.assertRaises(DirectorError):t.retained_range(strips)
    def test_hips_travel_under_stationary_root(self):
        data=[{'root':[0,0,0],'hips':[x,0,0]} for x in (0,2,0)]
        self.assertEqual(t.horizontal_span(data),2)
    def test_assembly_contract(self):
        t.validate_assembly({'clips':[{'action':'any name','start':7,'playback_speed':.8}],'fps':29.97})
    def test_fractional_start_refused_not_truncated(self):
        with self.assertRaises(DirectorError):t.validate_assembly({'clips':[{'action':'A','start':1.5}]})
    def test_negative_blend_and_unknown_clip_keys(self):
        for extra in ({'blend_in':-1},{'script':'x'},{'playback_speed':True}):
            with self.subTest(extra=extra),self.assertRaises(DirectorError):
                t.validate_assembly({'clips':[{'action':'A','start':1,**extra}]})
    def test_prepare_rejection_writes_no_jobs(self):
        with tempfile.TemporaryDirectory() as d, Library(d) as lib:
            with self.assertRaises(DirectorError):jobs.prepare(lib,'assemble',options={'clips':[]})
            self.assertFalse(list((Path(d)/'jobs').iterdir()))
    def test_grounded_tilt_refused_yaw_allowed(self):
        base=dict(rotation=[0,-1,0,1,0,0,0,0,1],translation_bone='hips',translation_scale=1,target_origin=[0,0,1],
                  ground_contact=dict(mesh='skin',vertex_groups=['foot'],height=0,max_correction=.1))
        pose(base)
        a=.2;c=math.cos(a);s=math.sin(a)
        base['rotation']=[1,0,0,0,c,-s,0,s,c]
        with self.assertRaises(DirectorError) as e:pose(base)
        self.assertEqual(e.exception.code,'GROUND_ALIGNMENT_REVIEW')
    def test_bad_ground_groups_and_origin(self):
        base=dict(rotation=[1,0,0,0,1,0,0,0,1],translation_bone='hips',translation_scale=1,target_origin=[0,0,1])
        with self.assertRaises(DirectorError):pose({**base,'target_origin':[1e10,0,0]})
        for names in (['foot','foot'],[[]]):
            with self.subTest(names=names),self.assertRaises(DirectorError):
                pose({**base,'ground_contact':dict(mesh='skin',vertex_groups=names,height=0,max_correction=.1)})


class CanonicalSamplingTests(unittest.TestCase):
    def test_fbx_31_intervals_does_not_duplicate_endpoint(self):
        duration = 31 / 30
        self.assertGreater(duration * 30, 31)
        points = t.capture_times(duration, 30)
        self.assertEqual(len(points), 32)
        self.assertEqual(points[0], 0)
        self.assertEqual(points[-1], duration)
        self.assertEqual(points.count(duration), 1)
        self.assertTrue(all(a < b for a, b in zip(points, points[1:])))

    def test_integral_duration_preserves_sample_grid(self):
        for fps in (24, 30, 60):
            self.assertEqual(t.capture_times(1, fps), [i / fps for i in range(fps + 1)])

    def test_near_integral_endpoint_preserves_exact_duration(self):
        for duration in (math.nextafter(1.0, 0.0), math.nextafter(1.0, 2.0)):
            points = t.capture_times(duration, 30)
            self.assertEqual(len(points), 31)
            self.assertEqual(points[-1], duration)
            self.assertLess(points[-2], duration)

    def test_real_fractional_endpoint_is_not_snapped_or_dropped(self):
        points = t.capture_times(1.0123, 30)
        self.assertEqual(points[-2:], [1.0, 1.0123])
        self.assertEqual(len(points), 32)

    def test_shortest_capture_has_two_samples(self):
        self.assertEqual(t.capture_times(1e-7, 240), [0.0, 1e-7])

    def test_exact_sample_budget_and_one_extra(self):
        self.assertEqual(len(t.capture_times(31/30, 30, 32)), 32)
        with self.assertRaises(DirectorError): t.capture_times(32/30, 30, 32)
        with self.assertRaises(DirectorError): t.capture_times(600, 240)

    def test_bad_timebase_or_unbounded_allocation_refused(self):
        for duration, rate in ((0, 30), (-1, 30), (601, 30), (True, 30),
                               (1, 0), (1, True), (1, 241), (float('nan'), 30)):
            with self.subTest(duration=duration, rate=rate), self.assertRaises(DirectorError):
                t.capture_times(duration, rate)
        for bound in (1, True, 10001):
            with self.assertRaises(DirectorError): t.capture_times(1, 30, bound)
