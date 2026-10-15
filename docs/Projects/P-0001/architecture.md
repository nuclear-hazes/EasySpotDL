# Architecture: EasySpotDL

## Componentes

Nombres sugeridos de módulos en `app/easyspotdl/`.

```mermaid
flowchart LR
    subgraph ZIP["Zip distribuido"]
        L["launcher<br/>Abrir EasySpotDL.command / .bat"]
        UV["uv / uv.exe"]
        subgraph APP["app/easyspotdl"]
            M["__main__.py<br/>arranque, instancia única, navegador"]
            CFG["config.py<br/>ENV, rutas, VERSION"]
            ENG["engine.py<br/>instalar/actualizar Engine"]
            DL["download.py<br/>validar link, subproceso spotDL, progreso"]
            RC["release_channel.py<br/>consulta + comparación de versión"]
            SRV["server.py<br/>FastAPI: / /status /download /open-folder"]
            UI["static/index.html<br/>página única, JS vanilla"]
        end
    end
    L --> UV --> M
    M --> CFG
    M --> ENG
    M --> RC
    M --> SRV
    SRV --> DL
    SRV --> UI
```

## Topología en la máquina del usuario

```mermaid
flowchart TB
    subgraph PC["Mac / PC del usuario"]
        Z["Carpeta descomprimida del zip"]
        D["Carpeta de datos<br/>mac: ~/Library/Application Support/EasySpotDL<br/>win: %LOCALAPPDATA%\\EasySpotDL<br/>(Python, env de la app, caché uv, Engine)"]
        S["~/.spotdl<br/>(deno, ffmpeg, config de spotDL)"]
        MU["~/Music/EasySpotDL/&lt;playlist&gt;/*.mp3"]
        B["Navegador → http://127.0.0.1:&lt;puerto&gt;"]
        T["Terminal / consola visible<br/>logs + 'No cierres esta ventana'"]
    end
    Z -->|uv instala| D
    D -->|spotdl --download-*| S
    D -->|spotdl download| MU
    B <--> D
    T --- D
```

## Sistemas externos

```mermaid
flowchart LR
    APP["EasySpotDL"] -->|"releases/latest (sin auth)"| GH["GitHub API<br/>nuclear-hazes/EasySpotDL"]
    APP -->|"uv: Python, paquetes"| PYPI["python-build-standalone / PyPI"]
    ENGINE["Engine (spotDL)"] -->|"metadatos de Public Playlist (sin credenciales)"| SP["Spotify"]
    ENGINE -->|"búsqueda + audio vía yt-dlp"| YT["YouTube / YouTube Music"]
    ENGINE -->|"--download-deno / --download-ffmpeg"| BIN["Binarios deno / ffmpeg"]
    APP --> ENGINE
```

## Flujo de datos de una descarga

```mermaid
flowchart LR
    URL["Link pegado"] --> V["download.py: validar + limpiar query"]
    V --> SUB["subproceso spotdl"]
    SUB -->|stdout| PARSE["parsing tolerante → done/total/current"]
    SUB -->|"--save-errors"| ERR["archivo de errores temporal"]
    PARSE --> ST["estado en memoria (DownloadJob)"]
    ERR --> ST
    ST -->|"GET /status"| UI["página"]
    SUB --> MP3["~/Music/EasySpotDL/&lt;playlist&gt;/"]
```

## Estructura del repositorio

```
launchers/        Abrir EasySpotDL.command, Abrir EasySpotDL.bat
app/              pyproject.toml, easyspotdl/ (módulos de arriba), tests/
scripts/build.sh  genera dist/EasySpotDL-{mac,win}.zip (descarga uv pinneado por plataforma)
docs/user/        LEEME.txt
VERSION           versión de EasySpotDL (semver)
```
