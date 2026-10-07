"""Prepare an explicit humanoid profile in a NEW Blender file.

Run Blender with --background --disable-autoexec input.blend --python this_file
-- --rig RIG --skeleton discovered-skeleton.json --mapping reviewed-roles.json
--ground-z METRES --output new-profiled.blend. Mapping is an anatomical-role to
observed-bone JSON object, not a name matcher. Provider discovery supplies the
exact skeleton. This does not approve generated motion or infer foot contacts.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    import bpy
    from asset_director.core import atomic_json, digest, require
    from asset_director.motion_bricks_provider import validate_skeleton, configured, execute
    from asset_director.motion_bricks_retarget import PROPERTY, build_profile, load_profile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rig', required=True)
    parser.add_argument('--skeleton', type=Path, required=True)
    parser.add_argument('--mapping', type=Path, required=True)
    parser.add_argument('--ground-z', type=float, required=True)
    parser.add_argument('--height-m', type=float, required=True, help='Fixed reviewed rest-character height, not generated-pose height')
    parser.add_argument('--hinge-calibration',type=Path,help='Explicitly reviewed measured elbow planes for ambiguous straight rest arms')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    require(args.output.is_absolute() and args.output.suffix == '.blend' and not args.output.exists(),
            'PROFILE_OUTPUT_EXISTS', 'Choose a new absolute .blend output; originals are never replaced')
    require(args.rig in bpy.data.objects, 'PROFILE_RIG_MISSING', 'Choose an observed armature')
    skeleton = json.loads(args.skeleton.read_text(encoding='utf-8-sig'))
    mapping = json.loads(args.mapping.read_text(encoding='utf-8-sig'))
    config = configured()
    require(config is not None, 'MOTION_BRICKS_NOT_CONFIGURED',
            'Configure the pinned standalone provider to verify the supplied skeleton before preparing a rig')
    actual = execute(config)['skeleton']
    validate_skeleton(skeleton, actual)
    rig = bpy.data.objects[args.rig]
    calibration=json.loads(args.hinge_calibration.read_text(encoding='utf-8-sig')) if args.hinge_calibration else None
    profile = build_profile(rig, skeleton, mapping, args.ground_z, reference_height_m=args.height_m,hinge_calibration=calibration)
    rig[PROPERTY] = json.dumps(profile)
    require(load_profile(rig) == profile, 'PROFILE_ROUNDTRIP', 'Prepared mapping did not validate')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output))
    atomic_json(args.output.with_suffix('.profile.json'), {
        'schema': 'motion-bricks.profile-preparation.v1', 'profile': profile,
        'sha256': digest(profile), 'status': 'GEOMETRY_VALIDATED',
        'pose_roundtrip': 'CHECKED_PER_GENERATED_REQUEST', 'motion_quality': 'NOT_VERIFIED'})


if __name__ == '__main__':
    main()
