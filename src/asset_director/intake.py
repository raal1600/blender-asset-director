"""Explicit local-file intake. No scanning outside the selected file/directory."""
from __future__ import annotations
from pathlib import Path
import shutil
from .core import Asset, Library, DirectorError, file_hash, load_json, fields, require, within
from .acquire import ASSET_SUFFIXES, MAX_DOWNLOAD, download, extract_zip, gltf_dependencies, safe_member


def intake(lib: Library, selected: str, evidence_file: str, *, preserve_existing: bool = False, prepared_member: str | None = None) -> dict:
    source = Path(selected).expanduser().resolve()
    require(source.exists(), "FILE_NOT_FOUND", "Selected local asset does not exist")
    evidence = load_json(Path(evidence_file))
    fields(evidence, {"title", "kind", "source_url", "license_id", "license_url", "author", "price", "tags", "attested"}, {"title", "kind", "source_url"})
    require(type(evidence.get("attested", False)) is bool, "INVALID_SCHEMA", "attested must be an explicit boolean")
    files = [source] if source.is_file() else sorted(source.rglob("*"))
    require(len(files) <= 4096, "RESOURCE_LIMIT", "Selected package contains too many entries")
    root = source.parent if source.is_file() else source
    chosen, seen, total = [], set(), 0
    for p in files:
        require(not p.is_symlink(), "UNSAFE_PATH", "Linked intake entries are not supported")
        if not p.is_file(): continue
        if prepared_member is not None and p.suffix.lower() == '.zip': continue
        name = safe_member(p.relative_to(root).as_posix())
        if p.suffix.lower() not in ASSET_SUFFIXES | {".zip"}: continue
        require(name.casefold() not in seen, "ARCHIVE_COLLISION", "Case-insensitive local package collision")
        seen.add(name.casefold()); total += p.stat().st_size
        require(total <= MAX_DOWNLOAD, "RESOURCE_LIMIT", "Intake is bounded to 500 MiB; split larger packages explicitly")
        chosen.append((p, name, file_hash(p)))
    require(chosen, "NO_ASSETS", "No supported asset files were selected")
    if prepared_member is not None:
        require(isinstance(prepared_member, str) and prepared_member in {name for _, name, _ in chosen}
                and Path(prepared_member).suffix.lower() in {'.blend', '.gltf', '.glb', '.fbx'},
                'SOURCE_NOT_IN_ASSET', 'Preparation must bind one exact supported source member')
    from .core import digest
    package = digest([(name, sha) for _, name, sha in chosen])
    dest = lib.root / "incoming" / package
    records = []
    with lib.lock("intake"):
        for p, name, sha in chosen:
            target = within(dest, name); target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists(): require(file_hash(target) == sha, "CORRUPT_CACHE", "Existing intake copy was modified")
            else:
                with p.open("rb") as src, target.open("xb") as out: shutil.copyfileobj(src, out, 65536)
            require(file_hash(target) == sha, "SOURCE_CHANGED", "Local source changed during intake")
            records.append({"path": target.relative_to(lib.root).as_posix(), "sha256": sha, "size": target.stat().st_size})
    extracted = []
    for f in records:
        if f["path"].lower().endswith(".zip"): extracted.extend(extract_zip(lib, f))
    usable = extracted or records
    for f in usable:
        if Path(f["path"]).suffix.lower() in {".gltf", ".glb"}:
            base = lib.root / "extracted" / Path(f["path"]).parts[1] if extracted else dest
            gltf_dependencies(lib.verify_file(f), base)
    a = Asset("local", package, evidence["title"], evidence["kind"], evidence["source_url"],
              evidence.get("license_id", "UNKNOWN"), evidence.get("license_url", ""), evidence.get("author", ""),
              evidence.get("price"), True, sorted({Path(f["path"]).suffix.lower() for f in usable}), evidence.get("tags", []),
              "user_attested" if evidence.get("attested") else "unverified", usable,
              {"intake": "explicit local selection; rights claims supplied by user", "package_sha256": package})
    if prepared_member is not None:
        a.metadata['prepared_member'] = (dest / prepared_member).relative_to(lib.root).as_posix()
    # Two different productions can prepare the same package concurrently.
    # Keep the existing-check and publication under one cross-process lease.
    with lib.lock("intake-catalog"):
        if preserve_existing:
            try:
                existing = lib.get(a.id)
            except DirectorError as exc:
                if exc.code != "ASSET_NOT_FOUND":
                    raise
            else:
                # A launcher intake never rewrites previously reviewed catalog
                # metadata, provider identity or licensing for the same package.
                for record in existing.local_files:
                    lib.verify_file(record)
                return {"status": "ALREADY_INTAKEN", "asset_id": existing.id,
                        "files": len(existing.local_files), "evidence": existing.evidence,
                        "catalog_evidence_preserved": True}
        lib.put(a)
    return {"status": "INTAKEN", "asset_id": a.id, "files": len(usable), "evidence": a.evidence}
