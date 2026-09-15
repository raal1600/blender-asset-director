"""Unit-invariant FBX numerical noise acceptance and real extra-motion refusal.

Run ONLY in isolated GitHub Actions Blender. Sources are procedurally generated;
no importer flags, source files or action keys are changed to make a positive pass.
"""
from pathlib import Path
import math
import sys
import bpy
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]
from sequence_fixture import export_take
from transfer_planning_fixture import make_rig
from asset_director import blender_ops as ops, transfer_blender as tb, sequence_blender as sb
from asset_director.pose_transfer import PoseTransfer
from asset_director.core import atomic_json, DirectorError, file_hash



def sequence_precision_checks():
    evidence = []
    for metres, scale in ((1, 1), (1, .01), (.01, 1)):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.object.armature_add(enter_editmode=True)
        rig = bpy.context.object
        anchor = rig.data.edit_bones[0]; anchor.name = 'Anchor'
        child = rig.data.edit_bones.new('Distal')
        child.head = anchor.tail; child.tail = (0, 0, 2); child.parent = anchor
        bpy.ops.object.mode_set(mode='OBJECT')
        rig.scale = (scale,)*3
        factor = metres*scale
        for frame in (1, 2):
            for bone in rig.pose.bones:
                bone.rotation_mode = 'QUATERNION'
                bone.location.x = (2e-7/factor if bone.name == 'Distal' and frame == 2 else 0)
                bone.keyframe_insert('location', frame=frame)
                bone.keyframe_insert('rotation_quaternion', frame=frame)
        action = rig.animation_data.action; slot = rig.animation_data.action_slot
        for curve in ops.curves(action, slot):
            for key in curve.keyframe_points: key.interpolation = 'LINEAR'
        bpy.context.view_layer.update()
        before = sb.signature(action, slot)
        sb.validate_action(rig, action, slot, 'Anchor', metres)
        assert sb.signature(action, slot) == before
        count = sum(len(c.keyframe_points) for c in ops.curves(action, slot))
        assert tb.action_signature(action, slot, count) == before
        try:
            tb.action_signature(action, slot, count-1)
            raise AssertionError('Source signature inspection exceeded explicit key budget')
        except DirectorError as exc: assert exc.code == 'RESOURCE_LIMIT'
        curve = next(c for c in ops.curves(action, slot)
                     if c.data_path == rig.pose.bones['Distal'].path_from_id('location') and c.array_index == 0)
        curve.keyframe_points[-1].co.y = .001/factor; curve.update()
        try:
            sb.validate_action(rig, action, slot, 'Anchor', metres)
            raise AssertionError('Sequence accepted genuine extra-bone translation')
        except DirectorError as exc: assert exc.code == 'SEQUENCE_ROOT_OWNERSHIP'
        evidence.append({'metres_per_scene_unit':metres,'object_scale':scale,
            'submicrometre_noise_accepted_without_key_changes':True,'one_mm_translation_rejected':True,
            'explicit_source_key_budget_enforced':True})
    return evidence


def main(output):
    assert bpy.app.background
    root = Path(output).resolve(); root.mkdir(parents=True, exist_ok=False)
    checks = []
    for units in (1, 100):
        path = root/f'generated-{units}.fbx'
        export_take(path, 32, units, .35, 1.0)
        source_hash = file_hash(path)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        objects = ops.import_file(path, root)
        source = next(o for o in objects if o.type == 'ARMATURE')
        action = source.animation_data.action; slot = source.animation_data.action_slot
        roles = ops.rig_report(source)['roles']; anchor = roles['hips']
        start, end = ops.action_range(action, slot)
        signature = tb.action_signature(action, slot)
        policy_evidence = tb.source_checks(source, action, anchor, start, end, 17, 1/units)
        assert policy_evidence['max_non_anchor_span_m'] < 1e-5
        assert tb.action_signature(action, slot) == signature
        target, _, names = make_rig('PrecisionTarget', 'target')
        bpy.context.scene.frame_set(math.floor(start), subframe=start-math.floor(start))
        config = dict(rotation=[1,0,0,0,1,0,0,0,1], translation_bone=names['hips'],
                      translation_scale=1/units, target_origin=[0,0,1], source_meters_per_unit=1/units)
        pairs = {roles['hips']:names['hips'], roles['forearm_l']:names['forearm_l']}
        transfer = PoseTransfer(source, target, pairs, config)
        transfer.matrices()
        bpy.context.scene.frame_set(math.floor(end), subframe=end-math.floor(end))
        transfer.matrices()
        # Inject exactly one millimetre of authored non-anchor motion IN MEMORY
        # for negative tests, never into either source file or a production asset.
        bone = source.pose.bones[roles['forearm_l']]
        curve = next(c for c in ops.curves(action, slot)
                     if c.data_path == bone.path_from_id('location') and c.array_index == 0)
        curve.keyframe_points[-1].co.y += .001*units; curve.update()
        refusals = []
        try:
            tb.source_checks(source, action, anchor, start, end, 17, 1/units)
            raise AssertionError('Planning accepted genuine extra-bone translation')
        except DirectorError as exc:
            assert exc.code == 'NON_ANCHOR_TRANSLATION', exc.code
            refusals.append('planner')
        bpy.context.scene.frame_set(math.floor(end), subframe=end-math.floor(end))
        bpy.context.view_layer.update()
        try:
            transfer.matrices()
            raise AssertionError('Execution accepted genuine extra-bone translation')
        except DirectorError as exc:
            assert exc.code == 'NON_ANCHOR_TRANSLATION', exc.code
            refusals.append('executor')
        assert file_hash(path) == source_hash
        checks.append({'units_per_meter':units,'measured':policy_evidence,
                       'one_mm_non_anchor_motion_rejected_by':refusals,'source_file_preserved':True})
    atomic_json(root/'translation_precision_report.json', {'status':'PASS', 'blender':bpy.app.version_string,
                'checks':checks, 'sequence_checks':sequence_precision_checks(), 'notice':'Numerical tolerance, not normalization, inferred capture quality or arbitrary extra translations.'})


if __name__ == '__main__': main(sys.argv[sys.argv.index('--')+1])
