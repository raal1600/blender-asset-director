"""Camera-plan contract and projection math (portable: no Blender import)."""
import math
from pathlib import Path
import tempfile
import unittest

from asset_director import camera_plan as contract
from asset_director import jobs
from asset_director.core import DirectorError, Library


def checkpoint(frame=1, **kw):
    entry = {"frame": frame, "aim": {"subject": "Opaque Subject.004"},
             "direction": [0.2, -1.0, 0.15], "distance": 8.5}
    entry.update(kw)
    if "position" in kw and "direction" not in kw:
        entry.pop("direction", None); entry.pop("distance", None); entry.pop("fit", None)
    return entry


def plan(**kw):
    data = {"mode": "create", "subjects": ["Opaque Subject.004"], "lens_mm": 40,
            "keyframes": [checkpoint()]}
    data.update(kw)
    return data


def error_code(callable_, *args, **kw):
    with unittest.TestCase().assertRaises(DirectorError) as caught:
        callable_(*args, **kw)
    return caught.exception.code


class ContractCase(unittest.TestCase):
    def test_minimal_plan_normalizes_explicit_defaults(self):
        result = contract.validate(plan())
        self.assertEqual(result["mode"], "create")
        self.assertEqual(result["sensor_fit"], "AUTO")
        self.assertEqual(result["projection"], "PERSP")
        self.assertEqual(result["constraints"], "mute")
        self.assertEqual(result["existing_animation"], "preserve")
        self.assertTrue(result["set_scene_camera"])
        self.assertEqual(result["keyframes"][0]["screen"], [0.5, 0.5])
        self.assertEqual(result["interpolation"],
                         {"type": "BEZIER", "easing": "AUTO", "handle_left": "AUTO_CLAMPED",
                          "handle_right": "AUTO_CLAMPED", "extrapolation": "CONSTANT"})

    def test_no_scene_specific_defaults(self):
        """A plan carries only what the caller supplied; nothing is invented."""
        result = contract.validate(plan())
        self.assertIsNone(result["fps"])
        self.assertIsNone(result["frame_range"])
        self.assertIsNone(result["roll_deg"])
        self.assertIsNone(result["dof"])
        self.assertIsNone(result["name"])
        self.assertIsNone(result["camera"])

    def test_unknown_top_level_field_rejected(self):
        self.assertEqual(error_code(contract.validate, plan(hero_shot=True)), "INVALID_SCHEMA")

    def test_unknown_checkpoint_field_rejected(self):
        self.assertEqual(error_code(contract.validate, plan(keyframes=[checkpoint(lens="wide")])),
                         "INVALID_SCHEMA")

    def test_keyframe_count_and_frame_bounds(self):
        self.assertEqual(error_code(contract.validate, plan(keyframes=[])), "RESOURCE_LIMIT")
        many = [checkpoint(frame=i) for i in range(1, contract.MAX_CHECKPOINTS + 2)]
        self.assertEqual(error_code(contract.validate, plan(keyframes=many)), "RESOURCE_LIMIT")

    def test_frames_must_strictly_increase(self):
        self.assertEqual(error_code(contract.validate, plan(keyframes=[checkpoint(12), checkpoint(12)])),
                         "INVALID_TIMEBASE")
        self.assertEqual(error_code(contract.validate, plan(keyframes=[checkpoint(9), checkpoint(3)])),
                         "INVALID_TIMEBASE")
        self.assertEqual(error_code(contract.validate, plan(keyframes=[checkpoint(1.5)])), "INVALID_TIMEBASE")

    def test_aim_variants(self):
        self.assertEqual(error_code(contract.validate, plan(keyframes=[checkpoint(aim={})])), "AIM_REQUIRED")
        both = {"subject": "Opaque Subject.004", "point": [0, 0, 0]}
        self.assertEqual(error_code(contract.validate, plan(keyframes=[checkpoint(aim=both)])), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate,
                                    plan(keyframes=[checkpoint(aim={"subject": "x", "bounds": [0, 2, 0.5]})])),
                         "INVALID_SCHEMA")
        point = contract.validate(plan(keyframes=[checkpoint(aim={"point": [1, 2, 3]})]))
        self.assertEqual(point["keyframes"][0]["aim"], {"point": [1.0, 2.0, 3.0]})
        head = contract.validate(plan(keyframes=[checkpoint(aim={"subject": "Opaque Subject.004",
                                                                 "bounds": [0.5, 0.5, 0.92]})]))
        self.assertEqual(head["keyframes"][0]["aim"]["bounds"], [0.5, 0.5, 0.92])

    def test_placement_variants(self):
        self.assertEqual(error_code(contract.validate, plan(keyframes=[checkpoint(position=[0, 0, 0],
                                                                                 direction=[0, -1, 0])])),
                         "PLACEMENT_REQUIRED")
        no_placement = {"frame": 1, "aim": {"subject": "Opaque Subject.004"}}
        self.assertEqual(error_code(contract.validate, plan(keyframes=[no_placement])), "PLACEMENT_REQUIRED")
        zero = checkpoint(direction=[0, 0, 0])
        self.assertEqual(error_code(contract.validate, plan(keyframes=[zero])), "DIRECTION_REQUIRED")
        both_distance = checkpoint(fit={"margin": 0.1})
        self.assertEqual(error_code(contract.validate, plan(keyframes=[both_distance])), "PLACEMENT_REQUIRED")
        neither = {"frame": 1, "aim": {"subject": "Opaque Subject.004"}, "direction": [0, -1, 0]}
        self.assertEqual(error_code(contract.validate, plan(keyframes=[neither])), "PLACEMENT_REQUIRED")
        fitted = contract.validate(plan(keyframes=[{"frame": 1, "aim": {"subject": "Opaque Subject.004"},
                                                    "direction": [0, -1, 0], "fit": {"margin": 0.25}}]))
        self.assertEqual(fitted["keyframes"][0]["fit"], {"margin": 0.25})
        self.assertEqual(error_code(contract.validate, plan(keyframes=[{"frame": 1,
                                                                        "aim": {"subject": "Opaque Subject.004"},
                                                                        "direction": [0, -1, 0],
                                                                        "fit": {"margin": 0.5}}])),
                         "INVALID_SCHEMA")

    def test_position_plan_accepts_world_coordinates(self):
        result = contract.validate(plan(keyframes=[checkpoint(position=[12.5, -40, 6.25])]))
        self.assertEqual(result["keyframes"][0]["position"], [12.5, -40.0, 6.25])

    def test_screen_target_bounds(self):
        self.assertEqual(error_code(contract.validate, plan(keyframes=[checkpoint(screen=[1.4, 0.5])])),
                         "SCREEN_TARGET_INVALID")
        self.assertEqual(error_code(contract.validate, plan(keyframes=[checkpoint(screen=[0.5])])),
                         "SCREEN_TARGET_INVALID")
        off_centre = contract.validate(plan(keyframes=[checkpoint(screen=[0.32, 0.61])]))
        self.assertEqual(off_centre["keyframes"][0]["screen"], [0.32, 0.61])

    def test_lens_is_required_and_bounded(self):
        self.assertEqual(error_code(contract.validate, plan(lens_mm=None)), "LENS_REQUIRED")
        self.assertEqual(error_code(contract.validate, plan(lens_mm=0.5)), "LENS_REQUIRED")
        self.assertEqual(error_code(contract.validate, plan(lens_mm=5000)), "LENS_REQUIRED")
        per_checkpoint = contract.validate({"mode": "create", "subjects": ["Opaque Subject.004"],
                                            "keyframes": [checkpoint(lens_mm=85)]})
        self.assertEqual(per_checkpoint["keyframes"][0]["lens_mm"], 85.0)

    def test_mode_specific_fields(self):
        self.assertEqual(error_code(contract.validate, plan(mode="adapt")), "CAMERA_REQUIRED")
        self.assertEqual(error_code(contract.validate, plan(mode="adapt", camera="Cam", name="New")),
                         "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate, plan(camera="Cam")), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate, plan(mode="teleport")), "INVALID_SCHEMA")

    def test_orthographic_plan_is_rejected_explicitly(self):
        self.assertEqual(error_code(contract.validate, plan(projection="ORTHO")), "UNSUPPORTED_PROJECTION")

    def test_sensor_and_rotation_options(self):
        for value in ("AUTO", "HORIZONTAL", "VERTICAL"):
            self.assertEqual(contract.validate(plan(sensor_fit=value))["sensor_fit"], value)
        self.assertEqual(error_code(contract.validate, plan(sensor_fit="DIAGONAL")), "INVALID_SCHEMA")
        self.assertEqual(contract.validate(plan(rotation_mode="YXZ"))["rotation_mode"], "YXZ")
        self.assertEqual(error_code(contract.validate, plan(rotation_mode="QWERTY")), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate, plan(sensor_width_mm=0)), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate, plan(roll_deg=400)), "INVALID_SCHEMA")

    def test_interpolation_options(self):
        out = contract.validate(plan(interpolation={"type": "LINEAR", "easing": "EASE_IN_OUT",
                                                    "handle_left": "VECTOR", "handle_right": "AUTO",
                                                    "extrapolation": "LINEAR"}))
        self.assertEqual(out["interpolation"]["type"], "LINEAR")
        self.assertEqual(out["interpolation"]["extrapolation"], "LINEAR")
        self.assertEqual(error_code(contract.validate, plan(interpolation={"type": "BOUNCE"})), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate, plan(interpolation={"handles": "AUTO"})), "INVALID_SCHEMA")

    def test_dof_options(self):
        out = contract.validate(plan(dof={"use_dof": True, "focus_object": "Aim.001", "focus_distance": 9.0}))
        self.assertEqual(out["dof"], {"use_dof": True, "focus_object": "Aim.001", "focus_distance": 9.0})
        self.assertEqual(contract.validate(plan(dof={"focus_object": None}))["dof"], {"focus_object": None})
        self.assertEqual(error_code(contract.validate, plan(dof={"focus_distance": -2})), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate, plan(dof={"use_dof": "yes"})), "INVALID_SCHEMA")
        override = contract.validate(plan(dof={"use_dof": True},
                                          keyframes=[checkpoint(dof={"focus_distance": 4.5})]))
        self.assertEqual(override["keyframes"][0]["dof"], {"focus_distance": 4.5})

    def test_frame_range_and_fps_are_explicit(self):
        out = contract.validate(plan(frame_range=[12, 60], fps=29.97))
        self.assertEqual(out["frame_range"], [12, 60])
        self.assertAlmostEqual(out["fps"], 29.97)
        self.assertEqual(error_code(contract.validate, plan(frame_range=[60, 12])), "INVALID_TIMEBASE")
        self.assertEqual(error_code(contract.validate, plan(frame_range=[1])), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate, plan(fps=0)), "INVALID_SCHEMA")

    def test_adaptation_policies(self):
        base = plan(mode="adapt", camera="Camera")
        self.assertEqual(contract.validate(base)["existing_animation"], "preserve")
        self.assertEqual(contract.validate(plan(mode="adapt", camera="Camera",
                                                existing_animation="clear"))["existing_animation"], "clear")
        self.assertEqual(error_code(contract.validate, plan(mode="adapt", camera="Camera",
                                                            existing_animation="delete")), "INVALID_SCHEMA")
        self.assertEqual(contract.validate(plan(mode="adapt", camera="Camera",
                                                constraints="keep"))["constraints"], "keep")
        self.assertEqual(error_code(contract.validate, plan(mode="adapt", camera="Camera",
                                                            constraints="remove")), "INVALID_SCHEMA")

    def test_subjects_are_bounded_and_unique(self):
        self.assertEqual(error_code(contract.validate, plan(subjects=[])), "SUBJECTS_REQUIRED")
        self.assertEqual(error_code(contract.validate, plan(subjects=["a", "a"])), "SUBJECTS_REQUIRED")
        self.assertEqual(error_code(contract.validate, plan(subjects=[1])), "SUBJECTS_REQUIRED")


class ProjectionMathCase(unittest.TestCase):
    def test_sensor_extents_follow_fit_and_aspect(self):
        self.assertEqual(contract.sensor_extents(36.0, 24.0, "AUTO", (1920, 1080)), (36.0, 36.0 * 1080 / 1920))
        self.assertEqual(contract.sensor_extents(36.0, 24.0, "AUTO", (1080, 1920)), (36.0 * 1080 / 1920, 36.0))
        self.assertEqual(contract.sensor_extents(36.0, 24.0, "HORIZONTAL", (1000, 4000)), (36.0, 144.0))
        # VERTICAL pins the declared sensor *height* to the image height.
        self.assertEqual(contract.sensor_extents(36.0, 24.0, "VERTICAL", (4000, 1000)), (96.0, 24.0))
        self.assertEqual(contract.sensor_extents(36.0, 24.0, "VERTICAL", (1920, 1080)),
                         (24.0 * 16 / 9, 24.0))
        wide, tall = contract.sensor_extents(36.0, 24.0, "AUTO", (1920, 1080), (2.0, 1.0))
        self.assertEqual((wide, tall), (36.0, 36.0 * 1080 / 3840))
        flipped, flipped_tall = contract.sensor_extents(36.0, 24.0, "AUTO", (1920, 1080), (1.0, 2.0))
        self.assertEqual((flipped, flipped_tall), (36.0 * 1920 / 2160, 36.0))

    def test_sensor_height_is_declared_not_inferred(self):
        self.assertEqual(contract.validate(plan())["sensor_height_mm"], 24.0)
        self.assertEqual(contract.validate(plan(sensor_height_mm=18.0))["sensor_height_mm"], 18.0)
        self.assertEqual(error_code(contract.validate, plan(sensor_height_mm=0)), "INVALID_SCHEMA")

    def test_half_angles_match_the_sensor(self):
        half_h, half_v = contract.half_angles(36.0, 36.0, 18.0)
        self.assertAlmostEqual(math.degrees(half_h), 26.56505117707799, places=9)
        self.assertAlmostEqual(math.degrees(half_v), 14.036243467926477, places=9)

    def base_basis(self):
        """Camera-local basis (right, up, backward = -forward) for a look-at with world up."""
        forward = self.normalize([0.3, -1.0, -0.12])
        right = self.normalize(self.cross(forward, [0, 0, 1]))
        up = self.cross(right, forward)
        return right, up, [-x for x in forward]

    @staticmethod
    def normalize(v):
        length = math.sqrt(sum(x * x for x in v))
        return [x / length for x in v]

    @staticmethod
    def cross(a, b):
        return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]

    def rotate_axes(self, axes, yaw, pitch):
        """Apply the plan's local rotation Ry(yaw) @ Rx(pitch) to right/up/forward axes."""
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        cos_p, sin_p = math.cos(pitch), math.sin(pitch)
        # Columns of Ry(yaw) @ Rx(pitch) expressed in the current camera frame.
        yaw_matrix = [[cos_y, 0.0, sin_y], [0.0, 1.0, 0.0], [-sin_y, 0.0, cos_y]]
        pitch_matrix = [[1.0, 0.0, 0.0], [0.0, cos_p, -sin_p], [0.0, sin_p, cos_p]]
        matrix = [[sum(yaw_matrix[i][k] * pitch_matrix[k][j] for k in range(3)) for j in range(3)]
                  for i in range(3)]
        # new_basis[i] = sum_k matrix[k][i] * basis[k]  (the i-th column of the rotation)
        return [[sum(matrix[k][i] * axes[k][c] for k in range(3)) for c in range(3)] for i in range(3)]

    def test_screen_solve_lands_on_target_for_real_axes(self):
        right, up, backward = self.base_basis()
        eye = [12.0, -40.0, 6.5]
        for lens in (18.0, 35.0, 65.0, 135.0):
            half_h, half_v = contract.half_angles(
                lens, *contract.sensor_extents(36.0, 24.0, "AUTO", (1920, 1080)))
            for target in ([0.5, 0.5], [0.32, 0.62], [0.72, 0.38], [0.5, 0.85], [0.18, 0.2]):
                with self.subTest(lens=lens, target=target):
                    yaw, pitch = contract.screen_angles(half_h, half_v, target)
                    axes = self.rotate_axes([right, up, backward], yaw, pitch)
                    forward_axis = [-x for x in axes[2]]
                    distance = 9.0
                    point = [eye[i] + (-backward[i]) * distance for i in range(3)]
                    x, y, depth = contract.project_point(point, eye, forward_axis, axes[0], axes[1],
                                                         half_h, half_v)
                    self.assertAlmostEqual(x, target[0], places=9)
                    self.assertAlmostEqual(y, target[1], places=9)
                    # Rotating the camera foreshortens the axis distance but not the range.
                    self.assertAlmostEqual(depth, distance * math.cos(yaw) * math.cos(pitch), places=9)
                    self.assertAlmostEqual(math.dist(point, eye), distance, places=9)

    def test_screen_solve_direction_matches_screen_direction(self):
        half_h, half_v = contract.half_angles(
            50.0, *contract.sensor_extents(36.0, 24.0, "AUTO", (1600, 900)))
        yaw, pitch = contract.screen_angles(half_h, half_v, [0.9, 0.9])
        self.assertGreater(yaw, 0.0)
        self.assertLess(pitch, 0.0)
        centre = contract.screen_angles(half_h, half_v, [0.5, 0.5])
        self.assertAlmostEqual(centre[0], 0.0)
        self.assertAlmostEqual(centre[1], 0.0)

    def test_projection_rejects_points_behind_the_camera(self):
        half_h, half_v = contract.half_angles(50.0, 36.0, 24.0)
        code = error_code(contract.project_point, [0, 10, 0], [0, 0, 0], [0, -1, 0], [1, 0, 0], [0, 0, 1],
                          half_h, half_v)
        self.assertEqual(code, "POINT_BEHIND_CAMERA")

    def test_screen_error_is_the_worst_axis(self):
        self.assertAlmostEqual(contract.screen_error([0.4, 0.6], [0.5, 0.55]), 0.1)

    def test_bisect_threshold_finds_a_monotone_boundary(self):
        solved = contract.bisect_threshold(lambda value: value >= 7.25, 0.001, 1.0, iterations=60)
        self.assertAlmostEqual(solved, 7.25, places=6)

    def test_bisect_threshold_reports_an_unreachable_fit(self):
        code = error_code(contract.bisect_threshold, lambda value: False, 0.001, 1.0, iterations=8, limit=10.0)
        self.assertEqual(code, "FIT_UNREACHABLE")


class JobRegistryCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.lib = Library(self.root / "library")
        self.input = self.root / "working-copy.blend"
        self.input.write_bytes(b"synthetic blender placeholder")

    def tearDown(self):
        self.lib.close()
        self.tmp.cleanup()

    def test_camera_plan_is_a_registered_mutation_needing_a_target(self):
        self.assertIn("camera-plan", jobs.OPS)
        self.assertIn("camera-plan", jobs.MUTATIONS)
        self.assertEqual(error_code(jobs.prepare, self.lib, "camera-plan", None, None, plan()), "TARGET_REQUIRED")

    def test_valid_plan_prepares_deterministically(self):
        first = jobs.prepare(self.lib, "camera-plan", str(self.input), options=plan())
        second = jobs.prepare(self.lib, "camera-plan", str(self.input), options=plan())
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["specification"]["operation"], "camera-plan")

    def test_invalid_plan_is_rejected_before_blender_runs(self):
        self.assertEqual(error_code(jobs.prepare, self.lib, "camera-plan", str(self.input),
                                    options=plan(keyframes=[checkpoint(screen=[2.0, 0.5])])),
                         "SCREEN_TARGET_INVALID")
        self.assertEqual(error_code(jobs.prepare, self.lib, "camera-plan", str(self.input),
                                    options=plan(projection="ORTHO")), "UNSUPPORTED_PROJECTION")
        self.assertEqual(error_code(jobs.prepare, self.lib, "camera-plan", str(self.input),
                                    options=plan(mode="adapt")), "CAMERA_REQUIRED")

    def test_camera_check_accepts_sampling_targets_and_occlusion(self):
        options = {"subjects": ["Opaque Subject.004"], "camera": "Camera",
                   "sample": {"start": 1, "end": 40, "count": 3},
                   "targets": [{"frame": 1, "subject": "Opaque Subject.004", "screen": [0.4, 0.55]}],
                   "occlusion": True}
        job = jobs.prepare(self.lib, "camera-check", str(self.input), options=options)
        self.assertEqual(job["specification"]["options"], options)
        self.assertEqual(error_code(jobs.prepare, self.lib, "camera-check", str(self.input),
                                    options={**options, "warp": True}), "INVALID_SCHEMA")


if __name__ == "__main__":
    unittest.main()
