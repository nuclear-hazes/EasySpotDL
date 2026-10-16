"""Download Service: validates Public Playlist links, runs the Engine and tracks progress."""

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

log = logging.getLogger(__name__)

INVALID_LINK_MESSAGE = "Pegá el link de una playlist de Spotify"
OUTPUT_TEMPLATE = "{list-name}/{artists} - {title}.{output-ext}"
UNKNOWN_SONG = "Canción sin identificar"
# Each extra pass recovers songs YouTube dropped under load (32 → 46 of 50 measured over passes).
MAX_RETRIES = 2

_PLAYLIST_PATH = re.compile(r"/(?:intl-[a-z]{2}(?:-[a-z]{2})?/)?playlist/([A-Za-z0-9]{22})/?")
# spotDL --simple-tui output (4.5.x). Lines that match nothing are ignored.
_FOUND = re.compile(r"^Found (\d+) songs in (.+) \(\w+\)$")
_COMPLETE = re.compile(r"^(\d+)/\d+ complete$")
_DOWNLOADED = re.compile(r'^Downloaded "(.+)": ')
_SKIPPED = re.compile(r"^Skipping (.+) \((?:file already exists|skip file found)\)")
_STATUS = re.compile(r"^(.+): (Searching for song|Getting audio meta|Downloading|Converting|Embedding metadata)$")
_ERROR_ENTRY = re.compile(r"^(https://open\.spotify\.com/track/\S+) - ")


class InvalidLink(ValueError):
    pass


class DownloadInProgress(RuntimeError):
    pass


@dataclass
class DownloadJob:
    playlist_url: str
    output_dir: Path
    playlist_name: str | None = None
    state: str = "running"  # running | finished | failed
    total: int = 0
    done: int = 0
    current_song: str | None = None
    downloaded: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
    # Songs reported as downloaded or already there, by "Artist - Title" (not part of /status).
    downloaded_names: set[str] = field(default_factory=set)
    skipped_names: set[str] = field(default_factory=set)

    def to_status(self) -> dict:
        return {
            "state": self.state,
            "playlist_name": self.playlist_name,
            "total": self.total,
            "done": self.done,
            "current_song": self.current_song,
            "downloaded": self.downloaded,
            "skipped": self.skipped,
            "failed": list(self.failed),
        }


def clean_playlist_url(text: str) -> str:
    """Return the canonical Public Playlist URL (no query string) or raise InvalidLink."""
    text = text.strip()
    if "://" not in text:
        text = f"https://{text}"
    try:
        parts = urlsplit(text)
        host = parts.hostname  # lowercased, without port
    except ValueError as e:  # e.g. "[" is an invalid IPv6 netloc
        raise InvalidLink(INVALID_LINK_MESSAGE) from e
    match = _PLAYLIST_PATH.fullmatch(parts.path)
    if parts.scheme not in ("http", "https") or host != "open.spotify.com" or not match:
        raise InvalidLink(INVALID_LINK_MESSAGE)
    return f"https://open.spotify.com/playlist/{match.group(1)}"


def apply_line(job: DownloadJob, line: str) -> None:
    """Update the job from one line of Engine output."""
    line = line.strip()
    if m := _FOUND.match(line):
        job.total, job.playlist_name = int(m[1]), m[2]
        job.output_dir = job.output_dir / job.playlist_name
    elif m := _COMPLETE.match(line):
        job.done = int(m[1])
    elif m := _DOWNLOADED.match(line):
        job.downloaded += 1
        job.downloaded_names.add(m[1])
    elif m := _SKIPPED.match(line):
        job.skipped += 1
        job.skipped_names.add(m[1])
    elif m := _STATUS.match(line):
        job.current_song = m[1]


def failed_songs(job: DownloadJob, errors_file: Path, songs_file: Path) -> list[str]:
    """Songs of the pass that ended neither downloaded nor already there, as 'Artist - Title'.

    Covers the Engine's error file and songs it drops without a trace (e.g. a Spotify token
    error while reloading a song). Falls back to the song link when the name is unknown.
    """
    try:
        songs = json.loads(songs_file.read_text(encoding="utf-8"))
        names = {s["url"]: f"{s['artist']} - {s['name']}" for s in songs}
    except (OSError, ValueError, KeyError, TypeError):
        names = {}
    try:
        lines = errors_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    error_urls = [m[1] for line in lines if (m := _ERROR_ENTRY.match(line))]
    accounted = job.downloaded_names | job.skipped_names
    dropped = [url for url, name in names.items() if name not in accounted and url not in error_urls]
    failed = [names.get(url, url) for url in error_urls + dropped]
    # spotDL writes both files only at the end; if it died mid-run, the rest are unaccounted for.
    unknown = job.total - job.downloaded - job.skipped - len(failed)
    if unknown > 0:
        log.warning("%d songs unaccounted for after the Engine run", unknown)
        failed += [UNKNOWN_SONG] * unknown
    return failed


class DownloadService:
    """Runs one Engine download at a time and keeps the last job in memory."""

    def __init__(self, spotdl: Path, music_dir: Path):
        self.spotdl = spotdl
        self.music_dir = music_dir
        self.job: DownloadJob | None = None
        self._lock = threading.Lock()

    def start(self, link: str) -> DownloadJob:
        url = clean_playlist_url(link)
        with self._lock:
            if self.job and self.job.state == "running":
                raise DownloadInProgress
            job = self.job = DownloadJob(playlist_url=url, output_dir=self.music_dir)
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return job

    def _run(self, job: DownloadJob) -> None:
        log.info("Download started: %s", job.playlist_url)
        try:
            self._download(job)
        except Exception:
            log.exception("Download crashed")
            job.total = 0  # reported as failed below
        job.current_song = None
        # Without "Found N songs" the playlist was never read (bad link, no network, Spotify error).
        job.state = "failed" if job.total == 0 else "finished"
        log.log(
            logging.WARNING if job.state == "failed" else logging.INFO,
            "Download %s: %d downloaded, %d skipped, %d failed",
            job.state, job.downloaded, job.skipped, len(job.failed),
        )

    def _download(self, job: DownloadJob) -> None:
        self.music_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="easyspotdl-") as tmp:
            if not self._run_engine(job, Path(tmp) / "pass-0"):
                return
            # YouTube drops many songs under parallel load; each retry pass skips the files
            # already on disk and tries only the failed ones again.
            for attempt in range(1, MAX_RETRIES + 1):
                if not (job.total and job.failed):
                    break
                log.info("Retry %d: %d failed songs", attempt, len(job.failed))
                retry = DownloadJob(playlist_url=job.playlist_url, output_dir=self.music_dir)
                if not (self._run_engine(retry, Path(tmp) / f"pass-{attempt}", shown=job) and retry.total):
                    break
                job.downloaded += retry.downloaded
                # A song dropped by an earlier pass may already be on disk: it counts as "ya existían".
                job.skipped += len(retry.skipped_names & set(job.failed))
                # Only songs that failed before can stay failed (a retry may drop other songs too).
                job.failed = [song for song in retry.failed if song in job.failed]

    def _run_engine(self, job: DownloadJob, workdir: Path, shown: DownloadJob | None = None) -> bool:
        """One spotDL pass over the playlist, applied to job; False if spotDL could not start.

        shown, when given, is the job the page displays: it gets the current song as the pass runs.
        """
        workdir.mkdir()
        errors_file, songs_file = workdir / "errors.txt", workdir / "songs.spotdl"
        cmd = [
            str(self.spotdl), "download", job.playlist_url,
            "--lyrics",  # no providers: lyrics lookup off
            "--format", "mp3",
            "--output", OUTPUT_TEMPLATE,
            "--save-errors", str(errors_file),
            "--save-file", str(songs_file),
            "--simple-tui",
        ]
        # Wide, unbuffered UTF-8 output so each event arrives whole and on time.
        env = {**os.environ, "COLUMNS": "1000", "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        try:
            with subprocess.Popen(
                cmd, cwd=self.music_dir, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            ) as proc:
                for line in proc.stdout:
                    log.debug("spotDL: %s", line.rstrip())
                    apply_line(job, line)
                    if shown:
                        shown.current_song = job.current_song
                returncode = proc.wait()
        except OSError as e:
            log.error("Could not start the Engine: %s", e)
            return False
        if returncode != 0:
            log.warning("Engine exited with code %d", returncode)
        job.failed = failed_songs(job, errors_file, songs_file)
        return True

    def open_folder(self) -> bool:
        """Open the last playlist's folder in Finder / Explorer; False when there is none yet."""
        if not self.job:
            return False
        # spotDL may sanitize the playlist name for the folder; fall back to the music folder.
        folder = self.job.output_dir if self.job.output_dir.is_dir() else self.music_dir
        if not folder.is_dir():
            return False
        if sys.platform == "win32":
            os.startfile(folder)
        else:
            subprocess.run(["open", str(folder)], check=False)
        return True
