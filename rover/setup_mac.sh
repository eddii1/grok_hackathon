#!/bin/bash
# Isolated rover SDK environment. Does not connect to or move any robot.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/rover/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  uv venv --python 3.12 "$ROOT/rover/.venv"
fi
uv pip install --python "$PY" 'numpy>=1.26,<2' 'av>=14,<17' opencv-python flask 'qrcode[pil]' netaddr netifaces MyQR
# Official pure-Python SDK, pinned source revision; avoid incompatible old PyPI binary wheels.
uv pip install --python "$PY" --no-deps \
  'robomaster @ git+https://github.com/dji-sdk/RoboMaster-SDK.git@ff6646e115ab125af3207a4ed3df42cc76c795b2'
echo "Installed. Start locally with: $PY $ROOT/rover/app.py"
