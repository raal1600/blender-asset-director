"""Generated scene and unrelated GUI sentinel. Disposable native CI use only."""
import bpy
import json
import sys
import time
from pathlib import Path
from mathutils import Vector

mode, destination = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.view_layer.objects.active
obj.name = 'NativeSubject' if mode == 'seed' else 'UnrelatedUnsavedSentinel'
if mode == 'seed':
    camera = bpy.data.objects.new('NativeCamera', bpy.data.cameras.new('NativeCamera'))
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (4, -6, 4)
    camera.rotation_euler = (-camera.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = camera
    bpy.ops.wm.save_as_mainfile(filepath=destination)
elif mode == 'sentinel':
    import gpu
    graphics = dict(renderer=gpu.platform.renderer_get(), vendor=gpu.platform.vendor_get(), version=gpu.platform.version_get())
    obj.location = (17, 3, 2)
    def pulse():
        value = dict(name=obj.name, location=list(obj.location), file=bpy.data.filepath,
                     dirty=bool(bpy.data.is_dirty), observed_at=time.time(), gpu=graphics)
        target = Path(destination); tmp = target.with_suffix('.tmp')
        tmp.write_text(json.dumps(value), encoding='utf-8'); tmp.replace(target)
        return 1.0
    bpy.app.timers.register(pulse, first_interval=.1, persistent=True)
else:
    raise ValueError('Unknown native fixture mode')
