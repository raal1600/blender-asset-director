"""Create one explicitly dimensioned, horizontal matte reference floor."""
import math
import bpy
from .floor_contract import validate


def create(options, owner):
    validate(options)
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
    return {'classification':'CREATE','floor':obj.name,'faces':len(faces),'size':options['size'],
            'location':list(obj.location),'existing_geometry_materials_preserved':True,'visual_acceptance':'PENDING'}
