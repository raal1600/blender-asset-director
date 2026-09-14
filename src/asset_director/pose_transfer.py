"""Evaluated world-pose deltas, reconstructed in target parent order.

Opt-in alternative to local matrix transfer. Callers supply a reviewed reference
alignment, proper source-to-target rotation, and one translation anchor. No IK,
bone renaming, invented choreography, or skeleton mutation occurs here.
"""
from mathutils import Matrix, Vector
from .core import require
from .pose_contract import validate


class PoseTransfer:
    def __init__(self, source, target, pairs, config):
        validate(config)
        self.source, self.target = source, target
        self.inverse = {t:s for s,t in pairs.items()}
        self.anchor = config['translation_bone']
        require(self.anchor in self.inverse, 'INVALID_POSE_TRANSFER', 'Translation bone must be mapped')
        values = config['rotation']
        self.rotation = Matrix([values[i:i+3] for i in (0,3,6)])
        self.origin = Vector(config['target_origin'])
        self.scale = config['translation_scale']
        self.axis_scale = config.get('translation_scale_xyz')
        self.source_world = source.matrix_world.copy()
        self.target_world = target.matrix_world.copy()
        self.source_rest = {s:(source.matrix_world @ source.data.bones[s].matrix_local).to_quaternion().to_matrix()
                            for s in pairs}
        self.target_reference = {t:(target.matrix_world @ target.pose.bones[t].matrix).to_quaternion().to_matrix()
                                 for t in pairs.values()}
        self.reference_basis = {b.name:b.matrix_basis.copy() for b in target.pose.bones}
        require(all(max(abs(v-1) for v in b.scale) < 1e-4 for b in target.pose.bones),
                'TARGET_REFERENCE_SCALE_UNSUPPORTED', 'Target reference pose must use unit scales')
        self.source_origin = None
        self.local_positions = None
        def depth(bone):
            count = 0
            while bone.parent:
                count += 1
                bone = bone.parent
            return count
        self.order = sorted(target.data.bones, key=depth)

    def matrices(self):
        source, target = self.source, self.target
        # Animated object/ancestor transforms require explicit root conversion.
        for actual, expected in [(source.matrix_world,self.source_world),(target.matrix_world,self.target_world)]:
            require(max(abs(actual[r][c]-expected[r][c]) for r in range(4) for c in range(4)) < 1e-5,
                    'OBJECT_TRANSFORM_CHANGED', 'Pose transfer requires fixed armature world transforms')
        source_position = source.matrix_world @ source.pose.bones[self.inverse[self.anchor]].head
        positions = {b.name:b.location.copy() for b in source.pose.bones}
        if self.local_positions is None:
            self.local_positions = positions
        require(all((positions[n]-p).length < 1e-4 for n,p in self.local_positions.items()
                    if n != self.inverse[self.anchor]),
                'NON_ANCHOR_TRANSLATION', 'Animated local translations outside the selected anchor need review')
        require(all(max(abs(v-1) for v in b.scale) < 1e-4 for b in source.pose.bones),
                'ANIMATED_SCALE_UNSUPPORTED', 'Pose transfer requires unit source pose scales')
        if self.source_origin is None:
            self.source_origin = source_position.copy()
        displacement = self.rotation @ (source_position-self.source_origin)
        if self.axis_scale is not None:
            displacement = Vector([displacement[i]*self.axis_scale[i] for i in range(3)])
        anchor_world = self.origin + self.scale * displacement
        world_inverse = target.matrix_world.inverted()
        rotation_inverse = target.matrix_world.to_quaternion().to_matrix().inverted()
        solved, result = {}, {}
        for bone in self.order:
            parent = bone.parent
            inherited = (bone.convert_local_to_pose(self.reference_basis[bone.name], bone.matrix_local,
                         parent_matrix=solved[parent.name], parent_matrix_local=parent.matrix_local)
                         if parent else bone.convert_local_to_pose(self.reference_basis[bone.name], bone.matrix_local))
            desired = inherited.copy()
            name = bone.name
            if name in self.inverse:
                src = self.inverse[name]
                evaluated = (source.matrix_world @ source.pose.bones[src].matrix).to_quaternion().to_matrix()
                rotation = (rotation_inverse @ self.rotation @ evaluated @ self.source_rest[src].inverted()
                            @ self.rotation.inverted() @ self.target_reference[name])
                desired = rotation.to_4x4()
                desired.translation = inherited.translation
                if name == self.anchor:
                    desired.translation = world_inverse @ anchor_world
            solved[name] = desired
            if name in self.inverse:
                result[name] = (bone.convert_local_to_pose(desired, bone.matrix_local,
                                parent_matrix=solved[parent.name], parent_matrix_local=parent.matrix_local, invert=True)
                                if parent else bone.convert_local_to_pose(desired, bone.matrix_local, invert=True))
        return result
