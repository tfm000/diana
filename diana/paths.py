"""Single per-user path resolver for Diana.

Every filesystem location the app uses (DB, config, uploads, chunks, output,
models, voices) derives from here via platformdirs, so no relative ``data/...``
literal re-anchors to the process CWD. macOS yields
``~/Library/Application Support/Diana``; Windows yields ``%LOCALAPPDATA%\\Diana``.
"""

from pathlib import Path

from platformdirs import PlatformDirs

# appauthor=False -> on Windows yields ...\Diana (NOT ...\Diana\Diana).
_dirs = PlatformDirs(appname="Diana", appauthor=False)


def data_dir() -> Path:
    return Path(_dirs.user_data_dir)


def config_dir() -> Path:
    return Path(_dirs.user_config_dir)


def db_path() -> Path:
    return data_dir() / "diana.db"


def upload_dir() -> Path:
    return data_dir() / "uploads"


def chunk_dir() -> Path:
    return data_dir() / "chunks"


def output_dir() -> Path:
    return data_dir() / "output"


def model_dir() -> Path:
    return data_dir() / "models"


def voices_dir() -> Path:
    return data_dir() / "voices"


def config_file() -> Path:
    return config_dir() / "config.yaml"


def ensure_dirs() -> None:
    """Create the full per-user directory tree if it does not exist."""
    for d in (data_dir(), upload_dir(), chunk_dir(), output_dir(),
              model_dir(), voices_dir(), config_dir()):
        d.mkdir(parents=True, exist_ok=True)
