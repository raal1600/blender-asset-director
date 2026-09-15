"""Opt-in vertical anchor correction for explicitly grounded source motion.

Uses measured weighted sole vertices, not ankle origins. Does not change joint
rotations or lock horizontal feet, and must not be used for jumping motion.
"""
import array
import hashlib
import math
import bpy
from mathutils import Vector
from .core import require


def topology(mesh):
    """Index/connectivity fingerprint; never treat equal vertex counts as proof."""
    require(len(mesh.loops) <= 8_000_000, 'RESOURCE_LIMIT', 'Contact topology exceeds loop bound')
    h = hashlib.sha256(str((len(mesh.vertices), len(mesh.edges), len(mesh.polygons))).encode())
    for collection, field, count in ((mesh.edges, 'vertices', len(mesh.edges)*2),
                                      (mesh.loops, 'vertex_index', len(mesh.loops)),
                                      (mesh.polygons, 'loop_total', len(mesh.polygons))):
        data = array.array('i', [0]) * count
        collection.foreach_get(field, data)
        h.update(data.tobytes())
    return h.hexdigest()


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
        # Only skin deformation is accepted. Same-count remeshing can reorder indices.
        self.check_modifiers()
        self.topology = topology(self.mesh.data)
        self.corrections=[]
        self.verification={}

    def check_modifiers(self):
        active = [m for m in self.mesh.modifiers if m.show_viewport or m.show_render]
        require(len(active) == 1 and active[0].type == 'ARMATURE' and active[0].object == self.target
                and active[0].show_viewport and active[0].show_render,
                'CONTACT_MODIFIER_UNSUPPORTED', 'Contact requires exactly one active target Armature modifier; other modifiers need review')

    def minimum(self):
        self.check_modifiers()
        require(topology(self.mesh.data) == self.topology, 'CONTACT_TOPOLOGY_CHANGED', 'Base sole topology changed')
        evaluated=self.mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=evaluated.to_mesh()
        try:
            require(topology(mesh)==self.topology,'CONTACT_TOPOLOGY_CHANGED',
                    'Contact requires stable evaluated vertex indices')
            return min((evaluated.matrix_world@mesh.vertices[i].co).z for i in self.indices)
        finally:
            evaluated.to_mesh_clear()

    def apply(self, frame, original_anchor=None):
        bpy.context.scene.frame_set(math.floor(frame), subframe=frame-math.floor(frame))
        bpy.context.view_layer.update()
        delta=self.config['height']-self.minimum()
        target=self.target;pb=target.pose.bones[self.anchor]
        before=target.matrix_world@pb.head
        total=delta if original_anchor is None else before.z+delta-original_anchor.z
        require(math.isfinite(total) and abs(total)<=self.config['max_correction'],'GROUND_CORRECTION_LIMIT',
                'Required vertical correction exceeds reviewed cap')
        pose=pb.matrix.copy()
        pose.translation+=target.matrix_world.inverted().to_3x3()@Vector((0,0,delta))
        bone=pb.bone;parent=pb.parent
        local=(bone.convert_local_to_pose(pose,bone.matrix_local,parent_matrix=parent.matrix,
                 parent_matrix_local=parent.bone.matrix_local,invert=True) if parent
               else bone.convert_local_to_pose(pose,bone.matrix_local,invert=True))
        pb.location=local.to_translation();pb.keyframe_insert('location',frame=frame,group=pb.name)
        # Newly inserted fractional keys must not introduce automatic Bezier
        # handles. Only anchor-location curves are touched; rotations stay intact.
        from .blender_ops import curves
        for curve in curves(target.animation_data.action, target.animation_data.action_slot):
            if curve.data_path == pb.path_from_id('location'):
                for key in curve.keyframe_points: key.interpolation='LINEAR'
        bpy.context.view_layer.update()
        require(abs(self.minimum()-self.config['height'])<1e-4,'GROUND_CONTACT_FAILED',
                'Vertical correction did not resolve the measured sole height')
        after=target.matrix_world@pb.head
        if original_anchor is not None:
            require(math.hypot(after.x-original_anchor.x, after.y-original_anchor.y)<1e-5,
                    'GROUND_CONTACT_FAILED','Vertical repair changed sampled horizontal anchor travel')
        self.corrections.append(total)

    def check_work(self, baked_frames, max_frames=361):
        from .ground_sampling import correction_frames
        frames = correction_frames(baked_frames, self.config.get('subdivisions', 1), max_frames)
        require(len(frames)*len(self.mesh.data.vertices)*3 <= 50_000_000,
                'RESOURCE_LIMIT', 'Ground-contact evaluation budget exceeded')
        return frames

    def correct(self, baked_frames, max_frames=361):
        """Correct the finished action, then verify all declared checkpoints.

        Capture the uncorrected anchor first. Neighboring repair keys influence
        later evaluations, so the residual correction alone is not a cap bound.
        """
        frames = self.check_work(baked_frames, max_frames)
        scene=bpy.context.scene;original={}
        for f in frames:
            scene.frame_set(math.floor(f),subframe=f-math.floor(f));bpy.context.view_layer.update()
            original[f]=(self.target.matrix_world@self.target.pose.bones[self.anchor].head).copy()
        for f in frames:self.apply(f,original[f])
        extrema={'integer_frames':[],'subframes':[]}
        for f in frames:
            scene.frame_set(math.floor(f),subframe=f-math.floor(f));bpy.context.view_layer.update()
            clearance=self.minimum()-self.config['height']
            anchor=self.target.matrix_world@self.target.pose.bones[self.anchor].head
            require(math.isfinite(clearance) and abs(clearance)<1e-4,
                    'GROUND_CONTACT_FAILED','Finished action failed a declared contact checkpoint')
            require(abs(anchor.z-original[f].z)<=self.config['max_correction']+1e-6 and
                    math.hypot(anchor.x-original[f].x,anchor.y-original[f].y)<1e-5,
                    'GROUND_CONTACT_FAILED','Finished correction exceeded cap or changed horizontal travel')
            extrema['integer_frames' if abs(f-round(f))<1e-6 else 'subframes'].append(clearance)
        self.verification={name:{'count':len(values),'max_abs_clearance':max(map(abs,values),default=None)}
                           for name,values in extrema.items()}

    def report(self):
        return {'method':'vertical anchor offset from weighted sole vertices; no horizontal IK',
                'floor_z':self.config['height'],'vertices':len(self.indices),'frames':len(self.corrections),
                'max_abs_correction':max(map(abs,self.corrections),default=0),'topology_sha256':self.topology,
                'subdivisions':self.config.get('subdivisions',1),'verification':self.verification,
                'cap_basis':'total vertical displacement from the uncorrected action at each checkpoint',
                'topology_policy':'one active Armature modifier plus index/connectivity fingerprint',
                'not_measured':['between-checkpoint extrema','pressure','horizontal foot lock','naturalness']}
