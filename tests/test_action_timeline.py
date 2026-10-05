import copy
import unittest
from asset_director.action_timeline_contract import validate, timing
from asset_director.action_layer_contract import validate as validate_batch
from asset_director.core import DirectorError


def clip(**kwargs):
    return dict(id='clip_one', take_id='take_'+'a'*64, start=1, frames=49, speed=1,
                repeat_reviewed=True, travel={'delta_m': [0, -5], 'meters_per_cycle': 2.5}, **kwargs)


class TimelineTests(unittest.TestCase):
    def test_distance_timing_and_inclusive_occupancy(self):
        c = clip()
        result = timing(c, {'range': [1, 25]})
        self.assertEqual(result, {'cycles': 2, 'end': 49, 'native_end': 49})
        validate({'performer': 'Rig', 'mode': 'timeline', 'clips': [c, c | {'id': 'clip_next', 'start': 50}]})
        validate_batch({'version': 'action-layer-v1', 'audit_sha256': 'b'*64,
                        'changes': [{'performer': 'Rig', 'mode': 'timeline', 'clips': [c]}]})

    def test_invalid_bounds_overlap_and_unknown_fields(self):
        for patch in [{'frames': 1}, {'speed': float('nan')}, {'start': True}, {'frames': 3602},
                      {'travel': {'delta_m': [0, 0], 'meters_per_cycle': 1}}, {'script': 'x'},
                      {'travel': {'delta_m': [1, 2, 3], 'meters_per_cycle': 1}}, {'repeat_reviewed': 1}]:
            with self.subTest(patch=patch), self.assertRaises(DirectorError):
                validate({'performer': 'Rig', 'mode': 'timeline', 'clips': [clip() | patch]})
        for start in [1, 49]:
            with self.assertRaises(DirectorError):
                validate({'performer': 'Rig', 'mode': 'timeline', 'clips': [clip(), clip() | {'id': 'clip_two', 'start': start}]})

    def test_no_implicit_loop_or_distance_disagreement(self):
        for patch in [{'repeat_reviewed': False}, {'frames': 50}]:
            with self.assertRaises(DirectorError):timing(clip() | patch, {'range': [1, 25]})
        # Fractional source endpoint is held to the next integer, not repeated.
        self.assertEqual(timing(clip() | {'travel': None, 'frames': 30, 'repeat_reviewed': False}, {'range': [0, 28.8]})['cycles'], 1)

    def test_empty_track_and_mixed_contract_refusal(self):
        validate({'performer': 'Rig', 'mode': 'timeline', 'clips': []})
        with self.assertRaises(DirectorError):
            validate_batch({'version': 'action-layer-v1', 'audit_sha256': 'b'*64, 'changes': [
                {'performer': 'Rig', 'mode': 'timeline', 'clips': []},
                {'performer': 'Other', 'mode': 'hold', 'frame': 1}]})

class GeneratedTimelineTests(unittest.TestCase):
    def test_generated_mode_requires_mapping_seed_and_intact_boundary(self):
        from asset_director.action_timeline_contract import connection
        a=clip()|{'travel':None,'frames':25,'repeat_reviewed':False}
        join={'mode':'generated','frames':25,'match_phase':False,'seed':1234,'profile_sha256':'c'*64}
        b=a|{'id':'clip_two','start':51,'transition':join}
        change={'performer':'Rig','mode':'timeline','clips':[a,b]}
        self.assertIs(validate(change),change)
        geometry=connection(a,b,{'range':[1,25]},{'range':[1,25]})
        self.assertTrue(geometry['placement_pending'])
        for patch in [{'seed':True},{'seed':-1},{'seed':2**32},{'match_phase':True},{'profile_sha256':'changed'}]:
            with self.subTest(patch=patch),self.assertRaises(DirectorError):
                validate(change|{'clips':[a,b|{'transition':join|patch}]})
