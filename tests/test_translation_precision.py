import unittest
from asset_director.core import DirectorError
from asset_director.translation_precision import precision, check_span, check_reference_residual, TOLERANCE_M


class PhysicalTranslationTests(unittest.TestCase):
    def test_identical_physical_variation_has_identical_decision_in_unlike_units(self):
        for meters in (1, .01, .001):
            for scale in (.1, 1, 10):
                p = precision(meters, scale)
                self.assertAlmostEqual(check_span([0, 2e-7/(meters*scale)], p), 2e-7)
                with self.assertRaises(DirectorError) as e:
                    check_span([0, .001/(meters*scale)], p)
                self.assertEqual(e.exception.code, 'NON_ANCHOR_TRANSLATION')

    def test_reported_centimetre_roundtrip_is_not_real_translation(self):
        self.assertLess(check_span([-5.7220458984375e-6, 9.298324584960938e-6], precision(.01)), TOLERANCE_M)

    def test_bound_is_fixed_and_source_arrays_unchanged(self):
        values = [1., 1.+1e-7]; before = list(values)
        p = precision(1)
        check_span(values, p)
        self.assertEqual(values, before)
        self.assertEqual(p['tolerance_m_per_component'], 1e-5)
        self.assertEqual(p['tolerance_local_units'], 1e-5)

    def test_invalid_units_and_nonfinite_values_refused(self):
        for v in (0, -1, True, None, '1', float('nan'), float('inf'), 1001):
            with self.subTest(value=v), self.assertRaises(DirectorError): precision(v)
        for v in (0, -1, True, None, float('nan'), float('inf')):
            with self.subTest(scale=v), self.assertRaises(DirectorError): precision(1, v)
        for samples in ([], [0,float('nan')], [0,float('inf')], [False,0], [0,'1']):
            with self.subTest(samples=samples), self.assertRaises(DirectorError): check_span(samples, precision(1))

    def test_known_units_validated_in_portable_pose_contract(self):
        from asset_director.pose_contract import validate
        cfg=dict(rotation=[1,0,0,0,1,0,0,0,1], translation_bone='hips',
                 translation_scale=1, target_origin=[0,0,0], source_meters_per_unit=.01)
        validate(cfg)
        with self.assertRaises(DirectorError): validate(cfg | {'source_meters_per_unit':True})

class ReferenceAlignmentPrecisionTests(unittest.TestCase):
    def test_recorded_zero_swing_roundtrip_is_submicrometre(self):
        residual = [4.76837158203125e-7, 1.9073486328125e-6, -1.52587890625e-5]
        before = list(residual)
        physical = check_reference_residual(residual, precision(1, .01))
        self.assertGreater(physical, 1e-7)
        self.assertLess(physical, 2e-7)
        self.assertEqual(residual, before)

    def test_equivalent_physical_errors_have_identical_decisions(self):
        for metres, scale in ((1, 1), (1, .01), (.01, 1), (.001, 10)):
            factor = metres*scale
            for error_m in (0, 2e-7, 5e-6):
                with self.subTest(metres=metres, scale=scale, error=error_m):
                    self.assertAlmostEqual(check_reference_residual(
                        [error_m/factor, 0, 0], precision(metres, scale)), error_m)
            with self.assertRaises(DirectorError) as caught:
                check_reference_residual([.001/factor, 0, 0], precision(metres, scale))
            self.assertEqual(caught.exception.code, 'ALIGNMENT_REVIEW_REQUIRED')

    def test_combined_vector_error_cannot_hide_in_individual_components(self):
        with self.assertRaises(DirectorError):
            check_reference_residual([8e-6, 8e-6, 0], precision(1))

    def test_nonfinite_or_malformed_reference_is_rejected(self):
        for values in ([], [0, 0], [0, 0, 0, 0], [True, 0, 0],
                       [float('nan'), 0, 0], [float('inf'), 0, 0]):
            with self.subTest(values=values), self.assertRaises(DirectorError):
                check_reference_residual(values, precision(1))
