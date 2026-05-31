"""Tests for diana.tts.registry after cloud-TTS removal (RETIRE-01).

Local-only enumeration (kokoro + piper), removed-engine ValueError, and the
pure stale-engine fallback helper. No model files or network needed.
"""

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

    def test_unknown_engine_defaults_ascii_only(self):
        # Unknown engines default to the safe, never-crashing ASCII side.
        assert engine_is_ascii_only("native_os") is True
        assert engine_is_ascii_only("does-not-exist") is True


class TestListEngines:
    def test_local_only(self):
        assert list_engines() == ["kokoro", "piper"]

    def test_removed_engines_absent(self):
        engines = list_engines()
        assert "openai_tts" not in engines
        assert "elevenlabs" not in engines


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
