"""Offline provider-contract failures; no mocked test claims native inference."""
import copy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from asset_director.core import DirectorError, atomic_json, digest, file_hash
from asset_director import motion_bricks_provider as provider


def request():
    return {"schema": provider.REQUEST_SCHEMA, "frames": 40, "seed": 7,
            "conventions": dict(provider.CONVENTIONS),
            "skeleton": {"id": "g1skel34", "joint_names": [f"j{i}" for i in range(34)],
                         "parents": [-1] + [0]*33, "neutral_joints": [[0., 0., 0.] for _ in range(34)]},
            **{side: {"roots": [[0., .8, f*.01] for f in range(4)],
                      "local_xyzw": [[[0., 0., 0., 1.] for _ in range(34)] for _ in range(4)]}
               for side in ("source", "target")}}


def result(value):
    return {"schema": provider.RESULT_SCHEMA, "status": "SUCCESS", "frames": value["frames"],
            "conventions": dict(provider.CONVENTIONS), "request_hash": digest(value),
            "seed": value["seed"], "argmax": value.get("argmax", False),
            "provider": "motion-bricks.cpp", "mode": "generated_boundary_conditioned",
            "source_revision": provider.SOURCE_REVISION, "model_revision": provider.MODEL_REVISION,
            "ggml_revision": provider.GGML_REVISION,
            "roots": [[0., .8, 0.] for _ in range(value["frames"])],
            "local_xyzw": [[[0., 0., 0., 1.] for _ in range(34)] for _ in range(value["frames"])]}


class MotionBricksContractTests(unittest.TestCase):
    def fails(self, code, function, *args):
        with self.assertRaises(DirectorError) as error:
            function(*args)
        self.assertEqual(error.exception.code, code)

    def test_output_records_the_actual_seed_and_sampling_mode(self):
        value = request(); value['argmax'] = True
        good = result(value); provider.validate_result(good, value)
        for patch in ({'seed': 99}, {'seed': True}, {'argmax': False}, {'argmax': 1}):
            self.fails('MOTION_BRICKS_CORRUPT_OUTPUT', provider.validate_result, {**good, **patch}, value)

    def test_discovery_is_honest_about_soft_constraints(self):
        value = provider.capabilities()
        self.assertFalse(value["exact_boundary_pins"])
        self.assertFalse(value["arbitrary_rig_retargeting"])
        self.assertEqual(value["state"], "NOT_CONFIGURED")
        self.assertEqual(value["durations_frames"], list(range(24,65,4)))

    def test_only_explicit_canonical_conventions(self):
        for key, bad in (("up", "Z"), ("rotations", "local_wxyz"), ("units", "centimetres"),
                         ("fps_numerator", 60), ("fps_denominator", 1.001)):
            with self.subTest(key=key):
                value = request(); value["conventions"][key] = bad
                self.fails("MOTION_BRICKS_CONVENTIONS", provider.validate_request, value)

    def test_duration_rejects_boolean_and_unsupported_windows(self):
        for frames in (True, 23, 25, 65, 40.0):
            value = request(); value["frames"] = frames
            self.fails("MOTION_BRICKS_DURATION", provider.validate_request, value)

    def test_finite_values_and_quaternion_convention(self):
        for bad in (math.nan, math.inf, 10001, True):
            value = request(); value["source"]["roots"][0][0] = bad
            self.fails("MOTION_BRICKS_INVALID_INPUT", provider.validate_request, value)
        value = request(); value["source"]["local_xyzw"][0][0] = [0,0,0,0]
        self.fails("MOTION_BRICKS_INVALID_INPUT", provider.validate_request, value)
        value = request(); value["source"]["local_xyzw"][0][0] = [0,0,0,-1]
        self.assertIs(provider.validate_request(value), value)

    def test_four_frames_and_all_joints_are_required(self):
        value = request(); value["target"]["local_xyzw"][1].pop()
        self.fails("MOTION_BRICKS_INVALID_INPUT", provider.validate_request, value)
        value = request(); value["source"]["roots"].append([0,0,0])
        self.fails("MOTION_BRICKS_INVALID_INPUT", provider.validate_request, value)

    def test_matching_names_does_not_validate_rest_or_parenting(self):
        actual = request()["skeleton"]
        for field in ("neutral_joints", "parents", "joint_names"):
            supplied = copy.deepcopy(actual)
            if field == "neutral_joints": supplied[field][1][1] = .01
            elif field == "parents": supplied[field][2] = 1
            else: supplied[field][1], supplied[field][2] = supplied[field][2], supplied[field][1]
            self.fails("MOTION_BRICKS_REST_POSE" if field == "neutral_joints" else "MOTION_BRICKS_UNSUPPORTED_RIG",
                       provider.validate_skeleton, supplied, actual)

    def test_output_is_bound_to_full_request(self):
        value = request(); output = result(value)
        self.assertIs(provider.validate_result(output, value), output)
        for field in ("seed", "frames", "source", "skeleton"):
            changed = copy.deepcopy(value)
            if field == "seed": changed[field] += 1
            elif field == "frames": changed[field] = 44
            elif field == "source": changed[field]["roots"][0][0] += .1
            else: changed[field]["neutral_joints"][0][0] += .1
            self.fails("MOTION_BRICKS_CORRUPT_OUTPUT", provider.validate_result, output, changed)

    def test_corrupt_output_and_fake_fallback_are_rejected(self):
        value = request()
        for edit in (lambda x: x["roots"].pop(), lambda x: x["local_xyzw"][0][0].__setitem__(0, math.nan),
                     lambda x: x.__setitem__("mode", "deterministic_blend"),
                     lambda x: x.__setitem__("source_revision", "different")):
            output = result(value); edit(output)
            self.fails("MOTION_BRICKS_CORRUPT_OUTPUT", provider.validate_result, output, value)

    def test_missing_binary_does_not_start_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = {"library": str(Path(temporary)/"missing.dll")}
            with patch.object(provider.subprocess, "Popen") as popen:
                self.fails("MOTION_BRICKS_MISSING_BINARY", provider.execute, config, request())
                popen.assert_not_called()

    def test_cancel_before_execution_has_no_partial_artifact(self):
        with patch.object(provider.subprocess, "Popen") as popen:
            with self.assertRaises(DirectorError) as error:
                provider.execute({}, request(), cancelled=lambda: True)
            self.assertEqual(error.exception.code, "MOTION_BRICKS_CANCELLED")
            popen.assert_not_called()

    def test_missing_or_corrupt_model_is_rejected_before_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); binary = root / "test-library.bin"; binary.write_bytes(b"unit-contract-only")
            manifest = root / "manifest.json"
            atomic_json(manifest, {"schema": provider.INSTALL_SCHEMA, "source_revision": provider.SOURCE_REVISION,
                "ggml_revision": provider.GGML_REVISION, "model_revision": provider.MODEL_REVISION,
                "library_sha256": file_hash(binary)})
            config = {"library": str(binary), "installation_manifest": str(manifest), "model_dir": str(root)}
            with patch.object(provider.subprocess, "Popen") as popen:
                self.fails("MOTION_BRICKS_MISSING_MODEL", provider.execute, config, request())
                (root / "pose.gguf").write_bytes(b"corrupt")
                self.fails("MOTION_BRICKS_MODEL_HASH", provider.execute, config, request())
                popen.assert_not_called()

    def test_moving_seams_compare_same_timestamp_not_adjacent_frames(self):
        value = request(); output = result(value)
        value["skeleton"]["neutral_joints"][1][1] = 1.
        output["roots"] = [[0., .8, i*.01] for i in range(40)]
        value["source"]["roots"] = copy.deepcopy(output["roots"][:4])
        value["target"]["roots"] = copy.deepcopy(output["roots"][-4:])
        checks = provider.boundary_diagnostics(value, output)
        self.assertEqual(checks["status"], "PASS_RAW_BOUNDARIES")
        output["roots"][3][0] = .01
        self.assertEqual(provider.boundary_diagnostics(value, output)["status"], "FAIL_RAW_BOUNDARIES")

    def test_predicted_placement_preserves_pose_and_velocity_constraints(self):
        value = request(); value["target_placement"] = "predicted"
        self.assertIs(provider.validate_request(value), value)
        masks = provider.boundary_masks(value)
        self.assertEqual(masks["global_root"], [1,1,1,1,0,0,0,0])
        self.assertEqual(masks["local_root"], [1,1,1,0,1,1,1,1])
        self.assertEqual(masks["pose"], [1]*8)
        self.assertEqual(provider.boundary_masks(request())["global_root"], [1]*8)
        for bad in ("automatic", None, True, "blended"):
            value["target_placement"] = bad
            self.fails("MOTION_BRICKS_PLACEMENT", provider.validate_request, value)

    def test_result_cannot_silently_ignore_predicted_placement(self):
        value = request(); value["target_placement"] = "predicted"
        output = result(value)
        self.fails("MOTION_BRICKS_CORRUPT_OUTPUT", provider.validate_result, output, value)
        output["target_placement"] = "predicted"
        output["constraint_masks"] = provider.boundary_masks(value)
        self.assertIs(provider.validate_result(output, value), output)
        output["constraint_masks"]["global_root"][-1] = 1
        self.fails("MOTION_BRICKS_CORRUPT_OUTPUT", provider.validate_result, output, value)

    def test_auto_and_nonfinite_budgets_rejected(self):
        self.fails("MOTION_BRICKS_DEVICE", provider.validate_config, {"device": "auto"})
        for budget in (math.nan, 0, True, -1):
            self.fails("MOTION_BRICKS_INVALID_CONFIG", provider.validate_config, {"host_memory_budget_mib": budget})


if __name__ == "__main__":
    unittest.main()
