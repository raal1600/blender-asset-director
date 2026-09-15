"""A proxy's visible anatomy is NOT the armature's complete control hierarchy.

Only host-reviewed anatomical roles define landmarks. Helpers remain in the rig
for evaluation, but never produce geometry merely by being parents or leaves.
There are deliberately no raw-name heuristics or terminal display-tail fallback.
"""
from __future__ import annotations

import math
from .core import require
from .motion_assets import validate_skeleton

VISUAL_SCHEMA = 'asset-director.proxy-geometry/2'
ANATOMICAL_ROLES = frozenset({
    'hips', 'spine', 'spine_mid', 'spine_upper', 'chest', 'neck', 'head',
    *(part + '_' + side for part in
      ('shoulder', 'upperarm', 'forearm', 'hand', 'thigh', 'calf', 'foot', 'toe')
      for side in ('l', 'r')),
})


def anatomy_graph(skeleton: dict) -> dict:
    """Connect a landmark to its nearest *anatomical* ancestor below hips.

    An explicitly reviewed role is evidence of anatomy; an arbitrary rig edge
    isn't. Unknown roles, all unlabelled bones and the locomotion-root role are
    excluded from visualization, not deleted from the motion skeleton.
    """
    validate_skeleton(skeleton)
    bones = {j['name']: j for j in skeleton['joints']}
    roles = skeleton['roles']
    require('hips' in roles, 'PROXY_ANATOMY_REVIEW_REQUIRED',
            'A diagnostic body needs an observed hips role; never draw a root as a pelvis')
    visible = {name: role for role, name in roles.items() if role in ANATOMICAL_ROLES}
    pelvis = roles['hips']
    links, coincident, landmarks = [], [], []
    for joint in skeleton['joints']:
        name = joint['name']
        if name not in visible:
            continue
        role = visible[name]
        landmarks.append({'role': role, 'bone': name, 'head': list(joint['head'])})
        if name == pelvis:
            continue  # No root-to-hips body segment, irrespective of its length.
        path = []
        parent = joint['parent']
        while parent is not None and parent not in visible:
            path.append(parent)
            parent = bones[parent]['parent']
        require(parent is not None, 'PROXY_ANATOMY_REVIEW_REQUIRED',
                'An anatomical role is not connected beneath the observed hips')
        ancestor = parent
        while ancestor is not None and ancestor != pelvis:
            ancestor = bones[ancestor]['parent']
        require(ancestor == pelvis, 'PROXY_ANATOMY_REVIEW_REQUIRED',
                'An anatomical role lies outside the observed hips subtree')
        length = math.dist(bones[parent]['head'], joint['head'])
        link = {'start_bone': parent, 'end_bone': name,
                'start_role': visible[parent], 'end_role': role,
                'start': list(bones[parent]['head']), 'end': list(joint['head']),
                'length_m': length, 'skipped_helpers': list(reversed(path))}
        if length <= 1e-6:
            coincident.append(link)
        else:
            links.append(link)
    require(links, 'PROXY_ANATOMY_REVIEW_REQUIRED',
            'At least two distinct reviewed anatomical landmarks are required')
    return {'schema': VISUAL_SCHEMA, 'landmarks': landmarks, 'segments': links,
            'coincident_links': coincident, 'excluded_bones': sorted(set(bones) - set(visible)),
            'excluded_roles': sorted(set(roles) - ANATOMICAL_ROLES),
            'root_bone': roles.get('root'), 'terminal_display_tails_used': False,
            'geometry_basis': 'reviewed anatomical joint heads; root/helpers have no surface'}
