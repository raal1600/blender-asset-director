"""Synthetic window resolver tests; actual GUI task remains a mandatory CI gate."""
import unittest
import sys
from types import SimpleNamespace as NS
from unittest.mock import patch
from asset_director.core import DirectorError
from asset_director.task_window import task_window

class TaskWindowTests(unittest.TestCase):
    def test_post_load_missing_context_window_uses_only_dedicated_manager(self):
        window = NS(screen=NS(is_temporary=False))
        popup = NS(screen=NS(is_temporary=True))
        bpy = NS(app=NS(background=False), context=NS(window=None, window_manager=NS(windows=[window,popup])))
        with patch.dict(sys.modules, {'bpy':bpy}):
            self.assertIs(task_window(),window)
            bpy.context.window_manager.windows=[]
            with self.assertRaises(DirectorError): task_window()
            bpy.context.window_manager.windows=[window,NS(screen=NS(is_temporary=False))]
            with self.assertRaises(DirectorError): task_window()
            bpy.app.background=True
            self.assertIsNone(task_window())
