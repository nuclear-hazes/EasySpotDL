"""Scope 1 acceptance: run the real macOS launcher against a throwaway HOME.

Needs internet and the uv binary at the repo root. Run with: uv run pytest -m integration
"""

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(sys.platform != "darwin", reason="exercises the macOS launcher"),
]

REPO = Path(__file__).resolve().parents[2]
LAUNCHER = REPO / "launchers" / "Abrir EasySpotDL.command"
UV = REPO / "uv"
# Nothing listens on port 9: with this proxy every download fails at once, like having no network.
OFFLINE_ENV = {name: "http://127.0.0.1:9" for name in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY")}
_local = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def data_dir(home: Path) -> Path:
    return home / "Library" / "Application Support" / "EasySpotDL"


def instance_port(home: Path) -> int | None:
    try:
        return json.loads((data_dir(home) / "instance.json").read_text())["port"]
    except (OSError, ValueError, KeyError):
        return None


def get(port: int, path: str = "/") -> tuple[int, str] | None:
    try:
        with _local.open(f"http://127.0.0.1:{port}{path}", timeout=2) as response:
            return response.status, response.read().decode()
    except OSError:
        return None


def spotdl_version(home: Path) -> str:
    spotdl = data_dir(home) / "bin" / "spotdl"
    return subprocess.run([spotdl, "--version"], capture_output=True, text=True, check=True).stdout.strip()


class Launch:
    """One double-click on the launcher, with the browser replaced by a recorder script."""

    def __init__(self, home: Path, extra_env: dict[str, str] | None = None):
        self.home = home
        recorder = home / "record-browser.sh"
        if not recorder.exists():
            recorder.write_text('#!/bin/sh\necho "$1" >> "$(dirname "$0")/browser.log"\n')
            recorder.chmod(0o755)
        env = {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",  # no Homebrew ffmpeg/uv leaking in
            "HOME": str(home),
            "ENV": "dev",
            "BROWSER": str(recorder),
            "LANG": "en_US.UTF-8",
            **(extra_env or {}),
        }
        self.proc = subprocess.Popen(
            ["/bin/bash", str(LAUNCHER)],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        self.lines: list[str] = []
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            self.lines.append(line)

    @property
    def output(self) -> str:
        return "".join(self.lines)

    def wait_until_serving(self, timeout: float) -> int:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            port = instance_port(self.home)
            if port and get(port, "/health"):
                return port
            if self.proc.poll() is not None:
                break
            time.sleep(0.25)
        raise AssertionError(f"EasySpotDL did not start in {timeout} s:\n{self.output}")

    def stop(self):
        if self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(timeout=30)
        time.sleep(0.5)  # let the output pump drain

    def browser_urls(self) -> list[str]:
        log = self.home / "browser.log"
        return log.read_text().split() if log.exists() else []


@pytest.fixture(scope="session")
def prepared_home(tmp_path_factory):
    """A home whose data folder went through a full first launch (Engine installed)."""
    assert UV.exists(), "put the uv binary at the repo root"
    home = tmp_path_factory.mktemp("home")
    launch = Launch(home)
    try:
        launch.wait_until_serving(timeout=900)
    finally:
        launch.stop()
    return home, launch.output


@pytest.fixture
def home(prepared_home):
    home, _ = prepared_home
    (home / "browser.log").unlink(missing_ok=True)
    return home


def test_engine_first_install(prepared_home):
    home, output = prepared_home
    assert (data_dir(home) / "tools" / "spotdl").is_dir()
    assert spotdl_version(home).startswith("4.")
    assert (home / ".spotdl" / "ffmpeg").exists()
    assert (home / ".spotdl" / "deno").exists()
    assert "[INFO] engine: Engine installed" in output


def test_launch_opens_browser(home):
    launch = Launch(home)
    started = time.monotonic()
    try:
        port = launch.wait_until_serving(timeout=30)
        status, body = get(port)
        assert time.monotonic() - started <= 30
        assert status == 200 and "EasySpotDL" in body
        assert "No cierres esta ventana" in launch.output
        time.sleep(1)
        assert launch.browser_urls() == [f"http://127.0.0.1:{port}/"]
    finally:
        launch.stop()


def test_launch_port_fallback(home):
    with socket.socket() as busy:
        busy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # 8765 may sit in TIME_WAIT from the last test
        busy.bind(("127.0.0.1", 8765))
        busy.listen()
        launch = Launch(home)
        try:
            port = launch.wait_until_serving(timeout=60)
            assert port != 8765
            time.sleep(1)
            assert launch.browser_urls() == [f"http://127.0.0.1:{port}/"]
        finally:
            launch.stop()


def test_launch_already_running(home):
    first = Launch(home)
    try:
        port = first.wait_until_serving(timeout=60)
        second = Launch(home)
        assert second.proc.wait(timeout=60) == 0
        second.stop()
        assert "already running" in second.output
        assert instance_port(home) == port
        time.sleep(1)
        assert second.browser_urls() == [f"http://127.0.0.1:{port}/"] * 2  # first launch + second
    finally:
        first.stop()


def test_engine_update_upgrades(home):
    tool_python = data_dir(home) / "tools" / "spotdl" / "bin" / "python"
    uv_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "UV_CACHE_DIR": str(data_dir(home) / "cache"),
        "UV_PYTHON_INSTALL_DIR": str(data_dir(home) / "python"),
    }
    subprocess.run([UV, "pip", "install", "--python", tool_python, "spotdl==4.5.0"], env=uv_env, check=True)
    assert spotdl_version(home) == "4.5.0"

    launch = Launch(home)
    try:
        launch.wait_until_serving(timeout=300)
    finally:
        launch.stop()
    with urllib.request.urlopen("https://pypi.org/pypi/spotdl/json", timeout=10) as response:
        latest = json.load(response)["info"]["version"]
    assert spotdl_version(home) == latest


def test_engine_update_offline(home):
    launch = Launch(home, OFFLINE_ENV)
    try:
        launch.wait_until_serving(timeout=60)
        assert "[WARNING] engine: Engine update skipped" in launch.output
    finally:
        launch.stop()


def test_engine_first_run_offline(tmp_path):
    launch = Launch(tmp_path, OFFLINE_ENV)
    assert launch.proc.wait(timeout=180) != 0
    launch.stop()
    assert "EasySpotDL necesita internet la primera vez" in launch.output
    assert "Traceback" not in launch.output


# --- Scope 2: Playlist Download ---------------------------------------------------------------

DOWNLOAD_LINK = "https://open.spotify.com/playlist/37i9dQZF1EVHGWrwldPRtj?si=abc"


def post_json(port: int, path: str, payload: dict) -> int:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with _local.open(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as e:
        return e.code


def download_playlist(home: Path) -> tuple[dict, str, list[int]]:
    """Download DOWNLOAD_LINK through a launched app; returns the final job, the app output and the N values seen."""
    launch = Launch(home)
    try:
        port = launch.wait_until_serving(timeout=300)
        assert post_json(port, "/download", {"url": DOWNLOAD_LINK}) == 202
        assert post_json(port, "/download", {"url": DOWNLOAD_LINK}) == 409  # single_download_at_a_time
        seen, last_change, job = [], None, None
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            job = json.loads(get(port, "/status")[1])["job"]
            if not seen or job["done"] != seen[-1]:
                seen.append(job["done"])
                if job["done"] > 0:
                    last_change = time.monotonic()  # the 30 s clock starts at the first completed song
            pending = job["state"] == "running" and job["done"] < job["total"]
            if pending and last_change is not None:
                assert time.monotonic() - last_change <= 30, f"N stuck at {job['done']} for more than 30 s"
            if job["state"] != "running":
                break
            time.sleep(2)
        return job, launch.output, seen
    finally:
        launch.stop()


def mp3_files(home: Path, playlist_name: str) -> list[Path]:
    return sorted((home / "Music" / "EasySpotDL" / playlist_name).glob("*.mp3"))


def test_download_public_playlist(home):
    job, output, seen = download_playlist(home)
    assert job["state"] == "finished", output
    files = mp3_files(home, job["playlist_name"])
    # progress_updates: "N de M" where M is the playlist size and N moved forward
    assert job["total"] == 50 and len(seen) > 2
    # summary_shown: X + Y + Z = M
    assert job["downloaded"] + job["skipped"] + len(job["failed"]) == job["total"]
    # download_no_lyrics
    assert "api.genius.com" not in output
    # title and artist tags, read with the Engine's own mutagen
    tool_python = data_dir(home) / "tools" / "spotdl" / "bin" / "python"
    check = "import sys, mutagen.easyid3 as e; t = e.EasyID3(sys.argv[1]); assert t['title'] and t['artist']"
    for f in files:
        subprocess.run([tool_python, "-c", check, f], check=True)
    assert len(files) >= 0.9 * job["total"], f"{len(files)} of {job['total']} songs; failed: {job['failed']}"


def test_redownload_skips_existing(home):
    first, _, _ = download_playlist(home)
    before = mp3_files(home, first["playlist_name"])
    job, output, _ = download_playlist(home)
    assert job["state"] == "finished", output
    after = mp3_files(home, job["playlist_name"])
    assert job["skipped"] == len(before)  # every file already on disk is reported as "ya existían"
    assert len(after) == len(before) + job["downloaded"]  # no duplicates
    new_songs = {f.stem for f in after} - {f.stem for f in before}
    # Only songs that failed in the previous download may be fetched now.
    assert job["downloaded"] <= len(first["failed"]), f"downloaded {sorted(new_songs)}; failed before: {first['failed']}"


# --- Scope 3: Version Notice ------------------------------------------------------------------


def wait_for_status(port: int, predicate, timeout: float = 15) -> dict:
    deadline = time.monotonic() + timeout
    status = {}
    while time.monotonic() < deadline:
        status = json.loads(get(port, "/status")[1])
        if predicate(status):
            break
        time.sleep(0.25)
    return status


def release_channel_file(tmp_path: Path, tag: str) -> str:
    path = tmp_path / "latest.json"
    path.write_text(json.dumps({"tag_name": tag, "html_url": f"https://github.com/nuclear-hazes/EasySpotDL/releases/tag/{tag}"}))
    return path.as_uri()


def test_notice_newer_version(home, tmp_path):
    launch = Launch(home, {"DEV_RELEASE_CHANNEL_URL": release_channel_file(tmp_path, "v0.2.0")})
    try:
        port = launch.wait_until_serving(timeout=120)
        status = wait_for_status(port, lambda s: s["version_notice"])
        assert status["app_version"] == "0.1.0"
        assert status["version_notice"] == {
            "version": "0.2.0",
            "html_url": "https://github.com/nuclear-hazes/EasySpotDL/releases/tag/v0.2.0",
        }
    finally:
        launch.stop()


def test_notice_same_version(home, tmp_path):
    launch = Launch(home, {"DEV_RELEASE_CHANNEL_URL": release_channel_file(tmp_path, "v0.1.0")})
    try:
        port = launch.wait_until_serving(timeout=120)
        time.sleep(3)  # the check runs in the background right after launch
        assert "Release Channel: latest 0.1.0" in launch.output
        assert json.loads(get(port, "/status")[1])["version_notice"] is None
    finally:
        launch.stop()


def test_notice_channel_unreachable(home):
    launch = Launch(home, {"DEV_RELEASE_CHANNEL_URL": "http://127.0.0.1:9/releases/latest"})
    try:
        port = launch.wait_until_serving(timeout=120)
        time.sleep(3)
        assert "[WARNING] release_channel: Release Channel check failed" in launch.output
        status, body = get(port)
        assert status == 200 and "EasySpotDL" in body  # the app works
        assert json.loads(get(port, "/status")[1])["version_notice"] is None
    finally:
        launch.stop()
