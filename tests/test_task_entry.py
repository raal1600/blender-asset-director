"""Bounded startup logging does not substitute for GUI acceptance."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from asset_director.task_entry import BoundedLog

class StartupLogTests(unittest.TestCase):
    def test_no_overwrite_and_bounded_output(self):
        with TemporaryDirectory() as d:
            path=Path(d)/'task.log'
            with BoundedLog(path,10) as log:
                self.assertEqual(log.write('a'*50),50)
                log.write('another message')
            self.assertEqual(path.read_text(),'a'*10)
            with self.assertRaises(FileExistsError):BoundedLog(path)
