"""Verified provider routes. No private marketplace scraping or paid API nodes."""
from __future__ import annotations
import dataclasses
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import shutil
import time
from urllib.parse import quote, urlencode, urljoin, urlsplit, unquote
from .core import Asset, DirectorError, Library, atomic_json, digest, load_json, rank, require, rights
from .acquire import HTTP, download, extract_zip, safe_member

PH_API = {"api.polyhaven.com"}
PH_FILES = {"dl.polyhaven.org", "cdn.polyhaven.com", "dl.polyhaven.com"}
AC_HOSTS = {"ambientcg.com", "www.ambientcg.com", "acg-download.struffelproductions.com", "acg-download.struffelproductions.net"}
OGA = "https://opengameart.org/content/universal-animation-library"
CC0 = "https://creativecommons.org/publicdomain/zero/1.0/"


def capabilities() -> dict:
    auth = bool(os.environ.get("SKETCHFAB_TOKEN"))
    return {
        "local": {"search": "READY", "intake": "READY"},
        "quaternius": {"search": "READY_CURATED_PACK", "download": "READY", "note": "Creator-posted Standard edition; index actual files, not assumed clip names"},
        "polyhaven": {"search": "READY", "download": "READY", "credit": "Assets from Poly Haven; API use credited separately from CC0"},
        "ambientcg": {"search": "READY", "download": "READY", "note": "v3 with explicit documented v2 fallback"},
        "sketchfab": {"search": "READY", "download": "READY" if auth else "AUTH_REQUIRED", "note": "Credentials present does not mean authentication has been runtime-tested"},
        "mixamo": {"search": "MANUAL_ONLY", "download": "MANUAL_ONLY", "intake": "READY", "note": "Use official Adobe site; no bulk ripper or auto-upload"},
        "blenderkit": {"search": "HOST_TOOL_OR_MANUAL", "download": "HOST_TOOL_OR_MANUAL", "intake": "READY"},
        "poly_pizza": {"search": "HOST_TOOL_OR_MANUAL", "download": "HOST_TOOL_OR_MANUAL", "intake": "READY"}}


class Providers:
    def __init__(self, library: Library, client=None):
        self.lib, self.http = library, client or HTTP()
        self.last_cache_state = "NONE"
    def cached(self, url: str, hosts: set[str], *, refresh=False):
        path = self.lib.root / "cache" / (digest(url) + ".json")
        prior = load_json(path) if path.exists() else None
        if prior and not refresh and time.time() - prior["at"] < 86400:
            self.last_cache_state = "FRESH_CACHE"; return prior["data"]
        try:
            result = self.http.json(url, hosts)
            atomic_json(path, {"at": time.time(), "data": result})
            self.last_cache_state = "LIVE"; return result
        except DirectorError:
            if prior and not refresh:
                self.last_cache_state = "STALE_OFFLINE_CACHE"; return prior["data"]
            raise
    def search(self, provider: str, query: str, kind: str | None = None, limit=5, refresh=False) -> dict:
        require(1 <= limit <= 50, "INVALID_SCHEMA", "Limit must be 1..50")
        candidates = []
        if provider == "local": candidates = self.lib.all()
        elif provider == "quaternius":
            candidates = [Asset("quaternius", "ual-standard-oga", "Universal Animation Library Standard", "pack", OGA,
                "CC0-1.0", CC0, "Quaternius", 0, True, [".zip"], ["walk", "idle", "animation", "humanoid", "combat"], "provider",
                metadata={"edition": "Standard; creator-posted 2025-04-16", "advertised_clips": 45, "actual_clips": None})]
        elif provider == "polyhaven":
            ph_kind = {"hdri": "hdris", "material": "textures", "model": "models"}.get(kind)
            url = "https://api.polyhaven.com/assets" + ("?type=" + ph_kind if ph_kind else "")
            data = self.cached(url, PH_API, refresh=refresh)
            require(isinstance(data, dict), "PROVIDER_SCHEMA", "Unexpected Poly Haven catalog")
            for sid, item in data.items():
                require(isinstance(item, dict), "PROVIDER_SCHEMA", "Unexpected Poly Haven asset")
                k = {0: "hdri", 1: "material", 2: "model"}.get(item.get("type"), kind)
                if k not in {"hdri", "material", "model"}: continue
                tags = item.get("tags", [])
                if not isinstance(tags, list): tags = []
                candidates.append(Asset("polyhaven", sid, item.get("name", sid), k, "https://polyhaven.com/a/" + quote(sid),
                    "CC0-1.0", "https://polyhaven.com/license", ", ".join(item.get("authors", {})), 0, True,
                    {"hdri": [".hdr", ".exr"], "material": [".jpg", ".png"], "model": [".blend", ".gltf"]}[k],
                    tags, "provider", metadata={"preview_url": item.get("thumbnail_url"), "polycount": item.get("polycount"), "cache_state": self.last_cache_state}))
        elif provider == "ambientcg":
            params = {"q": query, "type": "material" if kind in (None, "material") else kind, "limit": min(50, limit * 3), "include": "title,tags,url,downloads,type"}
            data = self.cached("https://ambientcg.com/api/v3/assets?" + urlencode(params), {"ambientcg.com"}, refresh=refresh)
            items = data.get("assets") if isinstance(data, dict) else None
            require(isinstance(items, list), "PROVIDER_SCHEMA", "Unexpected ambientCG v3 catalog")
            for item in items:
                sid = item.get("id")
                require(isinstance(sid, str), "PROVIDER_SCHEMA", "ambientCG ID missing")
                k = {"material": "material", "hdri": "hdri", "3d-model": "model"}.get(item.get("type"), kind or "material")
                tags = item.get("tags", [])
                if isinstance(tags, dict): tags = list(tags)
                if not isinstance(tags, list): tags = []
                candidates.append(Asset("ambientcg", sid, item.get("title") or sid, k, item.get("url") or "https://ambientcg.com/view?id=" + quote(sid),
                    "CC0-1.0", "https://docs.ambientcg.com/license/", "ambientCG / Lennart Demes", 0, True, [".zip"], tags + [query], "provider",
                    metadata={"api_version": "v3", "query_tag_inferred": query, "cache_state": self.last_cache_state}))
        elif provider == "sketchfab":
            params = {"type": "models", "q": query, "downloadable": "true", "count": min(24, limit * 3)}
            data = self.http.json("https://api.sketchfab.com/v3/search?" + urlencode(params), {"api.sketchfab.com"})
            require(isinstance(data.get("results"), list), "PROVIDER_SCHEMA", "Unexpected Sketchfab search response")
            for item in data["results"]:
                lic = item.get("license") or {}
                url = lic.get("url", "")
                lid = "UNKNOWN"
                for fragment, value in (("/publicdomain/zero/", "CC0-1.0"), ("/licenses/by/4.0", "CC-BY-4.0"), ("/licenses/by/3.0", "CC-BY-3.0")):
                    if url.startswith("https://creativecommons.org") and fragment in url: lid = value
                available = item.get("isDownloadable") is True
                candidates.append(Asset("sketchfab", item["uid"], item.get("name", item["uid"]), "model", item.get("viewerUrl", "https://sketchfab.com/models/" + item["uid"]),
                    lid, url, (item.get("user") or {}).get("displayName", ""), 0 if available else None, available,
                    [".gltf", ".glb"], [t.get("name", "") for t in item.get("tags", [])], "provider",
                    metadata={"animation_count_claimed": item.get("animationCount"), "face_count_claimed": item.get("faceCount"), "download_auth": "REQUIRED"}))
        else:
            return {"provider": provider, "status": "MANUAL_ONLY", "results": [], "next": "Use the supported provider UI/host tool; then intake local files with source and license evidence"}
        selected = rank(query, candidates, kind if provider != "quaternius" else None, limit)
        for r in selected:
            a = Asset.from_dict(r["asset"])
            try:
                old = self.lib.get(a.id)
                a.local_files = old.local_files
                a.metadata = {**old.metadata, **a.metadata}
            except DirectorError: pass
            self.lib.put(a)
            r["asset"] = a.to_dict()
        return {"provider": provider, "status": "OK", "cache_state": self.last_cache_state, "query": query, "results": selected}

    def resolve(self, a: Asset, resolution="1k") -> tuple[list[dict], set[str]]:
        require(resolution in {"1k", "2k"}, "RESOURCE_LIMIT", "Baseline supports only 1k or 2k acquisitions")
        if a.provider == "quaternius":
            page = self.http.bytes(OGA, {"opengameart.org"}, limit=2 * 1024**2).decode("utf-8")
            require("quaternius" in page.lower() and "creativecommons.org/publicdomain/zero" in page.lower(), "SOURCE_CHANGED", "Creator/license evidence changed")
            class Links(HTMLParser):
                urls = []
                def handle_starttag(self, tag, attrs):
                    if tag == "a":
                        href = dict(attrs).get("href", "")
                        if href.lower().endswith(".zip"): self.urls.append(urljoin(OGA, href))
            parser = Links(); parser.urls = []; parser.feed(page)
            urls = sorted(set(u for u in parser.urls if "standard" in u.lower() and "universal" in u.lower()))
            require(len(urls) == 1, "SOURCE_CHANGED", "Cannot identify one free Standard archive")
            return [{"url": urls[0], "name": unquote(Path(urlsplit(urls[0]).path).name)}], {"opengameart.org"}
        if a.provider == "polyhaven":
            data = self.http.json("https://api.polyhaven.com/files/" + quote(a.source_id, safe=""), PH_API)
            choices = []
            if a.kind == "hdri":
                formats = data.get("hdri", {}).get(resolution, {})
                selected = formats.get("hdr") or formats.get("exr")
                require(selected, "FORMAT_UNAVAILABLE", "Requested HDRI resolution not available")
                choices = [(None, selected)]
            elif a.kind == "model":
                for fmt in ("gltf", "fbx", "blend"):
                    branch = data.get(fmt, {}).get(resolution, {})
                    selected = branch.get(fmt)
                    if selected:
                        choices = [(None, selected)]; break
                require(choices, "FORMAT_UNAVAILABLE", "No supported model resolution/format in provider manifest")
            else:
                for map_name in ("diff", "rough", "nor_gl", "metal", "disp"):
                    branch = data.get(map_name, {}).get(resolution, {})
                    selected = branch.get("png") or branch.get("jpg")
                    if selected: choices.append((None, selected))
                require(choices, "FORMAT_UNAVAILABLE", "No supported material maps")
            files = []
            for name, selected in choices:
                files.append(self._ph_file(name, selected))
                includes = selected.get("include", {})
                require(isinstance(includes, dict), "PROVIDER_SCHEMA", "Unexpected dependency manifest")
                for local, dep in includes.items(): files.append(self._ph_file(local, dep))
            return files, PH_FILES
        if a.provider == "ambientcg":
            data = self.http.json("https://ambientcg.com/api/v3/assets?" + urlencode({"id": a.source_id, "include": "downloads", "limit": 1}), {"ambientcg.com"})
            items = data.get("assets", [])
            files = self._download_records(items[0].get("downloads", {})) if items else []
            choices = self._ac_options(files, resolution)
            if not choices:
                # Explicit compatibility fallback to the still documented v2 endpoint, not a guessed private API.
                data = self.http.json("https://ambientcg.com/api/v2/full_json?" + urlencode({"id": a.source_id, "include": "downloadData"}), {"ambientcg.com"})
                found = data.get("foundAssets", [])
                files = self._download_records(found[0].get("downloadFolders", {})) if found else []
                choices = self._ac_options(files, resolution)
                a.metadata["download_api_version"] = "v2_compatibility"
            require(choices, "PROVIDER_SCHEMA", "No 1k/2k JPG ZIP found; do not guess a download URL")
            return [sorted(choices, key=lambda f: (f.get("size", 10**18), f["name"]))[0]], AC_HOSTS
        if a.provider == "sketchfab":
            key = os.environ.get("SKETCHFAB_TOKEN")
            require(key, "AUTH_REQUIRED", "Enter Sketchfab token privately in the local environment; never in chat")
            result = self.http.json("https://api.sketchfab.com/v3/models/" + quote(a.source_id, safe="") + "/download", {"api.sketchfab.com"}, auth=("api.sketchfab.com", "Token " + key))
            item = result.get("gltf") or result.get("glb")
            require(item and item.get("url"), "DOWNLOAD_UNAVAILABLE", "No supported authorized download returned")
            host = urlsplit(item["url"]).hostname or ""
            require(host in {"media.sketchfab.com", "sketchfab-prod-media.s3.amazonaws.com"} or re.fullmatch(r"sketchfab-prod-media\.s3[.-][a-z0-9-]+\.amazonaws\.com", host), "UNSAFE_URL", "Unrecognized Sketchfab download host")
            # Temporary signed URL exists only in this local return value, never the catalog/logs.
            suffix = ".zip" if result.get("gltf") else ".glb"
            return [{"url": item["url"], "name": a.source_id + suffix}], {host}
        raise DirectorError("MANUAL_ONLY", "Provider requires supported UI/host acquisition followed by local intake")

    @staticmethod
    def _ph_file(name, item):
        require(isinstance(item, dict) and isinstance(item.get("url"), str), "PROVIDER_SCHEMA", "Invalid file record")
        filename = name or unquote(Path(urlsplit(item["url"]).path).name)
        return {"url": item["url"], "name": safe_member(filename), "size": item.get("size"), "checksum": item.get("md5"), "checksum_kind": "md5"}
    @staticmethod
    def _download_records(data, context="") -> list[dict]:
        out = []
        if isinstance(data, dict):
            url = data.get("downloadLink") or data.get("url") or data.get("downloadUrl")
            name = data.get("fileName") or data.get("filename") or data.get("name")
            if url and isinstance(url, str):
                inferred = unquote(Path(urlsplit(url).path).name)
                # Some download endpoints use ?file=; use explicit filename/context only, never guess IDs.
                name = name or (inferred if "." in inferred else context.rsplit("/", 1)[-1])
                if isinstance(name, str) and name.lower().endswith(".zip"):
                    out.append({"url": url, "name": safe_member(name), "size": data.get("size") or data.get("sizeBytes") or 10**18})
            for k, v in data.items():
                if isinstance(v, (list, dict)): out.extend(Providers._download_records(v, context + "/" + k))
        elif isinstance(data, list):
            for v in data: out.extend(Providers._download_records(v, context))
        return out
    @staticmethod
    def _ac_options(files, resolution):
        return [x for x in files if resolution.lower() in x["name"].lower() and "jpg" in x["name"].lower()]

    def acquire(self, asset_id: str, resolution="1k") -> dict:
        a = self.lib.get(asset_id)
        require(a.provider in {"polyhaven", "ambientcg", "quaternius", "sketchfab"} and a.evidence == "provider", "MANUAL_ONLY", "Only verified provider candidates are eligible for automated acquisition")
        p = rights(a); require(p["eligible"], "BLOCKED_POLICY", "; ".join(p["reasons"]))
        if a.local_files:
            for f in a.local_files: self.lib.verify_file(f)
            return {"status": "REUSED", "asset": a.to_dict()}
        files, hosts = self.resolve(a, resolution)
        records, bundle_items = [], []
        for f in files:
            d = download(self.lib, f["url"], Path(f["name"]).name, hosts, checksum=f.get("checksum"), checksum_kind=f.get("checksum_kind", "sha256"), client=self.http)
            if Path(f["name"]).suffix.lower() == ".zip":
                records.extend(extract_zip(self.lib, d))
            else:
                bundle_items.append((f["name"], d))
            a.metadata.setdefault("original_downloads", []).append(d)
        if bundle_items:
            root = self.lib.root / "prepared" / (a.id + "-" + resolution)
            require(not root.exists(), "INCOMPLETE_ACQUISITION", "Bundle already exists; inspect before retry")
            root.mkdir()
            try:
                seen = set()
                for name, d in bundle_items:
                    name = safe_member(name)
                    require(name.casefold() not in seen, "ARCHIVE_COLLISION", "Duplicate dependency filename")
                    seen.add(name.casefold())
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(self.lib.verify_file(d), path)
                    records.append({**d, "path": path.relative_to(self.lib.root).as_posix()})
            except BaseException:
                shutil.rmtree(root); raise
        a.local_files = records
        a.metadata["acquired_resolution"] = resolution
        a.metadata["visual_review"] = "PENDING"
        self.lib.put(a)
        self.lib.event("acquired", {"asset_id": a.id, "files": len(records)})
        return {"status": "ACQUIRED", "asset": a.to_dict()}
