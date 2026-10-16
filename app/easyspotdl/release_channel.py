"""Release Checker: asks the Release Channel for the latest EasySpotDL and builds the Version Notice."""

import http.client
import json
import logging
import threading
import urllib.request
from dataclasses import dataclass

log = logging.getLogger(__name__)

TIMEOUT_S = 5


@dataclass(frozen=True)
class VersionNotice:
    version: str
    html_url: str


def parse_version(text: str) -> tuple[int, int, int]:
    """'v1.2.3' or '1.2.3' -> (1, 2, 3); anything else raises ValueError."""
    parts = text.strip().removeprefix("v").split(".")
    if len(parts) != 3:
        raise ValueError(f"not a MAJOR.MINOR.PATCH version: {text!r}")
    major, minor, patch = (int(p) for p in parts)
    return major, minor, patch


def check(url: str | None, current: str) -> VersionNotice | None:
    """Version Notice when the Release Channel has a newer EasySpotDL, else None. Never raises."""
    if not url:
        log.debug("No Release Channel configured")
        return None
    # GitHub's API wants a User-Agent; file:// URLs (dev) ignore the headers.
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "EasySpotDL"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            release = json.load(response)
        latest, html_url = release["tag_name"].strip().removeprefix("v"), release["html_url"]
        if not html_url.startswith("https://"):
            raise ValueError(f"unexpected release link {html_url!r}")
        newer = parse_version(latest) > parse_version(current)
    except (OSError, http.client.HTTPException, ValueError, KeyError, TypeError, AttributeError) as e:
        log.warning("Release Channel check failed: %s", e)
        return None
    log.info("Release Channel: latest %s, running %s", latest, current)
    return VersionNotice(version=latest, html_url=html_url) if newer else None


class ReleaseChecker:
    """Runs check() in the background so a slow Release Channel never delays the launch."""

    def __init__(self, url: str | None, current: str):
        self.url = url
        self.current = current
        self.notice: VersionNotice | None = None

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        self.notice = check(self.url, self.current)
