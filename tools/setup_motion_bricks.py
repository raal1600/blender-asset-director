"""Build/register the explicitly pinned optional MotionBricks provider.

Uses an existing trusted compiler and checkout; never installs a system SDK,
modifies a production runtime, or downloads models without --download-models.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from asset_director.core import DirectorError, atomic_json, file_hash, require
from asset_director.motion_bricks_provider import (GGML_REVISION, INSTALL_SCHEMA,
    MODEL_REVISION, SOURCE_REVISION, execute)
from owned_process import OwnedCommand


def run(command, cwd, env, timeout=120):
    # CMake/compiler/download children must not outlive a timeout or the setup
    # owner. Reuse the tested platform guardian instead of killing only CMake.
    with tempfile.TemporaryDirectory(prefix="motion-bricks-setup-") as temporary:
        directory = Path(temporary)
        with (directory / "command.log").open("w+b") as log:
            try:
                owned = OwnedCommand(command, report=directory / "process.json", stdout=log,
                                     cwd=cwd, env=env, timeout=timeout, python=sys.executable)
            except OSError as exc:
                raise DirectorError("MOTION_BRICKS_SETUP_FAILED", f"Cannot start setup guardian: {exc}") from exc
            try:
                report = owned.wait(timeout=timeout + 20)
            except subprocess.TimeoutExpired as exc:
                raise DirectorError("MOTION_BRICKS_SETUP_TIMEOUT", "Setup guardian exceeded its deadline") from exc
            finally:
                owned.close()
            log.seek(0); output = log.read().decode("utf-8", "replace")
    if output:
        print(output, end="")
    require(report["state"] != "TIMED_OUT", "MOTION_BRICKS_SETUP_TIMEOUT", f"Setup command exceeded {timeout}s: {command[0]}")
    require(report["state"] == "EXITED" and report["exit_code"] == 0,
            "MOTION_BRICKS_SETUP_FAILED", f"Command failed: {command[0]}: {report.get('error', output[-2048:])}")
    return output.strip()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path, help="New isolated provider configuration path")
    p.add_argument("--library", type=Path, help="Register an already built pinned library instead of building")
    p.add_argument("--cmake", default="cmake")
    p.add_argument("--compiler-bin", type=Path)
    p.add_argument("--ninja-bin", type=Path)
    p.add_argument("--runtime-dir", action="append", default=[])
    p.add_argument("--device", choices=("cpu", "vulkan"), default="cpu")
    p.add_argument("--download-models", action="store_true")
    a = p.parse_args(argv)
    source = a.source.resolve(); output = a.output.resolve()
    require(not output.exists(), "MOTION_BRICKS_SETUP_EXISTS", "Choose a new configuration path; existing installations are preserved")
    env = dict(os.environ)
    added = [str(v.resolve()) for v in (a.compiler_bin, a.ninja_bin) if v]
    env["PATH"] = os.pathsep.join(added) + os.pathsep + env.get("PATH", "")
    require(run(["git", "rev-parse", "HEAD"], source, env) == SOURCE_REVISION,
            "MOTION_BRICKS_INSTALL_IDENTITY", "Checkout must match the exact supported source revision")
    require(run(["git", "rev-parse", "HEAD"], source / "ggml", env) == GGML_REVISION,
            "MOTION_BRICKS_INSTALL_IDENTITY", "GGML submodule must match its exact supported revision")
    for repo in (source, source / "ggml"):
        require(not run(["git", "status", "--porcelain", "--untracked-files=no"], repo, env),
                "MOTION_BRICKS_INSTALL_IDENTITY", "Tracked provider source must be clean before building/registering")
    if a.download_models:
        run([sys.executable, "-c", "import runpy,socket;socket.setdefaulttimeout(60);runpy.run_path('scripts/download_gguf_weights.py',run_name='__main__')"], source, env, 600)
    if a.library:
        library = a.library.resolve()
    else:
        build = source / ("build/asset-director-" + a.device)
        options = [a.cmake, "-S", str(source), "-B", str(build), "-G", "Ninja",
                   "-DCMAKE_BUILD_TYPE=Release", "-DMOTIONBRICKS_DOWNLOAD_MODELS=OFF",
                   "-DMOTIONBRICKS_CPU_ALL_VARIANTS=OFF", "-DMOTIONBRICKS_ENABLE_VULKAN=" + ("ON" if a.device == "vulkan" else "OFF")]
        if a.compiler_bin:
            options += ["-DCMAKE_C_COMPILER=clang", "-DCMAKE_CXX_COMPILER=clang++"]
        run(options, source, env, 180)
        run([a.cmake, "--build", str(build), "--parallel", "2"], source, env, 900)
        library = build / ("bin/libmotionbricks.dll" if os.name == "nt" else "libmotionbricks.so")
        if sys.platform == "darwin":
            library = build / "libmotionbricks.dylib"
    require(library.is_file(), "MOTION_BRICKS_MISSING_BINARY", "Build did not produce the native shared library")
    manifest = output.with_suffix(".installation.json")
    require(not manifest.exists(), "MOTION_BRICKS_SETUP_EXISTS", "Installation manifest already exists; choose a new output")
    config = {"library": str(library), "model_dir": str(source / "generated/g1-f32"),
              "python_executable": sys.executable,
              "installation_manifest": str(manifest), "device": a.device, "threads": 2,
              "runtime_dirs": list(dict.fromkeys(a.runtime_dir + added)), "timeout_seconds": 120,
              "host_memory_budget_mib": 2048, "gpu_memory_budget_mib": 8192, "gpu_headroom_mib": 2048,
              "gpu_total_limit_mib": 9216}
    atomic_json(manifest, {"schema": INSTALL_SCHEMA, "source_revision": SOURCE_REVISION,
                          "ggml_revision": GGML_REVISION, "model_revision": MODEL_REVISION,
                          "library_sha256": file_hash(library)})
    try:
        proof = execute(config)
        atomic_json(output.with_suffix(".discovery.json"), proof)
        atomic_json(output, config)
    except BaseException:
        manifest.unlink(missing_ok=True)
        raise
    print(json.dumps({"status": "CONFIGURED_AND_MODEL_LOADED", "configuration": str(output),
                      "device": a.device, "application_journey": "NOT_TESTED"}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DirectorError as exc:
        print(json.dumps(exc.as_dict()), file=sys.stderr)
        raise SystemExit(1)
