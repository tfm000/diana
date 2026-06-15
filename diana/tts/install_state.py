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
