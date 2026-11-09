#!/usr/bin/env bash
# Run a Blender Python script headless with whichever Blender is available.
#   run_headless.sh script.py [file.blend] [-- script args...]
# Order of preference: $BLENDER, `blender` on PATH, common install paths, then the `bpy` pip module.
# Examples:
#   run_headless.sh qa_check.py model.blend -- --tex-size 2048 --convention ue
#   run_headless.sh selftest.py
set -euo pipefail

script="${1:?usage: run_headless.sh script.py [file.blend] [-- args...]}"; shift
blend=""
if [[ "${1:-}" == *.blend ]]; then blend="$1"; shift; fi
[[ "${1:-}" == "--" ]] && shift
args=("$@")

find_blender() {
  [[ -n "${BLENDER:-}" && -x "$BLENDER" ]] && { echo "$BLENDER"; return; }
  command -v blender 2>/dev/null && return
  for p in /Applications/Blender.app/Contents/MacOS/Blender /usr/bin/blender /usr/local/bin/blender \
           /snap/bin/blender "$HOME"/blender*/blender /opt/blender*/blender; do
    [[ -x "$p" ]] && { echo "$p"; return; }
  done
  return 1
}

if bl="$(find_blender)"; then
  echo ">> $bl (real Blender, headless)" >&2
  cmd=("$bl" -b --factory-startup)
  [[ -n "$blend" ]] && cmd+=("$blend")
  exec "${cmd[@]}" -P "$script" -- "${args[@]}"
fi

if python3 -c "import bpy" 2>/dev/null; then
  echo ">> python3 + bpy module" >&2
  exec python3 "$script" ${blend:+"$blend"} "${args[@]}"
fi

cat >&2 <<'EOF'
No Blender found. Options:
  1) Install Blender (https://www.blender.org/download/) and set BLENDER=/path/to/blender, or
  2) pip install bpy      (headless module; the wheel's Python version must match: Blender 5.x wheels need Python 3.13,
                           4.x wheels Python 3.11 - use a venv with the right interpreter).
EOF
exit 127
