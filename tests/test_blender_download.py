"""Synthetic transport/failure tests, not evidence of an actual Blender install."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
import contextlib
import hashlib
import http.client
import io
import ssl
import subprocess
import sys
import unittest
import urllib.error
import urllib.request

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import blender_download as transport
import fetch_blender as fetch


class Response(io.BytesIO):
    def __init__(self, value, length=None):
        super().__init__(value)
        self.headers = {} if length is None else {"Content-Length": str(length)}


class DownloadTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.name = "blender-5.2.1-windows-x64.zip"
        self.bytes = b"SYNTHETIC ARCHIVE, NOT BLENDER"
        self.hash = hashlib.sha256(self.bytes).hexdigest()
        self.manifest = (self.hash + " *" + self.name + "\n").encode()

    def fake_download(self, url, destination, **kwargs):
        destination.write_bytes(self.manifest if url.endswith(".sha256") else self.bytes)
        return True

    def test_retry_fallback_keeps_partial_attempt_and_same_checksum(self):
        calls = []
        def download(url, destination, **kwargs):
            calls.append((url, kwargs))
            if len(calls) == 2:
                destination.write_bytes(b"partial")
                return False
            return self.fake_download(url, destination, **kwargs)
        with mock.patch.object(fetch, "download", side_effect=download):
            result = fetch.acquire("5.2.1", self.name, self.root)
        self.assertEqual(result.read_bytes(), self.bytes)
        self.assertEqual((self.root / (self.name + ".attempt-0")).read_bytes(), b"partial")
        self.assertTrue(calls[2][0].startswith(fetch.BASES[1]))
        self.assertEqual(calls[1][1], {"seconds": 150, "maximum": 2 * 1024**3})

    def test_manifest_fallback(self):
        def download(url, destination, **kwargs):
            if url.startswith(fetch.BASES[0]) and url.endswith(".sha256"):
                return False
            return self.fake_download(url, destination, **kwargs)
        with mock.patch.object(fetch, "download", side_effect=download):
            self.assertEqual(fetch.acquire("5.2.1", self.name, self.root).read_bytes(), self.bytes)

    def test_retry_limit_and_no_fabricated_success(self):
        calls = []
        def download(url, destination, **kwargs):
            calls.append(url)
            if url.endswith(".sha256"):
                return self.fake_download(url, destination, **kwargs)
            destination.write_bytes(b"partial")
            return False
        with mock.patch.object(fetch, "download", side_effect=download), mock.patch.object(fetch.time, "sleep") as sleep:
            with self.assertRaisesRegex(SystemExit, "four bounded attempts"):
                fetch.acquire("5.2.1", self.name, self.root)
        self.assertEqual(len(calls), 5)
        self.assertEqual(len(list(self.root.glob("*.attempt-*"))), 4)
        self.assertEqual(sleep.call_count, 2)

    def test_checksum_mismatch_is_terminal_and_retained(self):
        def download(url, destination, **kwargs):
            destination.write_bytes(self.manifest if url.endswith(".sha256") else b"corrupted")
            return True
        with mock.patch.object(fetch, "download", side_effect=download) as run:
            with self.assertRaisesRegex(SystemExit, "checksum mismatch"):
                fetch.acquire("5.2.1", self.name, self.root)
        self.assertEqual(run.call_count, 2)
        self.assertEqual((self.root / (self.name + ".attempt-0")).read_bytes(), b"corrupted")

    def test_invalid_manifest_is_not_retried_into_success(self):
        for value in [b"", self.manifest * 2, b"not-a-hash " + self.name.encode()]:
            with self.subTest(value=value), self.assertRaises(SystemExit):
                fetch.checksum(value, self.name)

    def test_missing_manifest_has_only_two_attempts(self):
        with mock.patch.object(fetch, "download", return_value=False) as run:
            with self.assertRaisesRegex(SystemExit, "checksum download failed"):
                fetch.acquire("5.2.1", self.name, self.root)
        self.assertEqual(run.call_count, 2)

    def test_existing_destination_and_download_not_overwritten(self):
        old = self.root / "owned"
        old.write_bytes(b"unchanged")
        with self.assertRaisesRegex(SystemExit, "new empty"):
            fetch.main("5.2.1", self.root)
        with self.assertRaisesRegex(RuntimeError, "overwrite"):
            transport.download("https://example.invalid/file", old, seconds=1, maximum=10)
        self.assertEqual(old.read_bytes(), b"unchanged")

    def test_hard_deadline_does_not_retry_other_worker_failures(self):
        destination = self.root / "part"
        with mock.patch.object(transport.subprocess, "run", side_effect=subprocess.TimeoutExpired("owned", 1)) as run:
            self.assertFalse(transport.download("https://example.invalid/a", destination, seconds=1, maximum=10))
            self.assertEqual(run.call_args.kwargs["timeout"], 1)
        with mock.patch.object(transport.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaises(RuntimeError):
                transport.download("https://example.invalid/a", destination, seconds=1, maximum=10)

    def test_transient_classification_preserves_tls_failure(self):
        for error, expected in [
            (TimeoutError(), 75),
            (ConnectionResetError(), 75),
            (http.client.IncompleteRead(b"", 10), 75),
            (urllib.error.URLError("temporary DNS problem"), 75),
            (urllib.error.URLError(ssl.SSLCertVerificationError("untrusted")), 1),
            (urllib.error.HTTPError("https://example.invalid", 503, "busy", {}, None), 75),
            (urllib.error.HTTPError("https://example.invalid", 404, "missing", {}, None), 1),
        ]:
            with self.subTest(error=error), mock.patch.object(transport, "stream", side_effect=error):
                self.assertEqual(transport.worker("https://example.invalid", self.root / "part", 10), expected)

    def test_response_size_and_incomplete_read_bounds(self):
        for data, length, maximum, error in [
            (b"too large", 9, 3, RuntimeError),
            (b"too large", None, 3, RuntimeError),
            (b"short", 8, 10, http.client.IncompleteRead),
        ]:
            destination = self.root / ("part-" + str(length))
            opener = mock.Mock()
            opener.open.return_value = Response(data, length)
            with mock.patch.object(transport.urllib.request, "build_opener", return_value=opener):
                with self.assertRaises(error):
                    transport.stream("https://example.invalid", destination, maximum)

    def test_successful_stream_and_secure_redirect(self):
        opener = mock.Mock()
        opener.open.return_value = Response(b"ok", 2)
        with mock.patch.object(transport.urllib.request, "build_opener", return_value=opener):
            transport.stream("https://example.invalid", self.root / "part", 10)
        self.assertEqual((self.root / "part").read_bytes(), b"ok")
        with self.assertRaisesRegex(RuntimeError, "HTTPS"):
            transport.stream("http://example.invalid", self.root / "bad", 10)
        request = urllib.request.Request("https://example.invalid")
        with self.assertRaisesRegex(RuntimeError, "non-HTTPS"):
            transport.SecureRedirect().redirect_request(request, None, 302, "Found", {}, "http://example.invalid")

    def test_setup_action_inherits_stderr_and_propagates_exit(self):
        # Execute the actual inline Python, not an alternate wrapper implementation.
        action = (TOOLS.parent / ".github/actions/setup-blender/action.yml").read_text()
        code = "\n".join(line[8:] for line in action.split("      run: |\n", 1)[1].splitlines())
        result = subprocess.CompletedProcess([], 19, stdout="diagnostic stdout\n")
        with mock.patch.dict("os.environ", {"RUNNER_TEMP": str(self.root), "BLENDER_VERSION": "5.2.1"}), mock.patch("subprocess.run", return_value=result) as run, contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as error:
                exec(compile(code, "setup-blender/action.yml", "exec"), {})
        self.assertEqual(error.exception.code, 19)
        self.assertIn("diagnostic stdout", output.getvalue())
        self.assertNotIn("stderr", run.call_args.kwargs)
        self.assertNotIn("capture_output", run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
