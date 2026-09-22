"""Portable texture budget for disposable native-to-WebGL inspection only."""
from .core import require

MAX_EDGE = 2048
MAX_PIXELS = 16 * 1024**2
MAX_SOURCE_PIXELS = 128 * 1024**2


def plan(images):
    require(len(images) <= 128, 'RESOURCE_LIMIT', 'Too many textures for in-app preview; inspect in Blender')
    require(all(i['source'] in {'FILE', 'GENERATED', 'VIEWER'} for i in images),
            'VIEWER_UNSUPPORTED', 'Sequence/movie/UDIM textures require Blender inspection')
    sizes = [i['size'] for i in images]
    require(all(len(s) == 2 and all(type(v) is int and 0 <= v <= 8192 for v in s)
                and (all(s) or s == [0, 0]) for s in sizes),
            'RESOURCE_LIMIT', 'Source texture dimensions exceed the bounded preview conversion; inspect in Blender')
    original_pixels = sum(w * h for w, h in sizes)
    require(original_pixels <= MAX_SOURCE_PIXELS, 'RESOURCE_LIMIT',
            'Source textures exceed the bounded preview conversion; inspect in Blender')
    output = []
    for width, height in sizes:
        factor = min(1, MAX_EDGE / max(width, height)) if width and height else 1
        output.append([max(1, int(width * factor)), max(1, int(height * factor))] if width and height else [0, 0])
    while sum(w * h for w, h in output) > MAX_PIXELS:
        output = [[max(1, w // 2), max(1, h // 2)] if w and h else [0, 0] for w, h in output]
    return {'scope': 'PREVIEW_ONLY', 'originals_changed': False,
            'source_pixels': original_pixels, 'preview_pixels': sum(w * h for w, h in output),
            'reduced_images': sum(a != b for a, b in zip(sizes, output)),
            'images': [{'name': i['name'], 'source_size': list(before), 'preview_size': after}
                       for i, before, after in zip(images, sizes, output)]}
