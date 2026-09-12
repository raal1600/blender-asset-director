"""Stable installed-skill launcher; ordinary system Python 3.11+, not Blender Python."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve()
runtime=HERE.parent/'runtime'
if runtime.is_dir():sys.path.insert(0,str(runtime))
else:sys.path.insert(0,str(HERE.parents[3]/'src'))
from asset_director.cli import main
raise SystemExit(main())
