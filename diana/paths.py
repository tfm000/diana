"""Single per-user path resolver for Diana.

Every filesystem location the app uses (DB, config, uploads, chunks, output,
models, voices) derives from here via platformdirs, so no relative ``data/...``
literal re-anchors to the process CWD. macOS yields
``~/Library/Application Support/Diana``; Windows yields ``%LOCALAPPDATA%\\Diana``.
"""

import sys
from importlib import resources
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


def venvs_dir() -> Path:
    """Per-user home for the isolated heavy-engine venvs (Phase 5, D-05).

    Each heavy engine family installs its Python deps into a subfolder here
    (``orpheus`` torch-free; ``torch`` shared by F5+Fish — D-03), never the
    global/system environment. The ``.{engine}.installed`` success markers live
    directly under this dir (``install_state.heavy_engine_installed`` probes them).
    """
    return data_dir() / "venvs"


def hf_cache_dir() -> Path:
    """Per-user Hugging Face cache for heavy-engine weights (Phase 5, ENGINE-04).

    Set as ``HF_HOME`` in the install/synth subprocess env so weights land here
    (not ``~/.cache/huggingface``) — keeping all heavy assets under the per-user
    data dir so uninstall can find and reclaim them (Pitfall 8 / D-07).
    """
    return data_dir() / "hf-cache"


def custom_voices_dir() -> Path:
    """Per-user library of saved reference-audio clips + transcripts (Phase 5, D-14).

    Home for the engine-agnostic Custom Voices section (F5 cloning now, reusable
    by future cloning-capable models — D-11). Clip/transcript files land here
    (basename + extension allow-list + containment, V12) and are removable like
    any other voice.
    """
    return data_dir() / "custom_voices"


def uv_binary() -> Path:
    """Resolve the bundled ``uv`` provisioner binary (a SHIPPED package resource).

    The standalone ``uv`` executable that creates the heavy venvs + pip-installs
    deps with no system Python (RESEARCH Pattern 1). It is bundled CODE/DATA under
    ``diana/data/bin/`` (Phase 6 drops the real per-OS binary there), NOT a per-user
    dir — so it is resolved from the installed package, never created at runtime,
    and never added to ``ensure_dirs()``. Dev falls back to ``uv`` on PATH inside
    the installer when this path does not exist yet.
    """
    name = "uv.exe" if sys.platform == "win32" else "uv"
    return Path(resources.files("diana.data").joinpath("bin", name))


def heavy_worker(name: str) -> Path:
    """Resolve a heavy-engine worker script (a SHIPPED package resource).

    The tiny per-engine worker scripts (``orpheus_worker.py`` / ``f5_worker.py`` /
    ``fish_worker.py``) run OUT OF PROCESS under the venv's own Python, so they are
    bundled CODE under ``diana/tts/heavy_workers/`` (package-data, NOT frozen-imported
    by the app interpreter — D-17). Resolved from the installed package, never a
    per-user dir, so NOT added to ``ensure_dirs()``.
    """
    return Path(resources.files("diana.tts").joinpath("heavy_workers", name))


def config_file() -> Path:
    return config_dir() / "config.yaml"


def ensure_dirs() -> None:
    """Create the full per-user directory tree if it does not exist."""
    for d in (data_dir(), upload_dir(), chunk_dir(), output_dir(),
              model_dir(), voices_dir(), venvs_dir(), hf_cache_dir(),
              custom_voices_dir(), config_dir()):
        d.mkdir(parents=True, exist_ok=True)
