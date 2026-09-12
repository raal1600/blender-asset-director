"""Acquire one reviewed upstream commit, independently of asset downloads.

No source is vendored or relicensed. Mwni's code declares GPL-3.0-or-later.
Our wrapper invokes its transfer math without enabling scripted drivers.
"""
from pathlib import Path
import hashlib
from .core import DirectorError, Library, atomic_json, load_json, require, file_hash
from .acquire import HTTP

COMMIT = "424f08bd7e675619adf539209a1e8816c242c386"
BLOBS = {
    "__init__.py": "23adc799a2f414ab7ded84244a458f52ace53c6d",
    "context.py": "94166fe8c2e69cbb19c1c8c18d57d2f3c348f5f7",
    "mapping.py": "16eb8a0dd6e1ab172ca2787517ae858a0535e7ca",
    "alignment.py": "321d27ae39f58e1ce58292d557f1a1c67dc314c3",
    "drivers.py": "27e140aaae2dced0b7e90f6dba3ee17d1187aa1a",
    "baking.py": "cfef0500a5d88ec233238ea62f849f65a8c85618",
    "ik.py": "5df2db26983a265cca6864d85b3ff017fba1d2c4",
    "util.py": "0974c59be588baaa11588847cda17c956ca77fb1",
    "log.py": "9c3c67fa8b1dfdfdcee932f8c3fc3198412d15df",
    "main.py": "e64587d7793fa9dd1925f9afdc566a3d230bd8e1",
    "corrections.py": "94c89315bbac2326cb5727d21c58431c23fba58f",
    "savefile.py": "e2d3068f859a4394a6cb7ab11f7b9c184c900eff",
    "blender_manifest.toml": "1840207d8dda98a114373a9d56a3e7bd4ff24ff0",
    "README.md": "bf4c072f65dd098286c2b1a2f8fd1943d6406e97",
}

def location(lib): return lib.root / "backends" / ("mwni-" + COMMIT)

def verify(lib: Library) -> Path:
    root = location(lib)
    require((root / "receipt.json").exists(), "BACKEND_MISSING", "Run backend-install to acquire the reviewed GPL backend")
    for name, expected in BLOBS.items():
        p = root / name
        require(p.is_file(), "BACKEND_CHANGED", "Backend source file missing")
        data = p.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(actual == expected, "BACKEND_CHANGED", "Pinned backend source mismatch")
    return root

def install(lib: Library, client=None) -> dict:
    root = location(lib)
    if (root / "receipt.json").exists():
        verify(lib); return {"status": "REUSED", "commit": COMMIT, "path": str(root)}
    client = client or HTTP()
    root.mkdir(parents=True, exist_ok=True)
    for name, expected in BLOBS.items():
        p = root / name
        data = p.read_bytes() if p.exists() else client.bytes(f"https://raw.githubusercontent.com/Mwni/blender-animation-retargeting/{COMMIT}/{name}", {"raw.githubusercontent.com"}, limit=1024**2)
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(actual == expected, "BACKEND_CHANGED", "Downloaded code does not match the reviewed commit")
        if not p.exists(): p.write_bytes(data)
    receipt = {"commit": COMMIT, "license": "GPL-3.0-or-later", "repository": "https://github.com/Mwni/blender-animation-retargeting",
               "files": {n: file_hash(root/n) for n in BLOBS}, "registration": "isolated worker only; no global preferences"}
    atomic_json(root / "receipt.json", receipt)
    return {"status": "INSTALLED", "commit": COMMIT, "path": str(root), "license": receipt["license"]}
