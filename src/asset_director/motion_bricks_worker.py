"""Private process entry point for the pinned MotionBricks C ABI.

Native code is imported only in this child, never in Blender or the launcher.
The result is atomically written only after validation. It is still a candidate
that requires application seam/contact acceptance before baking.
"""
from __future__ import annotations
import contextlib
import ctypes as c
import os
from pathlib import Path
import sys
import time
from .core import DirectorError, atomic_json, digest, file_hash, load_json, require
from .motion_bricks_provider import (CONVENTIONS, GGML_REVISION, MAX_JSON, MODEL_REVISION, RESULT_SCHEMA,
    SOURCE_REVISION, boundary_masks, validate_config, validate_request, validate_result, validate_skeleton)

P = c.c_void_p
U = c.c_uint64
I = c.c_uint32
F = c.c_float
ERROR_CODES = {1: "MOTION_BRICKS_INVALID_INPUT", 2: "MOTION_BRICKS_RESOURCE_EXHAUSTED",
    3: "MOTION_BRICKS_MODEL_IO", 4: "MOTION_BRICKS_MODEL_FORMAT", 5: "MOTION_BRICKS_INCOMPATIBLE_MODEL",
    6: "MOTION_BRICKS_BACKEND_UNAVAILABLE", 7: "MOTION_BRICKS_COMPUTE_FAILED",
    8: "MOTION_BRICKS_NOT_IMPLEMENTED", 9: "MOTION_BRICKS_NATIVE_ERROR"}


def _flat(value):
    for item in value:
        if isinstance(item, list):
            yield from _flat(item)
        else:
            yield item


class Native:
    def __init__(self, config):
        require('bpy' not in sys.modules, 'MOTION_BRICKS_PROCESS_ISOLATION',
                'The native model must run in standalone Python, never Blender Python')
        validate_config(config)
        self.config = config
        self.paths = contextlib.ExitStack()
        if os.name == "nt":
            for directory in [str(Path(config["library"]).resolve().parent)] + config.get("runtime_dirs", []):
                self.paths.enter_context(os.add_dll_directory(directory))
        try:
            self.lib = c.CDLL(str(Path(config["library"]).resolve()))
        except OSError as exc:
            self.paths.close()
            raise DirectorError("MOTION_BRICKS_MISSING_BINARY", f"Cannot load native library/dependencies: {exc}") from exc
        loaded = Path(config['library']).resolve()
        if os.name == 'nt':
            kernel = c.WinDLL('kernel32', use_last_error=True)
            kernel.GetModuleFileNameW.argtypes = [c.c_void_p, c.c_wchar_p, c.c_uint32]
            kernel.GetModuleFileNameW.restype = c.c_uint32
            buffer = c.create_unicode_buffer(32768)
            length = kernel.GetModuleFileNameW(self.lib._handle, buffer, len(buffer))
            require(0 < length < len(buffer), 'MOTION_BRICKS_INSTALL_IDENTITY', 'Cannot identify loaded DLL')
            loaded = Path(buffer.value).resolve()
            require(loaded == Path(config['library']).resolve(), 'MOTION_BRICKS_INSTALL_IDENTITY',
                    'Windows loaded a different native library path')
        self.loaded_library = {'path': str(loaded), 'sha256': file_hash(loaded),
                               'observation': 'GetModuleFileNameW' if os.name == 'nt' else 'explicit CDLL path'}
        self.model = P()
        self._bind()
        require(self.lib.mb_abi_version() == 1, "MOTION_BRICKS_ABI", "Expected upstream ABI version 1")
        options = P()
        try:
            self.call("mb_runtime_options_create", c.byref(options))
            self.call("mb_runtime_options_set_device", options, 1 if config.get("device", "cpu") == "cpu" else 2)
            self.call("mb_runtime_options_set_threads", options, config.get("threads", 2))
            self.call("mb_runtime_options_set_backend_directory", options, os.fsencode(Path(config["library"]).resolve().parent))
            self.call("mb_model_load", os.fsencode(config["model_dir"]), options, c.byref(self.model))
        finally:
            self.lib.mb_runtime_options_free(options)

    def _bind(self):
        signatures = {
            "mb_runtime_options_create": [c.POINTER(P)],
            "mb_runtime_options_set_device": [P, I], "mb_runtime_options_set_threads": [P, I],
            "mb_runtime_options_set_backend_directory": [P, c.c_char_p],
            "mb_model_load": [c.c_char_p, P, c.POINTER(P)],
            "mb_model_get_joint_count": [P, c.POINTER(I)],
            "mb_model_get_joint_name": [P, I, c.POINTER(c.c_char_p)],
            "mb_model_get_joint_parent": [P, I, c.POINTER(c.c_int32)],
            "mb_model_get_neutral_joint_position": [P, I, c.POINTER(F), c.POINTER(F), c.POINTER(F)],
            "mb_inference_request_create": [c.POINTER(P)],
            "mb_inference_request_set_boundary_poses": [P, P, I, c.POINTER(F), U, c.POINTER(F), U],
            "mb_inference_request_set_mask": [P, I, c.POINTER(I), U],
            "mb_inference_request_set_seed": [P, U], "mb_inference_request_set_sampling_argmax": [P, I],
            "mb_model_infer": [P, P, c.POINTER(P)],
            "mb_motion_get_frame_count": [P, c.POINTER(U)], "mb_motion_get_joint_count": [P, c.POINTER(U)],
            "mb_motion_get_root_translations": [P, c.POINTER(c.POINTER(F)), c.POINTER(U)],
            "mb_motion_get_local_rotations_xyzw": [P, c.POINTER(c.POINTER(F)), c.POINTER(U)],
        }
        try:
            self.lib.mb_abi_version.argtypes = []; self.lib.mb_abi_version.restype = I
            for name, args in signatures.items():
                function = getattr(self.lib, name); function.argtypes = args + [c.c_char_p, U]; function.restype = I
            for name in ("mb_runtime_options_free", "mb_model_free", "mb_inference_request_free", "mb_motion_free"):
                function = getattr(self.lib, name); function.argtypes = [P]; function.restype = None
        except AttributeError as exc:
            raise DirectorError("MOTION_BRICKS_ABI", f"Required stateless ABI symbol missing: {exc}") from exc

    def call(self, name, *args):
        error = c.create_string_buffer(2048)
        status = getattr(self.lib, name)(*args, error, len(error))
        require(status == 0, ERROR_CODES.get(status, "MOTION_BRICKS_NATIVE_ERROR"),
                f"{name}: {error.value.decode('utf-8', 'replace')} (native status {status})")

    def close(self):
        self.lib.mb_model_free(self.model); self.model = P(); self.paths.close()

    def skeleton(self):
        count = I(); self.call("mb_model_get_joint_count", self.model, c.byref(count))
        require(count.value == 34, "MOTION_BRICKS_INCOMPATIBLE_MODEL", "Expected G1 34-joint model")
        names, parents, neutral = [], [], []
        for i in range(34):
            name, parent = c.c_char_p(), c.c_int32()
            xyz = [F(), F(), F()]
            self.call("mb_model_get_joint_name", self.model, i, c.byref(name))
            self.call("mb_model_get_joint_parent", self.model, i, c.byref(parent))
            self.call("mb_model_get_neutral_joint_position", self.model, i, *(c.byref(v) for v in xyz))
            names.append(name.value.decode("utf-8")); parents.append(parent.value); neutral.append([v.value for v in xyz])
        return {"id": "g1skel34", "joint_names": names, "parents": parents, "neutral_joints": neutral}

    def infer(self, request):
        validate_request(request); validate_skeleton(request["skeleton"], self.skeleton())
        handle, motion = P(), P()
        started = time.monotonic()
        try:
            self.call("mb_inference_request_create", c.byref(handle))
            for i, side in enumerate(("source", "target")):
                roots = (F * 12)(*list(_flat(request[side]["roots"])))
                rotations = (F * 544)(*list(_flat(request[side]["local_xyzw"])))
                self.call("mb_inference_request_set_boundary_poses", handle, self.model, i, roots, 12, rotations, 544)
            masks = boundary_masks(request)
            for field, name in enumerate(("global_root", "local_root", "pose")):
                self.call("mb_inference_request_set_mask", handle, field, (I * 8)(*masks[name]), 8)
            durations = (I * 11)(*[int(24 + 4*i == request["frames"]) for i in range(11)])
            self.call("mb_inference_request_set_mask", handle, 3, durations, 11)
            self.call("mb_inference_request_set_seed", handle, request["seed"])
            self.call("mb_inference_request_set_sampling_argmax", handle, int(request.get("argmax", False)))
            inference_start = time.monotonic()
            self.call("mb_model_infer", self.model, handle, c.byref(motion))
            inference_end = time.monotonic()
            frames, joints = U(), U()
            self.call("mb_motion_get_frame_count", motion, c.byref(frames))
            self.call("mb_motion_get_joint_count", motion, c.byref(joints))
            require(frames.value == request["frames"] and joints.value == 34,
                    "MOTION_BRICKS_CORRUPT_OUTPUT", "Native output shape differs from requested G1 motion")
            root_ptr, quat_ptr, count = c.POINTER(F)(), c.POINTER(F)(), U()
            self.call("mb_motion_get_root_translations", motion, c.byref(root_ptr), c.byref(count))
            require(count.value == frames.value * 3, "MOTION_BRICKS_CORRUPT_OUTPUT", "Native root buffer size mismatch")
            roots = [[root_ptr[f*3+j] for j in range(3)] for f in range(frames.value)]
            self.call("mb_motion_get_local_rotations_xyzw", motion, c.byref(quat_ptr), c.byref(count))
            require(count.value == frames.value * 136, "MOTION_BRICKS_CORRUPT_OUTPUT", "Native rotation buffer size mismatch")
            rotations = [[[quat_ptr[(f*34+j)*4+k] for k in range(4)] for j in range(34)] for f in range(frames.value)]
            result = {"schema": RESULT_SCHEMA, "status": "SUCCESS", "provider": "motion-bricks.cpp",
                "mode": "generated_boundary_conditioned", "source_revision": SOURCE_REVISION,
                "ggml_revision": GGML_REVISION,
                "model_revision": MODEL_REVISION, "device": self.config.get("device", "cpu"),
                "request_hash": digest(request), "frames": frames.value, "conventions": dict(CONVENTIONS),
                "target_placement": request.get("target_placement", "fixed"), "constraint_masks": masks,
                "roots": roots, "local_xyzw": rotations, "seed": request["seed"], "argmax": request.get("argmax", False),
                "loaded_library": self.loaded_library,
                "timings": {"inference_seconds": inference_end-inference_start,
                            "request_conversion_seconds": inference_start-started,
                            "output_conversion_seconds": time.monotonic()-inference_end,
                            "inference_request_seconds": time.monotonic()-started},
                "acceptance": "CANDIDATE_REQUIRES_SEAM_AND_CONTACT_VALIDATION", "exact_boundary_pins": False}
            return validate_result(result, request)
        finally:
            self.lib.mb_motion_free(motion)
            self.lib.mb_inference_request_free(handle)


def _watch_parent(parent_pid):
    """Exit the isolated native process if its owning application is killed.

    A Windows process handle identifies the original process even if the PID
    is recycled. ctypes releases the GIL during inference, so this watchdog
    continues to run while native computation is active.
    """
    import threading
    require(type(parent_pid) is int and parent_pid > 0, "MOTION_BRICKS_WORKER_OWNER", "Missing owning process identity")
    if os.name == "nt":
        from ctypes import wintypes as w
        kernel = c.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; kernel.OpenProcess.restype = w.HANDLE
        kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]; kernel.WaitForSingleObject.restype = w.DWORD
        kernel.CloseHandle.argtypes = [w.HANDLE]
        handle = kernel.OpenProcess(0x100000, False, parent_pid)
        require(bool(handle), "MOTION_BRICKS_WORKER_OWNER", "Owning application has already exited")
        def watch():
            try:
                while True:
                    status = kernel.WaitForSingleObject(handle, 100)
                    if status != 258:  # WAIT_TIMEOUT; signalled/dead or invalid owner
                        os._exit(125)
            finally:
                kernel.CloseHandle(handle)
    else:
        require(os.getppid() == parent_pid, "MOTION_BRICKS_WORKER_OWNER", "Owning application has already exited")
        def watch():
            while True:
                if os.getppid() != parent_pid:
                    os._exit(125)
                time.sleep(.1)
    threading.Thread(target=watch, name="motion-bricks-owner-watch", daemon=True).start()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        return 2
    output = Path(argv[1]); native = None
    try:
        payload = load_json(Path(argv[0]), MAX_JSON)
        _watch_parent(payload.get("parent_pid"))
        started = time.monotonic(); native = Native(payload["config"])
        loading_seconds = time.monotonic() - started
        if payload.get("request") is None:
            result = {"status": "SUCCESS", "skeleton": native.skeleton(), "source_revision": SOURCE_REVISION,
                      "loaded_library": native.loaded_library,
                      "ggml_revision": GGML_REVISION,
                      "model_revision": MODEL_REVISION, "timings": {"loading_seconds": loading_seconds}}
        else:
            result = native.infer(payload["request"])
            result["timings"]["loading_seconds"] = loading_seconds
        atomic_json(output, result)
        return 0
    except DirectorError as exc:
        atomic_json(output, exc.as_dict()); return 1
    except Exception as exc:
        atomic_json(output, {"status": "ERROR", "code": "MOTION_BRICKS_WORKER_ERROR", "message": str(exc)}); return 1
    finally:
        if native is not None:
            native.close()


if __name__ == "__main__":
    raise SystemExit(main())
