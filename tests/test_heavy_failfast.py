"""Wave-0 RED/skip scaffold for heavy-engine fail-fast (Plan 04, success criterion #4).

D-16: choosing an uninstalled heavy engine must be refused UP FRONT with an
actionable prompt ("Install it in Settings ▸ Voices") — never erroring mid-job.
``registry.heavy_engine_failfast(engine)`` is that pre-flight check: it returns an
actionable string when a heavy engine is selected but not installed, and ``None``
when the engine is installed OR is a non-heavy engine (native_os/kokoro/piper).
These tests monkeypatch ``heavy_engine_installed`` and assert:

  - uninstalled heavy engine -> a non-empty string naming "Settings ▸ Voices";
  - installed heavy engine    -> ``None``;
  - non-heavy engine          -> ``None`` regardless of the probe.

``heavy_engine_failfast`` lands in Wave 2 (module home ``diana.tts.registry``);
collection stays GREEN until then.
"""

import pytest

from diana.tts import registry

_failfast = getattr(registry, "heavy_engine_failfast", None)
_FAILFAST_AVAILABLE = _failfast is not None


def _force_heavy_installed(monkeypatch, value):
    """Force ``heavy_engine_installed`` -> ``value`` at the source + registry binding."""
    import diana.tts.install_state as _ist

    monkeypatch.setattr(_ist, "heavy_engine_installed",
                        lambda *a, **k: value, raising=False)
    if hasattr(registry, "heavy_engine_installed"):
        monkeypatch.setattr(registry, "heavy_engine_installed",
                            lambda *a, **k: value, raising=False)


# --- D-16: refuse an uninstalled heavy engine with an actionable prompt ------
@pytest.mark.skipif(
    not _FAILFAST_AVAILABLE, reason="heavy_engine_failfast lands in Wave 2"
)
def test_failfast_refuses_uninstalled_heavy_engine(monkeypatch):
    """An uninstalled heavy engine yields an actionable Settings ▸ Voices prompt."""
    _force_heavy_installed(monkeypatch, False)
    msg = _failfast("orpheus")
    assert isinstance(msg, str) and msg
    assert "Settings" in msg and "Voices" in msg


# --- D-16: an installed heavy engine is allowed (no refusal) ----------------
@pytest.mark.skipif(
    not _FAILFAST_AVAILABLE, reason="heavy_engine_failfast lands in Wave 2"
)
def test_failfast_allows_installed_heavy_engine(monkeypatch):
    """An installed heavy engine returns None (the job may start)."""
    _force_heavy_installed(monkeypatch, True)
    assert _failfast("orpheus") is None


# --- D-16: non-heavy engines are never heavy-gated --------------------------
@pytest.mark.skipif(
    not _FAILFAST_AVAILABLE, reason="heavy_engine_failfast lands in Wave 2"
)
def test_failfast_ignores_non_heavy_engines(monkeypatch):
    """native_os/kokoro/piper always return None, even with the probe forced False."""
    _force_heavy_installed(monkeypatch, False)
    for engine in ("native_os", "kokoro", "piper"):
        assert _failfast(engine) is None
