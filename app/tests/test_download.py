import json
import sys
import time
from pathlib import Path

import pytest

from easyspotdl import download

PLAYLIST = "https://open.spotify.com/playlist/37i9dQZF1EVHGWrwldPRtj"
PAD = " " * 40  # spotDL pads its lines with spaces


@pytest.mark.parametrize(
    "link",
    [
        "https://open.spotify.com/playlist/37i9dQZF1EVHGWrwldPRtj?si=abc",
        "  https://open.spotify.com/playlist/37i9dQZF1EVHGWrwldPRtj  ",
        "https://open.spotify.com/intl-es/playlist/37i9dQZF1EVHGWrwldPRtj?si=abc&pt=1",
        "open.spotify.com/playlist/37i9dQZF1EVHGWrwldPRtj",
        "https://open.spotify.com/playlist/37i9dQZF1EVHGWrwldPRtj/",
        "https://Open.Spotify.com:443/playlist/37i9dQZF1EVHGWrwldPRtj",
    ],
)
def test_clean_playlist_url_accepts_and_drops_query(link):
    assert download.clean_playlist_url(link) == PLAYLIST


@pytest.mark.parametrize(
    "link",
    [
        "https://open.spotify.com/track/69kOkLUCkxIZYexIgSG8rq",
        "hola",
        "",
        "https://open.spotify.com/album/37i9dQZF1EVHGWrwldPRtj",
        "https://evil.example/playlist/37i9dQZF1EVHGWrwldPRtj",
        "https://open.spotify.com/playlist/short",
        "[",
        "https://[",
    ],
)
def test_clean_playlist_url_rejects(link):
    with pytest.raises(download.InvalidLink, match="Pegá el link de una playlist de Spotify"):
        download.clean_playlist_url(link)


def test_apply_line_follows_engine_output(tmp_path):
    job = download.DownloadJob(playlist_url=PLAYLIST, output_dir=tmp_path)
    for line in [
        "Processing query: https://open.spotify.com/playlist/37i9dQZF1EVHGWrwldPRtj",
        "Found 50 songs in Chill Mix (Playlist)",
        "Miguel - Sure Thing: Searching for song",
        "Miguel - Sure Thing: Downloading",
        'Downloaded "Miguel - Sure Thing": https://music.youtube.com/watch?v=abc',
        "Miguel - Sure Thing: Done",
        "1/50 complete",
        "Skipping Alex Warren - Ordinary (file already exists) (duplicate)",
        "Alex Warren - Ordinary: Skipped",
        "2/50 complete",
        "Tom Odell - Another Love: Embedding metadata",
        "AudioProviderError: YT-DLP download error - https://www.youtube.com/watch?v=x",
        "something spotDL may print in a future version",
    ]:
        download.apply_line(job, line + PAD + "\n")
    assert (job.playlist_name, job.total, job.done) == ("Chill Mix", 50, 2)
    assert (job.downloaded, job.skipped) == (1, 1)
    assert job.current_song == "Tom Odell - Another Love"
    assert job.output_dir == tmp_path / "Chill Mix"


TRACK_1 = "https://open.spotify.com/track/1i92UFFkxtKv4tYNzt1X1b"
TRACK_2 = "https://open.spotify.com/track/0rhJ30qQSus6Ckn3hKZ6Hr"
TRACK_3 = "https://open.spotify.com/track/2nO1DYEg1X5GHi8SSuNJQj"


def write_engine_files(tmp_path, songs):
    errors = tmp_path / "errors.txt"
    errors.write_text(
        "2026-10-16-12-11-37\n"
        f"{TRACK_1} - AudioProviderError: YT-DLP download error - https://www.youtube.com/watch?v=YCyq5bDe3Pk\n"
        f"{TRACK_2} - LookupError: No results found for song: Tom Odell - Another Love\n"
    )
    songs_file = tmp_path / "songs.spotdl"
    songs_file.write_text(json.dumps(songs))
    return errors, songs_file


def test_failed_songs_uses_names_and_falls_back_to_link(tmp_path):
    job = download.DownloadJob(playlist_url=PLAYLIST, output_dir=tmp_path)
    errors, songs = write_engine_files(tmp_path, [{"url": TRACK_1, "artist": "PARTYNEXTDOOR", "name": "Break from Toronto"}])
    assert download.failed_songs(job, errors, songs) == ["PARTYNEXTDOOR - Break from Toronto", TRACK_2]


def test_failed_songs_includes_songs_the_engine_dropped(tmp_path):
    # spotDL can drop a song with no error entry ("Could not get session auth tokens").
    job = download.DownloadJob(playlist_url=PLAYLIST, output_dir=tmp_path)
    download.apply_line(job, 'Downloaded "Miguel - Sure Thing": https://music.youtube.com/watch?v=abc')
    errors, songs = write_engine_files(tmp_path, [
        {"url": TRACK_1, "artist": "PARTYNEXTDOOR", "name": "Break from Toronto"},
        {"url": "https://open.spotify.com/track/miguel", "artist": "Miguel", "name": "Sure Thing"},
        {"url": TRACK_3, "artist": "Kendrick Lamar", "name": "LOVE. FEAT. ZACARI."},
    ])
    assert download.failed_songs(job, errors, songs) == [
        "PARTYNEXTDOOR - Break from Toronto",
        TRACK_2,
        "Kendrick Lamar - LOVE. FEAT. ZACARI.",
    ]


def test_failed_songs_without_files(tmp_path):
    job = download.DownloadJob(playlist_url=PLAYLIST, output_dir=tmp_path)
    assert download.failed_songs(job, tmp_path / "none.txt", tmp_path / "none.spotdl") == []


def test_failed_songs_keeps_total_when_engine_died_mid_run(tmp_path):
    # spotDL writes --save-errors / --save-file only at the end; killed after 1 of 3 songs, both are missing.
    job = download.DownloadJob(playlist_url=PLAYLIST, output_dir=tmp_path)
    download.apply_line(job, "Found 3 songs in Chill Mix (Playlist)")
    download.apply_line(job, 'Downloaded "Miguel - Sure Thing": https://music.youtube.com/watch?v=abc')
    failed = download.failed_songs(job, tmp_path / "none.txt", tmp_path / "none.spotdl")
    assert failed == [download.UNKNOWN_SONG] * 2
    assert job.downloaded + job.skipped + len(failed) == job.total


FAKE_SPOTDL = """#!{python}
# Stand-in for spotDL: prints recorded 4.5.2 output and writes --save-errors / --save-file.
# Pass 1: 1 downloaded, 1 already there, 1 failed. The first retry recovers it, except:
# FAKE_MODE=persistent: it fails on every pass. FAKE_MODE=twice: only the second retry recovers it.
# FAKE_MODE=dropped: pass 1 silently loses the song that is already there (no line, no error entry).
import json, os, pathlib, sys, time
args = sys.argv[1:]
log = pathlib.Path({calls!r})
calls = json.loads(log.read_text()) if log.exists() else []
calls.append({{"args": args, "cwd": os.getcwd()}})
log.write_text(json.dumps(calls))
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "broken":
    print("Traceback: Spotify said no", flush=True)
    sys.exit(1)
gate = pathlib.Path({gate!r})
print("Found 3 songs in Chill Mix (Playlist)", flush=True)
while mode == "slow" and not gate.exists():
    time.sleep(0.05)
counter = pathlib.Path("Chill Mix") / ".passes"  # passes over the playlist so far
passes = int(counter.read_text()) if counter.exists() else 0
retry = passes > 0
if retry:
    print("Skipping Miguel - Sure Thing (file already exists)", flush=True)
else:
    print('Downloaded "Miguel - Sure Thing": https://music.youtube.com/watch?v=abc', flush=True)
print("1/3 complete", flush=True)
if mode == "dropped" and not retry:
    print("Error occurred while reinitializing song: Could not get session auth tokens", flush=True)
else:
    print("Skipping Alex Warren - Ordinary (file already exists)", flush=True)
print("2/3 complete", flush=True)
failed = not retry or mode == "persistent" or (mode == "twice" and passes == 1)
if not failed:
    print('Downloaded "PARTYNEXTDOOR - Break from Toronto": https://music.youtube.com/watch?v=def', flush=True)
print("3/3 complete", flush=True)
errors = args[args.index("--save-errors") + 1]
entry = "https://open.spotify.com/track/1i92UFFkxtKv4tYNzt1X1b - AudioProviderError: x\\n" if failed else ""
pathlib.Path(errors).write_text("2026-10-16\\n" + entry)
songs = args[args.index("--save-file") + 1]
pathlib.Path(songs).write_text(json.dumps([
    {{"url": "https://open.spotify.com/track/miguel", "artist": "Miguel", "name": "Sure Thing"}},
    {{"url": "https://open.spotify.com/track/alex", "artist": "Alex Warren", "name": "Ordinary"}},
    {{"url": "https://open.spotify.com/track/1i92UFFkxtKv4tYNzt1X1b", "artist": "PARTYNEXTDOOR", "name": "Break from Toronto"}},
]))
os.makedirs("Chill Mix", exist_ok=True)
counter.write_text(str(passes + 1))
"""


@pytest.fixture
def service(tmp_path):
    spotdl = tmp_path / "spotdl"
    spotdl.write_text(FAKE_SPOTDL.format(python=sys.executable, calls=str(tmp_path / "calls.json"), gate=str(tmp_path / "gate")))
    spotdl.chmod(0o755)
    svc = download.DownloadService(spotdl, tmp_path / "Music" / "EasySpotDL")
    svc.tmp_path = tmp_path
    return svc


def wait_done(svc, timeout=10):
    deadline = time.monotonic() + timeout
    while svc.job.state == "running" and time.monotonic() < deadline:
        time.sleep(0.05)
    return svc.job


def engine_calls(service):
    return json.loads((service.tmp_path / "calls.json").read_text())


def test_service_runs_engine_and_retries_failed_songs(service):
    service.start("https://open.spotify.com/playlist/37i9dQZF1EVHGWrwldPRtj?si=abc")
    job = wait_done(service)
    assert job.state == "finished"
    # Pass 1: 1 downloaded, 1 already there, 1 failed; the retry downloads the failed one.
    assert (job.total, job.done, job.downloaded, job.skipped, job.failed) == (3, 3, 2, 1, [])
    assert job.output_dir == service.music_dir / "Chill Mix"

    calls = engine_calls(service)
    assert len(calls) == 2  # no second retry once nothing failed
    args = calls[0]["args"]
    assert args[:2] == ["download", PLAYLIST]
    assert args[args.index("--lyrics") + 1].startswith("--")  # no lyrics providers given
    assert args[args.index("--format") + 1] == "mp3"
    assert args[args.index("--output") + 1] == "{list-name}/{artists} - {title}.{output-ext}"
    assert "--simple-tui" in args
    assert Path(calls[0]["cwd"]).resolve() == service.music_dir.resolve()


def test_service_reports_songs_that_fail_twice(service, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "persistent")
    service.start(PLAYLIST)
    job = wait_done(service)
    assert (job.downloaded, job.skipped, job.failed) == (1, 1, ["PARTYNEXTDOOR - Break from Toronto"])
    assert job.downloaded + job.skipped + len(job.failed) == job.total
    assert len(engine_calls(service)) == 1 + download.MAX_RETRIES


def test_service_second_retry_recovers_song(service, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "twice")
    service.start(PLAYLIST)
    job = wait_done(service)
    assert (job.downloaded, job.skipped, job.failed) == (2, 1, [])
    assert len(engine_calls(service)) == 3


def test_service_counts_dropped_song_already_on_disk_as_skipped(service, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "dropped")
    service.start(PLAYLIST)
    job = wait_done(service)
    # Pass 1 lost "Alex Warren - Ordinary" and failed one song; the retry skips the first and downloads the second.
    assert (job.downloaded, job.skipped, job.failed) == (2, 1, [])
    assert job.downloaded + job.skipped + len(job.failed) == job.total


def test_service_allows_one_download_at_a_time(service, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "slow")
    service.start(PLAYLIST)
    with pytest.raises(download.DownloadInProgress):
        service.start(PLAYLIST)
    (service.tmp_path / "gate").touch()
    assert wait_done(service).state == "finished"
    service.start(PLAYLIST)  # allowed again once finished
    assert wait_done(service).state == "finished"


def test_service_rejects_invalid_link_without_running_engine(service):
    with pytest.raises(download.InvalidLink):
        service.start("hola")
    assert service.job is None
    assert not (service.tmp_path / "calls.json").exists()


def test_service_marks_unreadable_playlist_as_failed(service, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "broken")
    service.start(PLAYLIST)
    assert wait_done(service).state == "failed"


def test_service_never_stays_running_when_it_crashes(service, monkeypatch):
    def boom(job, workdir, shown=None):
        raise PermissionError("music folder not writable")

    monkeypatch.setattr(service, "_run_engine", boom)
    service.start(PLAYLIST)
    assert wait_done(service).state == "failed"
    service.start(PLAYLIST)  # not stuck: a new download is accepted


def test_service_marks_missing_engine_as_failed(tmp_path):
    svc = download.DownloadService(tmp_path / "missing-spotdl", tmp_path / "Music")
    svc.start(PLAYLIST)
    assert wait_done(svc).state == "failed"


def test_open_folder(service, monkeypatch):
    assert service.open_folder() is False  # no download yet
    service.start(PLAYLIST)
    wait_done(service)
    opened = []
    monkeypatch.setattr(download.sys, "platform", "darwin")
    monkeypatch.setattr(download.subprocess, "run", lambda cmd, check: opened.append(cmd))
    assert service.open_folder() is True
    assert opened == [["open", str(service.music_dir / "Chill Mix")]]
