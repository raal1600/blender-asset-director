"""Portable task identity validation; native selection is tested separately."""
import unittest
from uuid import uuid4
from asset_director.action_task import validate_context
from asset_director.core import DirectorError


class ActionTaskTests(unittest.TestCase):
    def test_optional_legacy_context_and_exact_action_identity(self):
        validate_context({'stage': 'world'})
        context = dict(version='action-layer-v1', checkpointId='cp_' + str(uuid4()),
                       inspectionId='run_' + str(uuid4()), sha256='a' * 64,
                       audit_sha256='b' * 64, performer='Observed Rig', frame=5)
        task = dict(stage='action', rigControls=True, actionContext=context,
                    input={'sha256': context['sha256']}, targets=['Observed Rig'], frame=5)
        validate_context(task)
        for change in [dict(stage='world'), dict(rigControls='true'), dict(frame=7),
                       dict(targets=['Other']), dict(input={'sha256': 'c' * 64}),
                       dict(actionContext=None), dict(actionContext={**context, 'script': 'no'})]:
            with self.assertRaises(DirectorError):
                validate_context({**task, **change})
