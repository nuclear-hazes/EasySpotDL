"""Runtime configuration: ENV, paths, version and logging."""

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# app/easyspotdl/config.py -> repo root (or unzipped folder), where VERSION and .env live.
ROOT_DIR = Path(__file__).resolve().parents[2]
PREFERRED_PORT = 8765
LOG_LEVELS = {"dev": logging.DEBUG, "prod": logging.WARNING}
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(module)s: %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class AppConfig:
    env: str
    version: str
    data_dir: Path
    music_dir: Path
    release_channel_url: str | None
    preferred_port: int
    log_level: int


def read_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines from a .env file; a missing file yields no values."""
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def default_data_dir() -> Path:
    """Per-platform data folder; must match the launchers."""
    if sys.platform == "win32":
        return Path(os.environ["LOCALAPPDATA"]) / "EasySpotDL"
    return Path.home() / "Library" / "Application Support" / "EasySpotDL"


def load_config(root: Path = ROOT_DIR) -> AppConfig:
    # Process environment wins over .env, so tests and shells can override it.
    values = {**read_env_file(root / ".env"), **os.environ}
    env = values.get("ENV", "dev").lower()
    if env not in LOG_LEVELS:
        raise ValueError(f"ENV must be one of {sorted(LOG_LEVELS)}, got {env!r}")
    return AppConfig(
        env=env,
        version=(root / "VERSION").read_text(encoding="utf-8").strip(),
        data_dir=default_data_dir(),
        music_dir=Path.home() / "Music" / "EasySpotDL",
        release_channel_url=values.get(f"{env.upper()}_RELEASE_CHANNEL_URL") or None,
        preferred_port=PREFERRED_PORT,
        log_level=LOG_LEVELS[env],
    )


def setup_logging(level: int) -> None:
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt=LOG_DATEFMT, stream=sys.stdout)
