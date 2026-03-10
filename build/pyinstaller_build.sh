#!/usr/bin/env bash
# build/pyinstaller_build.sh
# Build a single-file openia binary for macOS / Linux using PyInstaller.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

pip install --quiet pyinstaller
pip install --quiet -e "${REPO_ROOT}"

pyinstaller \
  --onefile \
  --console \
  --name openia \
  "${REPO_ROOT}/openia/cli.py"

echo "Build complete: dist/openia"
