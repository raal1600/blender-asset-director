"""Portable contract for explicitly selected evaluated-pose retargeting."""
import math
from .core import fields, require


def validate(config):
    fields(config, {'rotation', 'translation_bone', 'translation_scale', 'target_origin', 'ground_contact'},
           {'rotation', 'translation_bone', 'translation_scale', 'target_origin'})
    for key, count in [('rotation', 9), ('target_origin', 3)]:
        values = config[key]
        require(isinstance(values, list) and len(values) == count and
                all(type(v) in (int, float) and math.isfinite(v) for v in values),
                'INVALID_POSE_TRANSFER', 'Expected finite rotation and origin vectors')
    r = config['rotation']
    rows = [r[i:i+3] for i in (0, 3, 6)]
    require(all(abs(sum(a*b for a,b in zip(rows[i], rows[j]))-(i == j)) < 1e-4
                for i in range(3) for j in range(3)),
            'INVALID_POSE_TRANSFER', 'Rotation must be orthonormal')
    det = r[0]*(r[4]*r[8]-r[5]*r[7])-r[1]*(r[3]*r[8]-r[5]*r[6])+r[2]*(r[3]*r[7]-r[4]*r[6])
    require(abs(det-1) < 1e-4, 'INVALID_POSE_TRANSFER', 'Reflections are not supported')
    scale = config['translation_scale']
    require(type(scale) in (int, float) and math.isfinite(scale) and 0 < scale <= 100,
            'INVALID_POSE_TRANSFER', 'Specify a positive bounded translation scale')
    require(isinstance(config['translation_bone'], str) and config['translation_bone'].strip(),
            'INVALID_POSE_TRANSFER', 'Specify the mapped target translation bone')
    if 'ground_contact' in config:
        ground=config['ground_contact']
        fields(ground, {'mesh','vertex_groups','height','max_correction'}, {'mesh','vertex_groups','height','max_correction'})
        require(isinstance(ground['mesh'],str) and ground['mesh'].strip(), 'INVALID_GROUND_CONTACT','Name the skinned mesh')
        names=ground['vertex_groups']
        require(isinstance(names,list) and 1<=len(names)<=16 and all(isinstance(n,str) and n.strip() for n in names),
                'INVALID_GROUND_CONTACT','Specify measured sole vertex groups')
        require(type(ground['height']) in (int,float) and math.isfinite(ground['height']) and abs(ground['height'])<=1e4,
                'INVALID_GROUND_CONTACT','Invalid ground height')
        cap=ground['max_correction']
        require(type(cap) in (int,float) and math.isfinite(cap) and 0<cap<=1,
                'INVALID_GROUND_CONTACT','Vertical correction cap must be in (0,1] scene units')
