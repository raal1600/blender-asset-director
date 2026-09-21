"""CI-only official Blender download, verified against its release checksum list.

Uses Blender's official mirror service. See https://mirror.blender.org/ .
A fallback to the original publisher is bounded; TLS/checksum checks stay enabled.
"""
from pathlib import Path
import hashlib
import re
import shutil
import sys
import tarfile
import zipfile
import urllib.error
import urllib.request

BASES = ("https://mirror.blender.org/release/", "https://download.blender.org/release/")
USER_AGENT = "BlenderAssetDirector/0.1 (+https://github.com/raal1600/blender-asset-director)"


class SecureRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise RuntimeError("Refusing a non-HTTPS Blender mirror redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def main(version, directory):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("Invalid fixed version")
    suffix = "Blender" + ".".join(version.split(".")[:2]) + "/"
    windows = sys.platform == 'win32'
    platform = 'windows-x64' if windows else 'linux-x64'
    filename = f"blender-{version}-{platform}." + ('zip' if windows else 'tar.xz')
    dest = Path(directory).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(SecureRedirect())
    def get(url, timeout):
        return opener.open(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout)
    errors = []
    manifest = None
    for root in BASES:
        base = root + suffix
        try:
            with get(base + f"blender-{version}.sha256", 60) as response:
                manifest = response.read(65537)
            if len(manifest) > 65536:
                raise RuntimeError("Unexpectedly large Blender checksum manifest")
            manifest = manifest.decode("utf-8")
            break
        except (urllib.error.URLError, OSError) as exc:
            errors.append(type(exc).__name__ + ": " + str(exc))
            print("Blender checksum source unavailable: " + root, file=sys.stderr)
    if manifest is None:
        raise SystemExit("Official checksum download failed: " + "; ".join(errors))
    lines = [line.split() for line in manifest.splitlines() if line.strip()]
    matches = [parts[0] for parts in lines if len(parts) == 2 and parts[1].lstrip("*") == filename]
    if len(matches) != 1 or not re.fullmatch(r"[0-9a-fA-F]{64}", matches[0]):
        raise SystemExit("Official checksum entry missing or ambiguous")
    expected = matches[0].lower()
    archive = dest / filename
    with get(base + filename, 120) as response, archive.open("wb") as out:
        shutil.copyfileobj(response, out, 1024 * 1024)
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        archive.unlink(missing_ok=True)
        raise SystemExit("Official Blender checksum mismatch")
    if windows:
        with zipfile.ZipFile(archive) as zipped:
            for member in zipped.infolist():
                target = (dest / member.filename).resolve()
                if not target.is_relative_to(dest) or '\\' in member.filename or ':' in member.filename:
                    raise SystemExit('Unsafe Blender archive member')
            zipped.extractall(dest)
    else:
        with tarfile.open(archive) as tar:
            tar.extractall(dest, filter="data")
    archive.unlink()
    executable = dest / f"blender-{version}-{platform}" / ('blender.exe' if windows else 'blender')
    if not executable.is_file():
        raise SystemExit("Verified archive did not contain the expected executable")
    print(executable)


if __name__ == "__main__":
    main(*sys.argv[1:])
