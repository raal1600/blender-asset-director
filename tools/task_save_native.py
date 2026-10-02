"""Disposable Blender save-handler fixture. Never opens a user project.

Run through task_save_native.mjs. Background execution proves actual .blend
saves/handlers, not native X/Save/Don't Save dialog interaction.
"""
from pathlib import Path
import sys
import bpy
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director.core import load_json, within, atomic_json, file_hash
from asset_director.task_workspace import main
from asset_director.task_save import save_file, session_file

manifest, mode = sys.argv[sys.argv.index('--') + 1:]
task = load_json(Path(manifest))
project = Path(task['projectDirectory'])
assert project.parent.name == 'Projects' and project.parent.parent.name == 'Workspace'
assert load_json(project / 'project.json')['name'].startswith('Synthetic Save Return ')
main(manifest)
working = within(project, task['workingScene'])
assert not save_file(task).exists(), 'Initialization must not count as user Save'
initial = file_hash(working)
if mode.startswith('world-'):
    from asset_director.world_placement import select_instances, ancestor_control
    skin=bpy.data.objects['SyntheticSkin0']
    obj=ancestor_control(skin)
    assert obj is not None
    assert select_instances([skin,bpy.data.objects['SyntheticRig0']]) == {obj}
else:
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    obj.name = 'ExplicitSaveSubject'
obj.location.x = 1
bpy.context.view_layer.update()
if mode in {'save', 'saved-then-unsaved', 'repeat-save', 'world-save'}:
    bpy.ops.wm.save_as_mainfile(filepath=str(working), check_existing=False)
    assert save_file(task).exists()
    first = load_json(save_file(task))
    assert first['sha256'] == file_hash(working)
    history = project / 'Docs' / 'Workbench' / ('save-' + first['saveId'] + '.json')
    assert load_json(history) == first
    history_hash = file_hash(history)
    if mode in {'saved-then-unsaved', 'repeat-save'}:
        obj.location.x = 9
    if mode == 'repeat-save':
        bpy.ops.wm.save_as_mainfile(filepath=str(working), check_existing=False)
        assert first['saveId'] != load_json(save_file(task))['saveId']
        assert file_hash(history) == history_hash
elif mode == 'recovery-copy':
    bpy.ops.wm.save_as_mainfile(filepath=str(project / 'Scenes' / 'recovery-only.blend'), check_existing=False, copy=True)
    assert not save_file(task).exists(), 'A different recovery/copy destination must not publish'
elif mode in {'no-save', 'world-no-save'}:
    assert not save_file(task).exists()
else:
    raise ValueError('Unknown fixture mode')
if mode in {'no-save', 'recovery-copy', 'world-no-save'}:
    assert file_hash(working) == initial
atomic_json(project / 'Docs' / 'native-save-result.json', dict(mode=mode, status='PASS',
            background=bpy.app.background, session=load_json(session_file(task))['state'],
            in_memory_x=obj.location.x, saved_sha256=file_hash(working), original_unchanged=True))
