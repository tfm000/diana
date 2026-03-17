@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

set MODELS_DIR=data\models
set VENV_DIR=.venv

echo.
echo === Diana Setup ===
echo.

:: ── 1. Python ──────────────────────────────────────────
set PYTHON=
for %%P in (python3 python) do (
    where %%P >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%V in ('%%P -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2^>nul') do set PYVER=%%V
        for /f %%M in ('%%P -c "import sys; print(sys.version_info.major)" 2^>nul') do set PYMAJOR=%%M
        for /f %%N in ('%%P -c "import sys; print(sys.version_info.minor)" 2^>nul') do set PYMINOR=%%N
        if !PYMAJOR! geq 3 if !PYMINOR! geq 10 (
            set PYTHON=%%P
            goto :found_python
        )
    )
)
echo [X] Python 3.10+ is required but not found. Install from https://python.org
exit /b 1

:found_python
echo [OK] Found %PYTHON% (%PYVER%)

:: ── 2. ffmpeg ──────────────────────────────────────────
where ffmpeg >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] ffmpeg found
) else (
    echo [!] ffmpeg not found — required for MP3 encoding
    echo     Install with: choco install ffmpeg
    echo     Continuing setup without it...
    echo.
)

:: ── 3. Virtual environment ─────────────────────────────
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Creating virtual environment...
    %PYTHON% -m venv %VENV_DIR%
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

call %VENV_DIR%\Scripts\activate.bat

:: ── 4. Dependencies ────────────────────────────────────
echo Installing dependencies...
pip install -q -r requirements.txt
echo [OK] Dependencies installed

:: ── 5. Model downloads ────────────────────────────────
if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%"

echo.
echo --- Kokoro models (~340 MB) ---

if exist "%MODELS_DIR%\kokoro-v1.0.onnx" (
    echo [OK] kokoro-v1.0.onnx already downloaded
) else (
    echo Downloading kokoro-v1.0.onnx...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx' -OutFile '%MODELS_DIR%\kokoro-v1.0.onnx'"
    echo [OK] kokoro-v1.0.onnx downloaded
)

if exist "%MODELS_DIR%\voices-v1.0.bin" (
    echo [OK] voices-v1.0.bin already downloaded
) else (
    echo Downloading voices-v1.0.bin...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin' -OutFile '%MODELS_DIR%\voices-v1.0.bin'"
    echo [OK] voices-v1.0.bin downloaded
)

echo.
echo --- Piper models (~60 MB) ---

if exist "%MODELS_DIR%\en_US-lessac-medium.onnx" (
    echo [OK] en_US-lessac-medium.onnx already downloaded
) else (
    echo Downloading en_US-lessac-medium.onnx...
    powershell -Command "Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx' -OutFile '%MODELS_DIR%\en_US-lessac-medium.onnx'"
    echo [OK] en_US-lessac-medium.onnx downloaded
)

if exist "%MODELS_DIR%\en_US-lessac-medium.onnx.json" (
    echo [OK] en_US-lessac-medium.onnx.json already downloaded
) else (
    echo Downloading en_US-lessac-medium.onnx.json...
    powershell -Command "Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json' -OutFile '%MODELS_DIR%\en_US-lessac-medium.onnx.json'"
    echo [OK] en_US-lessac-medium.onnx.json downloaded
)

:: ── 6. Config ──────────────────────────────────────────
if not exist "config.yaml" (
    copy config.example.yaml config.yaml >nul
    echo [OK] config.yaml created from example
) else (
    echo [OK] config.yaml already exists
)

:: ── 7. Desktop launcher ───────────────────────────────
(
echo @echo off
echo cd /d "%%~dp0"
echo call .venv\Scripts\activate.bat
echo python run.py
) > Diana.bat
echo [OK] Created Diana.bat (double-click to launch)

echo.
echo === Setup complete! ===
echo.
echo To start Diana:
echo   * Double-click Diana.bat, or
echo   * Run: .venv\Scripts\activate ^&^& python run.py
echo.
pause
