"""Bounded CI transport. No credentials, insecure redirects or integrity fallback."""
from pathlib import Path
import http.client
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

USER_AGENT = "BlenderAssetDirector/0.1 (+https://github.com/raal1600/blender-asset-director)"
TRANSIENT_EXIT = 75


class SecureRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise RuntimeError("Refusing a non-HTTPS Blender mirror redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def stream(url, destination, maximum):
    if not url.startswith("https://"):
        raise RuntimeError("Blender download requires HTTPS")
    opener = urllib.request.build_opener(SecureRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener.open(request, timeout=30) as response:
        length = response.headers.get("Content-Length")
        length = int(length) if length is not None else None
        if length is not None and not 0 <= length <= maximum:
            raise RuntimeError("Blender response exceeds download size bound")
        total = 0
        with Path(destination).open("xb") as output:
            while True:
                chunk = response.read(min(1024 * 1024, maximum - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    raise RuntimeError("Blender response exceeds download size bound")
                output.write(chunk)
        if length is not None and total != length:
            raise http.client.IncompleteRead(b"", length - total)


def worker(url, destination, maximum):
    try:
        stream(url, destination, maximum)
    except urllib.error.HTTPError as exc:
        print("Blender HTTP download failed: " + str(exc.code), file=sys.stderr, flush=True)
        return TRANSIENT_EXIT if exc.code in {408, 429, 500, 502, 503, 504} else 1
    except urllib.error.URLError as exc:
        print("Blender transport failed: " + str(exc.reason), file=sys.stderr, flush=True)
        return 1 if isinstance(exc.reason, ssl.SSLCertVerificationError) else TRANSIENT_EXIT
    except (TimeoutError, ConnectionError, http.client.IncompleteRead) as exc:
        print("Blender transfer interrupted: " + type(exc).__name__, file=sys.stderr, flush=True)
        return TRANSIENT_EXIT
    return 0


def download(url, destination, *, seconds, maximum):
    """A separate process bounds slow trickle transfers, not just socket stalls."""
    if Path(destination).exists():
        raise RuntimeError("Refusing to overwrite a download attempt")
    print("Downloading " + url + " (deadline " + str(seconds) + "s)", file=sys.stderr, flush=True)
    try:
        result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()),
                                 url, str(destination), str(maximum)], timeout=seconds)
    except subprocess.TimeoutExpired:
        # subprocess.run has killed and waited for only this owned download child.
        print("Blender download deadline reached; partial attempt retained", file=sys.stderr, flush=True)
        return False
    if result.returncode == TRANSIENT_EXIT:
        return False
    if result.returncode:
        raise RuntimeError("Blender download refused; see transport error above")
    return True


if __name__ == "__main__":
    raise SystemExit(worker(sys.argv[1], sys.argv[2], int(sys.argv[3])))
