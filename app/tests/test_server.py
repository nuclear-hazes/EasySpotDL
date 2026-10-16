import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from easyspotdl import config, server


@pytest.fixture
def client(tmp_path):
    cfg = config.AppConfig(
        env="dev",
        version="0.1.0",
        data_dir=tmp_path,
        music_dir=Path(tmp_path) / "Music",
        release_channel_url=None,
        preferred_port=8765,
        log_level=logging.DEBUG,
    )
    return TestClient(server.create_app(cfg))


def test_index_serves_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>EasySpotDL</title>" in response.text


def test_health_identifies_app(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"app": "EasySpotDL", "version": "0.1.0"}
