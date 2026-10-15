# Workflows: EasySpotDL

## Launcher por plataforma [cap-001, flow-01]

```mermaid
flowchart TD
    A[Launcher] --> B[cd a la carpeta del launcher]
    B --> C{macOS}
    C -- sí --> D["xattr -dr com.apple.quarantine ."]
    C -- no --> E["chcp 65001"]
    D --> F
    E --> F["Exportar UV_* hacia la carpeta de datos"]
    F --> G["uv run --python 3.12 --project app python -m easyspotdl"]
    G --> H["Mostrar 'No cierres esta ventana' + logs"]
```

## Instancia única y puerto [cap-001]

```mermaid
flowchart TD
    A[Inicio] --> B{Archivo de instancia en carpeta de datos con puerto P?}
    B -- sí --> C{"GET 127.0.0.1:P/health == EasySpotDL?"}
    C -- sí --> D[Abrir navegador en P y salir]
    C -- no --> E
    B -- no --> E{Puerto 8765 libre?}
    E -- sí --> F[Usar 8765]
    E -- no --> G[Usar puerto libre asignado por el SO]
    F --> H[Escribir archivo de instancia, levantar servidor, abrir navegador]
    G --> H
```

## Engine Setup / Update [cap-002, cap-003]

```mermaid
flowchart TD
    A[Arranque] --> B{spotdl instalado en UV_TOOL_DIR?}
    B -- no --> C{internet?}
    C -- no --> X["'EasySpotDL necesita internet la primera vez' → exit 1"]
    C -- sí --> D[uv tool install spotdl]
    D --> E[spotdl --download-deno y --download-ffmpeg si faltan]
    E --> OK[INFO Engine installed]
    B -- sí --> F["uv tool upgrade spotdl (timeout)"]
    F -- error/timeout --> W[WARNING Engine update skipped] --> G
    F -- ok --> G[Verificar deno y ffmpeg; descargar si faltan]
    G --> OK2[Continuar]
```

## Estados de una descarga [cap-004, cap-005]

```mermaid
stateDiagram-v2
    [*] --> idle
    idle --> running: POST /download (link válido)
    idle --> idle: link inválido (400)
    running --> running: POST /download (409)
    running --> finished: spotDL termina
    running --> failed: spotDL no arranca / sale con error sin progreso
    finished --> running: nueva descarga
    failed --> running: nueva descarga
```

## Version Notice [cap-007, flow-03]

```mermaid
flowchart TD
    A[Arranque] --> B["GET Release Channel (timeout 5 s)"]
    B -- error --> W[WARNING, version_notice = null]
    B -- ok --> C{"tag sin 'v' > VERSION (semver)?"}
    C -- sí --> N["version_notice = {version, html_url}"]
    C -- no --> Z[version_notice = null]
```

## Packaging y publicación [cap-008, cap-009]

```mermaid
sequenceDiagram
    actor A as Autor
    participant B as scripts/build.sh
    participant GH as GitHub (nuclear-hazes/EasySpotDL)
    A->>A: subir VERSION, commit, merge a main
    A->>B: ./scripts/build.sh
    B->>B: descargar uv pinneado (aarch64-apple-darwin, x86_64-pc-windows-msvc)
    B->>B: armar carpetas: launcher + uv + app/ + VERSION + LEEME.txt + .env(ENV=prod)
    B-->>A: dist/EasySpotDL-mac.zip, dist/EasySpotDL-win.zip
    A->>GH: crear Release vX.Y.Z y adjuntar zips (manual)
    Note over GH: Las apps instaladas ven el Version Notice al próximo arranque
```
