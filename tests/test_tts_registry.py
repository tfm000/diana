"""Tests for diana.tts.registry after cloud-TTS removal (RETIRE-01).

Local-only enumeration (kokoro + piper), removed-engine ValueError, and the
pure stale-engine fallback helper. No model files or network needed.
"""

import sys
from unittest.mock import MagicMock

import pytest

from diana.tts.registry import (
    create_engine,
    engine_is_ascii_only,
    list_engines,
    resolve_engine_name,
)


class TestEngineIsAsciiOnly:
    """Static engine character-capability map (no heavy import)."""

    def test_kokoro_is_ascii_only(self):
        # Kokoro's ONNX tokenizer requires pure ASCII.
        assert engine_is_ascii_only("kokoro") is True

    def test_piper_is_not_ascii_only(self):
        # Piper's eSpeak-NG phonemizer tolerates real UTF-8.
        assert engine_is_ascii_only("piper") is False

    def test_native_os_is_not_ascii_only(self):
        # native_os is registered (Phase 3): OS voices speak UTF-8, so the cleaner
        # must NOT transliterate for it.
        assert engine_is_ascii_only("native_os") is False

    def test_unknown_engine_defaults_ascii_only(self):
        # Genuinely unknown engines default to the safe, never-crashing ASCII side.
        assert engine_is_ascii_only("does-not-exist") is True


class TestListEngines:
    def test_local_engines_first_then_heavy(self):
        # native_os first (it is the default — D-01), then the two light model engines,
        # then the heavy opt-in neural engines (orpheus/f5/fish register in
        # list_engines() so they surface in the cross-engine browser — Phase 5, D-17).
        engines = list_engines()
        assert engines[:3] == ["native_os", "kokoro", "piper"]
        for heavy in ("orpheus", "f5", "fish"):
            assert heavy in engines

    def test_removed_engines_absent(self):
        engines = list_engines()
        assert "openai_tts" not in engines
        assert "elevenlabs" not in engines


class TestNativeOsVoices:
    def test_native_os_has_no_static_voices(self):
        # D-04: native_os enumerates voices dynamically (NOT a static cls.VOICES
        # attribute). This half of D-04 is platform-INDEPENDENT — it is a fact about the
        # class shape, not about the host — so it carries NO gate and keeps running
        # everywhere, including the Linux CI runners where native_os itself is
        # unsupported by design.
        from diana.tts.native_os_engine import NativeOSEngine

        # native_os deliberately has no static VOICES class attribute.
        assert not hasattr(NativeOSEngine, "VOICES")

    @pytest.mark.skipif(
        sys.platform != "darwin",
        reason="live native_os enumeration shells the real macOS `say`",
    )
    def test_native_os_live_enumeration(self):
        # get_engine_voices() constructs and initializes a short-lived NativeOSEngine, so
        # this exercises the real `say` path end to end.
        #
        # Gated to darwin ONLY, deliberately — do NOT widen to ("darwin", "win32"):
        #   * Diana targets Windows + macOS, so NativeOSEngine.initialize() legitimately
        #     raises RuntimeError on Linux. The product is right; the test was ungated.
        #   * The win32 live path on a headless runner is unverified territory (no audio
        #     subsystem guarantees). Windows stays covered by the mocked WinRT tests in
        #     tests/test_native_os_engine.py plus the deferred human Windows UAT at
        #     .planning/phases/03-native-os-tts-new-default/03-05-WINDOWS-UAT-DEFERRED.md.
        #   * CI must stay deterministic.
        #
        # Intentionally the skipif DECORATOR rather than the in-body pytest.skip() form
        # used by tests/test_native_os_engine.py and tests/test_native_voices_macos.py: a
        # decorator condition is evaluated at COLLECTION time, so the skip and its reason
        # are visible in -v / -rs / --collect-only on the Linux runner and the gate stays
        # introspectable via pytestmark. Do not convert it back.
        from diana.tts.registry import get_engine_voices

        voices = get_engine_voices("native_os")
        assert len(voices) >= 1
        assert hasattr(voices[0], "tier")


class TestCreateEngineRemoved:
    def test_openai_tts_raises_value_error(self):
        config = MagicMock()
        with pytest.raises(ValueError, match="Unknown TTS engine: openai_tts"):
            create_engine(config, "openai_tts")

    def test_elevenlabs_raises_value_error(self):
        config = MagicMock()
        with pytest.raises(ValueError, match="Unknown TTS engine: elevenlabs"):
            create_engine(config, "elevenlabs")


def test_stale_engine_fallback():
    # A removed/unknown engine name falls back to the local default (kokoro);
    # a still-valid engine name is returned unchanged.
    assert resolve_engine_name("elevenlabs") == "kokoro"
    assert resolve_engine_name("openai_tts") == "kokoro"
    assert resolve_engine_name("piper") == "piper"
    assert resolve_engine_name("kokoro") == "kokoro"
