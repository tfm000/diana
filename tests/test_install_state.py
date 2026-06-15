"""Wave-0 RED/skip scaffolds for cheap install-state detection (Plan 02).

ENGINE-01 forbids importing onnxruntime/piper just to render a badge, so install
state is a pure filesystem probe of ``paths.model_dir()`` — mirroring Diana's
existing ``engine_is_ascii_only`` "no engine import" lane (RESEARCH Pattern 4).

The probe symbols (``piper_voice_installed`` / ``kokoro_model_installed`` /
``piper_footprint_bytes``) land in Plan 02; their module home is the
implementer's choice (a new ``diana.tts.install_state`` OR folded into
``diana.tts.registry``), so each is probed in both homes. Collection stays GREEN
until they land, then these flip to live gates with zero edits.

Every test monkeypatches ``diana.paths.model_dir`` to ``tmp_path`` and touches
fake model files there — the real per-user cache is never read or written
(threat T-04-01). ENGINE-01, D-11.
"""

import pytest

# --- Guarded probes: install-state helpers land in Plan 02 ------------------
_piper_installed = None
for _modname, _attr in (
    ("diana.tts.install_state", "piper_voice_installed"),
    ("diana.tts.registry", "piper_voice_installed"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _piper_installed = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue
_PIPER_PROBE_AVAILABLE = _piper_installed is not None

_kokoro_installed = None
for _modname, _attr in (
    ("diana.tts.install_state", "kokoro_model_installed"),
    ("diana.tts.registry", "kokoro_model_installed"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _kokoro_installed = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue
_KOKORO_PROBE_AVAILABLE = _kokoro_installed is not None

_piper_footprint = None
for _modname, _attr in (
    ("diana.tts.install_state", "piper_footprint_bytes"),
    ("diana.tts.registry", "piper_footprint_bytes"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _piper_footprint = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue
_FOOTPRINT_AVAILABLE = _piper_footprint is not None


# --- ENGINE-01: Piper voice install probe (filesystem only) -----------------
@pytest.mark.skipif(
    not _PIPER_PROBE_AVAILABLE,
    reason="piper_voice_installed implemented in Plan 02",
)
def test_piper_voice_installed(tmp_path, monkeypatch):
    """A voice is 'installed' iff its ``{id}.onnx`` exists in ``model_dir``."""
    monkeypatch.setattr("diana.paths.model_dir", lambda: tmp_path)

    assert _piper_installed("en_US-amy-medium") is False  # nothing on disk yet
    (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"fake-onnx")
    assert _piper_installed("en_US-amy-medium") is True
    # An unrelated id stays uninstalled.
    assert _piper_installed("en_GB-alan-medium") is False


# --- ENGINE-01: Kokoro is an engine-level "model installed?" probe (D-19) ----
@pytest.mark.skipif(
    not _KOKORO_PROBE_AVAILABLE,
    reason="kokoro_model_installed implemented in Plan 02",
)
def test_kokoro_model_installed(tmp_path, monkeypatch):
    """Kokoro needs BOTH an onnx variant AND ``voices-v1.0.bin`` present."""
    monkeypatch.setattr("diana.paths.model_dir", lambda: tmp_path)

    assert _kokoro_installed() is False  # neither file present
    (tmp_path / "kokoro-v1.0.onnx").write_bytes(b"fake-model")
    assert _kokoro_installed() is False, "onnx alone is not enough"
    (tmp_path / "voices-v1.0.bin").write_bytes(b"fake-voices")
    assert _kokoro_installed() is True, "onnx + voices.bin -> installed"


# --- ENGINE-03 / D-11: footprint of an installed voice -----------------------
@pytest.mark.skipif(
    not _FOOTPRINT_AVAILABLE,
    reason="piper_footprint_bytes implemented in Plan 02",
)
def test_piper_footprint(tmp_path, monkeypatch):
    """Footprint reflects the on-disk ``.onnx`` size; 0 when not installed."""
    monkeypatch.setattr("diana.paths.model_dir", lambda: tmp_path)

    assert _piper_footprint("en_US-amy-medium") == 0  # not installed
    payload = b"x" * 1234
    (tmp_path / "en_US-amy-medium.onnx").write_bytes(payload)
    assert _piper_footprint("en_US-amy-medium") == len(payload)
