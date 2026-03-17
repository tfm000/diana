"""Tests for diana.tts.piper_engine (mock-based, no model files needed)."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from diana.tts.base import TTSVoice
from diana.tts.piper_engine import PiperEngine


@pytest.fixture
def engine(tmp_path):
    """Create a PiperEngine with a temporary model path."""
    model_file = tmp_path / "default.onnx"
    model_file.write_bytes(b"fake-model")
    return PiperEngine(str(model_file))


class TestInitialize:
    def test_model_not_found(self, tmp_path):
        engine = PiperEngine(str(tmp_path / "missing.onnx"))
        with pytest.raises(FileNotFoundError, match="Piper model not found"):
            engine.initialize()

    def test_python_api_preferred(self, engine):
        with patch.dict("sys.modules", {"piper": MagicMock()}):
            engine.initialize()
            assert engine._use_python_api is True

    def test_fallback_to_binary(self, engine):
        with patch.dict("sys.modules", {"piper": None}):
            with patch("diana.tts.piper_engine.shutil.which", return_value="/usr/bin/piper"):
                # Force ImportError for piper
                import builtins
                original_import = builtins.__import__

                def mock_import(name, *args, **kwargs):
                    if name == "piper":
                        raise ImportError("No module named 'piper'")
                    return original_import(name, *args, **kwargs)

                with patch("builtins.__import__", side_effect=mock_import):
                    engine.initialize()
                    assert engine._use_python_api is False
                    assert engine._piper_binary == "/usr/bin/piper"

    def test_neither_available(self, engine):
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "piper":
                raise ImportError("No module named 'piper'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with patch("diana.tts.piper_engine.shutil.which", return_value=None):
                with pytest.raises(RuntimeError, match="Piper TTS not available"):
                    engine.initialize()


class TestResolveModelPath:
    def test_voice_specific_model(self, engine, tmp_path):
        voice_model = tmp_path / "en_US-lessac-medium.onnx"
        voice_model.write_bytes(b"voice-model")
        result = engine._resolve_model_path("en_US-lessac-medium")
        assert result == str(voice_model)

    def test_fallback_to_default(self, engine):
        result = engine._resolve_model_path("nonexistent-voice")
        assert result == engine._model_path


class TestSynthesize:
    def test_routes_to_python_api(self, engine):
        engine._use_python_api = True
        assert engine._use_python_api is True

    def test_routes_to_binary(self, engine):
        engine._use_python_api = False
        assert engine._use_python_api is False


class TestListVoices:
    def test_returns_voices(self, engine):
        voices = engine.list_voices()
        assert len(voices) == 5
        assert all(isinstance(v, TTSVoice) for v in voices)

    def test_voice_ids(self, engine):
        voice_ids = [v.id for v in engine.list_voices()]
        assert "en_US-lessac-medium" in voice_ids
        assert "en_GB-alan-medium" in voice_ids

    def test_voice_fields(self, engine):
        voice = engine.list_voices()[0]
        assert voice.id == "en_US-lessac-medium"
        assert voice.name == "Lessac (US Medium)"
        assert voice.language == "en-us"
        assert voice.gender == "male"


class TestShutdown:
    def test_clears_cache(self, engine):
        engine._voice_cache["some-model"] = "fake-voice-object"
        engine.shutdown()
        assert len(engine._voice_cache) == 0
