"""Entry point: single instance, port choice, Engine, server and browser."""

import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

from . import config, download, engine, release_channel, server

log = logging.getLogger(__name__)

HOST = "127.0.0.1"
INSTANCE_FILE = "instance.json"
# Local calls must never go through a proxy configured in the environment.
_local_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def url_for(port: int) -> str:
    return f"http://{HOST}:{port}/"


def running_instance_port(data_dir: Path) -> int | None:
    """Port of a live EasySpotDL recorded in the instance file, or None (missing or stale)."""
    try:
        port = int(json.loads((data_dir / INSTANCE_FILE).read_text())["port"])
        with _local_opener.open(f"{url_for(port)}health", timeout=2) as response:
            if json.load(response).get("app") == server.APP_NAME:
                return port
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _new_socket() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name == "posix":
        # Reopening right after closing must not lose the port to TIME_WAIT. Not on Windows,
        # where SO_REUSEADDR lets a socket steal a port that is actively in use.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return sock


def bind_socket(preferred_port: int) -> socket.socket:
    """Bind the preferred port, or any free port the OS assigns if it is taken."""
    sock = _new_socket()
    try:
        sock.bind((HOST, preferred_port))
    except OSError:
        log.warning("Port %d is busy, using a free port", preferred_port)
        sock.close()
        sock = _new_socket()
        sock.bind((HOST, 0))
    return sock


def open_browser(url: str) -> None:
    log.info("Opening browser at %s", url)
    webbrowser.open(url)


def _open_browser_when_started(srv: uvicorn.Server, url: str) -> None:
    while not srv.started:
        time.sleep(0.1)
    open_browser(url)


def main() -> int:
    try:
        cfg = config.load_config()
    except ValueError as e:
        config.setup_logging(logging.ERROR)
        log.error("Invalid configuration: %s", e)
        return 1
    config.setup_logging(cfg.log_level)
    log.info("EasySpotDL %s starting (ENV=%s)", cfg.version, cfg.env)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)

    port = running_instance_port(cfg.data_dir)
    if port is not None:
        log.info("EasySpotDL is already running on port %d", port)
        open_browser(url_for(port))
        return 0

    try:
        engine_status = engine.ensure_engine(cfg.data_dir)
    except engine.EngineError as e:
        log.error("%s", e)
        return 1

    release = release_channel.ReleaseChecker(cfg.release_channel_url, cfg.version)
    release.start()

    sock = bind_socket(cfg.preferred_port)
    port = sock.getsockname()[1]
    instance_file = cfg.data_dir / INSTANCE_FILE
    instance_file.write_text(json.dumps({"port": port, "pid": os.getpid()}))
    downloads = download.DownloadService(engine.spotdl_path(cfg.data_dir), cfg.music_dir)
    app = server.create_app(cfg, engine_status, downloads, release)
    srv = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False))
    threading.Thread(target=_open_browser_when_started, args=(srv, url_for(port)), daemon=True).start()
    try:
        srv.run(sockets=[sock])
    finally:
        instance_file.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
