"""Pinned G1 boundary inference through an isolated native worker.

This provider generates candidate motion. It does not promise exact seam pins,
contact cleanup, arbitrary-rig retargeting, or silently fall back to blending.
"""
from __future__ import annotations

import contextlib
import hashlib
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from .core import DirectorError, atomic_json, digest, file_hash, load_json, require

SOURCE_REVISION = "ee0cf5d9035f639ed0787f390fb1ce05d6a4c463"
GGML_REVISION = "8c63e70982c95ceb862e3a1073a2c1beef75d60a"
MODEL_REVISION = "cc2a47603dbc203a4f18f35dd06ed3611833f506"
MODEL_FILES = {
    "pose.gguf": (546369984, "6db82e5a67a355052f283bbcab104b71ecfc333dc8d9017c3812eb6f9650756e"),
    "root.gguf": (136504000, "46268d77e5c15449d68a39ce6ec7145e9eb457c5114d5dca934bd3ab539b29db"),
    "support.gguf": (5472, "5d41cae4bc494e612ef19e25f599351aafbc9ef1cb46d4ac3f1e42bb7ab07200"),
    "vq-decoder.gguf": (49753440, "6a1114b6906b07fab9deb18d602b4e731e1b5794318b1643ffd0605692f62d1e"),
    "manifest.json": (1101, "35321e8f760316e9a0e73619e23af4089deeedcc8efe7e7266fddbdb8d3c3cfc"),
}
CONVENTIONS = {"units": "metres", "handedness": "right", "up": "Y", "forward": "Z",
               "rotations": "local_xyzw", "fps_numerator": 30, "fps_denominator": 1}
REQUEST_SCHEMA = "asset-director.motion-bricks.request.v1"
RESULT_SCHEMA = "asset-director.motion-bricks.result.v1"
INSTALL_SCHEMA = "asset-director.motion-bricks.install.v1"
MAX_JSON = 4 * 1024 * 1024


def capabilities(config=None):
    """Discovery does not load native code or claim runtime availability."""
    return {"provider": "motion-bricks.cpp", "mode": "generated_boundary_conditioned",
            "source_revision": SOURCE_REVISION, "ggml_revision": GGML_REVISION,
            "model_revision": MODEL_REVISION, "skeleton": "g1skel34", "context_frames": 4,
            "durations_frames": list(range(24, 65, 4)), "conventions": dict(CONVENTIONS),
            "devices": ["cpu", "vulkan"], "exact_boundary_pins": False,
            "contacts": False, "arbitrary_rig_retargeting": False,
            "target_placement_modes": ["fixed", "predicted"],
            "state": "CONFIGURED_UNVERIFIED" if config else "NOT_CONFIGURED"}


def configured():
    path = os.environ.get("ASSET_DIRECTOR_MOTION_BRICKS_CONFIG")
    return load_json(Path(path), MAX_JSON) if path else None


def configuration_identity():
    """Cheap job-cache identity; execution still verifies every model checksum.

    Settings, binary/receipt content and model file signatures invalidate cache.
    This function never loads a model or makes an unavailable optional provider
    prevent ordinary native Action inspection.
    """
    path = os.environ.get("ASSET_DIRECTOR_MOTION_BRICKS_CONFIG")
    if not path:
        return digest({"provider": None})
    def signature(filename, content=False):
        try:
            file = Path(filename)
            if not file.is_file():
                return {"state": "MISSING"}
            stat = file.stat()
            return {"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns,
                    **({"sha256": file_hash(file)} if content and stat.st_size <= 64*1024*1024 else {})}
        except (OSError, TypeError, ValueError):
            return {"state": "UNAVAILABLE"}
    value = {"config": signature(path, True)}
    try:
        config = configured()
        require(isinstance(config, dict), "MOTION_BRICKS_CONFIG", "Expected provider settings")
        value.update(settings=config, library=signature(config.get("library"), True),
                     installation=signature(config.get("installation_manifest"), True))
        folder = Path(config.get("model_dir", ""))
        value["models"] = {name: signature(folder/name) for name in MODEL_FILES}
    except (DirectorError, OSError, TypeError, ValueError) as error:
        value["unavailable"] = type(error).__name__
    return digest(value)


def _number(value, label, bound=1e4):
    require(type(value) in (int, float) and math.isfinite(value) and abs(value) <= bound,
            "MOTION_BRICKS_INVALID_INPUT", f"{label} must be finite and within +/-{bound}")


def _array(value, shape, label):
    require(isinstance(value, list) and len(value) == shape[0],
            "MOTION_BRICKS_INVALID_INPUT", f"{label} requires shape {shape}")
    if len(shape) == 1:
        for v in value:
            _number(v, label)
    else:
        for v in value:
            _array(v, shape[1:], label)


def boundary_masks(request):
    """Public ABI slot masks, applied AFTER the pose helper resets them.

    Predicted placement leaves destination absolute root rows unspecified.
    Destination pose (including orientation/height) and velocity still condition
    inference. This is model prediction, not a promise of exact physical pins.
    """
    mode = request.get("target_placement", "fixed")
    require(mode in ("fixed", "predicted"), "MOTION_BRICKS_PLACEMENT",
            "Choose fixed or predicted target placement explicitly")
    return {"global_root": [1]*4 + ([0]*4 if mode == "predicted" else [1]*4),
            "local_root": [1,1,1,0,1,1,1,1], "pose": [1]*8}


def validate_request(request):
    require(isinstance(request, dict) and request.get("schema") == REQUEST_SCHEMA,
            "MOTION_BRICKS_INVALID_INPUT", "Expected versioned MotionBricks request")
    require(request.get("conventions") == CONVENTIONS, "MOTION_BRICKS_CONVENTIONS",
            "Convert evaluated poses explicitly to metres, right-handed Y-up/+Z-forward, local XYZW, 30 FPS")
    boundary_masks(request)
    frames = request.get("frames")
    require(type(frames) is int and frames in range(24, 65, 4), "MOTION_BRICKS_DURATION",
            "MotionBricks requires 24..64 frames in multiples of four, including both four-frame contexts")
    require(type(request.get("seed")) is int and 0 <= request["seed"] < 2**64,
            "MOTION_BRICKS_INVALID_INPUT", "Seed must be an unsigned 64-bit integer")
    require(type(request.get("argmax", False)) is bool, "MOTION_BRICKS_INVALID_INPUT", "argmax must be boolean")
    skeleton = request.get("skeleton", {})
    require(isinstance(skeleton, dict) and skeleton.get("id") == "g1skel34",
            "MOTION_BRICKS_UNSUPPORTED_RIG", "Only the verified G1Skeleton34 rest geometry is supported")
    names, parents = skeleton.get("joint_names"), skeleton.get("parents")
    require(isinstance(names, list) and len(names) == 34 and all(isinstance(n, str) for n in names)
            and len(set(names)) == 34, "MOTION_BRICKS_UNSUPPORTED_RIG", "Provide all 34 ordered G1 joint names")
    require(isinstance(parents, list) and len(parents) == 34 and parents[0] == -1
            and all(type(p) is int and 0 <= p < i for i, p in enumerate(parents) if i),
            "MOTION_BRICKS_UNSUPPORTED_RIG", "Provide the complete ordered G1 parent topology")
    _array(skeleton.get("neutral_joints"), (34, 3), "neutral_joints")
    for side in ("source", "target"):
        boundary = request.get(side)
        require(isinstance(boundary, dict), "MOTION_BRICKS_INVALID_INPUT", f"Missing {side} context")
        _array(boundary.get("roots"), (4, 3), f"{side}.roots")
        _array(boundary.get("local_xyzw"), (4, 34, 4), f"{side}.local_xyzw")
        for frame in boundary["local_xyzw"]:
            for q in frame:
                require(.9801 <= sum(v*v for v in q) <= 1.0201,
                        "MOTION_BRICKS_INVALID_INPUT", "Boundary quaternions must be unit length within .01")
    # Reject unknown/nonfinite metadata as part of content identity too.
    try:
        digest(request)
    except (TypeError, ValueError) as exc:
        raise DirectorError("MOTION_BRICKS_INVALID_INPUT", "Request metadata must be finite JSON data") from exc
    return request


def validate_skeleton(supplied, actual):
    require(supplied.get("id") == actual.get("id") == "g1skel34"
            and supplied.get("joint_names") == actual.get("joint_names")
            and supplied.get("parents") == actual.get("parents"),
            "MOTION_BRICKS_UNSUPPORTED_RIG", "Joint order and hierarchy do not match the loaded G1 model")
    _array(supplied.get("neutral_joints"), (34, 3), "neutral_joints")
    require(max(abs(a-b) for x, y in zip(supplied["neutral_joints"], actual["neutral_joints"])
                for a, b in zip(x, y)) <= 1e-6,
            "MOTION_BRICKS_REST_POSE", "G1 rest geometry differs from the model; matching names alone are insufficient")


def validate_result(result, request):
    require(isinstance(result, dict) and result.get("schema") == RESULT_SCHEMA and result.get("status") == "SUCCESS",
            "MOTION_BRICKS_CORRUPT_OUTPUT", "Worker did not return a successful versioned motion result")
    require(result.get("request_hash") == digest(request) and result.get("frames") == request["frames"]
            and result.get("conventions") == CONVENTIONS, "MOTION_BRICKS_CORRUPT_OUTPUT", "Worker result identity/timing mismatch")
    require(type(result.get("seed")) is int and result["seed"] == request["seed"]
            and type(result.get("argmax")) is bool and result["argmax"] == request.get("argmax", False),
            "MOTION_BRICKS_CORRUPT_OUTPUT", "Worker seed or sampling mode differs from the request")
    mode = request.get("target_placement", "fixed")
    require(result.get("target_placement", "fixed") == mode,
            "MOTION_BRICKS_CORRUPT_OUTPUT", "Worker ignored the selected target placement mode")
    if mode == "predicted" or "constraint_masks" in result:
        require(result.get("constraint_masks") == boundary_masks(request),
                "MOTION_BRICKS_CORRUPT_OUTPUT", "Worker conditioning masks differ from the request")
    try:
        _array(result.get("roots"), (request["frames"], 3), "output.roots")
        _array(result.get("local_xyzw"), (request["frames"], 34, 4), "output.local_xyzw")
        for frame in result["local_xyzw"]:
            for q in frame:
                require(.9801 <= sum(v*v for v in q) <= 1.0201,
                        "MOTION_BRICKS_CORRUPT_OUTPUT", "Output quaternion is not unit length")
    except DirectorError as exc:
        raise DirectorError("MOTION_BRICKS_CORRUPT_OUTPUT", exc.message) from exc
    require(result.get("provider") == "motion-bricks.cpp"
            and result.get("mode") == "generated_boundary_conditioned"
            and result.get("source_revision") == SOURCE_REVISION
            and result.get("ggml_revision") == GGML_REVISION
            and result.get("model_revision") == MODEL_REVISION,
            "MOTION_BRICKS_CORRUPT_OUTPUT", "Provider provenance differs from the pinned contract")
    return result


def boundary_diagnostics(request, result):
    """Compare both raw seams at identical timestamps, never adjacent positions.

    Entry = source slot 3 / output slot 3. Exit = target slot 0 / output N-4.
    Velocities are one-sided 1/30s differences in common canonical world axes.
    These are diagnostic reference thresholds, not a contact/visual acceptance.
    """
    from . import sequence_math as sm
    skeleton = request["skeleton"]; height = max(p[1] for p in skeleton["neutral_joints"]) - min(p[1] for p in skeleton["neutral_joints"])
    def fk(root, local):
        positions, rotations = [], []
        for i, xyzw in enumerate(local):
            q = sm.unit([xyzw[3], *xyzw[:3]]); parent = skeleton["parents"][i]
            world = sm.qmul(rotations[parent], q) if parent >= 0 else q
            if parent < 0:
                position = root
            else:
                offset = sm.sub(skeleton["neutral_joints"][i], skeleton["neutral_joints"][parent])
                rotated = sm.qmul(sm.qmul(rotations[parent], [0, *offset]), sm.inverse(rotations[parent]))[1:]
                position = sm.add(positions[parent], rotated)
            positions.append(position); rotations.append(world)
        return positions, rotations
    def omega(before, after):
        return sm.mul(sm.qlog(sm.qmul(after, sm.inverse(before))), 30)
    boundaries = []
    for side, sample, native_before, native_after, generated, gen_before, gen_after in (
            ("entry", 3, 2, 3, 3, 3, 4), ("exit", 0, 0, 1, request["frames"]-4, request["frames"]-5, request["frames"]-4)):
        source = request["source" if side == "entry" else "target"]
        expected_root = list(source["roots"][sample])
        placement = [0., 0., 0.]
        if side == "exit" and request.get("target_placement") == "predicted":
            # XY in Blender is XZ in this model. Placement is an output, not a pin.
            for axis in (0, 2):
                placement[axis] = result["roots"][generated][axis] - expected_root[axis]
                expected_root[axis] += placement[axis]
        expected_positions, expected_q = fk(expected_root, source["local_xyzw"][sample])
        actual_positions, actual_q = fk(result["roots"][generated], result["local_xyzw"][generated])
        _, native_q0 = fk(source["roots"][native_before], source["local_xyzw"][native_before])
        _, native_q1 = fk(source["roots"][native_after], source["local_xyzw"][native_after])
        _, actual_q0 = fk(result["roots"][gen_before], result["local_xyzw"][gen_before])
        _, actual_q1 = fk(result["roots"][gen_after], result["local_xyzw"][gen_after])
        velocity_expected = sm.mul(sm.sub(source["roots"][native_after], source["roots"][native_before]), 30)
        velocity_actual = sm.mul(sm.sub(result["roots"][gen_after], result["roots"][gen_before]), 30)
        metrics = {"boundary": side, "predicted_placement_model_m": placement, "root_position_mismatch_m": math.dist(expected_positions[0], actual_positions[0]),
            "joint_position_mismatch_m": max(math.dist(a,b) for a,b in zip(expected_positions,actual_positions)),
            "joint_orientation_mismatch_degrees": max(math.degrees(sm.norm(sm.qlog(sm.qmul(sm.inverse(a),b)))) for a,b in zip(expected_q,actual_q)),
            "root_velocity_mismatch_m_per_s": sm.norm(sm.sub(velocity_expected,velocity_actual)),
            "angular_velocity_mismatch_degrees_per_s": max(math.degrees(sm.norm(sm.sub(omega(a,b),omega(c,d))))
                for a,b,c,d in zip(native_q0,native_q1,actual_q0,actual_q1))}
        metrics["within_reference_tolerances"] = (height > 0 and metrics["joint_position_mismatch_m"] <= .001*height
            and metrics["joint_orientation_mismatch_degrees"] <= 1 and metrics["root_velocity_mismatch_m_per_s"] <= .05*height
            and metrics["angular_velocity_mismatch_degrees_per_s"] <= 5)
        boundaries.append(metrics)
    return {"status": "PASS_RAW_BOUNDARIES" if all(v["within_reference_tolerances"] for v in boundaries) else "FAIL_RAW_BOUNDARIES",
            "character_height_m": height, "same_timestamp_comparison": True,
            "derivatives": "one-sided 1/30-second differences; global angular velocity from shortest quaternion log",
            "boundaries": boundaries, "contact_quality": "NOT_VERIFIED", "visual_quality": "NOT_VERIFIED"}


def validate_config(config):
    require(isinstance(config, dict), "MOTION_BRICKS_NOT_CONFIGURED", "Configure the optional MotionBricks installation first")
    require(config.get("device", "cpu") in {"cpu", "vulkan"}, "MOTION_BRICKS_DEVICE",
            "Select cpu or vulkan explicitly; AUTO and silent fallback are not supported")
    for name, default, lower, upper in (("threads", 2, 1, 64), ("timeout_seconds", 120, .01, 3600),
            ("host_memory_budget_mib", 2048, 64, 131072), ("gpu_memory_budget_mib", 8192, 64, 131072),
            ("gpu_headroom_mib", 2048, 256, 131072), ("gpu_total_limit_mib", 9216, 256, 131072)):
        value = config.get(name, default)
        require(type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper,
                "MOTION_BRICKS_INVALID_CONFIG", f"Invalid {name}")
    require(type(config.get("threads", 2)) is int, "MOTION_BRICKS_INVALID_CONFIG", "threads must be an integer")
    require(isinstance(config.get("runtime_dirs", []), list) and all(isinstance(p, str) for p in config.get("runtime_dirs", [])),
            "MOTION_BRICKS_INVALID_CONFIG", "runtime_dirs must be a list of DLL/library directories")
    return config


def verify_installation(config, check=lambda: None):
    validate_config(config)
    library = Path(config.get("library", ""))
    require(library.is_file(), "MOTION_BRICKS_MISSING_BINARY", "Configured native MotionBricks library is missing")
    manifest_path = Path(config.get("installation_manifest", ""))
    require(manifest_path.is_file(), "MOTION_BRICKS_INSTALL_IDENTITY", "Run the pinned setup tool to create an installation manifest")
    manifest = load_json(manifest_path, MAX_JSON)
    require(manifest.get("schema") == INSTALL_SCHEMA and manifest.get("source_revision") == SOURCE_REVISION
            and manifest.get("ggml_revision") == GGML_REVISION and manifest.get("model_revision") == MODEL_REVISION,
            "MOTION_BRICKS_INSTALL_IDENTITY", "Installation revision does not match the supported pin")
    check()
    require(file_hash(library) == manifest.get("library_sha256"), "MOTION_BRICKS_INSTALL_IDENTITY", "Native library content changed after setup")
    for name, (size, expected) in MODEL_FILES.items():
        path = Path(config.get("model_dir", "")) / name
        require(path.is_file(), "MOTION_BRICKS_MISSING_MODEL", f"Missing pinned model component {name}")
        require(path.stat().st_size == size, "MOTION_BRICKS_MODEL_HASH", f"Model component size differs: {name}")
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                check(); h.update(block)
        require(h.hexdigest() == expected, "MOTION_BRICKS_MODEL_HASH", f"Model component checksum differs: {name}")
    return manifest


def _memory_mib(pid):
    if os.name == "nt":
        import ctypes as c
        from ctypes import wintypes as w
        class Counters(c.Structure):
            _fields_ = [("cb", w.DWORD), ("PageFaultCount", w.DWORD)] + [(n, c.c_size_t) for n in
                ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                 "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]
        kernel = c.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; kernel.OpenProcess.restype = w.HANDLE
        kernel.CloseHandle.argtypes = [w.HANDLE]
        psapi = c.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, c.POINTER(Counters), w.DWORD]
        handle = kernel.OpenProcess(0x1000 | 0x10, False, pid)
        if not handle:
            return None
        try:
            data = Counters(); data.cb = c.sizeof(data)
            if psapi.GetProcessMemoryInfo(handle, c.byref(data), c.sizeof(data)):
                return max(data.PeakWorkingSetSize, data.PrivateUsage) / 1048576
        finally:
            kernel.CloseHandle(handle)
    else:
        path = Path(f"/proc/{pid}/status")
        if path.is_file():
            for line in path.read_text().splitlines():
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) / 1024
    return None


def _gpu_usage():
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        run = subprocess.run(["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5, creationflags=flags)
        require(run.returncode == 0, "MOTION_BRICKS_RESOURCE_MONITOR", "nvidia-smi failed; GPU budget cannot be checked")
        rows = [tuple(float(v.strip()) for v in line.split(",")) for line in run.stdout.strip().splitlines()]
        require(len(rows) == 1 and len(rows[0]) == 2, "MOTION_BRICKS_RESOURCE_MONITOR",
                "GPU budget monitoring currently requires one NVIDIA GPU; select CPU on unsupported configurations")
        return rows[0]
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise DirectorError("MOTION_BRICKS_RESOURCE_MONITOR", "Cannot measure NVIDIA GPU memory; no silent CPU fallback") from exc


class _GpuMonitor:
    """NVIDIA NVML whole-device memory, sampled without spawning a CLI per poll.

    The public v1 memory ABI is three unsigned long long values. Its reported
    used memory includes the Windows display and other applications. This is
    sampled telemetry, not an allocator-enforced native memory limit.
    """
    def __enter__(self):
        import ctypes as c
        self.c = c; self.initialized = False
        try:
            self.lib = c.CDLL("nvml.dll" if os.name == "nt" else "libnvidia-ml.so.1")
            self.lib.nvmlInit_v2.argtypes = []; self.lib.nvmlInit_v2.restype = c.c_uint
            self.lib.nvmlShutdown.argtypes = []; self.lib.nvmlShutdown.restype = c.c_uint
            self.lib.nvmlDeviceGetCount_v2.argtypes = [c.POINTER(c.c_uint)]
            self.lib.nvmlDeviceGetHandleByIndex_v2.argtypes = [c.c_uint, c.POINTER(c.c_void_p)]
            class Memory(c.Structure):
                _fields_ = [(name, c.c_ulonglong) for name in ("total", "free", "used")]
            self.Memory = Memory
            self.lib.nvmlDeviceGetMemoryInfo.argtypes = [c.c_void_p, c.POINTER(Memory)]
            self._check(self.lib.nvmlInit_v2()); self.initialized = True
            count = c.c_uint(); self._check(self.lib.nvmlDeviceGetCount_v2(c.byref(count)))
            require(count.value == 1, "MOTION_BRICKS_RESOURCE_MONITOR",
                    "GPU budget monitoring currently requires exactly one NVIDIA GPU")
            self.device = c.c_void_p()
            self._check(self.lib.nvmlDeviceGetHandleByIndex_v2(0, c.byref(self.device)))
            return self
        except BaseException as exc:
            self.__exit__(None, None, None)
            if isinstance(exc, (OSError, AttributeError)):
                raise DirectorError("MOTION_BRICKS_RESOURCE_MONITOR", "Cannot load NVIDIA NVML memory monitor; no silent CPU fallback") from exc
            raise

    def _check(self, status):
        require(status == 0, "MOTION_BRICKS_RESOURCE_MONITOR", f"NVIDIA NVML memory query failed with status {status}")

    def sample(self):
        memory = self.Memory()
        self._check(self.lib.nvmlDeviceGetMemoryInfo(self.device, self.c.byref(memory)))
        return memory.total / 1048576, memory.used / 1048576

    def __exit__(self, *_):
        if self.initialized:
            self.lib.nvmlShutdown(); self.initialized = False


def _job_lock(check):
    from .execution_resources import gpu_lease
    return gpu_lease(check)


def execute(config, request=None, *, cancelled=None, progress=None):
    """Return a validated candidate or DirectorError; no partial result survives.

    request=None queries the loaded canonical skeleton through the same worker.
    Cancellation covers the serialized queue, model verification and execution.
    Worker RSS/private memory and whole-device NVIDIA usage are sampled; the
    GPU measurement is explicitly not attributed per-process under WDDM.
    """
    validate_config(config)
    if request is not None:
        validate_request(request)
    start = time.monotonic()
    def check():
        require(not (cancelled and cancelled()), "MOTION_BRICKS_CANCELLED", "MotionBricks job cancelled")
        require(time.monotonic() - start <= config.get("timeout_seconds", 120),
                "MOTION_BRICKS_TIMEOUT", "MotionBricks job exceeded its timeout")
    def emit(stage, **values):
        if progress:
            progress({"provider": "motion-bricks.cpp", "stage": stage, **values})
    check(); emit("queued")
    with _job_lock(check), contextlib.ExitStack() as resources:
        emit("verifying_model")
        install = verify_installation(config, check)
        gpu = resources.enter_context(_GpuMonitor()) if config.get("device", "cpu") == "vulkan" else None
        baseline_gpu = gpu.sample() if gpu else None
        if baseline_gpu:
            require(baseline_gpu[0] - baseline_gpu[1] >= config.get("gpu_headroom_mib", 2048) + 768,
                    "MOTION_BRICKS_RESOURCE_EXHAUSTED", "Insufficient GPU memory with configured display/Blender headroom")
            require(baseline_gpu[1] + 768 <= config.get("gpu_total_limit_mib", 9216),
                    "MOTION_BRICKS_RESOURCE_EXHAUSTED", "Insufficient capacity below the whole-device GPU limit")
        with tempfile.TemporaryDirectory(prefix="asset-director-motion-bricks-") as directory:
            root = Path(directory); input_path = root / "request.json"; output_path = root / "result.json"
            atomic_json(input_path, {"config": config, "request": request, "parent_pid": os.getpid()})
            env = dict(os.environ)
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]) + os.pathsep + env.get("PYTHONPATH", "")
            env["PATH"] = os.pathsep.join(config.get("runtime_dirs", [])) + os.pathsep + env.get("PATH", "")
            python = config.get("python_executable", sys.executable)
            require(isinstance(python, str) and Path(python).is_file()
                    and not ("bpy" in sys.modules and "python_executable" not in config),
                    "MOTION_BRICKS_PYTHON", "Configure the standalone worker Python executable; Blender's executable cannot launch a Python module")
            command = [python, "-m", "asset_director.motion_bricks_worker", str(input_path), str(output_path)]
            peak_host = 0.; peak_gpu = baseline_gpu[1] if baseline_gpu else None; monitor_at = 0.
            check(); emit("loading_and_inference")
            with (root / "worker.log").open("wb") as log:
                try:
                    worker = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=env,
                                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except OSError as exc:
                    raise DirectorError("MOTION_BRICKS_WORKER_START", str(exc)) from exc
                try:
                    emit("running", worker_pid=worker.pid)
                    while worker.poll() is None:
                        check()
                        memory = _memory_mib(worker.pid)
                        if memory is not None:
                            peak_host = max(peak_host, memory)
                            require(memory <= config.get("host_memory_budget_mib", 2048),
                                    "MOTION_BRICKS_RESOURCE_EXHAUSTED", "Worker exceeded configured host memory budget")
                        if baseline_gpu and time.monotonic() >= monitor_at:
                            total, used = gpu.sample(); peak_gpu = max(peak_gpu, used); monitor_at = time.monotonic() + .01
                            require(total - used >= config.get("gpu_headroom_mib", 2048)
                                    and used <= config.get("gpu_total_limit_mib", 9216)
                                    and used - baseline_gpu[1] <= config.get("gpu_memory_budget_mib", 8192),
                                    "MOTION_BRICKS_RESOURCE_EXHAUSTED", "GPU memory budget/headroom exceeded")
                        time.sleep(.02)
                    check()
                except BaseException:
                    if worker.poll() is None:
                        worker.kill()
                    worker.wait(timeout=10)
                    raise
            # Native crashes have no JSON response; preserve a bounded diagnostic
            # before the isolated temporary directory is cleaned.
            with (root / "worker.log").open("rb") as log:
                log.seek(0, 2); log.seek(max(0, log.tell() - 8192))
                native_log = log.read().decode("utf-8", "replace")
            require(output_path.is_file(), "MOTION_BRICKS_CRASH",
                    f"Native worker exited {worker.returncode} without a result: {native_log}")
            try:
                result = load_json(output_path, MAX_JSON)
            except (OSError, DirectorError) as exc:
                raise DirectorError("MOTION_BRICKS_CORRUPT_OUTPUT", "Native worker returned unreadable output") from exc
            require(isinstance(result, dict), "MOTION_BRICKS_CORRUPT_OUTPUT", "Worker response must be an object")
            if result.get("status") == "ERROR":
                raise DirectorError(result.get("code", "MOTION_BRICKS_FAILED"), str(result.get("message", "Worker failed")))
            require(worker.returncode == 0, "MOTION_BRICKS_CRASH", f"Native worker exited {worker.returncode}")
            if request is not None:
                validate_result(result, request)
                result["boundary_diagnostics"] = boundary_diagnostics(request, result)
            else:
                require(result.get("status") == "SUCCESS" and result.get("skeleton", {}).get("id") == "g1skel34",
                        "MOTION_BRICKS_CORRUPT_OUTPUT", "Skeleton discovery failed")
            require(peak_host > 0, "MOTION_BRICKS_RESOURCE_MONITOR", "Could not measure worker memory; budget acceptance is unverified")
            released_gpu = gpu.sample()[1] if gpu else None
            result["library_sha256"] = install["library_sha256"]
            result["native_log_tail"] = native_log
            result["resource_measurements"] = {"elapsed_seconds": time.monotonic() - start,
                "sampled_peak_host_mib": peak_host, "whole_gpu_baseline_mib": baseline_gpu[1] if baseline_gpu else None,
                "sampled_whole_gpu_peak_mib": peak_gpu, "gpu_attribution": "whole_device_not_per_process",
                "whole_gpu_after_worker_exit_mib": released_gpu,
                "gpu_monitor": "NVML whole-device sampled every approximately 20 ms" if gpu else None,
                "host_budget_mib": config.get("host_memory_budget_mib", 2048),
                "gpu_total_limit_mib": config.get("gpu_total_limit_mib", 9216),
                "gpu_budget_mib": config.get("gpu_memory_budget_mib", 8192), "device": config.get("device", "cpu")}
            result["artifact_hash"] = digest({k: v for k, v in result.items() if k not in {"resource_measurements", "timings", "native_log_tail"}})
            emit("validated_candidate")
            return result
