"""The shared dashboard voice-enumeration cache (04-03 Bug A).

Bug A: the Upload picker and Settings Default-Voice picker each wrapped
``get_engine_voices`` in their OWN ``@st.cache_data`` function, so installing a
Piper voice (which writes ``{id}.onnx`` to ``model_dir()``) never invalidated either
cache — the new voice only appeared after an app RESTART. The fix moves enumeration
into ONE shared ``diana.dashboard.voice_cache.cached_voices`` and exposes
``clear_voice_cache()`` so the install-DONE transition drops that single cache and
the voice shows up in BOTH pickers without a restart.

These tests assert the shared seam exists and clears. The picker REFRESH itself is
Streamlit-runtime behavior (manual UAT); here we verify the cached function is one
shared object with a working ``.clear()`` and that ``clear_voice_cache`` invokes it.
``cached_voices`` runs cleanly under pytest (``st.cache_data`` degrades to an
in-memory store with no ScriptRunContext), so no Streamlit runtime stub is needed.
"""

from diana.dashboard import voice_cache


def test_cached_voices_is_shared_and_clearable():
    """The module exposes ONE cached enumerator with a working clear() surface."""
    assert callable(voice_cache.cached_voices)
    assert hasattr(voice_cache.cached_voices, "clear"), (
        "cached_voices must be an @st.cache_data function (one shared cache to clear)"
    )


def test_clear_voice_cache_calls_underlying_clear(monkeypatch):
    """``clear_voice_cache()`` drops the shared cache (delegates to cached_voices.clear)."""
    calls = []
    monkeypatch.setattr(voice_cache.cached_voices, "clear", lambda: calls.append(1))

    voice_cache.clear_voice_cache()

    assert calls == [1], "clear_voice_cache must clear the one shared voice cache"


def test_cached_voices_enumerates_via_registry(monkeypatch):
    """The shared function delegates to registry.get_engine_voices (keyed by engine)."""
    from diana.tts.base import TTSVoice

    sentinel = [TTSVoice("x", "X", "en-us", "male")]
    seen = {}

    def _fake(engine_name, config=None):
        seen["engine"] = engine_name
        return sentinel

    monkeypatch.setattr(voice_cache, "get_engine_voices", _fake)
    # Clear first so this call is not served from a prior cached result.
    voice_cache.cached_voices.clear()

    result = voice_cache.cached_voices("piper")

    assert result == sentinel
    assert seen["engine"] == "piper"
