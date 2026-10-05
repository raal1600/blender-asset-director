"""Prepare root-only Action copies in a new .blend using explicit contact JSON.

Blender --background --disable-autoexec profiled.blend --python this_file --
--rig RIG --contacts reviewed.json --output new.blend
Existing Actions, timeline, skin and bone keys remain unchanged. This does not
approve artistic quality; evaluate planted intervals and render the new takes.
"""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def main():
    import bpy
    from asset_director.core import require,atomic_json
    from asset_director.root_contact_preparation import prepare
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rig',required=True);parser.add_argument('--contacts',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    require(args.output.is_absolute() and args.output.suffix=='.blend' and not args.output.exists(),
            'ROOT_CONTACT_OUTPUT','Choose a new absolute Blender file; source files are never overwritten')
    require(args.rig in bpy.data.objects,'ROOT_CONTACT_RIG','Choose an observed profiled armature')
    reports=prepare(bpy.data.objects[args.rig],json.loads(args.contacts.read_text(encoding='utf-8-sig')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output))
    atomic_json(args.output.with_suffix('.root-contacts.json'),{'status':'PREPARED_REQUIRES_QUALITY_VALIDATION','clips':reports})


if __name__=='__main__':main()
