"""CI-only official Blender download, verified against its release checksum list.

Uses Blender's official mirror service. See https://mirror.blender.org/ .
A fallback to the original publisher is bounded; TLS/checksum checks stay enabled.
"""
from pathlib import Path
import hashlib
import re
import sys
import tarfile
import zipfile
import time
from blender_download import download

BASES = ("https://mirror.blender.org/release/", "https://download.blender.org/release/")
ARCHIVE_LIMIT = 2 * 1024**3


def checksum(manifest, filename):
    lines = [line.split() for line in manifest.decode("utf-8").splitlines() if line.strip()]
    matches = [parts[0] for parts in lines if len(parts) == 2 and parts[1].lstrip("*") == filename]
    if len(matches) != 1 or not re.fullmatch(r"[0-9a-fA-F]{64}", matches[0]):
        raise SystemExit("Official checksum entry missing or ambiguous")
    return matches[0].lower()


def acquire(version, filename, dest):
    suffix = "Blender" + ".".join(version.split(".")[:2]) + "/"
    expected = None
    for index, root in enumerate(BASES):
        manifest = dest / ("checksum-attempt-" + str(index) + ".txt")
        if download(root + suffix + f"blender-{version}.sha256", manifest, seconds=40, maximum=65536):
            expected = checksum(manifest.read_bytes(), filename)
            break
    if expected is None:
        raise SystemExit("Official checksum download failed after both bounded sources")
    # Keep one trusted checksum across archive mirrors and every retry.
    for attempt in range(4):
        if attempt >= len(BASES):
            time.sleep(2)
        root = BASES[attempt % len(BASES)]
        archive = dest / (filename + ".attempt-" + str(attempt))
        if not download(root + suffix + filename, archive, seconds=150, maximum=ARCHIVE_LIMIT):
            print("Retrying official source after transport failure; attempt retained", file=sys.stderr, flush=True)
            continue
        with archive.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            # Never retry corrupt bytes into a passing integrity claim.
            raise SystemExit("Official Blender checksum mismatch; failed archive retained")
        print("Verified Blender archive SHA256: " + actual, file=sys.stderr, flush=True)
        return archive
    raise SystemExit("Official archive download failed after four bounded attempts")


def main(version, directory):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("Invalid fixed version")
    windows = sys.platform == 'win32'
    platform = 'windows-x64' if windows else 'linux-x64'
    filename = f"blender-{version}-{platform}." + ('zip' if windows else 'tar.xz')
    dest = Path(directory).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    if any(dest.iterdir()):
        raise SystemExit("Use a new empty Blender download directory; previous attempts are preserved")
    archive = acquire(version, filename, dest)
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
