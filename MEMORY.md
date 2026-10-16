# MEMORY.md

## Index

- **[2026-10-15] spotdl-needs-deno:** Without deno, spotDL 4.5.2 failed 12/50 songs with "YT-DLP download error"; with deno (`spotdl --download-deno`) 49/50 succeeded.
- **[2026-10-15] spotdl-disable-lyrics:** spotDL's default lyrics lookup hits HTTP 429 and makes runs crawl; pass `--lyrics` with no providers to disable it.
- **[2026-10-15] spotdl-web-ui-broken:** `spotdl web` (4.5.2) rejects playlist URLs with "Invalid URL" (upstream issue #2790); don't rely on it.
- **[2026-10-16] spotdl-output-parsing:** Under a pipe spotDL (rich) wraps lines at 80 columns; run it with `COLUMNS=1000 PYTHONUNBUFFERED=1`. `--save-errors` appends `<track url> - <Error>: <msg>` lines; `--save-file x.spotdl` writes a JSON list with `url`, `artist`, `name`.
- **[2026-10-16] spotdl-retry-pass:** A first pass over a 50-song playlist got only 32/50 (YouTube drops songs under parallel load); a second pass (skips existing files) reached 46/50; another run got 43/50 after 2 passes and 46 after more. EasySpotDL retries up to 2 times automatically.
- **[2026-10-16] spotdl-download-prompts:** `spotdl --download-ffmpeg` / `--download-deno` ask for confirmation (and crash with EOFError without a terminal) if the tool is in `~/.spotdl` **or on PATH** (e.g. Homebrew ffmpeg); check both first.
- **[2026-10-16] uv-gatekeeper:** The macOS `uv` binary is Developer ID signed, so it runs even when quarantined; only the unsigned `.command` needs one approval, and Python downloaded by uv carries no quarantine.
- **[2026-10-15] spotdl-isolated-install:** Isolated spike setup: standalone uv + `UV_*` dirs + `HOME=<dir>` keeps Python, spotDL and `~/.spotdl` out of the user's system.

