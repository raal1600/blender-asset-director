"""Actual saved dependency observations; synthetic only, no scene approval."""
from pathlib import Path
import sys
import bpy
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director.core import Asset, Library, atomic_json, file_hash
from asset_director.scene_ops import scene_audit
from asset_director.preview_dependencies import inventory

out = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
out.mkdir(parents=True, exist_ok=False)
library = out / 'Catalog'
checks = []
report = {'kind': 'SYNTHETIC_NATIVE_DEPENDENCY_INVENTORY', 'checks': checks}
try:
    with Library(library) as lib:
        texture_path = lib.root / 'incoming/color.png'
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add()
        bpy.context.object.name = 'DependencySubject'
        image = bpy.data.images.new('RecordedTexture', width=2, height=2)
        image.pixels[:] = [.1, .6, .9, 1] * 4
        image.file_format = 'PNG'
        image.filepath_raw = str(texture_path)
        image.save()
        material = bpy.data.materials.new('DependencyMaterial')
        material.use_nodes = True
        node = material.node_tree.nodes.new('ShaderNodeTexImage')
        node.image = image
        material.node_tree.links.new(node.outputs['Color'], material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        bpy.context.object.data.materials.append(material)
        absolute = out / 'absolute.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(absolute), relative_remap=False)
        bpy.ops.wm.open_mainfile(filepath=str(absolute), load_ui=False, use_scripts=False)
        audit = scene_audit()
        expected = {'version': 'preview-dependencies-v1', 'mode': 'EXACT_ABSOLUTE_FILES',
                    'source_sha256': file_hash(absolute), 'paths': [str(texture_path.resolve())]}
        assert audit['preview_dependencies'] == expected, audit['preview_dependencies']
        checks.append('Absolute recorded texture inventory binds exact saved scene bytes')
        atomic_json(out / 'audit.json', audit)
        bpy.data.images['RecordedTexture'].filepath = '//Catalog/incoming/color.png'
        bpy.ops.wm.save_as_mainfile(filepath=str(out / 'relative.blend'))
        assert inventory()['mode'] == 'ALL_PINNED'
        checks.append('Relative resources keep conservative copying')
        bpy.ops.wm.open_mainfile(filepath=str(absolute), load_ui=False, use_scripts=False)
        bpy.data.images['RecordedTexture'].source = 'SEQUENCE'
        bpy.ops.wm.save_as_mainfile(filepath=str(out / 'sequence.blend'))
        assert inventory()['mode'] == 'ALL_PINNED'
        checks.append('Time-varying image sequence is not narrowed to one file')
        bpy.ops.wm.open_mainfile(filepath=str(absolute), load_ui=False, use_scripts=False)
        bpy.data.images['RecordedTexture'].pack()
        packed = out / 'packed.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(packed))
        assert inventory()['mode'] == 'EXACT_ABSOLUTE_FILES' and inventory()['paths'] == []
        checks.append('Packed image does not need an external copy')
        bpy.ops.wm.open_mainfile(filepath=str(absolute), load_ui=False, use_scripts=False)
        modifier = bpy.data.objects['DependencySubject'].modifiers.new('UnrecordedCache', 'MESH_CACHE')
        modifier.filepath = str(out / 'unrecorded.pc2')
        bpy.ops.wm.save_as_mainfile(filepath=str(out / 'cache.blend'), relative_remap=False)
        assert inventory()['mode'] == 'ALL_PINNED'
        checks.append('Unknown modifier file path retains conservative copying')
        bpy.ops.wm.read_factory_settings(use_empty=True)
        with bpy.data.libraries.load(str(absolute), link=True) as (_, target):
            target.objects = ['DependencySubject']
        bpy.context.scene.collection.objects.link(target.objects[0])
        bpy.ops.wm.save_as_mainfile(filepath=str(out / 'linked.blend'), relative_remap=False)
        assert inventory()['mode'] == 'ALL_PINNED'
        checks.append('Linked library retains conservative copying')
        unrelated = lib.root / 'incoming/unrelated.bin'
        unrelated.write_bytes(b'not part of the scene' * (2 ** 18))
        files = [{'path': p.relative_to(lib.root).as_posix(), 'sha256': file_hash(p), 'size': p.stat().st_size}
                 for p in [texture_path, unrelated]]
        asset = Asset('local', 'synthetic-preview-dependencies', 'Synthetic dependency package', 'pack', '', local_files=files)
        lib.put(asset)
        report.update(asset_id=asset.id, files=files, source={'path': str(absolute), 'sha256': file_hash(absolute), 'size': absolute.stat().st_size}, status='PASS')
except Exception as error:
    report.update(status='FAIL', error=str(error))
    raise
finally:
    atomic_json(out / 'RESULTS.json', report)
