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
"""

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
