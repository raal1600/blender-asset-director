import unittest
from asset_director import frame_precision as fp
from asset_director.core import DirectorError


class FrameStorageTests(unittest.TestCase):
    def test_long_fractional_endpoint_has_exact_storage_identity(self):
        observed=[1.,890.5999755859375]
        evidence=fp.action_range(observed,[1.,890.6])
        self.assertEqual(evidence['stored'],observed)
        self.assertEqual(evidence['intended'],[1.,890.6])
        self.assertGreater(abs(evidence['error_frames'][1]),1e-5)

    def test_changed_key_is_not_tolerated_even_one_storage_step(self):
        end=fp.stored(890.6)
        for delta in (fp.ulp(end),1,-1):
            with self.subTest(delta=delta),self.assertRaises(DirectorError):
                fp.action_range([1,end+delta],[1,890.6])

    def test_rounding_budget_depends_on_actual_field_precision(self):
        self.assertLess(fp.ulp(1),fp.ulp(1113))
        self.assertLess(fp.strip_error_bound(44.39,[1,890.6],1.25),.001)
        self.assertGreater(fp.strip_error_bound(44.39,[1,890.6],1.25),fp.ulp(1113))

    def test_invalid_frame_domain_is_refused(self):
        for value in (True,None,'1',float('nan'),float('inf'),100001):
            with self.subTest(value=value),self.assertRaises(DirectorError):fp.stored(value)
