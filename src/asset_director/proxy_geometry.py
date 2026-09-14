"""Blender-only anatomical proxy skinning and bounded evaluated attachments QA.

This is an overlapping segmented diagnostic surface, not sculpting, human skin,
IK, or a continuous anatomical mesh. Segment ends bind to their OWN landmarks,
so helper rotations or pelvis translation cannot leave an end at a controller.
"""
from __future__ import annotations

import json
import math
import bpy
from mathutils import Matrix, Vector
from .core import canonical, digest, require
from .motion_assets import finite
from .motion_proxy import VISUAL_SCHEMA, anatomy_graph

SIDES = 10


def _radius(length, ratio):
    return min(.08, max(.008, length * ratio))


def create_skin(rig, skeleton, radius_ratio=.1, color=(.45, .45, .45)):
    """Create one skinned mesh; record inspectable landmark/ring membership."""
    graph = anatomy_graph(skeleton)  # Refuse missing anatomy before creating data.
    finite(radius_ratio, .025, .3)
    vertices, faces, assignments, attachments = [], [], [], []
    segment_reports = []

    def ring(center, frame, y, radius, influences):
        ids = []
        for k in range(SIDES):
            angle = 2 * math.pi * k / SIDES
            p = center + frame @ Vector((radius * math.cos(angle), y, radius * math.sin(angle)))
            ids.append(len(vertices)); vertices.append(tuple(p)); assignments.append(influences)
        return ids

    def join(rings):
        for first, second in zip(rings, rings[1:]):
            for k in range(SIDES):
                n = (k + 1) % SIDES
                faces.append((first[k], first[n], second[n], second[k]))
        faces.append(tuple(reversed(rings[0])))
        faces.append(tuple(rings[-1]))

    for segment in graph['segments']:
        start, end = Vector(segment['start']), Vector(segment['end'])
        length = segment['length_m']; radius = _radius(length, radius_ratio)
        frame = Vector((0, 1, 0)).rotation_difference((end-start).normalized()).to_matrix()
        a, b = segment['start_bone'], segment['end_bone']
        specs = [(-.99*radius, .14*radius), (-.7*radius, .714*radius), (0., radius),
                 (.25*length, radius), (.5*length, radius), (.75*length, radius),
                 (length, radius), (length+.7*radius, .714*radius), (length+.99*radius, .14*radius)]
        rings = []
        for y, r in specs:
            u = max(0., min(1., y/length))
            influences = {name: weight for name, weight in ((a, 1-u), (b, u)) if weight > 0}
            rings.append(ring(start, frame, y, r, influences))
        join(rings)
        # Centroid of these symmetric rings must coincide with evaluated heads.
        attachments += [{'kind': 'segment_start', 'bone': a, 'indices': rings[2]},
                        {'kind': 'segment_end', 'bone': b, 'indices': rings[6]}]
        segment_reports.append({**segment, 'radius_m': radius,
                                'start_ring': rings[2], 'end_ring': rings[6]})

    # Bound endpoint markers from incident anatomical reach, never helper tails.
    for landmark in graph['landmarks']:
        name = landmark['bone']
        incident = [s['length_m'] for s in graph['segments'] if name in (s['start_bone'], s['end_bone'])]
        radius = _radius(min(incident) if incident else .2, radius_ratio)
        center = Vector(landmark['head']); rings = []
        # Symmetric rings have a centroid exactly at this semantic joint head.
        for y_factor in (-.99, -.7, 0., .7, .99):
            rings.append(ring(center, Matrix.Identity(3), radius*y_factor,
                              radius*math.sqrt(1-y_factor*y_factor), {name: 1.}))
        join(rings)
        attachments.append({'kind': 'landmark', 'bone': name,
                            'indices': [i for r in rings for i in r]})

    require(vertices and len(vertices) <= 12000, 'RESOURCE_LIMIT', 'Proxy geometry vertex budget exceeded')
    mesh = bpy.data.meshes.new(rig.name + '_skin')
    mesh.from_pydata(vertices, [], faces); mesh.update()
    skin = bpy.data.objects.new(mesh.name, mesh); bpy.context.scene.collection.objects.link(skin)
    groups = {n['bone']: skin.vertex_groups.new(name=n['bone']) for n in graph['landmarks']}
    for index, influences in enumerate(assignments):
        require(abs(sum(influences.values())-1) < 1e-8 and set(influences) <= set(groups),
                'PROXY_WEIGHT_INVALID', 'Proxy weights must be normalized anatomical bindings')
        for name, weight in influences.items(): groups[name].add([index], weight, 'REPLACE')
    modifier = skin.modifiers.new('CanonicalSkin', 'ARMATURE'); modifier.object = rig
    modifier.use_vertex_groups = True; modifier.use_bone_envelopes = False
    modifier.use_deform_preserve_volume = False  # Endpoint-centroid checks use linear blend skinning.
    skin.parent = rig
    material = bpy.data.materials.new(rig.name + '_matte'); material.use_nodes = True
    bsdf = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = .7; mesh.materials.append(material)
    for poly in mesh.polygons: poly.use_smooth = True
    metadata = {'schema': VISUAL_SCHEMA, 'vertex_count': len(vertices), 'face_count': len(faces),
                'topology_hash': digest([list(p.vertices) for p in mesh.polygons]),
                'graph': graph, 'segments': segment_reports, 'attachments': attachments}
    skin['bad_proxy_geometry'] = canonical(metadata)
    rig['bad_proxy_geometry_schema'] = VISUAL_SCHEMA
    return skin, metadata


def check_attachments(rig, frames):
    """Inspect evaluated mesh ring/marker centres, not just the skeleton.

    This bounded structural check does not evaluate all surface intersections,
    volume, skin appearance, contact with a floor, or continuous performance.
    """
    if rig.get('bad_proxy_geometry_schema') != VISUAL_SCHEMA:
        return {'status': 'NOT_CHECKED', 'reason': 'not a v2 diagnostic proxy; no retrospective visual pass'}
    require(isinstance(frames, (tuple, list)) and 1 <= len(frames) <= 32,
            'RESOURCE_LIMIT', 'Proxy attachments need 1..32 explicit checkpoints')
    for frame in frames: finite(frame, -1e6, 1e6)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.parent == rig
              and 'bad_proxy_geometry' in o]
    require(len(meshes) == 1, 'PROXY_GEOMETRY_INVALID', 'Expected exactly one generated proxy skin')
    skin = meshes[0]; raw = skin['bad_proxy_geometry']
    require(isinstance(raw, str) and len(raw) <= 500000, 'PROXY_GEOMETRY_INVALID', 'Invalid proxy metadata size')
    try:
        metadata = json.loads(raw)
    except (ValueError, TypeError):
        require(False, 'PROXY_GEOMETRY_INVALID', 'Unreadable proxy metadata')
    require(isinstance(metadata, dict) and metadata.get('schema') == VISUAL_SCHEMA,
            'PROXY_GEOMETRY_INVALID', 'Unsupported proxy metadata')
    require(len(skin.modifiers) == 1 and skin.modifiers[0].type == 'ARMATURE'
            and skin.modifiers[0].object == rig and not skin.modifiers[0].use_bone_envelopes
            and skin.modifiers[0].use_vertex_groups and not skin.modifiers[0].use_deform_preserve_volume,
            'PROXY_GEOMETRY_INVALID', 'Attachment audit requires the original linear armature modifier')
    require(len(skin.data.vertices) == metadata.get('vertex_count')
            and len(skin.data.polygons) == metadata.get('face_count')
            and digest([list(p.vertices) for p in skin.data.polygons]) == metadata.get('topology_hash'),
            'PROXY_GEOMETRY_INVALID', 'Proxy topology changed; regenerate or review')
    graph = metadata.get('graph', {})
    require(isinstance(graph, dict) and isinstance(graph.get('landmarks'), list),
            'PROXY_GEOMETRY_INVALID', 'Missing anatomical landmarks')
    names = {n.get('bone') for n in graph['landmarks'] if isinstance(n, dict)}
    require(names and all(isinstance(n, str) and n in rig.pose.bones for n in names)
            and graph.get('root_bone') not in names,
            'PROXY_GEOMETRY_INVALID', 'Invalid anatomical binding or root surface')
    group_names = {g.index: g.name for g in skin.vertex_groups}
    require(set(group_names.values()) == names, 'PROXY_WEIGHT_INVALID', 'Root/helper or missing vertex group')
    for vertex in skin.data.vertices:
        require(vertex.groups and all(g.group in group_names and math.isfinite(g.weight) and 0 < g.weight <= 1
                                      for g in vertex.groups)
                and abs(sum(g.weight for g in vertex.groups)-1) < 1e-5,
                'PROXY_WEIGHT_INVALID', 'A proxy vertex has invalid or missing normalized weights')
    attachments = metadata.get('attachments')
    require(isinstance(attachments, list) and 1 <= len(attachments) <= 128,
            'PROXY_GEOMETRY_INVALID', 'Invalid attachment budget')
    for item in attachments:
        require(isinstance(item, dict) and item.get('bone') in names and isinstance(item.get('indices'), list)
                and 3 <= len(item['indices']) <= 100 and len(set(item['indices'])) == len(item['indices'])
                and all(type(i) is int and 0 <= i < len(skin.data.vertices) for i in item['indices']),
                'PROXY_GEOMETRY_INVALID', 'Invalid attachment vertex set')
    lengths = [s['length_m'] for s in graph['segments']]
    tolerance = max(2e-6, max(lengths) * max(rig.matrix_world.to_scale()) * 2e-5)
    scene = bpy.context.scene; old_frame, old_subframe = scene.frame_current, scene.frame_subframe
    results = []
    try:
        for frame in frames:
            scene.frame_set(math.floor(frame), subframe=frame-math.floor(frame))
            depsgraph = bpy.context.evaluated_depsgraph_get()
            evaluated_rig = rig.evaluated_get(depsgraph); evaluated_skin = skin.evaluated_get(depsgraph)
            mesh = evaluated_skin.to_mesh()
            try:
                require(len(mesh.vertices) == metadata['vertex_count'], 'PROXY_GEOMETRY_INVALID', 'Evaluated topology changed')
                maximum = 0.
                for item in attachments:
                    centre = sum((evaluated_skin.matrix_world @ mesh.vertices[i].co for i in item['indices']), Vector()) / len(item['indices'])
                    expected = evaluated_rig.matrix_world @ evaluated_rig.pose.bones[item['bone']].head
                    maximum = max(maximum, (centre-expected).length)
                results.append({'frame': frame, 'max_attachment_error_scene_units': maximum})
            finally:
                evaluated_skin.to_mesh_clear()
    finally:
        scene.frame_set(old_frame, subframe=old_subframe)
    maximum = max(r['max_attachment_error_scene_units'] for r in results)
    require(maximum <= tolerance, 'PROXY_ATTACHMENT_FAILED',
            f'Generated surface detached from anatomical landmarks: {maximum:.9g} > {tolerance:.9g}')
    return {'status': 'PASS', 'checkpoints': results, 'attachments_per_checkpoint': len(attachments),
            'max_attachment_error_scene_units': maximum, 'tolerance_scene_units': tolerance,
            'root_and_helper_weight_count': 0, 'scope': 'evaluated segment-ring and landmark centres only',
            'surface_intersections': 'NOT_MEASURED', 'performance': 'NOT_EVALUATED'}
