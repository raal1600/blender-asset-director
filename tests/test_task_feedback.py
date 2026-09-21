"""Portable observation semantics only; GUI proof belongs to native acceptance."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import patch
import json
import sys
import unittest
from asset_director.task_feedback import observation


class FeedbackTests(unittest.TestCase):
    def test_unrelated_file_details_are_not_exposed(self):
        with TemporaryDirectory() as d:
            root = Path(d); (root / 'Scenes').mkdir(); (root / 'Docs').mkdir()
            task = dict(id='t', projectId='p', sceneId='s', projectDirectory=d,
                        workingScene='Scenes/work.blend', returnFile='Docs/return.json')
            bpy = NS(app=NS(background=True), data=NS(filepath=str(root / 'Scenes/work.blend'), is_dirty=True),
                     context=NS(window=None, scene=NS(frame_current=4), view_layer=NS(objects=NS(active=NS(name='Selected')))))
            with patch.dict(sys.modules, {'bpy': bpy}):
                # Startup and timers have no area-specific context.object attribute.
                self.assertFalse(hasattr(bpy.context, 'object'))
                result = observation(task, False)
                self.assertEqual(result['state'], 'READY')
                self.assertTrue(result['dirty']); self.assertEqual(result['active_object'], 'Selected')
                bpy.data.filepath = str(root / 'unrelated.blend')
                result = observation(task, False)
                self.assertEqual(result['state'], 'CONTEXT_CHANGED')
                self.assertIsNone(result['dirty']); self.assertIsNone(result['active_object'])
                self.assertNotIn('unrelated.blend', json.dumps(result))
                (root / 'Docs/return.json').write_text('{}')
                self.assertEqual(observation(task, False)['state'], 'CHECKPOINT_SAVED')


class CheckpointMenuTests(unittest.TestCase):
    def test_canonical_command_is_in_file_menu_without_overriding_short_button(self):
        from asset_director.task_feedback import register_checkpoint_menus, CHECKPOINT_LABEL
        file_menu, topbar = [], []
        register_checkpoint_menus(NS(TOPBAR_MT_file=file_menu, TOPBAR_MT_editor_menus=topbar))
        self.assertEqual(len(file_menu), 1)
        self.assertEqual(len(topbar), 1)
        calls = []
        layout = NS(operator=lambda *args, **kw: calls.append((args, kw)))
        file_menu[0](NS(layout=layout), None)
        topbar[0](NS(layout=layout), None)
        self.assertEqual(calls, [
            (('asset_director.save_checkpoint',), {'text': CHECKPOINT_LABEL}),
            (('asset_director.save_checkpoint',), {'text': 'Save checkpoint & return'}),
        ])
        self.assertEqual(CHECKPOINT_LABEL, 'Save checkpoint and return to launcher')
