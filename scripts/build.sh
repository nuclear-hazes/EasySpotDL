#!/bin/bash
# Builds dist/EasySpotDL-mac.zip and dist/EasySpotDL-win.zip from this repo (runs on the author's Mac).
# Each zip holds one EasySpotDL/ folder: launcher, uv, app/, VERSION, LEEME.txt and a prod .env.
# Python, the app's packages and the Engine (spotDL, ffmpeg, deno) are fetched on the user's machine.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"

# Pinned uv release; bump deliberately and update both checksums from the release's .sha256 files.
UV_VERSION="0.13.1"
UV_BASE="https://github.com/astral-sh/uv/releases/download/$UV_VERSION"
UV_MAC_ASSET="uv-aarch64-apple-darwin.tar.gz"
UV_MAC_SHA256="cfe454573412ff7380d15fc7dae5997ab53ffce72fce0a78e91ddbc84001acd2"
UV_WIN_ASSET="uv-x86_64-pc-windows-msvc.zip"
UV_WIN_SHA256="3b2661a463a5baea7f5076ea2b25ab71d77f36a6c0d809e5350651792f80a672"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/easyspotdl-build.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

fetch() {  # fetch <asset> <sha256>: download a uv release asset into $WORK and verify it
  local asset="$1" expected="$2" actual
  echo "Downloading $asset"
  curl -fsSL -o "$WORK/$asset" "$UV_BASE/$asset"
  actual="$(shasum -a 256 "$WORK/$asset" | cut -d' ' -f1)"
  if [ "$actual" != "$expected" ]; then
    echo "Checksum mismatch for $asset: got $actual" >&2
    exit 1
  fi
}

stage() {  # stage <platform>: create $WORK/<platform>/EasySpotDL with everything but the launcher and uv
  local dir="$WORK/$1/EasySpotDL"
  mkdir -p "$dir"
  rsync -a --exclude .venv --exclude tests --exclude __pycache__ --exclude .pytest_cache --exclude '*.egg-info' --exclude .DS_Store \
    "$ROOT/app/" "$dir/app/"
  cp "$ROOT/VERSION" "$ROOT/docs/user/LEEME.txt" "$dir/"
  { echo "ENV=prod"; grep '^PROD_' "$ROOT/.env.example"; } > "$dir/.env"
  echo "$dir"
}

package() {  # package <platform> <zip name>
  rm -f "$DIST/$2"
  (cd "$WORK/$1" && zip -qrX "$DIST/$2" EasySpotDL)
  echo "Built dist/$2"
}

mkdir -p "$DIST"
fetch "$UV_MAC_ASSET" "$UV_MAC_SHA256"
fetch "$UV_WIN_ASSET" "$UV_WIN_SHA256"

mac="$(stage mac | tail -1)"
cp "$ROOT/launchers/Abrir EasySpotDL.command" "$mac/"
tar -xzf "$WORK/$UV_MAC_ASSET" -C "$WORK" --strip-components 1 "${UV_MAC_ASSET%.tar.gz}/uv"
mv "$WORK/uv" "$mac/uv"
chmod 755 "$mac/uv" "$mac/Abrir EasySpotDL.command"
package mac EasySpotDL-mac.zip

win="$(stage win | tail -1)"
cp "$ROOT/launchers/Abrir EasySpotDL.bat" "$win/"
unzip -q -j "$WORK/$UV_WIN_ASSET" uv.exe -d "$win"
package win EasySpotDL-win.zip
