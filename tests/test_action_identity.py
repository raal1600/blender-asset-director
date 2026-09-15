import unittest
from types import SimpleNamespace as NS
from asset_director.action_identity import imported_slot
from asset_director.core import DirectorError


class ImportedSlotTests(unittest.TestCase):
    def fixture(self):
        slot = NS(identifier="OBArmature.001", target_id_type="OBJECT")
        action = NS(slots=[slot])
        obj = NS(name="Armature.001", animation_data=NS(action=action, action_slot=slot))
        return obj, action, slot

    def test_proven_owner_rename_is_resolved_without_mutation(self):
        obj, action, slot = self.fixture()
        self.assertEqual(imported_slot(obj, action, "OBArmature", "Armature"), "OBArmature.001")
        self.assertIs(obj.animation_data.action, action)
        self.assertIs(obj.animation_data.action_slot, slot)
        self.assertEqual(slot.identifier, "OBArmature.001")

    def test_exact_slot_and_legacy_paths_remain_strict_assign_inputs(self):
        obj, action, slot = self.fixture()
        self.assertEqual(imported_slot(obj, action, slot.identifier, "Armature"), slot.identifier)
        self.assertIsNone(imported_slot(obj, action, None, "Armature"))
        self.assertEqual(imported_slot(obj, NS(slots=[]), "legacy", "Armature"), "legacy")

    def test_exact_unrenamed_owner_slot_is_not_a_collision(self):
        obj, action, slot = self.fixture()
        obj.name = "Armature"; slot.identifier = "OBArmature"
        self.assertEqual(imported_slot(obj, action, "OBArmature", "Armature"), "OBArmature")

    def test_wrong_owner_or_slot_is_not_normalized(self):
        for owner, name in [("Other", "OBArmature"), ("Armature", "OBElse"), (None, "OBArmature")]:
            obj, action, _ = self.fixture()
            with self.subTest(owner=owner, slot=name), self.assertRaises(DirectorError):
                imported_slot(obj, action, name, owner)

    def test_ambiguous_slots_are_rejected(self):
        obj, action, _ = self.fixture()
        action.slots.append(NS(identifier="OBArmature.002", target_id_type="OBJECT"))
        with self.assertRaises(DirectorError):
            imported_slot(obj, action, "OBArmature", "Armature")

    def test_unbound_wrong_action_or_wrong_type_is_rejected(self):
        for change in ("unbound", "wrong_action", "wrong_type", "wrong_slot"):
            obj, action, slot = self.fixture()
            if change == "unbound": obj.animation_data.action_slot = None
            if change == "wrong_action": obj.animation_data.action = NS(slots=[])
            if change == "wrong_type": slot.target_id_type = "ARMATURE"
            if change == "wrong_slot": obj.animation_data.action_slot = NS(identifier="OBElse")
            with self.subTest(change=change), self.assertRaises(DirectorError):
                imported_slot(obj, action, "OBArmature", "Armature")

    def test_noncollision_owner_is_rejected(self):
        for name in ("Other.001", "Armature.1", "Armature.001.extra"):
            obj, action, slot = self.fixture()
            obj.name = name; slot.identifier = "OB" + name
            with self.subTest(name=name), self.assertRaises(DirectorError):
                imported_slot(obj, action, "OBArmature", "Armature")
