"""Reviewed Blender task entry point; run only in a dedicated Blender process."""
from pathlib import Path
import sys
HERE = Path(__file__).resolve()
runtime = HERE.parent / 'runtime'
sys.path.insert(0, str(runtime if runtime.is_dir() else HERE.parents[3] / 'src'))
from asset_director.task_entry import start
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if len(args) != 1:
    raise SystemExit('Expected one launcher-created task manifest')
start(args[0])
