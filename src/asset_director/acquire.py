"""Bounded HTTPS acquisition and cross-platform archive validation.

No cookies, browser sessions, proxies, or credentials are inherited by downloads.
Separate processes / disable-autoexec are defense in depth, not an OS sandbox.
"""
from __future__ import annotations
import base64
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import ssl
import stat
import struct
import tempfile
import time
from urllib.parse import unquote, urljoin, urlsplit
import zipfile
from .core import DirectorError, Library, atomic_json, file_hash, load_json, require, within

USER_AGENT = "BlenderAssetDirector/0.1 (+https://github.com/raal1600/blender-asset-director)"
MAX_DOWNLOAD = 500 * 1024**2
MAX_EXTRACT = 2 * 1024**3
ASSET_SUFFIXES = {".glb", ".gltf", ".bin", ".fbx", ".blend", ".obj", ".bvh", ".mtl", ".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".hdr", ".exr", ".txt", ".md", ".json", ".license", ".pdf"}
RESERVED = {"CON", "PRN", "AUX", "NUL", "CLOCK$", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_member(name: str) -> str:
    require(isinstance(name, str) and name and len(name) <= 1024, "UNSAFE_ARCHIVE", "Invalid archive path")
    # ZIP can carry backslashes even when extracted on Linux. Apply Windows rules everywhere.
    name = name.replace("\\", "/")
    require(not name.startswith("/") and ":" not in name and not any(ord(x) < 32 for x in name), "UNSAFE_ARCHIVE", "Absolute/drive/control path")
    parts = name.rstrip("/").split("/")
    require(0 < len(parts) <= 16, "UNSAFE_ARCHIVE", "Excessive archive nesting")
    for p in parts:
        require(p not in {"", ".", ".."} and not p.endswith((" ", ".")) and not any(c in '<>"|?*' for c in p), "UNSAFE_ARCHIVE", "Unsafe path component")
        require(p.split(".")[0].upper() not in RESERVED, "UNSAFE_ARCHIVE", "Windows device path")
    return "/".join(parts)


def check_url(url: str, hosts: set[str]) -> tuple[str, str]:
    try:
        u = urlsplit(url)
        port = u.port
    except ValueError as exc:
        raise DirectorError("UNSAFE_URL", "Invalid URL") from exc
    require(u.scheme == "https" and u.hostname in hosts and port in (None, 443) and not u.username and not u.password and not u.fragment,
            "UNSAFE_URL", "External URL must be HTTPS on an approved origin")
    require(not any(c in url for c in ("\r", "\n", "\x00", "\\")), "UNSAFE_URL", "Invalid URL characters")
    return u.hostname, (u.path or "/") + (("?" + u.query) if u.query else "")


def public_addresses(host: str) -> list[str]:
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
    except OSError as exc:
        raise DirectorError("NETWORK_UNAVAILABLE", "DNS lookup failed") from exc
    require(addresses and all(ipaddress.ip_address(x).is_global for x in addresses), "UNSAFE_URL", "Non-public network destination blocked")
    return addresses


class HTTP:
    """Small GET-only client. Validates and pins public DNS addresses per connection."""
    def __init__(self, timeout: float = 20): self.timeout = timeout
    def stream(self, url: str, hosts: set[str], *, auth: tuple[str, str] | None = None, max_bytes: int = MAX_DOWNLOAD):
        initial_host, _ = check_url(url, hosts)
        deadline = time.monotonic() + 180
        retries = 0
        redirects = 0
        while True:
            host, path = check_url(url, hosts)
            addresses = public_addresses(host)
            conn = http.client.HTTPSConnection(host, 443, timeout=self.timeout, context=ssl.create_default_context())
            response = None
            try:
                # Pin the validated address while retaining TLS certificate/SNI verification for host.
                raw = socket.create_connection((addresses[0], 443), self.timeout)
                try: conn.sock = conn._context.wrap_socket(raw, server_hostname=host)
                except BaseException:
                    raw.close(); raise
                headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
                if auth and host == initial_host == auth[0]: headers["Authorization"] = auth[1]
                conn.request("GET", path, headers=headers)
                response = conn.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    redirects += 1
                    require(redirects <= 5, "REDIRECT_LIMIT", "Too many redirects")
                    location = response.getheader("Location")
                    require(location, "INVALID_RESPONSE", "Redirect missing location")
                    url = urljoin(url, location)
                    check_url(url, hosts)
                    continue
                if response.status in (429, 503) and retries < 2:
                    delay = response.getheader("Retry-After", "1")
                    require(delay.isdigit() and int(delay) <= 5, "RATE_LIMITED", "Provider requested a longer retry delay; try later")
                    retries += 1; time.sleep(int(delay)); continue
                if response.status in (401, 403):
                    raise DirectorError("AUTH_OR_ACCESS_REQUIRED", "Provider refused access; use its supported authentication or manual route")
                require(response.status == 200, "HTTP_ERROR", f"Provider HTTP status {response.status}")
                length = response.getheader("Content-Length")
                expected = int(length) if length and length.isdigit() else None
                require(expected is None or expected <= max_bytes, "DOWNLOAD_BUDGET", "Response exceeds remaining byte budget")
                received = 0
                while True:
                    require(time.monotonic() <= deadline, "DOWNLOAD_TIMEOUT", "Download deadline exceeded")
                    block = response.read(min(65536, max_bytes - received + 1))
                    if not block: break
                    received += len(block)
                    require(received <= max_bytes, "DOWNLOAD_BUDGET", "Actual bytes exceed download budget")
                    yield block
                require(expected is None or received == expected, "INCOMPLETE_DOWNLOAD", "Response length mismatch")
                return
            except DirectorError:
                raise
            except (OSError, http.client.HTTPException, ValueError) as exc:
                # Deliberately omit arbitrary response bodies and signed URLs from errors.
                raise DirectorError("NETWORK_ERROR", "HTTPS request failed or response was incomplete") from exc
            finally:
                if response: response.close()
                conn.close()
    def bytes(self, url: str, hosts: set[str], *, auth=None, limit=16 * 1024**2) -> bytes:
        return b"".join(self.stream(url, hosts, auth=auth, max_bytes=limit))
    def json(self, url: str, hosts: set[str], *, auth=None):
        try:
            return json.loads(self.bytes(url, hosts, auth=auth), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        except (ValueError, UnicodeError) as exc:
            raise DirectorError("PROVIDER_SCHEMA", "Provider returned invalid JSON") from exc


def budget(lib: Library) -> dict:
    path = lib.root / "budget.json"
    b = load_json(path) if path.exists() else {"downloaded": 0, "extracted": 0, "max_download": MAX_DOWNLOAD, "max_extract": MAX_EXTRACT}
    require(all(type(b.get(k)) is int and b[k] >= 0 for k in ("downloaded", "extracted", "max_download", "max_extract")), "INVALID_BUDGET", "Bad budget ledger")
    return b


def download(lib: Library, url: str, name: str, hosts: set[str], *, checksum: str | None = None, checksum_kind="sha256", client=None) -> dict:
    name = safe_member(name)
    require("/" not in name, "UNSAFE_PATH", "Download name must be a single filename")
    client = client or HTTP()
    if checksum:
        require(checksum_kind in {"md5", "sha256"} and re.fullmatch(r"[0-9a-fA-F]{32}|[0-9a-fA-F]{64}", checksum), "INVALID_CHECKSUM", "Invalid checksum")
    with lib.lock("acquire"):
        b = budget(lib)
        remaining = b["max_download"] - b["downloaded"]
        require(remaining > 0, "DOWNLOAD_BUDGET", "Compressed download budget exhausted")
        fd, tmp = tempfile.mkstemp(prefix="partial-", dir=lib.root / "downloads")
        total = 0
        h = hashlib.sha256()
        publisher = hashlib.new(checksum_kind) if checksum else None
        try:
            with os.fdopen(fd, "wb") as out:
                for block in client.stream(url, hosts, max_bytes=remaining):
                    total += len(block)
                    require(total <= remaining, "DOWNLOAD_BUDGET", "Actual download budget exceeded")
                    out.write(block); h.update(block)
                    if publisher: publisher.update(block)
                out.flush(); os.fsync(out.fileno())
            require(total > 0, "EMPTY_DOWNLOAD", "Empty file")
            require(not publisher or publisher.hexdigest().lower() == checksum.lower(), "CHECKSUM_MISMATCH", "Publisher checksum did not match")
            sha = h.hexdigest()
            destination = lib.root / "downloads" / sha / name
            destination.parent.mkdir(exist_ok=True)
            if destination.exists(): require(file_hash(destination) == sha, "CORRUPT_CACHE", "Existing immutable download changed")
            else: os.replace(tmp, destination)
            return {"path": destination.relative_to(lib.root).as_posix(), "sha256": sha, "size": total}
        finally:
            Path(tmp).unlink(missing_ok=True)
            b["downloaded"] += total
            atomic_json(lib.root / "budget.json", b)
            lib.event("download", {"bytes": total})


def extract_zip(lib: Library, record: dict) -> list[dict]:
    archive = lib.verify_file(record)
    dest = lib.root / "extracted" / record["sha256"]
    receipt = dest / ".extraction.json"
    if receipt.exists():
        data = load_json(receipt)
        for f in data["files"]: lib.verify_file(f)
        return data["files"]
    require(not dest.exists(), "INCOMPLETE_EXTRACTION", "Existing extraction has no valid receipt")
    with lib.lock("acquire"):
        b = budget(lib)
        staging = Path(tempfile.mkdtemp(prefix="extract-", dir=lib.root / "extracted"))
        written = 0
        try:
            with zipfile.ZipFile(archive) as z:
                entries = z.infolist()
                require(len(entries) <= 4096, "ARCHIVE_LIMIT", "Too many archive entries")
                seen, members, declared = {}, [], 0
                for item in entries:
                    name = safe_member(item.filename)
                    key = name.casefold()
                    require(key not in seen, "ARCHIVE_COLLISION", "Case-insensitive archive name collision")
                    seen[key] = item.is_dir()
                    mode = item.external_attr >> 16
                    require(not stat.S_ISLNK(mode) and stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR), "UNSAFE_ARCHIVE", "Special archive member")
                    require(not item.flag_bits & 1, "UNSAFE_ARCHIVE", "Encrypted archives unsupported")
                    declared += item.file_size
                    require(declared <= b["max_extract"] - b["extracted"], "EXTRACTION_BUDGET", "Expanded archive exceeds budget")
                    require(item.file_size <= max(1, item.compress_size) * 2000, "ARCHIVE_BOMB", "Suspicious compression ratio")
                    if not item.is_dir() and Path(name).suffix.lower() in ASSET_SUFFIXES:
                        members.append((item, name))
                for name in seen:
                    for parent in PurePosixPath(name).parents:
                        if str(parent) != ".": require(seen.get(str(parent), True), "ARCHIVE_COLLISION", "File used as directory")
                file_records = []
                for item, name in members:
                    output = within(staging, name)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(item) as src, output.open("xb") as out:
                        count = 0
                        while block := src.read(65536):
                            count += len(block); written += len(block)
                            require(count <= item.file_size and written <= b["max_extract"] - b["extracted"], "EXTRACTION_BUDGET", "Expanded bytes exceed budget")
                            out.write(block)
                    file_records.append({"path": (dest / name).relative_to(lib.root).as_posix(), "sha256": file_hash(output), "size": output.stat().st_size})
                require(file_records, "EMPTY_ARCHIVE", "No supported asset files")
                atomic_json(staging / ".extraction.json", {"archive": record["sha256"], "files": file_records,
                            "skipped": len(entries) - len(members)})
            os.replace(staging, dest)
            return file_records
        except (zipfile.BadZipFile, RuntimeError) as exc:
            raise DirectorError("INVALID_ARCHIVE", "Archive integrity check failed") from exc
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            b["extracted"] += written; atomic_json(lib.root / "budget.json", b)


def gltf_dependencies(path: Path, package_root: Path) -> list[str]:
    """Check every URI before invoking Blender's importer; includes nested extension URIs."""
    # Use one canonical root for BOTH containment and relative-path conversion.
    # Windows may expand an 8.3 temp path (RUNNER~1) while resolving the resource.
    path = Path(path).resolve()
    package_root = Path(package_root).resolve()
    if path.suffix.lower() == ".glb":
        with path.open("rb") as f:
            header = f.read(20)
            require(len(header) == 20, "INVALID_GLTF", "Truncated GLB")
            magic, version, length, chunk_length, chunk_type = struct.unpack("<4sIIII", header)
            require(magic == b"glTF" and version == 2 and length == path.stat().st_size and chunk_type == 0x4E4F534A and chunk_length <= 16 * 1024**2, "INVALID_GLTF", "Invalid GLB header")
            data = json.loads(f.read(chunk_length))
    else: data = load_json(path)
    dependencies = []
    def visit(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "uri":
                    require(isinstance(v, str), "INVALID_GLTF", "Invalid resource URI")
                    if v.startswith("data:"):
                        require(v.startswith(("data:image/", "data:application/")) and len(v) <= 32 * 1024**2, "INVALID_GLTF", "Unsupported inline data")
                    else:
                        uri = unquote(v)
                        require(not urlsplit(uri).scheme and not urlsplit(uri).netloc and "?" not in uri and "#" not in uri, "UNSAFE_DEPENDENCY", "External network resource blocked")
                        # Parent-relative references are valid only when the final path
                        # remains inside the already acquired package. Validate every other
                        # component using the same Windows rules used by extraction.
                        require(not uri.startswith(("/", "\\")) and "\\" not in uri, "UNSAFE_DEPENDENCY", "Absolute or backslash resource path")
                        for part in uri.split("/"):
                            if part not in {".", ".."}: safe_member(part)
                        resolved = (path.parent / uri).resolve()
                        require(resolved.is_relative_to(package_root.resolve()) and resolved.is_file(), "MISSING_OR_UNSAFE_DEPENDENCY", "Dependency missing or outside package")
                        dependencies.append(resolved.relative_to(package_root).as_posix())
                else: visit(v)
        elif isinstance(node, list):
            for v in node: visit(v)
    visit(data)
    return sorted(set(dependencies))
