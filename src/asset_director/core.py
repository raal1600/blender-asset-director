"""Portable records, policy, search, and durable library; Python standard library only."""
from __future__ import annotations
import contextlib
import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import tempfile
import time
from typing import Any, Iterator

SCHEMA = 1
KINDS = {"model", "material", "hdri", "animation", "pack", "scene"}
FORMATS = {".glb", ".gltf", ".fbx", ".blend", ".obj", ".bvh", ".hdr", ".exr", ".png", ".jpg", ".jpeg", ".zip"}

class DirectorError(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)
    def as_dict(self) -> dict:
        return {"status": "ERROR", "code": self.code, "message": self.message}

def require(test: Any, code: str, message: str) -> None:
    if not test:
        raise DirectorError(code, message)

def canonical(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

def digest(data: Any) -> str:
    return hashlib.sha256(canonical(data).encode()).hexdigest()

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def load_json(path: Path, max_bytes: int = 16 * 1024 * 1024) -> Any:
    require(path.stat().st_size <= max_bytes, "INPUT_TOO_LARGE", "JSON input exceeds the size limit")
    try:
        def no_duplicates(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result, "INVALID_JSON", "Duplicate JSON field")
                result[key] = value
            return result
        def reject_constant(value):
            raise ValueError(value)
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=no_duplicates, parse_constant=reject_constant)
    except (ValueError, UnicodeError) as exc:
        raise DirectorError("INVALID_JSON", "Invalid JSON input") from exc

def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = canonical(data) + "\n"
    fd, name = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)

def within(root: Path, relative: str) -> Path:
    """Resolve library-relative paths. Do not permit absolute paths or symlink escapes."""
    require(isinstance(relative, str) and relative and "\\" not in relative and ":" not in relative,
            "UNSAFE_PATH", "Expected a relative POSIX-style library path")
    p = PurePosixPath(relative)
    require(not p.is_absolute() and all(x not in {"", ".", ".."} for x in p.parts), "UNSAFE_PATH", "Path traversal is not allowed")
    base = root.resolve()
    result = (base / p).resolve()
    require(result != base and result.is_relative_to(base), "UNSAFE_PATH", "Path leaves the library")
    return result

def fields(data: dict, allowed: set[str], required: set[str] = frozenset()) -> None:
    require(isinstance(data, dict), "INVALID_SCHEMA", "Expected an object")
    require(set(data) <= allowed and required <= set(data), "INVALID_SCHEMA", "Unknown or missing fields")

def text(value: Any, limit: int = 1000) -> str:
    require(isinstance(value, str) and len(value) <= limit and not any(ord(c) < 32 and c not in "\n\t" for c in value),
            "INVALID_SCHEMA", "Invalid text value")
    return value

@dataclasses.dataclass
class Asset:
    provider: str
    source_id: str
    title: str
    kind: str
    source_url: str
    license_id: str = "UNKNOWN"
    license_url: str = ""
    author: str = ""
    price: float | None = None
    downloadable: bool | None = None
    formats: list[str] = dataclasses.field(default_factory=list)
    tags: list[str] = dataclasses.field(default_factory=list)
    evidence: str = "unverified"
    local_files: list[dict] = dataclasses.field(default_factory=list)
    metadata: dict = dataclasses.field(default_factory=dict)
    checked_at: float = dataclasses.field(default_factory=time.time)
    schema_version: int = SCHEMA

    @property
    def id(self) -> str:
        return "a_" + digest([self.provider, self.source_id])[:24]
    def to_dict(self) -> dict:
        return {**dataclasses.asdict(self), "id": self.id}
    @classmethod
    def from_dict(cls, data: dict) -> "Asset":
        names = {f.name for f in dataclasses.fields(cls)}
        fields(data, names | {"id"}, {"provider", "source_id", "title", "kind", "source_url"})
        a = cls(**{k: v for k, v in data.items() if k != "id"})
        for name in ("provider", "source_id", "title", "source_url", "license_id", "license_url", "author", "evidence"):
            text(getattr(a, name), 2048)
        require(a.schema_version == SCHEMA and a.kind in KINDS, "INVALID_SCHEMA", "Unsupported record version or kind")
        require(re.fullmatch(r"[a-z][a-z0-9_-]{0,40}", a.provider), "INVALID_SCHEMA", "Invalid provider")
        require(a.price is None or (type(a.price) in (float, int) and math.isfinite(a.price) and a.price >= 0), "INVALID_SCHEMA", "Invalid price")
        require(a.downloadable is None or type(a.downloadable) is bool, "INVALID_SCHEMA", "Invalid download state")
        require(type(a.checked_at) in (int, float) and math.isfinite(a.checked_at), "INVALID_SCHEMA", "Invalid timestamp")
        for seq in (a.formats, a.tags):
            require(isinstance(seq, list) and len(seq) <= 256, "INVALID_SCHEMA", "Invalid tags/formats")
            for s in seq: text(s, 200)
        require(isinstance(a.metadata, dict) and isinstance(a.local_files, list) and len(a.local_files) <= 10000, "INVALID_SCHEMA", "Invalid metadata/files")
        require("id" not in data or data["id"] == a.id, "INVALID_SCHEMA", "Asset ID mismatch")
        canonical(a.to_dict())
        return a

def rights(a: Asset, *, commercial: bool = True) -> dict:
    """Conservative policy classification, not legal advice or third-party-rights clearance."""
    reasons = []
    if a.price is None: reasons.append("PRICE_UNVERIFIED")
    elif a.price != 0: reasons.append("PAID_NOT_AUTHORIZED")
    if not a.local_files and a.downloadable is not True: reasons.append("DOWNLOAD_UNVERIFIED")
    if not any(x.lower() in FORMATS for x in a.formats): reasons.append("FORMAT_UNSUPPORTED")
    lid = a.license_id.upper().strip()
    allowed = lid in {"CC0", "CC0-1.0", "CC-BY-4.0", "CC-BY-3.0"}
    if commercial and not allowed: reasons.append("LICENSE_REVIEW_REQUIRED")
    if a.evidence not in {"provider", "user_attested"} or not a.license_url:
        reasons.append("LICENSE_EVIDENCE_MISSING")
    return {"eligible": not reasons, "reasons": reasons, "attribution_required": lid.startswith("CC-BY-"),
            "raw_redistribution": "REVIEW" if not allowed else "SUBJECT_TO_LICENSE",
            "third_party_rights": "NOT_VERIFIED", "commercial_clearance": "NOT_A_LEGAL_CLEARANCE"}

ALIASES = {
    "walking": "walk", "walks": "walk", "stroll": "walk", "strolling": "walk", "locomotion": "walk",
    "running": "run", "sprint": "run", "sprinting": "run", "jog": "run", "jogging": "run",
    "standing": "idle", "stand": "idle", "waiting": "idle", "guard": "vigilant", "attentive": "vigilant",
    "sword": "armed", "weapon": "armed", "combat": "armed", "warrior": "armed",
    "sand": "desert", "sandy": "desert", "dune": "desert", "dunes": "desert",
    "stops": "stop", "stopping": "stop", "turns": "turn", "turning": "turn", "slowly": "slow"
}
STOPWORDS = {"a", "an", "the", "to", "and", "in", "on", "of", "for", "with", "make", "create", "my", "this", "then"}
def tokens(s: str) -> set[str]:
    # CamelCase animation names such as Walking_A are searchable too.
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    return {ALIASES.get(x, x) for x in re.findall(r"[a-z0-9]+", s.lower()) if x not in STOPWORDS}

def plan(brief: str) -> dict:
    text(brief, 8000)
    words = tokens(brief)
    beats = [x for x in ("walk", "run", "stop", "turn", "idle", "attack") if x in words]
    if "vigilant" in words and "idle" not in beats: beats.append("idle")
    return {"schema_version": SCHEMA, "brief": brief, "extraction": "deterministic keyword hints; host must confirm semantics",
            "motions": [{"query": x, "constraints": sorted(words & {"armed", "slow", "vigilant"})} for x in beats],
            "environment_queries": ["desert"] if "desert" in words else [],
            "preserve": ["existing hero", "existing terrain", "original file"],
            "order": ["inspect_scene", "local_search", "provider_search", "preflight", "source_preview", "retarget_flat", "terrain_qa", "human_review"],
            "budget": {"paid_assets": 0, "local_ai": False, "max_render_frames": 8},
            "unknowns": ["target rig", "source quality", "motion compatibility", "user asset rights"]}

def rank(query: str, assets: list[Asset], kind: str | None = None, limit: int = 5) -> list[dict]:
    require(1 <= limit <= 50, "INVALID_SCHEMA", "Limit must be 1..50")
    q = tokens(text(query, 2000))
    results = []
    for a in assets:
        if kind and a.kind != kind: continue
        corpus = tokens(a.title + " " + " ".join(a.tags))
        match = q & corpus
        if q and not match: continue
        p = rights(a)
        # A known wrong gait is not rescued by matching 'armed' or 'slow'.
        if "walk" in q and "run" in corpus and "walk" not in corpus:
            p["eligible"] = False; p["reasons"].append("WRONG_MOTION_RUN_NOT_WALK")
        score = (len(match) / max(1, len(q))) * 80 + (10 if a.local_files else 0) + (5 if p["eligible"] else 0)
        results.append({"asset": a.to_dict(), "score": round(score, 2), "policy": p,
                        "matched_terms": sorted(match), "unmatched_terms": sorted(q - corpus),
                        "rig_compatibility": a.metadata.get("rig_compatibility", "UNKNOWN"),
                        "visual_review": a.metadata.get("visual_review", "PENDING")})
    return sorted(results, key=lambda r: (not r["policy"]["eligible"], -r["score"], r["asset"]["id"]))[:limit]

class Library:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for d in ("manifests", "downloads", "extracted", "prepared", "previews", "licenses", "incoming", "jobs", "reports", "cache", "backends"):
            (self.root / d).mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.root / "catalog.sqlite", timeout=15)
        self.db.execute("PRAGMA journal_mode=WAL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, SCHEMA):
            self.db.close()
            raise DirectorError("CATALOG_VERSION", "Unsupported catalog version; do not downgrade")
        self.db.executescript("CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY, record TEXT NOT NULL); CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, at REAL NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL);")
        self.db.execute(f"PRAGMA user_version={SCHEMA}"); self.db.commit()
    def close(self): self.db.close()
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    @contextlib.contextmanager
    def lock(self, name: str = "mutation") -> Iterator[None]:
        require(re.fullmatch(r"[a-zA-Z0-9_-]+", name), "UNSAFE_PATH", "Invalid lock name")
        path = self.root / ("." + name + ".lock")
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise DirectorError("BUSY", "Library operation already locked; inspect a stale lock before removing it") from exc
        try:
            with os.fdopen(fd, "w") as stream: stream.write(str(os.getpid()))
            yield
        finally: path.unlink(missing_ok=True)
    def put(self, a: Asset) -> str:
        a = Asset.from_dict(a.to_dict())
        for f in a.local_files:
            fields(f, {"path", "sha256", "size"}, {"path", "sha256", "size"})
            within(self.root, f["path"])
            require(bool(re.fullmatch(r"[0-9a-f]{64}", f["sha256"])), "INVALID_SCHEMA", "Bad file hash")
            require(type(f["size"]) is int and f["size"] >= 0, "INVALID_SCHEMA", "Bad file size")
        atomic_json(self.root / "manifests" / (a.id + ".json"), a.to_dict())
        with self.db: self.db.execute("INSERT OR REPLACE INTO assets VALUES (?,?)", (a.id, canonical(a.to_dict())))
        return a.id
    def get(self, aid: str) -> Asset:
        row = self.db.execute("SELECT record FROM assets WHERE id=?", (aid,)).fetchone()
        require(row, "ASSET_NOT_FOUND", "Unknown asset ID")
        return Asset.from_dict(json.loads(row[0]))
    def all(self) -> list[Asset]:
        return [Asset.from_dict(json.loads(r[0])) for r in self.db.execute("SELECT record FROM assets ORDER BY id")]
    def rebuild(self) -> int:
        records = [Asset.from_dict(load_json(p)) for p in sorted((self.root / "manifests").glob("a_*.json"))]
        with self.db:
            self.db.execute("DELETE FROM assets")
            self.db.executemany("INSERT INTO assets VALUES (?,?)", [(a.id, canonical(a.to_dict())) for a in records])
        return len(records)
    def event(self, kind: str, data: dict):
        # Callers supply only sanitized IDs/counts/status; never URLs with tokens.
        with self.db: self.db.execute("INSERT INTO events(at,kind,data) VALUES (?,?,?)", (time.time(), kind, canonical(data)))
    def verify_file(self, f: dict) -> Path:
        path = within(self.root, f["path"])
        require(path.is_file() and path.stat().st_size == f["size"] and file_hash(path) == f["sha256"], "STALE_INPUT", "Input missing or changed; re-index before use")
        return path
    def export_report(self) -> dict:
        records = self.all()
        report = {"schema_version": SCHEMA, "assets": len(records), "clips": sum(a.kind == "animation" for a in records),
                  "licenses": [{"id": a.id, "title": a.title, "source": a.source_url, "author": a.author,
                                "license": a.license_id, "license_url": a.license_url, "policy": rights(a)} for a in records]}
        atomic_json(self.root / "reports" / "library.json", report)
        lines = ["# Asset sources and attribution", "", "This records evidence, not a blanket legal clearance. Raw assets are not part of the code repository.", ""]
        for a in records:
            lines.extend([f"## {a.title.replace(chr(10), ' ')}", f"Author: {a.author or 'Unknown'}", f"Source: {a.source_url}", f"License: {a.license_id} ({a.license_url or 'evidence needed'})", f"Evidence: {a.evidence}; modifications/analysis: see manifest {a.id}.", ""])
        (self.root / "reports" / "ATTRIBUTION.md").write_text("\n".join(lines), encoding="utf-8")
        return report
