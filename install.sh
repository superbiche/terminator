#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

python_bin="${PYTHON:-python3}"
py_tag="$("$python_bin" -c 'import sys; print(f"{sys.version_info[0]}{sys.version_info[1]}")')"
record_file="${RECORD:-install-files-user-py${py_tag}.txt}"
icon_dir="${HOME}/.local/share/icons/hicolor"

if [[ ! -f setup.py ]]; then
  echo "setup.py not found in $script_dir" >&2
  exit 1
fi

echo "Building Terminator with $python_bin"
"$python_bin" setup.py build

echo "Installing Terminator to the current user's site-packages"
"$python_bin" setup.py install --user --force --record="$record_file"

if command -v gtk-update-icon-cache >/dev/null 2>&1 && [[ -d "$icon_dir" ]]; then
  echo "Updating GTK icon cache: $icon_dir"
  gtk-update-icon-cache -q -f "$icon_dir"
fi

echo "Install record: $script_dir/$record_file"
echo "Installed Terminator module:"
(
  cd /
  "$python_bin" - <<'PY'
import terminatorlib
from terminatorlib.version import APP_VERSION

print(f"  version: {APP_VERSION}")
print(f"  path:    {terminatorlib.__file__}")
PY
)
