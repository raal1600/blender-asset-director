"""Small JSON CLI. No host writes; doctor reads a redacted user-level MCP declaration."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from . import __version__
from .core import DirectorError, Library, canonical, load_json, plan, require
from .providers import Providers, capabilities
from . import jobs
from . import settings


def compact_asset(a):
    return {k: a[k] for k in ("id", "provider", "source_id", "title", "kind", "source_url", "license_id", "license_url", "formats", "tags")} | {
        "local_files": len(a["local_files"]), "motion": {k:a["metadata"][k] for k in ("action", "slot", "source_object", "fps", "frame_range", "duration", "motion_family", "visual_review") if k in a["metadata"]}}


def parser():
    p = argparse.ArgumentParser(prog="asset-director", description="Search, acquire, index and adapt existing Blender assets; JSON output.")
    p.add_argument("--library", default=settings.library_path())
    s = p.add_subparsers(dest="command", required=True)
    q=s.add_parser("transfer-prepare"); q.add_argument("--review",required=True,help="Explicit approval of a completed transfer-plan job")
    q=s.add_parser("configure"); q.add_argument("--blender"); q.add_argument("--skill-path")
    s.add_parser("doctor"); s.add_parser("providers"); s.add_parser("report"); s.add_parser("rebuild-catalog")
    q=s.add_parser("plan"); q.add_argument("brief")
    q=s.add_parser("studio-plan"); q.add_argument("--brief",required=True); q.add_argument("--audit",required=True)
    q=s.add_parser("studio-handoff"); q.add_argument("--plan",required=True); q.add_argument("--proposal",required=True); q.add_argument("--audit",required=True)
    q=s.add_parser("studio-review"); q.add_argument("--review",required=True); q.add_argument("--audit",required=True); q.add_argument("--vision-available",action="store_true")
    q=s.add_parser("search"); q.add_argument("query"); q.add_argument("--provider", default="local", choices=list(capabilities())); q.add_argument("--kind", choices=["model","material","hdri","pack","animation"]); q.add_argument("--limit",type=int,default=5); q.add_argument("--refresh",action="store_true")
    q=s.add_parser("show"); q.add_argument("asset_id"); q.add_argument("--full",action="store_true")
    q=s.add_parser("acquire"); q.add_argument("asset_id"); q.add_argument("--resolution",choices=["1k","2k"],default="1k")
    q=s.add_parser("seed"); q.add_argument("--download", action="store_true", help="Explicitly acquire the free Quaternius Standard archive")
    q=s.add_parser("intake"); q.add_argument("path"); q.add_argument("--evidence",required=True)
    s.add_parser("backend-install")
    q=s.add_parser("job-prepare"); q.add_argument("operation",choices=list(jobs.OPS)); q.add_argument("--input"); q.add_argument("--asset"); q.add_argument("--options",help="Path to options JSON (not an executable script)")
    q=s.add_parser("job-run"); q.add_argument("job_id"); q.add_argument("--blender",default=settings.blender_path()); q.add_argument("--timeout",type=int,default=360)
    q=s.add_parser("job-show"); q.add_argument("job_id")
    q=s.add_parser("job-retry"); q.add_argument("job_id")
    q=s.add_parser("index-collect"); q.add_argument("asset_id"); q.add_argument("job_id")
    from .motion_cli import add_parsers
    add_parsers(s)
    return p


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        with Library(args.library) as lib:
            command=args.command
            if command.startswith("motion-") or command == "retarget-profile":
                from .motion_cli import dispatch
                result = dispatch(lib, args)
            elif command == "configure":
                result=settings.configure(library=args.library,blender=args.blender,skill_path=args.skill_path)
            elif command == "doctor":
                from .backend import verify
                try: backend_state={"status":"VERIFIED", "path":str(verify(lib))}
                except DirectorError as e: backend_state={"status":e.code}
                result={"version":__version__, "python":sys.version.split()[0], "library":str(lib.root),
                        "records":len(lib.all()), "blender_on_path":shutil.which("blender"), "backend":backend_state,
                        "providers":capabilities(), "extra_model_calls":False, "runtime_gpu_ai":False,
                        "mcp_connection":"Host must verify its existing Blender MCP; this CLI does not replace or configure it",
                        "environment":settings.health()}
            elif command == "transfer-prepare":
                from .transfer_review import prepare
                result=prepare(lib,load_json(Path(args.review)))
            elif command == "providers": result=capabilities()
            elif command == "plan": result=plan(args.brief)
            elif command == "studio-plan":
                from .studio import compile_plan
                result=compile_plan(load_json(Path(args.brief)),load_json(Path(args.audit)))
            elif command == "studio-handoff":
                from .studio import validate_handoff
                result=validate_handoff(load_json(Path(args.plan)),load_json(Path(args.proposal)),load_json(Path(args.audit)))
            elif command == "studio-review":
                from .studio import validate_review
                result=validate_review(load_json(Path(args.review)),load_json(Path(args.audit)),vision_available=args.vision_available)
            elif command == "search":
                result=Providers(lib).search(args.provider,args.query,args.kind,args.limit,args.refresh)
                for r in result["results"]: r["asset"]=compact_asset(r["asset"])
            elif command == "show":
                a=lib.get(args.asset_id).to_dict(); result=a if args.full else compact_asset(a)
            elif command == "acquire": result=Providers(lib).acquire(args.asset_id,args.resolution)
            elif command == "seed":
                provider=Providers(lib); found=provider.search("quaternius","animation")
                aid=found["results"][0]["asset"]["id"]
                result=provider.acquire(aid) if args.download else {"status":"METADATA_ONLY", "asset_id":aid, "next":"seed --download explicitly acquires the free Standard package"}
            elif command == "intake":
                from .intake import intake
                result=intake(lib,args.path,args.evidence)
            elif command == "backend-install":
                from .backend import install
                result=install(lib)
            elif command == "job-prepare":
                result=jobs.prepare(lib,args.operation,args.input,args.asset,load_json(Path(args.options)) if args.options else {})
            elif command == "job-run":
                require(args.blender, "BLENDER_NOT_FOUND", "Run configure --blender <executable>, set BAD_BLENDER, or pass job-run --blender")
                result=jobs.run(lib,args.job_id,args.blender,args.timeout)
            elif command == "job-show": result=jobs.read_job(lib,args.job_id)[0]
            elif command == "job-retry": result=jobs.retry(lib,args.job_id)
            elif command == "index-collect": result=jobs.index_result(lib,args.asset_id,args.job_id)
            elif command == "report": result=lib.export_report()
            elif command == "rebuild-catalog": result={"records":lib.rebuild()}
            else: raise DirectorError("UNKNOWN_COMMAND", "Unsupported command")
        print(canonical(result)); return 0
    except DirectorError as exc:
        print(canonical(exc.as_dict())); return 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Never dump an arbitrary response or secrets to a model through an exception string.
        print(canonical({"status":"ERROR", "code":"LOCAL_OR_SCHEMA_ERROR", "message":type(exc).__name__+": inspect the selected local input or provider schema"})); return 2

if __name__ == "__main__": raise SystemExit(main())
