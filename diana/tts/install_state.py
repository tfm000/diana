"""Cheap install-state + footprint probes — NO heavy SDK import (ENGINE-01).

ENGINE-01 forbids importing onnxruntime/piper just to render a badge, so install
state is a pure filesystem probe of ``paths.model_dir()`` — the same "resolve a
capability without pulling the engine SDK" lane as ``registry.engine_is_ascii_only``.

A Piper voice is installed iff its ``{id}.onnx`` exists in ``model_dir`` (matches
``piper_engine._resolve_model_path``). Kokoro is an engine-level "model installed?"
probe (one model, many baked-in voices — D-19): an ``.onnx`` variant AND
``voices-v1.0.bin``. Footprint of an installed voice is its on-disk ``.onnx`` size;
0 when absent (the catalog manifest ``size_bytes`` is the not-installed estimate,
resolved by the caller from the catalog, not here — this module stays import-light).

Heavy engines (Orpheus / F5 / Fish — Phase 5) extend the SAME contract: their
install state is a pure filesystem probe of the per-engine venv under
``paths.venvs_dir()`` plus a ``.{engine}.installed`` marker. Orpheus has its own
torch-free venv; F5 + Fish share the ``torch`` venv (D-03), so uninstalling one of
the shared pair removes only its marker (and the venv tree only once nothing else
still uses it). NOTHING here imports torch/llama-cpp/orpheus_cpp/f5_tts (ENGINE-01).
"""

import shutil
import sys

from diana import paths

# The Kokoro model filenames (match config.py / RESEARCH Pattern 4). Any one onnx
# variant plus the shared voices bin counts as installed.
_KOKORO_ONNX_VARIANTS = ("kokoro-v1.0.onnx", "kokoro-v1.0.fp16.onnx", "kokoro-v1.0.int8.onnx")
_KOKORO_VOICES_BIN = "voices-v1.0.bin"


def piper_voice_installed(voice_id: str) -> bool:
    """True iff ``{voice_id}.onnx`` exists in ``model_dir`` (cheap filesystem probe)."""
    return (paths.model_dir() / f"{voice_id}.onnx").exists()


def list_installed_piper_voice_ids() -> list[str]:
    """Bare ids of every installed Piper voice — a cheap ``*.onnx`` glob (ENGINE-01).

    Globs ``{id}.onnx`` in ``model_dir`` (the same lane as ``piper_voice_installed``)
    and returns the filename stems, EXCLUDING the Kokoro model variants
    (``_KOKORO_ONNX_VARIANTS``) — Kokoro is one model with baked-in voices (D-19),
    never a Piper voice file. Result is sorted for stable enumeration. Pure
    filesystem probe: NO onnxruntime/piper import (ENGINE-01). Returns ``[]`` when
    the model dir does not exist yet (fresh install).
    """
    md = paths.model_dir()
    if not md.exists():
        return []
    ids = [
        f.stem for f in md.glob("*.onnx")
        if f.name not in _KOKORO_ONNX_VARIANTS
    ]
    return sorted(ids)


def piper_footprint_bytes(voice_id: str) -> int:
    """On-disk ``.onnx`` size if the voice is installed, else 0 (ENGINE-03/D-11).

    Not-installed footprint estimates come from the catalog manifest ``size_bytes``
    at the call site (``catalog.voice_footprint_bytes``) — this probe stays a cheap
    filesystem read and never reaches for the manifest or an engine SDK.
    """
    f = paths.model_dir() / f"{voice_id}.onnx"
    return f.stat().st_size if f.exists() else 0


def kokoro_model_installed() -> bool:
    """True iff a Kokoro onnx variant AND ``voices-v1.0.bin`` are present (D-19)."""
    md = paths.model_dir()
    onnx = any((md / n).exists() for n in _KOKORO_ONNX_VARIANTS)
    return onnx and (md / _KOKORO_VOICES_BIN).exists()


def voice_in_use(db_path: str, engine: str, voice_id: str) -> str | None:
    """Human reason a voice may NOT be uninstalled, else ``None`` (D-17/VOICE-07).

    The up-front protective block on top of the Phase-3 selection-time backstop
    (``registry.resolve_default_voice``): refuse to delete a voice that something
    still needs, and tell the user WHAT needs it so they can switch first. A voice is
    in use when EITHER

      (a) it is the ``tts_voice`` of any NON-TERMINAL job — a pending/in-flight job
          (anything whose status is not the terminal ``COMPLETED``/``FAILED``) still
          needs its voice file when the worker reaches it; or
      (b) it is the stored ``tts.default_voice.<engine>`` per-engine default — the
          remembered choice both pages preselect.

    Returns a short reason string (truthy) when blocked, ``None`` when free to remove.
    A terminal job's voice (a finished/failed conversion) does NOT block — its audio
    is already produced. Cheap-probe lane (DB read only — NO engine SDK import,
    ENGINE-01); ``database`` is imported lazily inside the function so this module
    stays import-light.
    """
    from diana.database import get_setting, list_jobs
    from diana.models import JobStatus

    terminal = {JobStatus.COMPLETED, JobStatus.FAILED}
    for job in list_jobs(db_path):
        if job.tts_voice == voice_id and job.status not in terminal:
            return "in use by a pending or in-progress job"
    if get_setting(db_path, f"tts.default_voice.{engine}", None) == voice_id:
        return f"set as the {engine} default voice"
    return None


def uninstall_piper_voice(voice_id: str) -> int:
    """Delete an installed Piper voice's files from the cache; return freed bytes (D-16).

    Removes ``{voice_id}.onnx`` and its sibling ``{voice_id}.onnx.json`` from
    ``paths.model_dir()`` and returns the total bytes freed (so the UI can show the
    reclaimed space before/after the confirm — D-16). Scoped to ``model_dir()`` ONLY:
    the destinations are basename-joined Paths under the per-user cache, never a
    user-supplied absolute path (T-04-FILE), and each unlink uses
    ``missing_ok=True`` — mirroring the ``database.delete_job`` cleanup idiom. Pure
    filesystem op: NO onnxruntime/piper import (ENGINE-01).
    """
    md = paths.model_dir()
    freed = 0
    for name in (f"{voice_id}.onnx", f"{voice_id}.onnx.json"):
        target = md / name
        if target.exists():
            freed += target.stat().st_size
        target.unlink(missing_ok=True)
    return freed


# --- Heavy-engine install-state probes (Phase 5 — filesystem only, NO heavy SDK) --

def _is_win() -> bool:
    """True on Windows (venv python is ``Scripts/python.exe`` vs ``bin/python``)."""
    return sys.platform == "win32"


def _heavy_venv_name(engine: str) -> str:
    """Map a heavy engine to its venv folder name (D-03 shared-torch).

    Orpheus is torch-free in its own ``orpheus`` venv; F5 and Fish share the
    ``torch`` venv (F5 installs torch, Fish reuses it). Unknown engines default to
    ``torch`` — the conservative shared home.
    """
    return "orpheus" if engine == "orpheus" else "torch"


def _heavy_venv_python(engine: str):
    """The venv interpreter path for a heavy engine (per OS)."""
    venv = paths.venvs_dir() / _heavy_venv_name(engine)
    return venv / ("Scripts/python.exe" if _is_win() else "bin/python")


def heavy_engine_installed(engine: str) -> bool:
    """True iff the engine's venv python AND ``.{engine}.installed`` marker exist.

    Pure filesystem probe (RESEARCH install-state example): the venv interpreter
    (``venvs_dir()/<venv>/<bin/python>``) confirms the deps were provisioned, and
    the per-engine ``venvs_dir()/.{engine}.installed`` marker (written at the END of
    a successful install) confirms BOTH deps and weights finished — so a half-done or
    shared-venv-but-not-this-engine state reads as not installed. NO torch/llama-cpp/
    orpheus_cpp/f5_tts import (ENGINE-01 / D-17).
    """
    py = _heavy_venv_python(engine)
    marker = paths.venvs_dir() / f".{engine}.installed"
    return py.exists() and marker.exists()


def _dir_size_bytes(path) -> int:
    """Total on-disk size of a directory tree (0 if absent). Pure filesystem walk."""
    if not path.exists():
        return 0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


def heavy_footprint_bytes(engine: str) -> int:
    """On-disk size of a heavy engine's venv tree, else 0 (ENGINE-03/D-04).

    Sums the per-engine venv directory (deps + any co-located weight/library files)
    so the UI can show reclaimable space before/after an uninstall (D-04). 0 when the
    venv does not exist (not installed). Pure filesystem walk: NO heavy SDK import.
    The HF weight cache (``hf_cache_dir()``) is shared across engines, so it is NOT
    summed here — the venv footprint is the per-engine reclaimable figure.
    """
    venv = paths.venvs_dir() / _heavy_venv_name(engine)
    return _dir_size_bytes(venv)


def uninstall_heavy_engine(engine: str) -> int:
    """Remove a heavy engine's install; return freed bytes (D-16, scoped to venvs_dir).

    Always removes the ``.{engine}.installed`` marker. The venv directory itself is
    ``shutil.rmtree``'d ONLY when no OTHER engine still shares it — so removing F5
    while Fish remains installed deletes the ``.f5.installed`` marker but KEEPS the
    shared ``torch`` venv (and vice-versa); removing the last engine that uses a venv
    deletes the tree. Orpheus owns its venv alone, so it is always removed.

    Scoped to ``paths.venvs_dir()`` ONLY (the marker + the venv subfolder are
    basename-joined Paths under the per-user dir, never a user-supplied path —
    T-05-EXE), with marker-then-venv ordering. Returns the bytes freed (the venv tree
    size when removed, else 0). Pure filesystem op: NO heavy SDK import.
    """
    venvs = paths.venvs_dir()
    marker = venvs / f".{engine}.installed"
    marker.unlink(missing_ok=True)

    venv_name = _heavy_venv_name(engine)
    venv = venvs / venv_name

    # Does any OTHER engine still share this venv (its marker survives)?
    shared_by_other = any(
        other != engine
        and _heavy_venv_name(other) == venv_name
        and (venvs / f".{other}.installed").exists()
        for other in ("orpheus", "f5", "fish")
    )
    freed = 0
    if venv.exists() and not shared_by_other:
        freed = _dir_size_bytes(venv)
        shutil.rmtree(venv, ignore_errors=True)
    return freed
