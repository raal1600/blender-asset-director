"""Independently reopen real production output; never modify or save either input."""
import json
from pathlib import Path
import sys

import bpy

original, produced, camera_name, output = sys.argv[sys.argv.index('--')+1:]


def subject_snapshot(filename):
    bpy.ops.wm.open_mainfile(filepath=filename, load_ui=False, use_scripts=False)
    obj = bpy.data.objects['Synthetic_E2E_Cube']
    positions = []
    for frame in (1, 12):
        bpy.context.scene.frame_set(frame)
        positions.append(list(obj.matrix_world.translation))
    return {'vertices': [list(v.co) for v in obj.data.vertices], 'positions': positions}


baseline = subject_snapshot(original)
current = subject_snapshot(produced)
assert baseline == current, 'Production changed the generated source geometry or motion'
scene = bpy.context.scene
assert scene.camera.name == camera_name
assert scene.camera.animation_data and scene.camera.animation_data.action
camera_positions = []
for frame in (1, 12):
    scene.frame_set(frame)
    camera_positions.append(list(scene.camera.matrix_world.translation))
assert camera_positions[0] != camera_positions[1], 'Camera move was not persisted'
assert abs(bpy.data.objects['Synthetic_E2E_Key'].data.energy - 125) < 1e-5
assert abs(scene.view_settings.exposure - .25) < 1e-5
background = next(node for node in scene.world.node_tree.nodes if node.type == 'BACKGROUND')
assert abs(background.inputs['Strength'].default_value - .3) < 1e-5
assert [scene.render.resolution_x, scene.render.resolution_y] == [320, 180]
assert scene.cycles.samples == 7
Path(output).write_text(json.dumps({'status': 'PASS', 'camera': camera_name,
    'camera_positions': camera_positions, 'original_geometry_and_motion': 'PRESERVED',
    'light_energy': 125, 'world_strength': .3, 'exposure': .25,
    'production_settings_restored': True}, indent=2), encoding='utf-8')
