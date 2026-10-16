"""Web UI: the local FastAPI server and its single page."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from .config import AppConfig

STATIC_DIR = Path(__file__).parent / "static"
APP_NAME = "EasySpotDL"


def create_app(cfg: AppConfig) -> FastAPI:
    # The OpenAPI document stays at /openapi.json; the docs UIs are off (they load assets from a CDN).
    app = FastAPI(title=APP_NAME, version=cfg.version, docs_url=None, redoc_url=None)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health", summary="Identify a running EasySpotDL instance")
    def health() -> dict[str, str]:
        return {"app": APP_NAME, "version": cfg.version}

    return app
