import json
import logging
import time

import pytest

from easyspotdl import release_channel

RELEASE_URL = "https://github.com/nuclear-hazes/EasySpotDL/releases/tag/v0.2.0"


def channel(tmp_path, tag="v0.2.0", html_url=RELEASE_URL, raw=None):
    """A local Release Channel file, as dev uses (DEV_RELEASE_CHANNEL_URL=file://...)."""
    path = tmp_path / "latest.json"
    path.write_text(raw if raw is not None else json.dumps({"tag_name": tag, "html_url": html_url}))
    return path.as_uri()


@pytest.mark.parametrize("text, expected", [("v0.2.0", (0, 2, 0)), ("0.10.3", (0, 10, 3)), (" v1.0.0 ", (1, 0, 0))])
def test_parse_version(text, expected):
    assert release_channel.parse_version(text) == expected


@pytest.mark.parametrize("text", ["0.2", "v0.2.0-beta", "latest", ""])
def test_parse_version_rejects(text):
    with pytest.raises(ValueError):
        release_channel.parse_version(text)


def test_newer_version_gives_notice(tmp_path):
    notice = release_channel.check(channel(tmp_path, "v0.2.0"), "0.1.0")
    assert notice == release_channel.VersionNotice(version="0.2.0", html_url=RELEASE_URL)


def test_compares_numerically_not_as_text(tmp_path):
    assert release_channel.check(channel(tmp_path, "v0.10.0"), "0.9.0") is not None


@pytest.mark.parametrize("tag", ["v0.1.0", "v0.0.9"])
def test_same_or_older_version_gives_no_notice(tmp_path, tag):
    assert release_channel.check(channel(tmp_path, tag), "0.1.0") is None


@pytest.mark.parametrize(
    "url_maker",
    [
        lambda tmp: "http://127.0.0.1:9/releases/latest",  # nothing listens: unreachable
        lambda tmp: (tmp / "missing.json").as_uri(),
        lambda tmp: channel(tmp, raw="not json"),
        lambda tmp: channel(tmp, raw=json.dumps({"message": "API rate limit exceeded"})),
        lambda tmp: channel(tmp, tag="v0.2.0-beta"),
        lambda tmp: channel(tmp, html_url="javascript:alert(1)"),
    ],
)
def test_channel_problems_give_no_notice_and_warn(tmp_path, caplog, url_maker):
    assert release_channel.check(url_maker(tmp_path), "0.1.0") is None
    assert any(r.levelno == logging.WARNING and "Release Channel check failed" in r.message for r in caplog.records)


def test_no_channel_configured(caplog):
    assert release_channel.check(None, "0.1.0") is None
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)


def test_checker_runs_in_background(tmp_path):
    checker = release_channel.ReleaseChecker(channel(tmp_path), "0.1.0")
    assert checker.notice is None
    checker.start()
    deadline = time.monotonic() + 5
    while checker.notice is None and time.monotonic() < deadline:
        time.sleep(0.05)
    assert checker.notice == release_channel.VersionNotice(version="0.2.0", html_url=RELEASE_URL)
