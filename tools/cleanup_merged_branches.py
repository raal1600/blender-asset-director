"""One-time, manifest-bound cleanup after successful main workflows.

No force updates, settings changes, new branches, tags or unlisted deletions.
Expected-value leases make the deletion transaction fail if any selected tip moved.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def validate_manifest(manifest: dict[str, Any], repository: str) -> None:
    if manifest.get("schema") != "asset-director.branch-cleanup/1" or manifest.get("repository") != repository:
        raise ValueError("Cleanup manifest does not match this repository")
    names = [b["name"] for b in manifest["branches"]] + [manifest["integration_branch"]]
    if not names or len(names) != len(set(names)):
        raise ValueError("Duplicate or empty cleanup inventory")
    for name in names:
        if (name == "main" or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", name)
                or ".." in name or "//" in name or name.endswith(("/", ".", ".lock"))):
            raise ValueError("Unsafe or reserved cleanup branch")
    if not all(re.fullmatch(r"[0-9a-f]{40}", b["sha"]) for b in manifest["branches"]):
        raise ValueError("Original branch tips must be full immutable commit SHAs")
    if not manifest.get("required_workflows") or len(set(manifest["required_workflows"])) != len(manifest["required_workflows"]):
        raise ValueError("Explicit unique required workflows are mandatory")


def gates_passed(runs: list[dict[str, Any]], required: list[str], sha: str) -> bool:
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        if run.get("head_sha") != sha or run.get("head_branch") != "main" or run.get("event") != "push":
            continue
        name = run.get("name")
        if name in required and run["id"] > latest.get(name, {}).get("id", -1):
            latest[name] = run
    return all(name in latest and latest[name].get("status") == "completed"
               and latest[name].get("conclusion") == "success" for name in required)


def decision(name: str, actual_sha: str, expected_sha: str | None, *,
             protected: bool, ancestor: bool, open_pr: bool, merged_pr: bool = False) -> str:
    if name == "main":
        return "preserve: main"
    if protected:
        return "preserve: protected"
    if expected_sha is not None and actual_sha != expected_sha:
        return "preserve: tip moved since inventory"
    if open_pr:
        return "preserve: open pull request"
    if not ancestor:
        return "preserve: not an ancestor of tested main"
    if expected_sha is None and not merged_pr:
        return "preserve: integration tip lacks matching merged pull request"
    return "eligible"


def deletion_command(candidates: list[dict[str, str]]) -> list[str]:
    if not candidates or any(b["name"] == "main" or not re.fullmatch(r"[0-9a-f]{40}", b["sha"]) for b in candidates):
        raise ValueError("Only checked, named non-main branches can be deleted")
    return (["git", "push", "--atomic", "--porcelain"]
            + [f"--force-with-lease=refs/heads/{b['name']}:{b['sha']}" for b in candidates]
            + ["origin"] + [f":refs/heads/{b['name']}" for b in candidates])


class GitHub:
    def __init__(self, repository: str, token: str):
        self.base = f"https://api.github.com/repos/{repository}/"
        self.token = token

    def get(self, path: str) -> Any:
        request = Request(self.base + path, headers={"Authorization": "Bearer " + self.token,
                          "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def pages(self, path: str, key: str | None = None) -> list[Any]:
        results = []
        separator = "&" if "?" in path else "?"
        for page in range(1, 21):
            data = self.get(f"{path}{separator}per_page=100&page={page}")
            batch = data[key] if key else data
            results.extend(batch)
            if len(batch) < 100:
                return results
        raise RuntimeError("Inventory exceeded bounded pagination; no deletion authorized")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="docs/consolidation/branches.json")
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", default="cleanup-evidence/report.json")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.target_sha):
        raise ValueError("A full target SHA is required")
    repository = os.environ["GITHUB_REPOSITORY"]
    manifest = json.loads(Path(args.manifest).read_text())
    validate_manifest(manifest, repository)
    api = GitHub(repository, os.environ["GH_TOKEN"])
    report: dict[str, Any] = {"repository": repository, "tested_main": args.target_sha,
                              "dry_run": args.dry_run, "status": "NOT_READY", "branches": [], "deleted": []}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        current_main = api.get("branches/main")["commit"]["sha"]
        runs = api.pages("actions/runs?" + urlencode({"head_sha": args.target_sha}), "workflow_runs")
        if not args.dry_run and (current_main != args.target_sha or not gates_passed(runs, manifest["required_workflows"], args.target_sha)):
            report["reason"] = "Main moved or exact-SHA required main workflows have not all succeeded"
            return
        branches = api.pages("branches")
        open_heads = {p["head"]["ref"] for p in api.pages("pulls?state=open")}
        expected = {b["name"]: b["sha"] for b in manifest["branches"]}
        expected[manifest["integration_branch"]] = None
        candidates = []
        for branch in branches:
            name, sha = branch["name"], branch["commit"]["sha"]
            if name not in expected:
                report["branches"].append({"name": name, "sha": sha, "decision": "preserve: not in one-time inventory"})
                continue
            comparison = api.get(f"compare/{sha}...{args.target_sha}")
            ancestor = comparison["status"] in ("ahead", "identical") and comparison["behind_by"] == 0
            merged_pr = False
            if expected[name] is None:
                owner = repository.split("/")[0]
                prs = api.pages("pulls?" + urlencode({"state": "closed", "head": f"{owner}:{name}"}))
                merged_pr = any(p.get("merged_at") and p["head"]["sha"] == sha and p["base"]["ref"] == "main" for p in prs)
            reason = decision(name, sha, expected[name], protected=branch["protected"], ancestor=ancestor,
                              open_pr=name in open_heads, merged_pr=merged_pr)
            entry = {"name": name, "sha": sha, "decision": reason}
            report["branches"].append(entry)
            if reason == "eligible":
                candidates.append({"name": name, "sha": sha})
        report["status"] = "DRY_RUN" if args.dry_run else "COMPLETE"
        if candidates and not args.dry_run:
            if api.get("branches/main")["commit"]["sha"] != args.target_sha:
                raise RuntimeError("Main moved before deletion; preserving all branches")
            # Credential is passed in the subprocess environment, not a URL, argument or log.
            env = os.environ.copy()
            auth = base64.b64encode(("x-access-token:" + env["GH_TOKEN"]).encode()).decode()
            env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
                       GIT_CONFIG_VALUE_0="AUTHORIZATION: basic " + auth)
            subprocess.run(deletion_command(candidates), env=env, check=True)
            report["deleted"] = candidates
    except Exception as exc:
        report["status"] = "FAILED_CLOSED"
        report["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        output.write_text(json.dumps(report, indent=2) + "\n")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a") as stream:
                stream.write("# Manifest-bound branch cleanup\n\nStatus: **" + report["status"] + "**\n\n")
                stream.write("Target: `" + args.target_sha + "`. See the retained JSON for every branch decision.\n\n")
                stream.write("Deleted branches: " + str(len(report["deleted"])) + ". Unknown, moved, protected and divergent work is preserved.\n")


if __name__ == "__main__":
    main()
