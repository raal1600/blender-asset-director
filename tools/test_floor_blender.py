"""Isolated floor/contact regression. No files are loaded or saved."""
import sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from asset_director.floor_stage import create
from asset_director.ground_contact import GroundContact
from asset_director.core import DirectorError

assert bpy.app.background
bpy.ops.wm.read_factory_settings(use_empty=True)
arm=bpy.data.armatures.new('test_rig');rig=bpy.data.objects.new('test_rig',arm);bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
bone=arm.edit_bones.new('anchor');bone.head=(0,0,0);bone.tail=(0,0,1);bpy.ops.object.mode_set(mode='OBJECT')
mesh=bpy.data.meshes.new('test_sole');mesh.from_pydata([(-.1,-.1,.2),(.1,-.1,.2),(.1,.1,.2),(-.1,.1,.2)],[],[(0,1,2,3)])
obj=bpy.data.objects.new('test_sole',mesh);bpy.context.collection.objects.link(obj)
group=obj.vertex_groups.new(name='anchor');group.add(list(range(4)),1,'REPLACE');mod=obj.modifiers.new('skin','ARMATURE');mod.object=rig
rig.rotation_euler.z=.7;rig.scale=(1.4,)*3;bpy.context.view_layer.update()
before=[tuple(v.co) for v in mesh.vertices]
contact=GroundContact(rig,'anchor',dict(mesh=obj.name,vertex_groups=['anchor'],height=0,max_correction=.3))
contact.apply(1)
assert abs(contact.minimum())<1e-5
assert before==[tuple(v.co) for v in mesh.vertices]
contact.config['height']=2
try:
    contact.apply(2)
    raise AssertionError('Correction cap was ignored')
except DirectorError as e:assert e.code=='GROUND_CORRECTION_LIMIT'
existing=set(bpy.data.objects)
r=create(dict(size=[4,6],location=[1,2,0],color=[.2]*3,grid_color=[.22]*3,tile_size=1,roughness=.8),'test')
assert set(bpy.data.objects)-existing=={bpy.data.objects[r['floor']]}
assert r['faces']==24 and before==[tuple(v.co) for v in mesh.vertices]
assert len(mesh.materials)==0
# Same-count deform modifiers are not proof of stable selected vertex indices.
unsupported=obj.modifiers.new('UnreviewedDeform','SMOOTH')
try:
    contact.minimum()
    raise AssertionError('An unreviewed modifier was accepted')
except DirectorError as e:assert e.code=='CONTACT_MODIFIER_UNSUPPORTED'
obj.modifiers.remove(unsupported)
# Same vertex count but changed connectivity must be refused.
mesh.clear_geometry();mesh.from_pydata([(-.1,-.1,.2),(.1,-.1,.2),(.1,.1,.2),(-.1,.1,.2)],[],[(0,1,2),(0,2,3)])
try:
    contact.minimum()
    raise AssertionError('Same-count topology replacement was accepted')
except DirectorError as e:assert e.code=='CONTACT_TOPOLOGY_CHANGED'
print('FLOOR_CONTACT_REGRESSION_PASS')
