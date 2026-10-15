# Glossary — Ubiquitous Language

This file is the single source of truth for domain vocabulary across this project. Every pitch, spec, doc, and code identifier must use the canonical terms defined here. If a concept does not yet have an entry, it is not yet part of the Ubiquitous Language — invoke the `glossary` skill to add it before using the term in artifacts.

Keep this file under ~200 lines. If it grows beyond that, push project-specific terminology into the relevant `docs/Projects/P-xxxx/spec.md` instead, and keep this file for system-wide concepts only.

---

## Domain Terms

<!--
Entities, roles, business concepts. Alphabetical.

Example:

### Customer

**Definition:** A person or organisation that holds an active subscription. Distinguished from prospects (no subscription) and former customers (cancelled, in grace period).
**Not to be confused with:** User — a Customer may have many Users (humans logging in on their behalf).
**Aliases (deprecated):** Client, Account holder.
-->

### EasySpotDL

**Definition:** A portable desktop app for macOS (Apple Silicon) and Windows 11 that sets up and updates the Engine for non-technical users and gives them a window to download a Public Playlist as MP3 files. EasySpotDL does not download music itself.
**Not to be confused with:** Engine.

### Public Playlist

**Definition:** A Spotify playlist that anyone with its link can open without signing in. It is the only input EasySpotDL accepts; private playlists and saved tracks are out of scope.

---

## System Terms

<!--
Architectural or technical concepts that are project-specific — not standard CS vocabulary. Alphabetical.

Example:

### Ingest Pipeline

**Definition:** The sequence of stages that pulls raw events from external sources, normalises them, and writes to the event store. Owned by the data platform team.
-->

### Engine

**Definition:** spotDL plus the tools it depends on (yt-dlp, ffmpeg, deno). EasySpotDL downloads it into the user's folder on first launch and updates it automatically on every launch. The Engine is what actually downloads the music.
**Not to be confused with:** EasySpotDL.

### Release Channel

**Definition:** The public location on GitHub where new EasySpotDL versions are published and which EasySpotDL checks on launch. It covers EasySpotDL only, never the Engine.

### Version Notice

**Definition:** The message EasySpotDL shows on launch when the Release Channel has a newer version, with a link to download it. EasySpotDL never replaces itself; the user updates it manually.

---

## Deprecated

<!--
Terms that used to be in the glossary but were retired. One line each.

Example:

- ~~Client~~ — replaced by [Customer](#customer) on 2026-01-15.
-->

- ~~easySpotDL~~ — renamed to [EasySpotDL](#easyspotdl) (casing aligned with the repository name) on 2026-10-15.
