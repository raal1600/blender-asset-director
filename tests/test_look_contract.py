"""Lighting/look contract coverage (portable: no Blender import)."""
from pathlib import Path
import tempfile
import unittest

from asset_director import jobs
from asset_director import look_contract as contract
from asset_director.core import DirectorError, Library


def error_code(callable_, *args, **kw):
    with unittest.TestCase().assertRaises(DirectorError) as caught:
        callable_(*args, **kw)
    return caught.exception.code


class LightAdjustContractCase(unittest.TestCase):
    def test_valid_request_normalizes(self):
        result = contract.validate_light_adjust({"lights": [
            {"name": "opaque key 01", "energy": 250.0, "color": [1.0, 0.8, 0.6], "location": [2, -3, 4]},
            {"name": "0042 fill", "size": 2.5, "size_y": 1.0, "rotation_euler_deg": [10, 0, 45]}]})
        self.assertEqual([entry["name"] for entry in result["lights"]], ["opaque key 01", "0042 fill"])
        self.assertEqual(result["lights"][0]["changes"]["color"], [1.0, 0.8, 0.6])
        self.assertEqual(result["lights"][1]["changes"]["size_y"], 1.0)

    def test_entries_need_a_name_and_a_change(self):
        # A missing name is a schema error; a blank name is a missing light reference.
        self.assertEqual(error_code(contract.validate_light_adjust, {"lights": [{"energy": 5.0}]}),
                         "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_light_adjust, {"lights": [{"name": "lamp"}]}),
                         "LIGHT_CHANGE_REQUIRED")
        self.assertEqual(error_code(contract.validate_light_adjust, {"lights": [{"name": "   ", "energy": 1}]}),
                         "LIGHT_REQUIRED")
        # Names are passed through exactly; only emptiness after stripping is rejected.
        self.assertEqual(contract.validate_light_adjust({"lights": [{"name": " odd name 01 ", "energy": 1.0}]})
                         ["lights"][0]["name"], " odd name 01 ")

    def test_unknown_property_is_rejected(self):
        self.assertEqual(error_code(contract.validate_light_adjust,
                                    {"lights": [{"name": "lamp", "intensity": 5.0}]}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_light_adjust, {"lights": [{"name": "lamp", "energy": 1}],
                                                                     "extra": 1}), "INVALID_SCHEMA")

    def test_empty_duplicate_and_bounded_requests(self):
        self.assertEqual(error_code(contract.validate_light_adjust, {"lights": []}), "RESOURCE_LIMIT")
        self.assertEqual(error_code(contract.validate_light_adjust,
                                    {"lights": [{"name": "l", "energy": 1}, {"name": "l", "energy": 2}]}),
                         "INVALID_SCHEMA")
        too_many = {"lights": [{"name": "l%d" % i, "energy": 1.0} for i in range(33)]}
        self.assertEqual(error_code(contract.validate_light_adjust, too_many), "RESOURCE_LIMIT")

    def test_value_types_and_ranges(self):
        self.assertEqual(error_code(contract.validate_light_adjust, {"lights": [{"name": "l", "energy": -1}]}),
                         "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_light_adjust,
                                    {"lights": [{"name": "l", "color": [1.2, 0.5, 0.5]}]}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_light_adjust,
                                    {"lights": [{"name": "l", "color": [0.2, 0.5]}]}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_light_adjust,
                                    {"lights": [{"name": "l", "angle_deg": 400.0}]}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_light_adjust,
                                    {"lights": [{"name": "l", "spot_blend": 2.0}]}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_light_adjust,
                                    {"lights": [{"name": "l", "use_shadow": "yes"}]}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_light_adjust,
                                    {"lights": [{"name": "l", "rotation_quaternion": [1, 0, 0]}]}),
                         "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_light_adjust,
                                    {"lights": [{"name": "l", "shape": ""}]}), "INVALID_SCHEMA")

    def test_property_support_by_light_type_is_explicit(self):
        self.assertEqual(contract.unsupported_properties("SUN", {"size"}), ["size"])
        self.assertEqual(contract.unsupported_properties("AREA", {"angle_deg"}), ["angle_deg"])
        self.assertEqual(contract.unsupported_properties("POINT", {"spot_size_deg", "energy"}),
                         ["spot_size_deg"])
        self.assertEqual(contract.unsupported_properties("SPOT", {"spot_blend", "shadow_soft_size"}), [])
        self.assertEqual(contract.unsupported_properties("AREA", {"size", "size_y", "shape"}), [])
        for light_type in contract.LIGHT_TYPES:
            self.assertIn("energy", contract.light_properties_for_type(light_type))


class WorldAdjustContractCase(unittest.TestCase):
    def test_valid_values(self):
        self.assertEqual(contract.validate_world_adjust({"strength": 0.35}), {"strength": 0.35})
        self.assertEqual(contract.validate_world_adjust({"color": [0.6, 0.4, 0.25]}),
                         {"color": [0.6, 0.4, 0.25]})

    def test_rejects_empty_unknown_and_out_of_range(self):
        self.assertEqual(error_code(contract.validate_world_adjust, {}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_world_adjust, {"nope": 1}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_world_adjust, {"strength": -1}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_world_adjust, {"color": [2.0, 0.0, 0.0]}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_world_adjust, {"color": [0.2, 0.2]}), "INVALID_SCHEMA")


class LookAdjustContractCase(unittest.TestCase):
    def test_valid_values(self):
        result = contract.validate_look_adjust({"exposure": 0.4, "gamma": 1.1, "view_transform": "AgX",
                                                 "look": "None", "display_device": "sRGB",
                                                 "use_white_balance": True, "white_balance_temperature": 5000,
                                                 "white_balance_tint": 12.5})
        self.assertEqual(result["exposure"], 0.4)
        self.assertEqual(result["view_transform"], "AgX")
        self.assertTrue(result["use_white_balance"])

    def test_rejects_empty_unknown_and_invalid_types(self):
        self.assertEqual(error_code(contract.validate_look_adjust, {}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_look_adjust, {"contrast": 1.2}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_look_adjust, {"exposure": "bright"}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_look_adjust, {"exposure": 500.0}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_look_adjust, {"gamma": 0.0}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_look_adjust, {"view_transform": ""}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_look_adjust, {"use_white_balance": 1}), "INVALID_SCHEMA")
        self.assertEqual(error_code(contract.validate_look_adjust, {"white_balance_temperature": -5}),
                         "INVALID_SCHEMA")


class LookJobRegistryCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.lib = Library(self.root / "library")
        self.input = self.root / "working-copy.blend"
        self.input.write_bytes(b"synthetic blender placeholder")

    def tearDown(self):
        self.lib.close()
        self.tmp.cleanup()

    def test_operations_are_registered(self):
        valid = {"look-audit": {}, "light-adjust": {"lights": [{"name": "l", "energy": 1.0}]},
                 "world-adjust": {"strength": 1.0}, "look-adjust": {"exposure": 0.2}}
        for operation, options in valid.items():
            with self.subTest(operation=operation):
                self.assertIn(operation, jobs.OPS)
                # Every look operation reads or writes a specific saved working file.
                self.assertEqual(error_code(jobs.prepare, self.lib, operation, None, None, options),
                                 "TARGET_REQUIRED")
        self.assertNotIn("look-audit", jobs.MUTATIONS)
        for operation in ("light-adjust", "world-adjust", "look-adjust"):
            self.assertIn(operation, jobs.MUTATIONS)

    def test_valid_requests_prepare_deterministically(self):
        first = jobs.prepare(self.lib, "light-adjust", str(self.input),
                             options={"lights": [{"name": "l", "energy": 2.0}]})
        second = jobs.prepare(self.lib, "light-adjust", str(self.input),
                              options={"lights": [{"name": "l", "energy": 2.0}]})
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(jobs.prepare(self.lib, "look-adjust", str(self.input),
                                      options={"exposure": 0.2})["specification"]["operation"], "look-adjust")
        self.assertEqual(jobs.prepare(self.lib, "world-adjust", str(self.input),
                                      options={"strength": 0.5})["specification"]["operation"], "world-adjust")

    def test_invalid_values_are_rejected_before_blender_runs(self):
        self.assertEqual(error_code(jobs.prepare, self.lib, "light-adjust", str(self.input),
                                    options={"lights": [{"name": "l", "watts": 5}]}), "INVALID_SCHEMA")
        self.assertEqual(error_code(jobs.prepare, self.lib, "look-adjust", str(self.input),
                                    options={"exposure": 999}), "INVALID_SCHEMA")
        self.assertEqual(error_code(jobs.prepare, self.lib, "world-adjust", str(self.input),
                                    options={"strength": -2}), "INVALID_SCHEMA")


if __name__ == "__main__":
    unittest.main()
