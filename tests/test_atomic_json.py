"""Atomic publication tolerates brief Windows readers without losing the old record."""
import ctypes
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from asset_director.core import atomic_json, load_json


class AtomicJsonPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "worker-ownership.json"
        self.original = {"job_id": "j_owned", "state": "STARTING"}
        self.updated = {"job_id": "j_owned", "state": "WATCHING_EXECUTOR"}
        atomic_json(self.path, self.original)

    def assert_original_and_no_temporary(self):
        self.assertEqual(load_json(self.path), self.original)
        self.assertEqual(list(self.root.glob(".write-*")), [])

    def test_windows_transient_reader_preserves_old_record_until_replacement(self):
        replace = os.replace
        for error_code in (5, 32, 33):
            with self.subTest(winerror=error_code):
                atomic_json(self.path, self.original)
                attempts = []
                def busy_then_replace(source, target):
                    self.assertEqual(load_json(self.path), self.original)
                    self.assertEqual(json.loads(Path(source).read_text(encoding="utf-8")), self.updated)
                    attempts.append(source)
                    if len(attempts) <= 3:
                        error = PermissionError("Windows reader temporarily denies replacement")
                        error.winerror = error_code
                        raise error
                    return replace(source, target)
                with patch("asset_director.core.os.replace", side_effect=busy_then_replace), patch("asset_director.core.time.sleep") as sleep:
                    atomic_json(self.path, self.updated)
                self.assertEqual(len(attempts), 4)
                self.assertEqual(sleep.call_count, 3)
                self.assertEqual(load_json(self.path), self.updated)
                self.assertEqual(list(self.root.glob(".write-*")), [])

    def test_persistent_windows_denial_remains_bounded_and_keeps_original(self):
        error = PermissionError("Still locked or not writable")
        error.winerror = 5
        with patch("asset_director.core.os.replace", side_effect=error) as replace, patch("asset_director.core.time.sleep") as sleep:
            with self.assertRaises(PermissionError) as caught:
                atomic_json(self.path, self.updated)
        self.assertIs(caught.exception, error)
        self.assertEqual(replace.call_count, 21)
        self.assertEqual(sleep.call_count, 20)
        self.assertLessEqual(sum(call.args[0] for call in sleep.call_args_list), .500001)
        self.assert_original_and_no_temporary()

    def test_other_io_failure_is_not_retried(self):
        for error in (PermissionError("Permanent non-Windows denial"), OSError("Disk failed")):
            with self.subTest(error=type(error).__name__):
                with patch("asset_director.core.os.replace", side_effect=error) as replace, patch("asset_director.core.time.sleep") as sleep:
                    with self.assertRaises(type(error)) as caught:
                        atomic_json(self.path, self.updated)
                self.assertIs(caught.exception, error)
                self.assertEqual(replace.call_count, 1)
                sleep.assert_not_called()
                self.assert_original_and_no_temporary()

    @unittest.skipUnless(os.name == "nt", "Windows sharing semantics require a real Windows handle")
    def test_real_windows_reader_closes_during_atomic_publication(self):
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        # Share reads/writes but deliberately deny FILE_SHARE_DELETE, as a Windows reader can.
        handle = kernel.CreateFileW(str(self.path), 0x80000000, 3, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        closed = threading.Event()
        def release_reader():
            try:
                time.sleep(.10)
            finally:
                kernel.CloseHandle(handle)
                closed.set()
        thread = threading.Thread(target=release_reader)
        thread.start()
        try:
            atomic_json(self.path, self.updated)
        finally:
            thread.join(timeout=2)
        self.assertTrue(closed.is_set(), "Owned read handle must be released")
        self.assertEqual(load_json(self.path), self.updated)
        self.assertEqual(list(self.root.glob(".write-*")), [])


if __name__ == "__main__":
    unittest.main()
