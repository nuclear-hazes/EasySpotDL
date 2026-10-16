#!/bin/bash
# EasySpotDL launcher for macOS: double-click to start the app.
cd "$(dirname "$0")" || exit 1
ROOT="$PWD"
# Unzipped layout has app/ next to this file; in the repo it sits one level up.
[ -d "$ROOT/app" ] || ROOT="$(dirname "$ROOT")"

# Once this approved script runs, nothing else in the folder triggers Gatekeeper.
xattr -dr com.apple.quarantine "$ROOT" 2>/dev/null

# Python, the app environment and uv's cache live in the data folder (must match config.py).
DATA="$HOME/Library/Application Support/EasySpotDL"
export UV_PYTHON_INSTALL_DIR="$DATA/python"
export UV_CACHE_DIR="$DATA/cache"
export UV_PROJECT_ENVIRONMENT="$DATA/app-env"
export UV_PYTHON_PREFERENCE=only-managed

UV_EXE="$ROOT/uv"
[ -x "$UV_EXE" ] || UV_EXE="$(command -v uv)"

echo "EasySpotDL está abierto. No cierres esta ventana mientras lo uses."
"$UV_EXE" run --frozen --no-dev --directory "$ROOT/app" python -m easyspotdl
rc=$?
if [ $rc -ne 0 ]; then
  # uv could not even build the app environment: on a first launch that means no internet.
  [ -d "$UV_PROJECT_ENVIRONMENT" ] || echo "EasySpotDL necesita internet la primera vez. Conectate y volvé a abrirlo."
  read -r -p "Presioná Enter para cerrar..."
fi
exit $rc
