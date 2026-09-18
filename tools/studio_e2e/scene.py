"""Generate only synthetic geometry and animation for disposable E2E tests."""
import sys
from pathlib import Path
import bpy
from mathutils import Vector

out = Path(sys.argv[sys.argv.index('--') + 1])
out.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.object
obj.name = 'Synthetic_E2E_Cube'
obj.location.x = -0.25
obj.keyframe_insert('location', frame=1)
obj.location.x = 0.25
obj.keyframe_insert('location', frame=12)
bpy.ops.object.camera_add(location=(4, -6, 4))
camera = bpy.context.object
camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = camera
bpy.ops.object.light_add(type='AREA', location=(1, -3, 5))
bpy.context.object.name = 'Synthetic_E2E_Key'
bpy.context.object.data.energy = 500
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
# This fixture tests direct scene rendering, not compositor/VSE output.
scene.render.use_compositing = scene.render.use_sequencer = False
scene.cycles.device = 'CPU'
scene.cycles.samples = 7
scene.render.resolution_x = 320
scene.render.resolution_y = 180
scene.render.resolution_percentage = 100
world = bpy.data.worlds.new('Synthetic_E2E_World')
world.use_nodes = True
scene.world = world
scene.frame_end = 12
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out))
