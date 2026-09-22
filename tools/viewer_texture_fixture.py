"""Real Blender checks called by the existing asset-preview evidence partition."""
import json
import struct
import bpy
from asset_director.core import file_hash
from asset_director.viewer_export import preview_textures


def run(source, preview, check):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    mesh = bpy.context.object
    image = bpy.data.images.new('LargeExternalPreviewTexture', width=4096, height=1024)
    image.generated_color = (.8, .2, .05, 1)
    image.filepath_raw = str(source/'textures/large.png')
    image.file_format = 'PNG'
    image.save()
    image.source = 'FILE'
    image.reload()
    packed = bpy.data.images.load(str(source/'textures/large.png'), check_existing=False)
    packed.name = 'LargePackedPreviewTexture'
    packed.pack()
    for item in (image, packed):
        material = bpy.data.materials.new(item.name)
        material.use_nodes = True
        node = material.node_tree.nodes.new('ShaderNodeTexImage')
        node.image = item
        material.node_tree.links.new(node.outputs['Color'], material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        mesh.data.materials.append(material)
    for polygon in mesh.data.polygons:
        polygon.material_index = polygon.index % 2
    image.filepath = '//textures/large.png'
    bpy.ops.wm.save_as_mainfile(filepath=str(source/'large-textures.blend'))
    before = {p: file_hash(source/p) for p in ('large-textures.blend', 'textures/large.png')}
    result, directory = preview('embedded-large-textures', 'large-textures.blend', embedded=True, kind='checkpoint')
    textures = result['data']['embedded_viewer']['textures']
    check(textures['reduced_images'] == 2 and textures['originals_changed'] is False,
          'packed and external textures report preview-only reduction')
    model = (directory/result['model']['path']).read_bytes()
    length = struct.unpack_from('<I', model, 12)[0]
    document = json.loads(model[20:20+length])
    binary = model[28+length:]
    check(len(document['images']) == 2, 'both textured material bindings exported')
    for index, record in enumerate(document['images']):
        view = document['bufferViews'][record['bufferView']]
        data = binary[view.get('byteOffset', 0):view.get('byteOffset', 0)+view['byteLength']]
        check(data[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack_from('>II', data, 16) == (2048, 512),
              'exported image %s contains reduced PNG bytes, not original packed/file bytes' % index)
        target = directory/('decoded-texture-%s.png' % index)
        target.write_bytes(data)
        decoded = bpy.data.images.load(str(target), check_existing=False)
        check(decoded.pixels[0] > decoded.pixels[1] > decoded.pixels[2] > 0,
              'exported image %s retains genuine color pixels' % index)
        bpy.data.images.remove(decoded)
    bpy.ops.wm.open_mainfile(filepath=str(directory/result['blend']['path']), load_ui=False, use_scripts=False)
    for name in ('LargeExternalPreviewTexture', 'LargePackedPreviewTexture'):
        check(list(bpy.data.images[name].size) == [4096, 1024], name+' remains full resolution in Blender copy')
    check(all(file_hash(source/p) == digest for p, digest in before.items()), 'large source blend and texture bytes unchanged')
    bindings = [m.node_tree.nodes.get('Image Texture') for m in bpy.context.object.data.materials]
    original_images = [n.image for n in bindings]
    names = set(bpy.data.images.keys())
    try:
        with preview_textures():
            check(all(n.image != original for n, original in zip(bindings, original_images)), 'export temporarily uses copied image bindings')
            raise RuntimeError('Deliberate synthetic exporter failure')
    except RuntimeError as error:
        check(str(error) == 'Deliberate synthetic exporter failure', 'controlled export failure retained')
    check(set(bpy.data.images.keys()) == names and all(n.image == original for n, original in zip(bindings, original_images)),
          'failed export restores original bindings and removes temporary image datablocks')
    dirty = bpy.data.images.new('UnsavedPreviewPixels', width=4096, height=1)
    dirty.pixels[0:4] = (.7, .3, .1, 1)
    node = bindings[0]
    node.image = dirty
    before_pixel = list(dirty.pixels[:4])
    with preview_textures():
        check(node.image != dirty and node.image.is_dirty and node.image.pixels[0] > 0,
              'unsaved generated pixels copied before resizing')
    check(node.image == dirty and list(dirty.size) == [4096, 1] and list(dirty.pixels[:4]) == before_pixel,
          'unsaved source pixels and dimensions survive temporary reduction')
