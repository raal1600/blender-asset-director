import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from fixture_contact_timebase import rescale_contacts


class ContactTimebaseTests(unittest.TestCase):
    def test_authored_and_prepared_contacts_follow_physical_time(self):
        prepared = {'contacts':[{'start':-2,'end':3,'side':'left','mesh':'skin','vertex':17}],
                    'placement_delta_m':[0,1],'source_sha256':'original','provenance':'reviewed'}
        authored = {'version':'native-contact-intervals-v1','rig_sha256':'rig',
                    'intervals':[{'chain':'leg','start':4,'end':12}]}
        source = {'bad_root_contact_preparation_v1':json.dumps(prepared),
                  'bad_contact_intervals_v1':json.dumps(authored)}
        before = dict(source)
        for fps in (24,30,60):
            converted = rescale_contacts(source,30,fps)
            for key,field in [('bad_root_contact_preparation_v1','contacts'),
                              ('bad_contact_intervals_v1','intervals')]:
                original=json.loads(source[key]);result=json.loads(converted[key])
                for old,new in zip(original[field],result[field]):
                    for time in ('start','end'):
                        self.assertAlmostEqual(old[time]/30,new[time]/fps)
                        new[time]=old[time]
                self.assertEqual(original,result)
        self.assertEqual(before,source)

    def test_unknown_or_invalid_annotations_refused(self):
        for metadata in ({'version':'future','intervals':[{'start':0,'end':3}]},
                         {'version':'native-contact-intervals-v1','intervals':[]},
                         {'version':'native-contact-intervals-v1','intervals':[{'start':3,'end':3}]}):
            with self.assertRaises(ValueError):
                rescale_contacts({'bad_contact_intervals_v1':json.dumps(metadata)},30,60)
        for fps in (0,-1,float('nan'),True):
            with self.assertRaises(ValueError):rescale_contacts({},fps,30)

    def test_unannotated_action_stays_unannotated(self):
        self.assertEqual(rescale_contacts({},24,60),{})


if __name__ == '__main__':unittest.main()
