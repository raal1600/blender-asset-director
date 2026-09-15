#!/bin/sh
# Pinned bootstrap for macOS/Linux. No sudo, Git, or global pip installation.
set -eu
version=0.6.0-dev.2
python_bin=${BAD_PYTHON:-}
if [ -z "$python_bin" ]; then
    for name in python3 python; do
        if command -v "$name" >/dev/null 2>&1 && "$name" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
            python_bin=$name; break
        fi
    done
fi
if [ -z "$python_bin" ] || ! "$python_bin" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    echo 'Python 3.11+ is required. Install it from python.org or your OS package manager, then retry. No changes made.' >&2
    exit 1
fi
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
offline=false
for arg in "$@"; do [ "$arg" != '--archive' ] || offline=true; done
if [ "$offline" = true ]; then
    cp "$script_dir/install.py" "$tmp/install.py"
else
    curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
        "https://raw.githubusercontent.com/raal1600/blender-asset-director/v$version/install.py" -o "$tmp/install.py"
fi
"$python_bin" "$tmp/install.py" --version "$version" "$@"
