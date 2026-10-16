"""Web UI: the local FastAPI server and its single page."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .config import AppConfig
from .download import DownloadInProgress, DownloadService, InvalidLink
from .engine import EngineStatus

STATIC_DIR = Path(__file__).parent / "static"
APP_NAME = "EasySpotDL"


class DownloadRequest(BaseModel):
    url: str


def create_app(cfg: AppConfig, engine_status: EngineStatus, downloads: DownloadService) -> FastAPI:
    # The OpenAPI document stays at /openapi.json; the docs UIs are off (they load assets from a CDN).
    app = FastAPI(title=APP_NAME, version=cfg.version, docs_url=None, redoc_url=None)
    # Only our own page may call the API: blocks DNS-rebinding pages that resolve to 127.0.0.1.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def reject_foreign_posts(request: Request, call_next):
        # Any web page can send a simple POST to localhost; browsers label it with Sec-Fetch-Site.
        if request.method == "POST" and request.headers.get("sec-fetch-site") in ("cross-site", "same-site"):
            return JSONResponse({"detail": "Forbidden"}, status_code=403)
        return await call_next(request)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health", summary="Identify a running EasySpotDL instance")
    def health() -> dict[str, str]:
        return {"app": APP_NAME, "version": cfg.version}

    @app.get("/status", summary="App version, Engine, Version Notice and the last download")
    def status() -> dict:
        return {
            "app_version": cfg.version,
            "engine": {"installed": engine_status.installed, "spotdl_version": engine_status.spotdl_version},
            "version_notice": None,
            "job": downloads.job.to_status() if downloads.job else None,
        }

    @app.post(
        "/download",
        status_code=202,
        summary="Start downloading a Public Playlist",
        responses={400: {"description": "Not a Public Playlist link"}, 409: {"description": "A download is running"}},
    )
    def download(request: DownloadRequest) -> dict:
        try:
            job = downloads.start(request.url)
        except InvalidLink as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except DownloadInProgress as e:
            raise HTTPException(status_code=409, detail="Ya hay una descarga en curso") from e
        return job.to_status()

    @app.post(
        "/open-folder",
        status_code=204,
        summary="Open the last playlist's folder in Finder / Explorer",
        responses={404: {"description": "No download yet"}},
    )
    def open_folder() -> Response:
        if not downloads.open_folder():
            raise HTTPException(status_code=404, detail="Todavía no hay una descarga")
        return Response(status_code=204)

    return app
