"""Scope 3 acceptance for Packaging: run scripts/build.sh and inspect the zips.

Needs internet (downloads the pinned uv from GitHub). Run with: uv run pytest -m integration
"""

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(sys.platform != "darwin", reason="the build runs on the author's Mac"),
]

REPO = Path(__file__).resolve().parents[2]
ZIPS = {
    "mac": (REPO / "dist" / "EasySpotDL-mac.zip", "Abrir EasySpotDL.command", "uv"),
    "win": (REPO / "dist" / "EasySpotDL-win.zip", "Abrir EasySpotDL.bat", "uv.exe"),
}
FORBIDDEN = ("ffmpeg", "deno", "python")


@pytest.fixture(scope="module")
def built():
    subprocess.run(["/bin/bash", str(REPO / "scripts" / "build.sh")], check=True, timeout=600)
    return {name: zipfile.ZipFile(path) for name, (path, _, _) in ZIPS.items()}


def test_build_produces_zips(built):
    for path, _, _ in ZIPS.values():
        assert path.is_file()


@pytest.mark.parametrize("platform", ["mac", "win"])
def test_zip_contents(built, platform):
    _, launcher, uv = ZIPS[platform]
    names = set(built[platform].namelist())
    for required in [launcher, uv, "VERSION", "LEEME.txt", ".env", "app/pyproject.toml", "app/uv.lock",
                     "app/easyspotdl/__main__.py", "app/easyspotdl/static/index.html"]:
        assert f"EasySpotDL/{required}" in names, required
    assert (built[platform].read("EasySpotDL/.env").decode().splitlines())[0] == "ENV=prod"
    for name in names:
        base = Path(name).name.lower()
        assert not base.startswith(FORBIDDEN), f"third-party binary in zip: {name}"
    assert not any("/tests/" in n or "/.venv/" in n or "__pycache__" in n for n in names)


def test_uv_binaries_match_platform(built, tmp_path):
    built["mac"].extract("EasySpotDL/uv", tmp_path)
    built["win"].extract("EasySpotDL/uv.exe", tmp_path)
    mac_kind = subprocess.run(["file", tmp_path / "EasySpotDL/uv"], capture_output=True, text=True).stdout
    win_kind = subprocess.run(["file", tmp_path / "EasySpotDL/uv.exe"], capture_output=True, text=True).stdout
    assert "Mach-O 64-bit executable arm64" in mac_kind
    assert "PE32+ executable" in win_kind and "x86-64" in win_kind


def test_mac_launcher_executable(built, tmp_path):
    # ditto -x -k is how Archive Utility unpacks a double-clicked zip.
    subprocess.run(["ditto", "-x", "-k", ZIPS["mac"][0], tmp_path], check=True)
    for name in ["Abrir EasySpotDL.command", "uv"]:
        assert os.access(tmp_path / "EasySpotDL" / name, os.X_OK), name


def test_windows_launcher_has_crlf(built):
    bat = built["win"].read("EasySpotDL/Abrir EasySpotDL.bat")
    assert bat.count(b"\r\n") == bat.count(b"\n") > 0
