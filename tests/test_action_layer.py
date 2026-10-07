import copy
import tempfile
import unittest
from uuid import uuid4
from pathlib import Path
from asset_director import action_layer_contract as contract, jobs
from asset_director.core import Library, DirectorError, atomic_json, load_json


class ActionContractTests(unittest.TestCase):
    def test_generated_attempts_have_distinct_native_jobs_and_keep_failed_evidence(self):
        first={'id':'clip_a','take_id':'take_'+'b'*64,'start':1,'frames':25,'speed':1,'repeat_reviewed':False,'travel':None}
        second=first|{'id':'clip_b','start':38,'transition':{'mode':'generated','frames':12,'match_phase':False,'seed':1234,'profile_sha256':'c'*64}}
        options={'version':contract.VERSION,'audit_sha256':'a'*64,'changes':[{'performer':'Rig','mode':'timeline','clips':[first,second]}],
                 'generation_attempt':'run_'+str(uuid4())}
        with tempfile.TemporaryDirectory() as tmp, Library(Path(tmp)/'library') as lib:
            source=Path(tmp)/'input.blend';source.write_bytes(b'identity-only portable fixture; no Blender execution')
            original=jobs.prepare(lib,'action-edit',input_file=str(source),options=options)
            folder=lib.root/'jobs'/original['id'];original['state']='FAILED';atomic_json(folder/'job.json',original)
            (folder/'worker.log').write_text('retained failed attempt')
            duplicate=jobs.prepare(lib,'action-edit',input_file=str(source),options=options)
            self.assertEqual(duplicate['state'],'FAILED','Same attempt must remain idempotent')
            new=jobs.prepare(lib,'action-edit',input_file=str(source),options=options|{'generation_attempt':'run_'+str(uuid4())})
            self.assertNotEqual(new['id'],original['id']);self.assertEqual(new['state'],'PLANNED')
            self.assertEqual(load_json(folder/'job.json'),original)
            self.assertEqual((folder/'worker.log').read_text(),'retained failed attempt')
        for attempt in ['',True,'run_guess','../escape']:
            with self.assertRaises(DirectorError):contract.validate(options|{'generation_attempt':attempt})
        with self.assertRaises(DirectorError):contract.validate(self.options()|{'generation_attempt':'run_'+str(uuid4())})

    def options(self):
        return {'version': contract.VERSION, 'audit_sha256': 'a' * 64,
                'changes': [{'performer': 'Observed performer', 'mode': 'clip', 'take_id': 'take_' + 'b' * 64, 'start': 1, 'speed': 1}]}

    def test_native_clip_and_explicit_hold(self):
        contract.validate(self.options())
        value = self.options();value['changes'] = [{'performer': 'Static prop', 'mode': 'hold', 'frame': 12}]
        value['frame_range'] = [1, 48]
        self.assertEqual(contract.validate(value), value)

    def test_unknown_fields_guessed_bindings_and_bad_timing_refuse(self):
        for patch in [{'script': 'no'}, {'take_id': 'Idle'}, {'mode': 'retarget'}, {'speed': 0}, {'speed': float('nan')},
                      {'speed': True}, {'start': 1.5}, {'start': 100001}, {'performer': ''}, {'slot': 'guessed'}]:
            value = self.options();value['changes'][0].update(patch)
            with self.subTest(patch=patch), self.assertRaises(DirectorError):contract.validate(value)
        for interval in [[2, 1], [1, 3602], [True, 2], [0, 1, 2]]:
            with self.subTest(interval=interval), self.assertRaises(DirectorError):contract.validate(self.options() | {'frame_range': interval})

    def test_distinct_bounded_batch_and_exact_audit_required(self):
        variants = [self.options() | {'version': 'new'}, self.options() | {'audit_sha256': 'no'}, self.options() | {'changes': []}]
        duplicate = self.options();duplicate['changes'] *= 2;variants.append(duplicate)
        large = self.options();large['changes'] = [dict(copy.deepcopy(large['changes'][0]), performer=str(i)) for i in range(33)];variants.append(large)
        for value in variants:
            with self.assertRaises(DirectorError):contract.validate(value)

    def test_requires_saved_scene_and_rejects_before_job_write(self):
        with tempfile.TemporaryDirectory() as tmp, Library(Path(tmp) / 'library') as lib:
            for op, options in [('action-edit', self.options()), ('action-audit', {})]:
                for filename, asset in [(None, None), ('scene.glb', None), ('scene.blend', 'a_' + '1' * 24)]:
                    with self.assertRaises(DirectorError) as error:jobs.prepare(lib, op, input_file=filename, asset_id=asset, options=options)
                    self.assertEqual(error.exception.code, 'TARGET_REQUIRED')
            self.assertFalse(list((lib.root / 'jobs').iterdir()))
        self.assertIn('action-edit', jobs.MUTATIONS);self.assertNotIn('action-audit', jobs.MUTATIONS)


if __name__ == '__main__':unittest.main()
