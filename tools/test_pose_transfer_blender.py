"""Headless regression: unlike bone rolls, rotated/scaled objects and hip travel.

Run with Blender --background --factory-startup --python this_file. Generates
only an in-memory synthetic fixture; no user files or backend downloads.
"""
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from asset_director.pose_transfer import PoseTransfer
from asset_director.core import DirectorError

assert bpy.app.background
bpy.ops.wm.read_factory_settings(use_empty=True)


def rig(name, length, roll, angle, scale):
    data = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    previous = None
    for i in range(3):
        bone = data.edit_bones.new(str(i))
        bone.head = (0,0,i*length)
        bone.tail = (0,0,(i+1)*length)
        bone.roll = roll*(i+1)
        bone.parent = previous
        previous = bone
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.rotation_euler.z = angle
    obj.scale = (scale,)*3
    obj.select_set(False)
    bpy.context.view_layer.update()
    return obj


source = rig('source',1,0.13,0.8,0.7)
target = rig('target',1.4,-0.48,-0.5,1.3)
c = target.matrix_world.to_quaternion().to_matrix() @ source.matrix_world.to_quaternion().to_matrix().inverted()
config = dict(rotation=[v for row in c for v in row], translation_bone='0',
              translation_scale=2.6, target_origin=[2,3,0])
transfer = PoseTransfer(source,target,{str(i):str(i) for i in range(3)},config)
source_origin = None
maximum_error = 0
naive_error = 0
for f in range(25):
    for i,b in enumerate(source.pose.bones):
        b.rotation_mode='XYZ'
        b.rotation_euler=(0.5*math.sin(f/8+i),0.2*math.cos(f/5+i),0.1*i)
    source.pose.bones['0'].location=(f*.03,0,0)
    bpy.context.view_layer.update()
    if source_origin is None:
        source_origin=source.matrix_world@source.pose.bones['0'].head
    for name,mat in transfer.matrices().items():
        target.pose.bones[name].matrix_basis=mat
    bpy.context.view_layer.update()
    for i in range(2):
        sv=c@source.matrix_world.to_3x3()@(source.pose.bones[str(i+1)].head-source.pose.bones[str(i)].head)
        tv=target.matrix_world.to_3x3()@(target.pose.bones[str(i+1)].head-target.pose.bones[str(i)].head)
        maximum_error=max(maximum_error,sv.normalized().cross(tv.normalized()).length)
        assert (sv.normalized()-tv.normalized()).length < 1e-4
    expected=Vector(config['target_origin'])+config['translation_scale']*(c@((source.matrix_world@source.pose.bones['0'].head)-source_origin))
    assert ((target.matrix_world@target.pose.bones['0'].head)-expected).length < 1e-4
    # An unchanged local rotation does not represent the same world pose on a
    # differently rolled target skeleton; ensure this fixture exercises it.
    target.pose.bones['0'].matrix_basis=source.pose.bones['0'].matrix_basis
    bpy.context.view_layer.update()
    sv=c@source.matrix_world.to_3x3()@(source.pose.bones['1'].head-source.pose.bones['0'].head)
    tv=target.matrix_world.to_3x3()@(target.pose.bones['1'].head-target.pose.bones['0'].head)
    naive_error=max(naive_error,(sv.normalized()-tv.normalized()).length)
assert naive_error > .05

source.pose.bones['1'].location.x=.2
bpy.context.view_layer.update()
try:
    transfer.matrices()
    raise AssertionError('Unreviewed non-anchor translation was accepted')
except DirectorError as error:
    assert error.code=='NON_ANCHOR_TRANSLATION'
source.pose.bones['1'].location.x=0
source.pose.bones['1'].scale.x=1.2
bpy.context.view_layer.update()
try:
    transfer.matrices()
    raise AssertionError('Pose scale was accepted')
except DirectorError as error:
    assert error.code=='ANIMATED_SCALE_UNSUPPORTED'
source.pose.bones['1'].scale.x=1
source.location.x=.2
bpy.context.view_layer.update()
try:
    transfer.matrices()
    raise AssertionError('Animated object transform was accepted')
except DirectorError as error:
    assert error.code=='OBJECT_TRANSFORM_CHANGED'
print('POSE_TRANSFER_REGRESSION_PASS', {'max_cross_error':maximum_error,'naive_vector_error':naive_error,'frames':25})
