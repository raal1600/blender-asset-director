"""Machine-local path configuration. No API keys, host writes, or network probes."""
from __future__ import annotations
import os
from pathlib import Path
import re
import shutil
import sys
import tomllib
from .core import DirectorError, atomic_json, fields, load_json, require


def config_path() -> Path:
    if os.getenv('BAD_CONFIG'):
        return Path(os.environ['BAD_CONFIG']).expanduser().resolve()
    if sys.platform == 'win32':
        base = Path(os.getenv('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'BlenderAssetDirector'
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support' / 'BlenderAssetDirector'
    else:
        base = Path(os.getenv('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'blender-asset-director'
    return base / 'runtime.json'


def read_settings() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    data = load_json(path, max_bytes=65536)
    fields(data, {'schema_version', 'owner', 'library', 'blender', 'python', 'skill_path'}, {'schema_version', 'owner'})
    require(data['owner'] == 'blender-asset-director' and data['schema_version'] == 1,
            'RUNTIME_CONFIG_INVALID', 'Unrecognized local settings; preserve this file rather than overwriting it')
    for key in ('library', 'blender', 'python', 'skill_path'):
        require(data.get(key) is None or (isinstance(data[key], str) and Path(data[key]).is_absolute()),
                'RUNTIME_CONFIG_INVALID', 'Runtime paths must be absolute')
    return data


def blender_candidates() -> list[str]:
    """Only PATH and conventional installation directories, never a whole-disk scan."""
    result = []
    on_path = shutil.which('blender')
    if on_path:
        result.append(Path(on_path))
    conventional = []
    if sys.platform == 'win32':
        for root in (os.getenv('ProgramFiles'), os.getenv('ProgramFiles(x86)'),
                     str(Path(os.getenv('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'Programs')):
            if root:
                conventional.extend(Path(root).glob('Blender Foundation/Blender*/blender.exe'))
    elif sys.platform == 'darwin':
        for root in (Path('/Applications'), Path.home() / 'Applications'):
            conventional.extend(root.glob('Blender*.app/Contents/MacOS/Blender'))
    else:
        conventional.extend((Path('/usr/bin/blender'), Path('/snap/bin/blender'), Path('/usr/local/bin/blender')))
    def version_key(path):
        return tuple(int(n) for n in re.findall(r'\d+', str(path))), str(path)
    result.extend(sorted(conventional, key=version_key, reverse=True))
    return list(dict.fromkeys(str(p.resolve()) for p in result if p.is_file()))


def library_path(explicit=None) -> str:
    return str(Path(explicit or os.getenv('BAD_LIBRARY') or read_settings().get('library') or
                    Path.home() / 'CGI-Library').expanduser().resolve())


def blender_path(explicit=None) -> str | None:
    value = explicit or os.getenv('BAD_BLENDER') or read_settings().get('blender')
    if value:
        # Never silently replace a selected installation that has disappeared.
        return str(Path(value).expanduser().resolve())
    return next(iter(blender_candidates()), None)


def configure(*, library=None, blender=None, skill_path=None) -> dict:
    previous = read_settings()
    lib = Path(library_path(library))
    skill = Path(skill_path).expanduser().resolve() if skill_path else (
        Path(previous['skill_path']) if previous.get('skill_path') else None)
    if skill:
        require(not lib.is_relative_to(skill) and not skill.is_relative_to(lib), 'UNSAFE_LIBRARY_LOCATION',
                'Keep the asset library and installed skill in separate directories')
    chosen = blender_path(blender)
    if blender:
        require(Path(chosen).is_file(), 'BLENDER_NOT_FOUND', 'The explicitly selected Blender executable does not exist')
    from .core import Library
    with Library(lib):
        pass
    data = {'schema_version': 1, 'owner': 'blender-asset-director', 'library': str(lib),
            'blender': chosen, 'python': str(Path(sys.executable).resolve()),
            'skill_path': str(skill) if skill else None}
    path = config_path()
    atomic_json(path, data)
    if os.name != 'nt':
        path.chmod(0o600)
    return {'settings_file': str(path), 'library': str(lib), 'blender': chosen,
            'host_config_modified': False}


def codex_status() -> dict:
    """Read the user-level MCP declaration, never run its commands or expose secrets."""
    home = Path(os.getenv('CODEX_HOME', str(Path.home() / '.codex'))).expanduser()
    path = home / 'config.toml'
    out = {'cli_on_path': bool(shutil.which('codex')), 'config_present': path.is_file(),
           'blender_mcp': 'NOT_DETECTED_IN_USER_CONFIG', 'connection': 'NOT_TESTED',
           'note': 'Project/plugin MCP declarations may exist elsewhere; verify in a fresh Codex session'}
    if path.is_file():
        try:
            if path.stat().st_size > 1024 * 1024:
                out['blender_mcp'] = 'CONFIG_TOO_LARGE_TO_INSPECT'
                return out
            data = tomllib.loads(path.read_text(encoding='utf-8-sig'))
            for name, entry in data.get('mcp_servers', {}).items():
                if not isinstance(entry, dict) or entry.get('enabled', True) is False:
                    continue
                # Inspect only the declaration in memory; return no commands, arguments or env.
                label = str(name) + ' ' + str(entry.get('command', '')) + ' ' + str(entry.get('args', []))
                if 'blender' in label.lower() and 'overlay' not in label.lower():
                    out['blender_mcp'] = 'CONFIGURED_LIVE_TEST_PENDING'
                    break
        except (OSError, ValueError, TypeError, AttributeError):
            out['blender_mcp'] = 'CONFIG_UNREADABLE_OR_INVALID'
    return out


def health() -> dict:
    path = blender_path()
    found = bool(path and Path(path).is_file())
    return {'settings_file': str(config_path()), 'settings_saved': config_path().is_file(),
            'python_executable': str(Path(sys.executable).resolve()),
            'blender': {'path': path, 'status': 'EXECUTABLE_FOUND' if found else 'NOT_FOUND',
                        'version_and_live_scene': 'NOT_TESTED'},
            'codex': codex_status(), 'skill_discovery': 'VERIFY_IN_NEW_CODEX_SESSION',
            'ready_for': 'LOCAL_HOST_CHECK' if found else 'INSTALL_BLENDER_OR_SET_BAD_BLENDER',
            'network_requests': 0, 'model_calls': 0}
