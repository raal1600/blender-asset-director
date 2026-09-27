"""Owned generated Action task. Actual background selection/save, not native dialogs."""
from pathlib import Path
import sys
import bpy
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director.core import load_json, atomic_json, file_hash, within
from asset_director import action_layer, action_task, task_workspace, task_save, world_placement

manifest, mode = sys.argv[sys.argv.index('--') + 1:]
task = load_json(Path(manifest)); project = Path(task['projectDirectory'])
assert load_json(project / 'project.json')['name'].startswith(('Synthetic Action handoff', 'Synthetic Action browser'))
assert mode in {'no-save', 'save', 'saved-then-unsaved'}
original = within(project, task['input']['path']); source_hash = file_hash(original)
state = task_workspace.initialize(task)
assert not state['gui_configured']
rig = bpy.context.scene.objects[task['actionContext']['performer']]
assert bpy.context.view_layer.objects.active == rig
assert bpy.context.scene.frame_current == task['frame'] == 5
assert not bpy.context.scene.use_preview_range
assert rig.mode == ('POSE' if task['rigControls'] else 'OBJECT')
working = within(project, task['workingScene']); initial_hash = file_hash(working)
snapshot = action_layer.preserved(set())
render_flags = {o.name: o.hide_render for o in world_placement.widgets(bpy.context.scene)}
action_task.install_tools(task)
for enabled in [True, False, True, False]:
    assert bpy.ops.asset_director.action_controls(enabled=enabled) == {'FINISHED'}
    assert rig.mode == ('POSE' if enabled else 'OBJECT')
    assert bpy.context.view_layer.objects.active == rig
    assert action_layer.preserved(set()) == snapshot
    assert {o.name: o.hide_render for o in world_placement.widgets(bpy.context.scene)} == render_flags
task_save.install(task, state)
assert not task_save.save_file(task).exists(), 'Setup/display never counts as explicit Save'
bpy.context.scene['synthetic_action_edit'] = 1
if mode != 'no-save':
    bpy.ops.wm.save_as_mainfile(filepath=str(working), check_existing=False)
    receipt = load_json(task_save.save_file(task))
    assert receipt['sha256'] == file_hash(working) and receipt['human_acceptance'] == 'PENDING'
    if mode == 'saved-then-unsaved':
        bpy.context.scene['synthetic_action_edit'] = 2
    assert file_hash(working) == receipt['sha256'], 'Unsaved changes must not replace the last explicit Save'
else:
    assert file_hash(working) == initial_hash and not task_save.save_file(task).exists()
assert file_hash(original) == source_hash
atomic_json(project / 'Docs/action-task-native.json', {'status': 'PASS', 'mode': mode,
            'selected': rig.name, 'frame': bpy.context.scene.frame_current,
            'initial_rig_controls': task['rigControls'], 'preserved_motion': True,
            'render_flags_preserved': True, 'native_dialogs': 'NOT_TESTED'})
