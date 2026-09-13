"""Opt-in vertical anchor correction for explicitly grounded source motion.

Uses measured weighted sole vertices, not ankle origins. Does not change joint
rotations or lock horizontal feet, and must not be used for jumping motion.
"""
import bpy
from mathutils import Vector
from .core import require


class GroundContact:
    def __init__(self, target, anchor, config):
        self.target,self.anchor,self.config=target,anchor,config
        self.mesh=bpy.data.objects.get(config['mesh'])
        require(self.mesh and self.mesh.type=='MESH' and
                any(m.type=='ARMATURE' and m.object==target for m in self.mesh.modifiers),
                'INVALID_GROUND_CONTACT','Expected a mesh skinned to this target')
        require(len(self.mesh.data.vertices)<=2_000_000,'RESOURCE_LIMIT','Contact mesh exceeds vertex limit')
        require(all(self.mesh.vertex_groups.get(n) for n in config['vertex_groups']),
                'INVALID_GROUND_CONTACT','Sole vertex group missing')
        groups={self.mesh.vertex_groups[n].index for n in config['vertex_groups']}
        self.indices=[v.index for v in self.mesh.data.vertices if any(g.group in groups and g.weight>.1 for g in v.groups)]
        require(self.indices and len(self.indices)<=500_000,'RESOURCE_LIMIT','Invalid sole vertex selection')
        self.corrections=[]

    def minimum(self):
        evaluated=self.mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=evaluated.to_mesh()
        try:
            require(len(mesh.vertices)==len(self.mesh.data.vertices),'CONTACT_TOPOLOGY_CHANGED',
                    'Contact requires stable evaluated vertex indices')
            return min((evaluated.matrix_world@mesh.vertices[i].co).z for i in self.indices)
        finally:
            evaluated.to_mesh_clear()

    def apply(self, frame):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        delta=self.config['height']-self.minimum()
        require(abs(delta)<=self.config['max_correction'],'GROUND_CORRECTION_LIMIT',
                'Required vertical correction exceeds reviewed cap')
        target=self.target;pb=target.pose.bones[self.anchor];pose=pb.matrix.copy()
        pose.translation+=target.matrix_world.inverted().to_3x3()@Vector((0,0,delta))
        bone=pb.bone;parent=pb.parent
        local=(bone.convert_local_to_pose(pose,bone.matrix_local,parent_matrix=parent.matrix,
                 parent_matrix_local=parent.bone.matrix_local,invert=True) if parent
               else bone.convert_local_to_pose(pose,bone.matrix_local,invert=True))
        pb.location=local.to_translation();pb.keyframe_insert('location',frame=frame,group=pb.name)
        bpy.context.view_layer.update()
        require(abs(self.minimum()-self.config['height'])<1e-4,'GROUND_CONTACT_FAILED',
                'Vertical correction did not resolve the measured sole height')
        self.corrections.append(delta)

    def report(self):
        return {'method':'vertical anchor offset from weighted sole vertices; no horizontal IK',
                'floor_z':self.config['height'],'vertices':len(self.indices),'frames':len(self.corrections),
                'max_abs_correction':max(map(abs,self.corrections),default=0),'not_measured':['pressure','horizontal foot lock','naturalness']}
