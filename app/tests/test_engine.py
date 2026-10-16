import logging
import subprocess

import pytest

from easyspotdl import engine


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))  # ~/.spotdl lives under the fake home
    monkeypatch.setenv("UV", "/fake/uv")
    monkeypatch.setattr(engine, "_spotdl_version", lambda spotdl: "4.5.2")
    return tmp_path / "data"


@pytest.fixture
def calls(monkeypatch):
    recorded = []
    monkeypatch.setattr(engine, "_run", lambda cmd, env, timeout: recorded.append((cmd, env)))
    return recorded


def install_spotdl(data_dir):
    spotdl = engine.spotdl_path(data_dir)
    spotdl.parent.mkdir(parents=True)
    spotdl.touch()
    return spotdl


def install_tools(home):
    (home / ".spotdl").mkdir()
    for name in engine.SPOTDL_TOOLS:
        (home / ".spotdl" / name).touch()


def test_first_launch_offline_asks_for_internet(data_dir, calls, monkeypatch):
    monkeypatch.setattr(engine, "has_internet", lambda: False)
    with pytest.raises(engine.EngineError, match="EasySpotDL necesita internet la primera vez"):
        engine.ensure_engine(data_dir)
    assert calls == []


def test_first_launch_installs_spotdl_then_tools(data_dir, calls, monkeypatch, caplog):
    monkeypatch.setattr(engine, "has_internet", lambda: True)
    caplog.set_level(logging.INFO)
    status = engine.ensure_engine(data_dir)
    commands = [cmd for cmd, _ in calls]
    spotdl = str(engine.spotdl_path(data_dir))
    assert commands == [
        ["/fake/uv", "tool", "install", "spotdl", "--python", "3.12"],
        [spotdl, "--download-ffmpeg"],
        [spotdl, "--download-deno"],
    ]
    assert calls[0][1]["UV_TOOL_DIR"] == str(data_dir / "tools")
    assert calls[0][1]["UV_TOOL_BIN_DIR"] == str(data_dir / "bin")
    assert status == engine.EngineStatus(installed=True, spotdl_version="4.5.2", updated_this_launch=True)
    assert "Engine installed" in caplog.text


def test_first_launch_install_failure_is_a_user_message(data_dir, monkeypatch):
    monkeypatch.setattr(engine, "has_internet", lambda: True)

    def fail(cmd, env, timeout):
        raise subprocess.CalledProcessError(2, cmd)

    monkeypatch.setattr(engine, "_run", fail)
    with pytest.raises(engine.EngineError, match="No se pudo instalar el Engine"):
        engine.ensure_engine(data_dir)


def test_update_upgrades_and_skips_present_tools(data_dir, calls, monkeypatch, tmp_path):
    install_spotdl(data_dir)
    install_tools(tmp_path)
    monkeypatch.setattr(engine, "has_internet", lambda: True)
    status = engine.ensure_engine(data_dir)
    assert [cmd for cmd, _ in calls] == [["/fake/uv", "tool", "upgrade", "spotdl"]]
    assert status.updated_this_launch


def test_update_restores_missing_tool(data_dir, calls, monkeypatch, tmp_path):
    install_spotdl(data_dir)
    install_tools(tmp_path)
    (tmp_path / ".spotdl" / f"deno{engine.EXE}").unlink()
    monkeypatch.setattr(engine, "has_internet", lambda: True)
    engine.ensure_engine(data_dir)
    assert [cmd[-1] for cmd, _ in calls] == ["spotdl", "--download-deno"]


def test_update_offline_is_skipped_with_warning(data_dir, calls, monkeypatch, caplog):
    install_spotdl(data_dir)
    monkeypatch.setattr(engine, "has_internet", lambda: False)
    status = engine.ensure_engine(data_dir)
    assert calls == []
    assert status.installed and not status.updated_this_launch
    assert any(r.levelno == logging.WARNING and "Engine update skipped" in r.message for r in caplog.records)


def test_update_warns_when_tools_cannot_be_downloaded(data_dir, monkeypatch, caplog):
    install_spotdl(data_dir)
    monkeypatch.setattr(engine, "has_internet", lambda: True)

    def fail_tools(cmd, env, timeout):
        if cmd[-1].startswith("--download-"):
            raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(engine, "_run", fail_tools)
    status = engine.ensure_engine(data_dir)
    assert status.updated_this_launch  # the spotDL upgrade itself worked
    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Engine tools download failed" in m for m in warnings)
    assert any(f"Engine is missing ffmpeg{engine.EXE}, deno{engine.EXE}" in m for m in warnings)
    assert not any("Engine update skipped" in m for m in warnings)


def test_update_failure_is_skipped_with_warning(data_dir, monkeypatch, caplog):
    install_spotdl(data_dir)
    monkeypatch.setattr(engine, "has_internet", lambda: True)

    def timeout(cmd, env, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(engine, "_run", timeout)
    status = engine.ensure_engine(data_dir)
    assert status.installed and not status.updated_this_launch
    assert any(r.levelno == logging.WARNING and "Engine update skipped" in r.message for r in caplog.records)
