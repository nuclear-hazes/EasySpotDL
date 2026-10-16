"""Engine Manager: installs and updates the Engine (spotDL, plus the deno and ffmpeg it downloads)."""

import logging
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

CONNECTIVITY_URL = "https://pypi.org/simple/spotdl/"
INSTALL_TIMEOUT_S = 600
UPGRADE_TIMEOUT_S = 180
EXE = ".exe" if sys.platform == "win32" else ""
# spotDL's own download commands, keyed by the file each one leaves in ~/.spotdl (or finds on PATH).
SPOTDL_TOOLS = {f"ffmpeg{EXE}": "--download-ffmpeg", f"deno{EXE}": "--download-deno"}


class EngineError(Exception):
    """Engine cannot be made usable; the message is shown to the user as is."""


@dataclass
class EngineStatus:
    installed: bool
    spotdl_version: str | None
    updated_this_launch: bool
    error: str | None = None


def spotdl_path(data_dir: Path) -> Path:
    return data_dir / "bin" / f"spotdl{EXE}"


def has_internet() -> bool:
    try:
        urllib.request.urlopen(CONNECTIVITY_URL, timeout=5).close()
    except urllib.error.HTTPError:
        return True  # the server answered
    except OSError:
        return False
    return True


def ensure_engine(data_dir: Path) -> EngineStatus:
    """Install the Engine on first launch; otherwise try to update it."""
    uv = os.environ.get("UV") or shutil.which("uv")  # `uv run` exports UV
    if not uv:
        raise EngineError("No se encontró uv. Volvé a descomprimir EasySpotDL.")
    env = {**os.environ, "UV_TOOL_DIR": str(data_dir / "tools"), "UV_TOOL_BIN_DIR": str(data_dir / "bin")}
    spotdl = spotdl_path(data_dir)

    if not spotdl.exists():
        if not has_internet():
            raise EngineError("EasySpotDL necesita internet la primera vez. Conectate y volvé a abrirlo.")
        log.info("Installing Engine")
        try:
            # Same Python as the app (validated in the spike), so no second interpreter is downloaded.
            _run([uv, "tool", "install", "spotdl", "--python", "3.12"], env, INSTALL_TIMEOUT_S)
            _ensure_tools(spotdl, env)
        except (subprocess.SubprocessError, OSError) as e:
            log.error("Engine install failed: %s", e)
            raise EngineError("No se pudo instalar el Engine. Revisá tu conexión y volvé a abrir EasySpotDL.") from e
        version = _spotdl_version(spotdl)
        log.info("Engine installed (spotDL %s)", version)
        return EngineStatus(installed=True, spotdl_version=version, updated_this_launch=True)

    updated = False
    if not has_internet():
        log.warning("Engine update skipped: no internet")
    else:
        try:
            _run([uv, "tool", "upgrade", "spotdl"], env, UPGRADE_TIMEOUT_S)
            updated = True
        except (subprocess.SubprocessError, OSError) as e:
            log.warning("Engine update skipped: %s", e)
        try:
            _ensure_tools(spotdl, env)
        except (subprocess.SubprocessError, OSError) as e:
            log.warning("Engine tools download failed: %s", e)
    missing = _missing_tools()
    if missing:
        log.warning("Engine is missing %s: some songs may fail to download", ", ".join(missing))
    version = _spotdl_version(spotdl)
    log.info("Engine ready (spotDL %s)", version)
    return EngineStatus(installed=True, spotdl_version=version, updated_this_launch=updated)


def _missing_tools() -> list[str]:
    # Same check as spotDL: a tool on PATH counts as installed, and spotDL uses it.
    tools_dir = Path.home() / ".spotdl"
    return [name for name in SPOTDL_TOOLS if not (tools_dir / name).exists() and not shutil.which(name)]


def _ensure_tools(spotdl: Path, env: dict[str, str]) -> None:
    """Download deno and ffmpeg through spotDL when missing (spotDL prompts, and fails, if they already exist)."""
    for name in _missing_tools():
        log.info("Downloading %s for the Engine", name)
        _run([str(spotdl), SPOTDL_TOOLS[name]], env, INSTALL_TIMEOUT_S)


def _spotdl_version(spotdl: Path) -> str | None:
    try:
        result = subprocess.run([str(spotdl), "--version"], capture_output=True, text=True, timeout=60, check=True)
    except (subprocess.SubprocessError, OSError) as e:
        log.warning("Could not read spotDL version: %s", e)
        return None
    return result.stdout.strip()


def _run(cmd: list[str], env: dict[str, str], timeout: int) -> None:
    # Output is not captured: uv/spotDL progress shows in the visible terminal window.
    log.debug("Running %s", " ".join(cmd))
    subprocess.run(cmd, env=env, stdin=subprocess.DEVNULL, timeout=timeout, check=True)
