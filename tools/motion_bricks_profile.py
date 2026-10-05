"""Measure real model cold/warm latency and resource release in an owned child.

This diagnostic deliberately retains one model for repeated calls. Production
jobs continue to use one native subprocess per request and release it afterward.
"""
from pathlib import Path
import argparse
import contextlib
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from asset_director.core import atomic_json, digest, load_json, require
from asset_director.motion_bricks_provider import _GpuMonitor, _job_lock, _memory_mib, verify_installation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--child", type=int)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    config = load_json(args.config)
    if args.child is not None:
        from asset_director.motion_bricks_worker import Native, _watch_parent
        _watch_parent(args.child)
        request = load_json(args.request)
        started = time.monotonic(); native = Native(config)
        loading = time.monotonic() - started
        hashes, timings = [], []
        try:
            for _ in range(30):
                result = native.infer(request)
                hashes.append(digest([result["roots"], result["local_xyzw"]]))
                timings.append(result["timings"]["inference_seconds"])
            require(len(set(hashes)) == 1, "FIXTURE_REPEATABILITY", "Warm inference with the same seed changed")
        finally:
            native.close()
        atomic_json(args.output / "native-profile.json", {"loading_seconds": loading,
            "first_inference_seconds": timings[0], "warm_inference_seconds": timings[1:],
            "pose_hash": hashes[0], "same_model_repeated_inference": "EXACT", "calls": len(hashes)})
        return
    require(not (args.output / "native-profile.json").exists(), "FIXTURE_OUTPUT_EXISTS", "Use a fresh profiling directory")
    started = time.monotonic()
    def check():
        require(time.monotonic() - started < 120, "FIXTURE_TIMEOUT", "Profile exceeded its 120-second bound")
    with _job_lock(check), contextlib.ExitStack() as stack:
        verify_installation(config, check)
        gpu = stack.enter_context(_GpuMonitor()) if config.get("device") == "vulkan" else None
        baseline = gpu.sample() if gpu else None
        peak_gpu = baseline[1] if baseline else None; peak_host = 0.; samples = []
        command = [sys.executable, str(Path(__file__).resolve()), "--config", str(args.config),
            "--request", str(args.request), "--output", str(args.output), "--child", str(os.getpid())]
        with (args.output / "native.log").open("wb") as log:
            child = subprocess.Popen(command, stdout=log, stderr=log,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                while child.poll() is None:
                    check(); memory = _memory_mib(child.pid)
                    if memory is not None:
                        peak_host = max(peak_host, memory)
                        require(memory <= config.get("host_memory_budget_mib", 2048), "FIXTURE_HOST_BUDGET", "Host memory limit exceeded")
                    if gpu:
                        total, used = gpu.sample(); peak_gpu = max(peak_gpu, used)
                        samples.append([time.monotonic() - started, used])
                        require(used <= config.get("gpu_total_limit_mib", 9216)
                            and total-used >= config.get("gpu_headroom_mib", 2048)
                            and used-baseline[1] <= config.get("gpu_memory_budget_mib", 8192),
                            "FIXTURE_GPU_BUDGET", "GPU memory budget/headroom exceeded")
                    time.sleep(.01)
                require(child.returncode == 0, "FIXTURE_PROFILE_FAILED", f"Native profile exited {child.returncode}; inspect native.log")
            finally:
                if child.poll() is None: child.kill()
                child.wait(timeout=10)
        after = gpu.sample()[1] if gpu else None
        require(peak_host > 0, "FIXTURE_NO_MEASUREMENT", "No memory sample captured")
        if gpu:
            require(after <= baseline[1] + 32, "FIXTURE_GPU_RELEASE", "Whole-device memory did not return within32MiB of baseline")
        result = {"status": "PASS_REAL_COLD_WARM_PROFILE", "device": config.get("device", "cpu"),
            **load_json(args.output / "native-profile.json"), "sampled_peak_host_mib": peak_host,
            "whole_gpu_baseline_mib": baseline[1] if baseline else None, "sampled_whole_gpu_peak_mib": peak_gpu,
            "whole_gpu_after_exit_mib": after, "gpu_samples": len(samples),
            "gpu_measurement": "NVML whole-device, approximately10ms samples; includes unrelated display use" if gpu else None,
            "elapsed_seconds": time.monotonic()-started}
        atomic_json(args.output / "gpu-samples.json", samples)
        atomic_json(args.output / "summary.json", result)
        print(result)


if __name__ == "__main__":
    main()
