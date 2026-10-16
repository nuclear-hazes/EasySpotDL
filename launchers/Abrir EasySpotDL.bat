@echo off
rem EasySpotDL launcher for Windows: double-click to start the app.
chcp 65001 >nul
cd /d "%~dp0"
set "ROOT=%CD%"
rem Unzipped layout has app\ next to this file; in the repo it sits one level up.
if not exist "%ROOT%\app" for %%I in ("%ROOT%\..") do set "ROOT=%%~fI"

rem Python, the app environment and uv's cache live in the data folder (must match config.py).
set "DATA=%LOCALAPPDATA%\EasySpotDL"
set "UV_PYTHON_INSTALL_DIR=%DATA%\python"
set "UV_CACHE_DIR=%DATA%\cache"
set "UV_PROJECT_ENVIRONMENT=%DATA%\app-env"
set "UV_PYTHON_PREFERENCE=only-managed"

set "UV_EXE=%ROOT%\uv.exe"
if not exist "%UV_EXE%" set "UV_EXE=uv"

echo EasySpotDL está abierto. No cierres esta ventana mientras lo uses.
"%UV_EXE%" run --frozen --no-dev --directory "%ROOT%\app" python -m easyspotdl
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  rem uv could not even build the app environment: on a first launch that means no internet.
  if not exist "%UV_PROJECT_ENVIRONMENT%" echo EasySpotDL necesita internet la primera vez. Conectate y volvé a abrirlo.
  pause
)
exit /b %RC%
