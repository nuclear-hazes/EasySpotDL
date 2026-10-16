import json
import logging
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from easyspotdl import __main__ as main_module
from easyspotdl import config, engine


def serve_health(app_name: str) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"app": app_name}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    httpd = HTTPServer((main_module.HOST, 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def free_port() -> int:
    with socket.socket() as s:
        s.bind((main_module.HOST, 0))
        return s.getsockname()[1]


def write_instance(data_dir, port):
    (data_dir / main_module.INSTANCE_FILE).write_text(json.dumps({"port": port, "pid": 1}))


def test_bind_socket_uses_preferred_port_when_free():
    port = free_port()
    with main_module.bind_socket(port) as sock:
        assert sock.getsockname() == (main_module.HOST, port)


def test_bind_socket_falls_back_when_port_busy():
    with socket.socket() as busy:
        busy.bind((main_module.HOST, 0))
        busy.listen()
        taken = busy.getsockname()[1]
        with main_module.bind_socket(taken) as sock:
            assert sock.getsockname()[1] not in (0, taken)


def test_bind_socket_reuses_port_right_after_close():
    port = free_port()
    with socket.socket() as server, socket.socket() as client:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((main_module.HOST, port))
        server.listen()
        client.connect((main_module.HOST, port))
        conn, _ = server.accept()
        conn.close()  # server-side close leaves the port in TIME_WAIT
    with main_module.bind_socket(port) as sock:
        assert sock.getsockname()[1] == port


def test_no_instance_file_means_not_running(tmp_path):
    assert main_module.running_instance_port(tmp_path) is None


def test_detects_live_instance(tmp_path):
    httpd = serve_health("EasySpotDL")
    try:
        write_instance(tmp_path, httpd.server_port)
        assert main_module.running_instance_port(tmp_path) == httpd.server_port
    finally:
        httpd.shutdown()


def test_ignores_stale_instance_file(tmp_path):
    write_instance(tmp_path, free_port())
    assert main_module.running_instance_port(tmp_path) is None


def test_ignores_other_app_on_recorded_port(tmp_path):
    httpd = serve_health("SomethingElse")
    try:
        write_instance(tmp_path, httpd.server_port)
        assert main_module.running_instance_port(tmp_path) is None
    finally:
        httpd.shutdown()


def test_main_exits_1_on_invalid_env(monkeypatch, caplog):
    def bad_config():
        raise ValueError("ENV must be one of ['dev', 'prod'], got 'staging'")

    monkeypatch.setattr(main_module.config, "load_config", bad_config)
    assert main_module.main() == 1
    assert "Invalid configuration" in caplog.text


@pytest.fixture
def app_config(tmp_path, monkeypatch):
    cfg = config.AppConfig(
        env="dev",
        version="0.1.0",
        data_dir=tmp_path / "data",
        music_dir=tmp_path / "Music",
        release_channel_url=None,
        preferred_port=8765,
        log_level=logging.DEBUG,
    )
    monkeypatch.setattr(main_module.config, "load_config", lambda: cfg)
    return cfg


def test_main_reuses_running_instance(app_config, monkeypatch):
    opened = []
    monkeypatch.setattr(main_module, "running_instance_port", lambda data_dir: 9999)
    monkeypatch.setattr(main_module.webbrowser, "open", opened.append)
    monkeypatch.setattr(main_module.engine, "ensure_engine", lambda data_dir: pytest.fail("Engine must not run"))
    assert main_module.main() == 0
    assert opened == ["http://127.0.0.1:9999/"]


def test_main_exits_1_with_message_when_engine_unavailable(app_config, monkeypatch, caplog):
    def no_engine(data_dir):
        raise engine.EngineError("EasySpotDL necesita internet la primera vez. Conectate y volvé a abrirlo.")

    monkeypatch.setattr(main_module.engine, "ensure_engine", no_engine)
    assert main_module.main() == 1
    assert "EasySpotDL necesita internet la primera vez" in caplog.text
