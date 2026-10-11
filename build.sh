#!/usr/bin/env bash
# Builds dist/background_sync-<version>.ankiaddon from src/background_sync.
# Double-click the resulting file (or drag it onto Anki) to install it.
set -euo pipefail
cd "$(dirname "$0")"
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/background_sync/__init__.py)
mkdir -p dist
OUT="dist/background_sync-${VERSION}.ankiaddon"
rm -f "$OUT"
(cd src/background_sync && zip -q -r -X "../../$OUT" . -x "__pycache__/*" "*.pyc" "meta.json" ".DS_Store")
echo "Built $OUT"
