# Data Model: EasySpotDL

Sin base de datos. Todo el estado vive en memoria mientras la app corre, salvo el archivo de instancia (puerto) en la carpeta de datos. Los MP3 son la única salida persistente.

```mermaid
classDiagram
    class AppConfig {
        +str env  "dev | prod"
        +str version  "de VERSION"
        +Path data_dir
        +Path music_dir  "~/Music/EasySpotDL"
        +str release_channel_url
        +int preferred_port  "8765"
        +str log_level
    }
    class EngineStatus {
        +bool installed
        +str spotdl_version
        +bool updated_this_launch
        +str error  "nullable"
    }
    class DownloadJob {
        +str playlist_url  "sin query string"
        +str playlist_name  "nullable hasta que spotDL lo informe"
        +str state  "idle | running | finished | failed"
        +int total
        +int done
        +str current_song  "nullable"
        +int downloaded
        +int skipped
        +list~str~ failed  "Artista - Título o link"
        +Path output_dir
    }
    class VersionNotice {
        +str version
        +str html_url
    }
    class InstanceFile {
        +int port
        +int pid
    }
    AppConfig "1" --> "1" EngineStatus
    AppConfig "1" --> "0..1" VersionNotice
    AppConfig "1" --> "0..1" DownloadJob : última descarga
    AppConfig "1" --> "0..1" InstanceFile
```

## Contrato `GET /status`

```json
{
  "app_version": "0.1.0",
  "engine": {"installed": true, "spotdl_version": "4.5.2"},
  "version_notice": {"version": "0.2.0", "html_url": "https://github.com/nuclear-hazes/EasySpotDL/releases/tag/v0.2.0"},
  "job": {
    "state": "running", "playlist_name": "Chill Mix", "total": 50, "done": 12,
    "current_song": "Coldplay - Yellow", "downloaded": 12, "skipped": 0, "failed": []
  }
}
```

`version_notice` y `job` pueden ser `null`.
