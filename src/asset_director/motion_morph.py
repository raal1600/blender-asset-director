"""Pure morphology helpers for source-shaped diagnostic motion proxies.

Display-bone tails are not anatomical landmarks.  Scaling therefore follows
reviewed semantic joint-head paths (hip->knee->ankle, shoulder->elbow->wrist)
and leaves unrelated branches attached without silently changing their reach.
"""
from __future__ import annotations
import copy
import math
from .core import require
from .motion_assets import finite, validate_skeleton

CHAIN_NEXT = {
    'thigh_l': 'calf_l', 'calf_l': 'foot_l', 'foot_l': 'toe_l',
    'thigh_r': 'calf_r', 'calf_r': 'foot_r', 'foot_r': 'toe_r',
    'upperarm_l': 'forearm_l', 'forearm_l': 'hand_l',
    'upperarm_r': 'forearm_r', 'forearm_r': 'hand_r',
}


def semantic_successor(role, roles):
    nxt = CHAIN_NEXT.get(role)
    return nxt if nxt in roles else None


def _path_to_ancestor(bones, start, end):
    """Return parent->child edges from start to descendant end."""
    reverse = []
    current = end
    while current != start:
        parent = bones[current]['parent']
        require(parent is not None, 'BODY_CHAIN_REVIEW_REQUIRED',
                'Semantic successor is not below the requested segment')
        reverse.append((parent, current))
        current = parent
    reverse.reverse()
    return reverse


def morph_skeleton(source, length_scales):
    """Fit rest lengths once without using arbitrary Blender display tails.

    A requested scale applies to the hierarchy edges between a semantic segment
    start and its semantic successor. This makes the same joint-head distances
    used by ``body_profile`` change by the requested ratio, even when source
    display tails are offset, disconnected, or merely decorative.
    """
    validate_skeleton(source)
    require(isinstance(length_scales, dict) and len(length_scales) <= 128,
            'INVALID_MOTION', 'Bounded semantic segment scales required')
    sk = copy.deepcopy(source)
    bones = {j['name']: j for j in source['joints']}
    roles = source['roles']
    require(set(length_scales) <= set(roles), 'BODY_ROLE_MISSING',
            'A scale names an unknown semantic role')

    edge_scale = {}
    tail_scale = {}
    for role, raw in length_scales.items():
        scale = finite(raw, .5, 2)
        successor = semantic_successor(role, roles)
        start = roles[role]
        if successor:
            end = roles[successor]
            edges = _path_to_ancestor(bones, start, end)
            require(edges, 'BODY_CHAIN_REVIEW_REQUIRED', 'Semantic segment has no measurable joint span')
            for edge in edges:
                previous = edge_scale.get(edge)
                require(previous is None or abs(previous-scale) < 1e-9,
                        'BODY_CHAIN_REVIEW_REQUIRED', 'Overlapping morphology requests disagree')
                edge_scale[edge] = scale
            # Scale the Blender display vector too, but never use it as the
            # anatomical measurement driving child placement.
            tail_scale[start] = scale
        else:
            # Terminal hands/feet/toes may be visualized with their display
            # length, but changing them cannot claim to change a measured limb
            # chain because no reviewed semantic successor exists.
            require(not any(j['parent'] == start for j in source['joints']),
                    'BODY_CHAIN_REVIEW_REQUIRED',
                    'Cannot scale a branching/non-terminal role without a reviewed semantic successor')
            tail_scale[start] = scale

    solved = {}
    for joint in sk['joints']:
        old = bones[joint['name']]
        if old['parent'] is None:
            head = list(old['head'])
        else:
            parent = old['parent']
            parent_old = bones[parent]['head']
            parent_new = solved[parent]['head']
            factor = edge_scale.get((parent, old['name']), 1.0)
            head = [parent_new[i] + factor*(old['head'][i]-parent_old[i]) for i in range(3)]
        factor = tail_scale.get(old['name'], 1.0)
        tail = [head[i] + factor*(old['tail'][i]-old['head'][i]) for i in range(3)]
        joint['head'] = head
        joint['tail'] = tail
        solved[old['name']] = joint

    validate_skeleton(sk)
    return sk


def inclusive_scene_end(start_frame, duration_seconds, fps):
    """Integer scene end that includes a direct action's exact final key.

    Unlike an NLA strip, a directly assigned FCurve holds its final value after
    its last key. A fractional endpoint therefore needs the next integer frame
    for interactive playback coverage. Values numerically equal to an integer
    are snapped instead of being rounded down by floating-point error.
    """
    finite(start_frame, -1e6, 1e6)
    finite(duration_seconds, 0, 600)
    finite(fps, .01, 1000)
    exact = float(start_frame) + float(duration_seconds)*float(fps)
    nearest = round(exact)
    if math.isclose(exact, nearest, rel_tol=0.0, abs_tol=1e-5):
        end = int(nearest)
    else:
        end = int(math.ceil(exact))
    return max(int(math.floor(start_frame)), end), exact
