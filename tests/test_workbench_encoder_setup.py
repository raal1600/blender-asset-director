"""CI encoder archive safety using synthetic bytes, never executable downloads."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/ci'))
import fetch_ffmpeg


class EncoderSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / 'synthetic.zip'
        self.destination = self.root / 'encoder'

    def archive_with(self, files):
        with zipfile.ZipFile(self.archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, content in files:
                z.writestr(name, content)
        return hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def test_checksum_required_before_destination_created(self):
        self.archive.write_bytes(b'not a reviewed vendor archive')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            fetch_ffmpeg.extract(self.archive, self.destination)
        self.assertFalse(self.destination.exists())

    def test_only_exact_named_executables_extract_and_budgets_are_distinct(self):
        sha = self.archive_with([(fetch_ffmpeg.PREFIX + n, b'SYNTHETIC' * 1000) for n in ('ffmpeg.exe','ffprobe.exe')] + [('outside.txt', b'never extract')])
        # Highly compressible fixture mimics the distinction, not executable behavior.
        with patch.object(fetch_ffmpeg, 'SHA256', sha), patch.object(fetch_ffmpeg, 'MAX_BYTES', 2000), patch.object(fetch_ffmpeg, 'MAX_EXTRACTED_BYTES', 20000):
            fetch_ffmpeg.extract(self.archive, self.destination)
        self.assertEqual(sorted(p.name for p in self.destination.iterdir()), ['ffmpeg.exe','ffprobe.exe'])
        self.assertFalse((self.root / 'outside.txt').exists())

    def test_expanded_payload_limit_is_still_enforced(self):
        sha = self.archive_with([(fetch_ffmpeg.PREFIX + n, b'x' * 100) for n in ('ffmpeg.exe','ffprobe.exe')])
        with patch.object(fetch_ffmpeg, 'SHA256', sha), patch.object(fetch_ffmpeg, 'MAX_EXTRACTED_BYTES', 100):
            with self.assertRaisesRegex(ValueError, 'extraction bound'):
                fetch_ffmpeg.extract(self.archive, self.destination)
        self.assertFalse(self.destination.exists())

    def test_missing_or_empty_executable_refused(self):
        for files in [[(fetch_ffmpeg.PREFIX + 'ffmpeg.exe', b'x')], [(fetch_ffmpeg.PREFIX + 'ffmpeg.exe', b'x'), (fetch_ffmpeg.PREFIX + 'ffprobe.exe', b'')]]:
            sha = self.archive_with(files)
            with patch.object(fetch_ffmpeg, 'SHA256', sha), self.assertRaises(ValueError):
                fetch_ffmpeg.extract(self.archive, self.destination)
            self.assertFalse(self.destination.exists())

    def test_existing_destination_and_oversized_archive_are_preserved(self):
        self.destination.mkdir()
        sentinel = self.destination / 'sentinel'; sentinel.write_text('keep')
        with self.assertRaisesRegex(ValueError, 'new'):
            fetch_ffmpeg.extract(self.archive, self.destination)
        self.assertEqual(sentinel.read_text(), 'keep')
        self.archive.write_bytes(b'too large')
        with patch.object(fetch_ffmpeg, 'MAX_BYTES', 1), self.assertRaisesRegex(ValueError, 'download bound'):
            fetch_ffmpeg.extract(self.archive, self.root / 'other')
        self.assertFalse((self.root / 'other').exists())
