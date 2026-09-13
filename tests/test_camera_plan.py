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

    def test_all_point_aims_are_contract_valid(self):
        """The plan class that failed in local acceptance: every checkpoint aims at a world point."""
        result = contract.validate(plan(keyframes=[
            checkpoint(frame=1, aim={"point": [11.0, -34.0, 4.863]}, position=[6.2681, -67.6691, 6.21],
                       screen=[0.40, 0.50]),
            checkpoint(frame=48, aim={"point": [11.0, -34.0, 4.863]}, position=[6.0486, -63.5886, 6.41],
                       screen=[0.41, 0.50])]))
        self.assertEqual([k["aim"]["point"] for k in result["keyframes"]],
                         [[11.0, -34.0, 4.863], [11.0, -34.0, 4.863]])
        self.assertEqual([k["screen"] for k in result["keyframes"]], [[0.40, 0.50], [0.41, 0.50]])

    def test_roll_can_be_requested_per_checkpoint_or_for_the_plan(self):
        result = contract.validate(plan(roll_deg=2.5, keyframes=[checkpoint(frame=1, roll_deg=-3.0),
                                                                 checkpoint(frame=12)]))
        self.assertEqual(result["roll_deg"], 2.5)
        self.assertEqual(result["keyframes"][0]["roll_deg"], -3.0)
        self.assertNotIn("roll_deg", result["keyframes"][1])
        self.assertEqual(error_code(contract.validate, plan(keyframes=[checkpoint(roll_deg=400)])),
                         "INVALID_SCHEMA")

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

    @staticmethod
    def normalize(v):
        length = math.sqrt(sum(x * x for x in v))
        return [x / length for x in v]

    @staticmethod
    def cross(a, b):
        return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]

    @staticmethod
    def dot(a, b):
        return sum(a[i] * b[i] for i in range(3))

    def measured_roll(self, forward, up):
        """Independent implementation of the roll metric camera-check reports."""
        right = self.cross(forward, [0.0, 0.0, 1.0])
        if math.sqrt(sum(v * v for v in right)) < 1e-12:
            return 0.0
        right = self.normalize(right)
        level_up = self.cross(right, forward)
        return math.degrees(math.atan2(self.dot(up, right), self.dot(up, level_up)))

    def solve(self, direction, lens, resolution, screen, roll_deg=0.0, sensor_fit="AUTO"):
        half_h, half_v = contract.half_angles(
            lens, *contract.sensor_extents(36.0, 24.0, sensor_fit, resolution))
        solved = contract.unroll_screen(screen, half_h, half_v, roll_deg)
        forward, right, up = contract.screen_frame(direction, half_h, half_v, solved)
        right, up = contract.roll_axes(right, up, roll_deg)
        return forward, right, up, half_h, half_v

    def test_screen_frame_places_aim_point_exactly_on_target(self):
        eye = [12.0, -40.0, 6.5]
        for lens, resolution in ((18.0, (1920, 1080)), (65.0, (1080, 1920)), (135.0, (2100, 900))):
            for direction in ([0.3, -1.0, -0.12], [-0.8, 0.6, -0.4], [0.05, -1.0, 0.35]):
                for target in ([0.5, 0.5], [0.32, 0.62], [0.72, 0.38], [0.5, 0.85], [0.18, 0.2]):
                    with self.subTest(lens=lens, resolution=resolution, direction=direction, target=target):
                        forward, right, up, half_h, half_v = self.solve(direction, lens, resolution, target)
                        distance = 9.0
                        point = [eye[i] + self.normalize(direction)[i] * distance for i in range(3)]
                        x, y, depth = contract.project_point(point, eye, forward, right, up, half_h, half_v)
                        self.assertAlmostEqual(x, target[0], places=9)
                        self.assertAlmostEqual(y, target[1], places=9)
                        # An off-centre target tilts the view axis away from the aim
                        # direction, so depth is the true range over |(X, Y, 1)|.
                        x_offset = 2.0 * (target[0] - 0.5) * math.tan(half_h)
                        y_offset = 2.0 * (target[1] - 0.5) * math.tan(half_v)
                        scale = math.sqrt(1.0 + x_offset ** 2 + y_offset ** 2)
                        self.assertAlmostEqual(depth, distance / scale, places=9)
                        self.assertAlmostEqual(
                            math.sqrt(sum((point[i] - eye[i]) ** 2 for i in range(3))), distance, places=9)

    def test_screen_frame_stays_roll_free_with_aggressive_offsets(self):
        """A steeply pitched camera with a strong yaw offset used to inject roll."""
        eye = [-13.0, 21.0, 2.0]
        for lens, resolution in ((24.0, (1600, 900)), (85.0, (900, 1600))):
            for pitch_deg in (-25.0, -8.0, 0.0, 11.0):
                for target in ([0.9, 0.12], [0.1, 0.9], [0.5, 0.5], [0.5, 0.95]):
                    with self.subTest(lens=lens, pitch=pitch_deg, target=target):
                        radians = math.radians(pitch_deg)
                        direction = [math.cos(radians), 0.4, math.sin(radians)]
                        forward, right, up, half_h, half_v = self.solve(direction, lens, resolution, target)
                        self.assertAlmostEqual(self.measured_roll(forward, up), 0.0, places=9)
                        point = [eye[i] + self.normalize(direction)[i] * 7.0 for i in range(3)]
                        x, y, _ = contract.project_point(point, eye, forward, right, up, half_h, half_v)
                        self.assertAlmostEqual(x, target[0], places=9)
                        self.assertAlmostEqual(y, target[1], places=9)

    def test_roll_axes_match_the_requested_roll(self):
        direction = [0.25, -1.0, -0.3]
        target = [0.78, 0.28]
        eye = [0.0, 0.0, 0.0]
        aim = [v * 6.0 for v in self.normalize(direction)]
        for requested in (0.0, 7.0, -4.0, 12.5, -150.0):
            with self.subTest(requested=requested):
                forward, right, up, half_h, half_v = self.solve(direction, 50.0, (1920, 1080), target,
                                                                roll_deg=requested)
                self.assertAlmostEqual(self.measured_roll(forward, up), requested, places=9)
                # Rolling about the view axis must not move the aim point itself.
                x, y, _ = contract.project_point(aim, eye, forward, right, up, half_h, half_v)
                self.assertAlmostEqual(x, target[0], places=9)
                self.assertAlmostEqual(y, target[1], places=9)

    def test_screen_frame_centred_target_keeps_level_horizon(self):
        direction = [0.0, -1.0, -0.15]
        forward, right, up, _, _ = self.solve(direction, 35.0, (1920, 1080), [0.5, 0.5])
        self.assertAlmostEqual(self.measured_roll(forward, up), 0.0, places=9)
        self.assertAlmostEqual(up[0], 0.0, places=12)
        pitch = math.asin(self.normalize(direction)[2])
        self.assertAlmostEqual(self.dot(up, [0.0, 0.0, 1.0]), math.cos(pitch), places=9)

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


class TargetContractCase(unittest.TestCase):
    """Camera-check screen targets, including explicit world-point aims."""

    def test_point_subject_and_mixed_targets_are_accepted(self):
        targets = contract.validate_targets([
            {"frame": 1, "point": [1.0, -2.0, 3.0], "screen": [0.4, 0.55]},
            {"frame": 12, "subject": "opaque.004", "bounds": [0.5, 0.5, 0.9], "screen": [0.5, 0.5]},
            {"frame": 24, "point": [-8.0, 12.5, 0.25], "screen": [0.85, 0.2], "roll_deg": -3.5}])
        self.assertEqual(len(targets), 3)
        self.assertEqual(targets[0]["aim"], {"point": [1.0, -2.0, 3.0]})
        self.assertEqual(targets[1]["aim"], {"subject": "opaque.004", "bounds": [0.5, 0.5, 0.9]})
        self.assertEqual(targets[2]["roll_deg"], -3.5)
        self.assertNotIn("roll_deg", targets[0])

    def test_absent_targets_mean_no_screen_checks(self):
        self.assertIsNone(contract.validate_targets(None))

    def test_empty_target_list_is_still_rejected(self):
        """An empty list silently verifies nothing; absence must be explicit."""
        self.assertEqual(error_code(contract.validate_targets, []), "RESOURCE_LIMIT")

    def test_target_count_is_bounded(self):
        too_many = [{"frame": i, "point": [0, 0, 0], "screen": [0.5, 0.5]} for i in range(33)]
        self.assertEqual(error_code(contract.validate_targets, too_many), "RESOURCE_LIMIT")

    def test_missing_aim_is_rejected(self):
        self.assertEqual(error_code(contract.validate_targets, [{"frame": 1, "screen": [0.5, 0.5]}]),
                         "AIM_REQUIRED")

    def test_point_and_subject_cannot_be_mixed_in_one_target(self):
        self.assertEqual(error_code(contract.validate_targets, [{"frame": 1, "point": [0, 0, 0],
                                                                 "subject": "opaque", "screen": [0.5, 0.5]}]),
                         "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_targets, [{"frame": 1, "point": [0, 0, 0],
                                                                 "bounds": [0.5, 0.5, 0.5],
                                                                 "screen": [0.5, 0.5]}]),
                         "INVALID_SCHEMA")

    def test_malformed_points_are_rejected(self):
        for bad in ([0, 0], [0, 0, 0, 0], [0, 0, "x"], [0, 0, float("nan")]):
            with self.subTest(point=bad):
                self.assertEqual(error_code(contract.validate_targets,
                                            [{"frame": 1, "point": bad, "screen": [0.5, 0.5]}]),
                                 "INVALID_SCHEMA")

    def test_malformed_screen_targets_are_rejected(self):
        for bad in ([0.5], [1.4, 0.5], [0.5, -0.2], ["x", 0.5]):
            with self.subTest(screen=bad):
                self.assertEqual(error_code(contract.validate_targets,
                                            [{"frame": 1, "point": [0, 0, 0], "screen": bad}]),
                                 "SCREEN_TARGET_INVALID")
        self.assertEqual(error_code(contract.validate_targets, [{"frame": 1, "point": [0, 0, 0]}]),
                         "INVALID_SCHEMA")

    def test_duplicate_frames_unknown_keys_and_bad_roll_rejected(self):
        duplicate = [{"frame": 4, "point": [0, 0, 0], "screen": [0.5, 0.5]},
                     {"frame": 4, "subject": "opaque", "screen": [0.5, 0.5]}]
        self.assertEqual(error_code(contract.validate_targets, duplicate), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_targets, [{"frame": 1, "point": [0, 0, 0],
                                                                 "screen": [0.5, 0.5], "warp": 1}]),
                         "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_targets, [{"frame": 1, "point": [0, 0, 0],
                                                                 "screen": [0.5, 0.5], "roll_deg": 400}]),
                         "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_targets, [{"frame": 1.5, "point": [0, 0, 0],
                                                                 "screen": [0.5, 0.5]}]),
                         "INVALID_SCHEMA")


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
