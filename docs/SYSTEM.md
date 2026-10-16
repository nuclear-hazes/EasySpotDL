# System: EasySpotDL

## What This System Does

EasySpotDL is a portable desktop app (macOS Apple Silicon, Windows 11) that lets non-technical users turn a Spotify Public Playlist into MP3 files for MP3-only devices (e.g. swimming headphones). It wraps spotDL (the Engine) instead of reimplementing any download logic: a launcher starts a local web page, the app keeps the Engine installed and updated, and it shows a Version Notice when the Release Channel has a newer EasySpotDL.

## Stack

- **Language:** Python 3.12 (managed by a bundled standalone `uv` binary; never the system Python)
- **Framework:** FastAPI + uvicorn serving a single static HTML page (vanilla JS)
- **Database:** None (in-memory state; MP3 files are the only persistent output)
- **Infrastructure:** Runs locally on the user's machine; distributed as zip files on GitHub Releases (`nuclear-hazes/EasySpotDL`)

## Architecture Principles

- Never reimplement download, search, matching or conversion: that belongs to the Engine (spotDL).
- No compilation or native packaging: the zip ships `uv` + source; `uv` installs everything else into the user's data folder.
- Zero credentials: no Spotify, YouTube or GitHub secrets anywhere in the app.
- Do not bundle third-party binaries (ffmpeg, deno, Python) in the zip; they are fetched at runtime.
- Server binds to `127.0.0.1` only.

## Cross-Project Constraints

- Engine invocation must disable lyrics lookup and requires deno (see `MEMORY.md`).
- User-facing text is Spanish; code, identifiers and glossary are English.

## Subsystems / Components

- Launcher — per-platform double-click scripts that run `uv` and start the app
- Engine Manager — installs and updates the Engine (`engine.py`)
- Download Service — validates Public Playlist links, runs spotDL, tracks progress (`download.py`)
- Web UI — local server and single page (`server.py`, `static/index.html`)
- Release Checker — queries the Release Channel and builds the Version Notice (`release_channel.py`)
- Packaging — builds the distributable zips (`scripts/build.sh`)

## Logging

- **Framework:** Python `logging`, to stdout (the visible terminal/console window)
- **Format:** `YYYY-MM-DD HH:MM:SS [LEVEL] module: message`
- **dev level:** DEBUG | **prod level:** WARNING

## Work Artifact Indexes

- Pitches: [docs/Pitches/INDEX.md](Pitches/INDEX.md)
- Tasks: [docs/Tasks/INDEX.md](Tasks/INDEX.md)
- Projects: [docs/Projects/INDEX.md](Projects/INDEX.md)

## Deployment

- Targets and procedures: see `docs/local/deployment.md` (gitignored — not committed).
- Secrets: see `.deploy-secrets` (gitignored — not committed).
- Do NOT inline target details, hostnames, or credentials here.

## Current State

P-0001 (EasySpotDL v0.1.0) in progress: Scopes 1 and 2 done; Scope 3 open until the Windows 11 end-to-end run passes. v0.1.0 is published on the Release Channel with the macOS zip only (approved exception); the Windows zip is added to the same Release once tested. Build with `scripts/build.sh`.
