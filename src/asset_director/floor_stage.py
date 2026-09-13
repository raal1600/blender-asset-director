"""Create one explicitly dimensioned, horizontal matte reference floor."""
import math
import bpy
from .floor_contract import validate
from .core import require


def create(options, owner):
    validate(options)
    existing_objects = {o.name:(o.type, o.data, tuple(v for row in o.matrix_world for v in row)) for o in bpy.data.objects}
    existing_materials = {m.name:m for m in bpy.data.materials}
    width,depth=options['size'];step=options['tile_size']
    nx,ny=math.ceil(width/step),math.ceil(depth/step)
    vertices=[(-width/2+width*x/nx,-depth/2+depth*y/ny,0) for y in range(ny+1) for x in range(nx+1)]
    faces=[]
    for y in range(ny):
        for x in range(nx):
            p=y*(nx+1)+x;faces.append((p,p+1,p+nx+2,p+nx+1))
    mesh=bpy.data.meshes.new('BAD_FLOOR_'+owner);mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(mesh.name,mesh);bpy.context.scene.collection.objects.link(obj);obj.location=options['location']
    for i,key in enumerate(('color','grid_color')):
        material=bpy.data.materials.new(mesh.name+'_'+str(i));material.diffuse_color=(*options[key],1);material.use_nodes=True
        bsdf=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value=(*options[key],1);bsdf.inputs['Roughness'].default_value=options['roughness']
        mesh.materials.append(material)
    for y in range(ny):
        for x in range(nx):mesh.polygons[y*nx+x].material_index=(x+y)%2
    obj['bad_job']=owner
    bpy.context.view_layer.update()
    require(all(n in bpy.data.objects and (bpy.data.objects[n].type, bpy.data.objects[n].data,
                tuple(v for row in bpy.data.objects[n].matrix_world for v in row)) == state
                for n,state in existing_objects.items()) and
            all(bpy.data.materials.get(n) == m for n,m in existing_materials.items()),
            'FLOOR_ISOLATION_VIOLATION', 'Existing object/data/material identities or object transforms changed')
    return {'classification':'CREATE','floor':obj.name,'faces':len(faces),'size':options['size'],
            'location':list(obj.location),'existing_geometry_materials_preserved':True,
            'preservation_scope':'object/data/material identities and object transforms; not a full shader hash',
            'new_materials':[m.name for m in mesh.materials],'visual_acceptance':'PENDING'}
