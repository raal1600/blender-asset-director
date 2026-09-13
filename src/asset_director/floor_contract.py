"""Bounded additive floor contract; no changes to existing scene materials."""
import math
from .core import fields, require


def validate(options):
    fields(options, {'size','location','color','grid_color','tile_size','roughness'},
           {'size','location','color','grid_color','tile_size','roughness'})
    for key,count in [('size',2),('location',3),('color',3),('grid_color',3)]:
        v=options[key]
        require(isinstance(v,list) and len(v)==count and all(type(x) in (int,float) and math.isfinite(x) and abs(x)<=1e4 for x in v),
                'INVALID_FLOOR','Floor vectors must be finite and bounded')
    require(all(0<x<=1000 for x in options['size']), 'INVALID_FLOOR','Positive floor dimensions required')
    require(all(0<=x<=1 for key in ('color','grid_color') for x in options[key]),'INVALID_FLOOR','Invalid floor colors')
    step=options['tile_size'];roughness=options['roughness']
    require(type(step) in (int,float) and math.isfinite(step) and .01<=step<=1000,'INVALID_FLOOR','Invalid tile size')
    require(type(roughness) in (int,float) and math.isfinite(roughness) and 0<=roughness<=1,'INVALID_FLOOR','Invalid roughness')
    require(math.ceil(options['size'][0]/step)*math.ceil(options['size'][1]/step)<=16384,
            'RESOURCE_LIMIT','Floor grid exceeds 16384 faces')
