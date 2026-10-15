# MEMORY.md

## Index

- **[2026-10-15] spotdl-needs-deno:** Without deno, spotDL 4.5.2 failed 12/50 songs with "YT-DLP download error"; with deno (`spotdl --download-deno`) 49/50 succeeded.
- **[2026-10-15] spotdl-disable-lyrics:** spotDL's default lyrics lookup hits HTTP 429 and makes runs crawl; pass `--lyrics` with no providers to disable it.
- **[2026-10-15] spotdl-web-ui-broken:** `spotdl web` (4.5.2) rejects playlist URLs with "Invalid URL" (upstream issue #2790); don't rely on it.
- **[2026-10-15] spotdl-isolated-install:** Isolated spike setup: standalone uv + `UV_*` dirs + `HOME=<dir>` keeps Python, spotDL and `~/.spotdl` out of the user's system.

