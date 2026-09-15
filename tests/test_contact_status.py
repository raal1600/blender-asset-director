import unittest
from asset_director.contact_diagnostics import summarize
from asset_director.contact_status import sequence_status
from asset_director.core import DirectorError


class ContactStatusTests(unittest.TestCase):
    def measured(self, clearance):
        sample = {'frame': 1.5, 'time': .05,
                  'left': {'minimum_z': clearance, 'centroid': [0, 0, clearance]},
                  'right': {'minimum_z': .01, 'centroid': [1, 0, .01]}}
        return summarize([sample], {'meters_per_unit': 1, 'ground_z': 0,
                'tolerance_m': .001, 'near_ground_m': .02, 'glide_speed_m_s': .01})

    def test_actual_penetration_label_survives_aggregation(self):
        measured = self.measured(-.01)
        self.assertEqual(measured['status'], 'SAMPLED_PENETRATION')
        self.assertEqual(sequence_status([measured], True), 'SAMPLED_PENETRATION')
        self.assertEqual(sequence_status([self.measured(.01), measured], True), 'SAMPLED_PENETRATION')

    def test_clear_measurements_still_require_interpretation(self):
        self.assertEqual(sequence_status([self.measured(.01)], True), 'REVIEW_MEASURED_EXTREMA')
        self.assertEqual(sequence_status([], False), 'NOT_MEASURED')

    def test_absent_unknown_or_obsolete_measurement_is_refused(self):
        for batches in ([], None, [{}], [{'status': 'PENETRATION_DETECTED'}], [{'status': 'PASS'}]):
            with self.subTest(batches=batches), self.assertRaises(DirectorError):
                sequence_status(batches, True)
        with self.assertRaises(DirectorError):
            sequence_status([self.measured(.01)], False)
