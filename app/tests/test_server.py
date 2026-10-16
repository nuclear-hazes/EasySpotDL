import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from easyspotdl import config, download, server
from easyspotdl.engine import EngineStatus
from easyspotdl.release_channel import ReleaseChecker, VersionNotice

PLAYLIST = "https://open.spotify.com/playlist/37i9dQZF1EVHGWrwldPRtj"


class FakeDownloads:
    """DownloadService stand-in: records calls, never runs the Engine."""

    def __init__(self):
        self.job = None
        self.started = []
        self.folder_opened = False

    def start(self, link):
        url = download.clean_playlist_url(link)
        if self.job and self.job.state == "running":
            raise download.DownloadInProgress
        self.started.append(url)
        self.job = download.DownloadJob(playlist_url=url, output_dir=Path("/tmp"))
        return self.job

    def open_folder(self):
        self.folder_opened = self.job is not None
        return self.folder_opened


@pytest.fixture
def downloads():
    return FakeDownloads()


@pytest.fixture
def release():
    return ReleaseChecker(url=None, current="0.1.0")  # never started: tests set .notice directly


@pytest.fixture
def client(tmp_path, downloads, release):
    cfg = config.AppConfig(
        env="dev",
        version="0.1.0",
        data_dir=tmp_path,
        music_dir=tmp_path / "Music",
        release_channel_url=None,
        preferred_port=8765,
        log_level=logging.DEBUG,
    )
    engine_status = EngineStatus(installed=True, spotdl_version="4.5.2", updated_this_launch=True)
    return TestClient(server.create_app(cfg, engine_status, downloads, release), base_url="http://127.0.0.1")


def test_index_serves_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>EasySpotDL</title>" in response.text


def test_health_identifies_app(client):
    assert client.get("/health").json() == {"app": "EasySpotDL", "version": "0.1.0"}


def test_status_without_job(client):
    assert client.get("/status").json() == {
        "app_version": "0.1.0",
        "engine": {"installed": True, "spotdl_version": "4.5.2"},
        "version_notice": None,
        "job": None,
    }


def test_status_includes_version_notice(client, release):
    release.notice = VersionNotice(version="0.2.0", html_url="https://github.com/nuclear-hazes/EasySpotDL/releases/tag/v0.2.0")
    assert client.get("/status").json()["version_notice"] == {
        "version": "0.2.0",
        "html_url": "https://github.com/nuclear-hazes/EasySpotDL/releases/tag/v0.2.0",
    }


def test_page_has_version_notice_text(client):
    # The banner reads "Hay una nueva versión de EasySpotDL (<version>)." with a link to html_url.
    page = client.get("/").text
    assert 'Hay una nueva versión de EasySpotDL (<span id="notice-version"></span>).' in page
    assert 'id="notice-link"' in page


def test_download_starts_with_clean_url(client, downloads):
    response = client.post("/download", json={"url": PLAYLIST + "?si=abc"})
    assert response.status_code == 202
    assert response.json()["state"] == "running"
    assert downloads.started == [PLAYLIST]
    job = client.get("/status").json()["job"]
    assert set(job) == {"state", "playlist_name", "total", "done", "current_song", "downloaded", "skipped", "failed"}


@pytest.mark.parametrize("link", ["https://open.spotify.com/track/69kOkLUCkxIZYexIgSG8rq", "hola"])
def test_download_rejects_non_playlist(client, downloads, link):
    response = client.post("/download", json={"url": link})
    assert response.status_code == 400
    assert response.json()["detail"] == "Pegá el link de una playlist de Spotify"
    assert downloads.started == []


def test_second_download_while_running_is_409(client):
    assert client.post("/download", json={"url": PLAYLIST}).status_code == 202
    assert client.post("/download", json={"url": PLAYLIST}).status_code == 409


def test_open_folder(client, downloads):
    assert client.post("/open-folder").status_code == 404
    client.post("/download", json={"url": PLAYLIST})
    assert client.post("/open-folder").status_code == 204
    assert downloads.folder_opened


def test_rejects_foreign_host_header(client):
    # A DNS-rebinding page reaches 127.0.0.1 but sends its own Host.
    assert client.get("/status", headers={"Host": "attacker.example"}).status_code == 400


@pytest.mark.parametrize("site", ["cross-site", "same-site"])
def test_rejects_posts_from_other_sites(client, downloads, site):
    # Any page can send a simple POST to localhost; the browser marks it with Sec-Fetch-Site.
    assert client.post("/open-folder", headers={"Sec-Fetch-Site": site}).status_code == 403
    assert client.post("/download", json={"url": PLAYLIST}, headers={"Sec-Fetch-Site": site}).status_code == 403
    assert downloads.started == []


def test_accepts_posts_from_own_page(client):
    assert client.post("/download", json={"url": PLAYLIST}, headers={"Sec-Fetch-Site": "same-origin"}).status_code == 202
