"""Conservative name candidates resolved by observed direct hierarchy, not provider.

Only three-joint torso/finger families are recognized in v1. Other counts,
namespace collisions, helper-interrupted chains and missing sides stay reviewable.
No joints are renamed, merged, deleted or synthesized.
"""
import re
from .core import require

FINGERS = ('thumb', 'index', 'middle', 'ring', 'pinky')


def base_name(name):
    name = name.rsplit(':', 1)[-1]
    return re.sub(r'^def-', '', name, flags=re.I).lower()


def finger_candidate(name):
    raw = base_name(name)
    # Mixamo and exported DEF-only naming families. Side and index are explicit.
    match = re.fullmatch(r'(left|right)hand(thumb|index|middle|ring|pinky)([1-3])', raw)
    if match:
        side, finger, index = match.groups()
        return finger, 'l' if side == 'left' else 'r', int(index)
    match = re.fullmatch(r'(?:f[_-])?(thumb|index|middle|ring|pinky)[._-](\d{1,3})[._-]([lr])', raw)
    if match and 1 <= int(match[2]) <= 3:
        return match[1], match[3], int(match[2])
    return None


def extend(bones, assigned, ambiguous, torso):
    require(len(bones) <= 256, 'RESOURCE_LIMIT', 'Skeleton discovery is bounded to 256 bones')
    by_name = {b['name']: b for b in bones}
    require(len(by_name) == len(bones), 'INVALID_SKELETON', 'Duplicate bone names')
    chains, notes = [], []
    numbered = []
    for bone in bones:
        match = re.fullmatch(r'spine(?:[._-]?(\d+))?', base_name(bone['name']))
        if match:
            numbered.append((int(match[1]) if match[1] else 0, bone))
    # Preserve the existing single-spine fallback. Never collapse multiple joints.
    if torso is None and len(numbered) > 1:
        ordered = sorted(numbered, key=lambda x: (x[0], x[1]['name']))
        nums, chain = [n for n, _ in ordered], [b for _, b in ordered]
        valid = (len(chain) == 3 and nums in ([0, 1, 2], [1, 2, 3])
                 and assigned.get('hips') is not None
                 and chain[0].get('parent') == assigned['hips']
                 and all(b.get('parent') == a['name'] for a, b in zip(chain, chain[1:])))
        if valid:
            assigned.update(zip(('spine', 'spine_mid', 'chest'), (b['name'] for b in chain)))
            ambiguous.pop('spine', None)
            torso = {'method': 'numbered torso with direct observed parent order',
                     'chain': [assigned['hips']] + [b['name'] for b in chain],
                     'provider_identity_proven': False}
        else:
            assigned.pop('spine', None)
            ambiguous['spine'] = sorted(b['name'] for _, b in numbered)
            notes.append({'chain': 'torso', 'status': 'REVIEW_REQUIRED',
                          'reason': 'Need one directly connected three-joint torso; no count compression or alias choice'})
    for side in ('l', 'r'):
        hand = assigned.get('hand_' + side)
        for finger in FINGERS:
            candidates = {i: [b for b in bones if finger_candidate(b['name']) == (finger, side, i)]
                          for i in (1, 2, 3)}
            if not any(candidates.values()):
                notes.append({'chain': finger+'_'+side, 'status': 'ABSENT'})
                continue
            valid = hand is not None and all(len(v) == 1 for v in candidates.values())
            chain = [candidates[i][0] for i in (1, 2, 3)] if valid else []
            valid = (valid and chain[0].get('parent') == hand
                     and all(b.get('parent') == a['name'] for a, b in zip(chain, chain[1:])))
            if valid:
                assigned.update({f'{finger}_{i}_{side}': b['name'] for i, b in enumerate(chain, 1)})
                chains.append({'side': side, 'finger': finger, 'hand': hand,
                               'joints': [b['name'] for b in chain], 'evidence': 'name + direct hierarchy'})
            else:
                names = sorted(b['name'] for v in candidates.values() for b in v)
                ambiguous[f'{finger}_chain_{side}'] = names
                notes.append({'chain': finger+'_'+side, 'status': 'REVIEW_REQUIRED', 'candidates': names})
    return torso, chains, notes
