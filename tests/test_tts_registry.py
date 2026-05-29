"""Tests for diana.tts.registry after cloud-TTS removal (RETIRE-01).

Local-only enumeration (kokoro + piper), removed-engine ValueError, and the
pure stale-engine fallback helper. No model files or network needed.
"""

from unittest.mock import MagicMock

import pytest

from diana.tts.registry import create_engine, list_engines, resolve_engine_name


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
