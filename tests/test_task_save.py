"""Portable identity filters only; actual save handlers need the native fixture."""
import unittest
from types import SimpleNamespace as NS
from asset_director.task_feedback import register_checkpoint_menus


class SaveMenuTests(unittest.TestCase):
    def test_new_mode_has_save_return_and_keeps_standard_blender_save_untouched(self):
        menus, header, calls = [], [], []
        register_checkpoint_menus(NS(TOPBAR_MT_file=menus, TOPBAR_MT_editor_menus=header), True)
        layout = NS(operator=lambda *args, **kwargs: calls.append((args, kwargs)))
        menus[0](NS(layout=layout), None)
        header[0](NS(layout=layout), None)
        self.assertEqual(calls[0][1]['text'], 'Save and return to Director')
        self.assertEqual(calls[1][1]['text'], 'Save & return to Director')
        self.assertTrue(all(call[0] == ('asset_director.save_checkpoint',) for call in calls))
