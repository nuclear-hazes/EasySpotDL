import logging
import re
import tomllib
from pathlib import Path

import pytest

from easyspotdl import config


def make_root(tmp_path: Path, env_text: str | None = None) -> Path:
    (tmp_path / "VERSION").write_text("0.1.0\n")
    if env_text is not None:
        (tmp_path / ".env").write_text(env_text)
    return tmp_path


def test_defaults_to_dev_without_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    cfg = config.load_config(make_root(tmp_path))
    assert cfg.env == "dev"
    assert cfg.log_level == logging.DEBUG
    assert cfg.version == "0.1.0"
    assert cfg.preferred_port == 8765
    assert cfg.release_channel_url is None


def test_env_file_selects_prefixed_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    root = make_root(
        tmp_path,
        "# comment\nENV=prod\nDEV_RELEASE_CHANNEL_URL=file:///tmp/dev.json\n"
        'PROD_RELEASE_CHANNEL_URL="https://api.github.com/repos/nuclear-hazes/EasySpotDL/releases/latest"\n',
    )
    cfg = config.load_config(root)
    assert cfg.env == "prod"
    assert cfg.log_level == logging.WARNING
    assert cfg.release_channel_url == "https://api.github.com/repos/nuclear-hazes/EasySpotDL/releases/latest"


def test_process_env_overrides_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    root = make_root(tmp_path, "ENV=prod\nDEV_RELEASE_CHANNEL_URL=file:///tmp/dev.json\n")
    cfg = config.load_config(root)
    assert cfg.env == "dev"
    assert cfg.release_channel_url == "file:///tmp/dev.json"


def test_rejects_unknown_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ENV", "staging")
    with pytest.raises(ValueError, match="staging"):
        config.load_config(make_root(tmp_path))


def test_macos_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(config.sys, "platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = config.load_config(make_root(tmp_path))
    assert cfg.data_dir == tmp_path / "Library" / "Application Support" / "EasySpotDL"
    assert cfg.music_dir == tmp_path / "Music" / "EasySpotDL"


def test_windows_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert config.default_data_dir() == tmp_path / "EasySpotDL"


def test_pyproject_version_matches_version_file():
    pyproject = tomllib.loads((config.ROOT_DIR / "app" / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == (config.ROOT_DIR / "VERSION").read_text().strip()


def test_log_format():
    formatter = logging.Formatter(config.LOG_FORMAT, config.LOG_DATEFMT)
    record = logging.LogRecord("easyspotdl.engine", logging.INFO, "/x/engine.py", 1, "Engine installed", None, None)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[INFO\] engine: Engine installed", formatter.format(record))
