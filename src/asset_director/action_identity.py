"""Resolve only an observed, uniquely owned import-slot rename; never guess a slot.

Callers must restrict object/action candidates to the current verified import.
Indexed metadata and review hashes stay unchanged. Generic assign stays strict.
"""
from __future__ import annotations
import re
from .core import require


def imported_slot(obj, action, indexed_slot, indexed_owner):
    """Return the runtime identifier without mutating action, object, or metadata."""
    slots = list(getattr(action, "slots", []))
    if indexed_slot is None or not slots:
        return indexed_slot
    if any(slot.identifier == indexed_slot for slot in slots):
        return indexed_slot
    data = getattr(obj, "animation_data", None)
    assigned = getattr(data, "action_slot", None)
    # Blender 4.5 FBX imports may suffix both owner and slot (OBArmature.001).
    # Only the already-bound, sole OBJECT slot can prove this narrow rename.
    renamed_owner = (isinstance(indexed_owner, str) and isinstance(obj.name, str)
        and re.fullmatch(re.escape(indexed_owner) + r"\.[0-9]{3,}", obj.name) is not None)
    require(renamed_owner and indexed_slot == "OB" + indexed_owner
        and len(slots) == 1 and getattr(data, "action", None) == action
        and assigned is not None and assigned == slots[0]
        and assigned.identifier == "OB" + obj.name
        and getattr(assigned, "target_id_type", None) == "OBJECT",
        "SLOT_AMBIGUOUS", "Indexed slot is absent; no uniquely bound import-owner rename was proven")
    return assigned.identifier
