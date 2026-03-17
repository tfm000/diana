from diana.config import DianaConfig
from diana.tts.base import TTSVoice
from diana.tts.kokoro_engine import KokoroEngine


_ENGINE_CLASSES = {
    "kokoro": KokoroEngine,
}


def _get_engine_class(engine_name: str):
    if engine_name == "piper":
        from diana.tts.piper_engine import PiperEngine
        return PiperEngine
    if engine_name == "openai_tts":
        from diana.tts.openai_tts_engine import OpenAITTSEngine
        return OpenAITTSEngine
    if engine_name == "elevenlabs":
        from diana.tts.elevenlabs_engine import ElevenLabsEngine
        return ElevenLabsEngine
    cls = _ENGINE_CLASSES.get(engine_name)
    if cls is None:
        raise ValueError(f"Unknown TTS engine: {engine_name}")
    return cls


def create_engine(config: DianaConfig, engine_name: str | None = None):
    """Create and initialize a TTS engine."""
    engine_name = engine_name or config.tts.engine

    if engine_name == "kokoro":
        engine = KokoroEngine(
            model_path=config.tts.kokoro.model_path,
            voices_path=config.tts.kokoro.voices_path,
        )
    elif engine_name == "piper":
        from diana.tts.piper_engine import PiperEngine
        engine = PiperEngine(model_path=config.tts.piper.model_path)
    elif engine_name == "openai_tts":
        from diana.tts.openai_tts_engine import OpenAITTSEngine
        engine = OpenAITTSEngine(
            api_key=config.tts.openai_tts.api_key,
            model=config.tts.openai_tts.model,
        )
    elif engine_name == "elevenlabs":
        from diana.tts.elevenlabs_engine import ElevenLabsEngine
        engine = ElevenLabsEngine(
            api_key=config.tts.elevenlabs.api_key,
            model=config.tts.elevenlabs.model,
        )
    else:
        raise ValueError(f"Unknown TTS engine: {engine_name}")

    engine.initialize()
    return engine


def get_engine_voices(engine_name: str, config: DianaConfig | None = None) -> list[TTSVoice]:
    """Return available voices for an engine.

    For ElevenLabs, config must be provided to fetch the live voice list.
    If config is absent or the API key is missing, returns an empty list.
    For all other engines, returns the static VOICES class attribute.
    """
    if engine_name == "elevenlabs":
        if config is None:
            return []
        key = config.tts.elevenlabs.api_key
        if not key or key.startswith("${"):
            return []
        from diana.tts.elevenlabs_engine import ElevenLabsEngine, _FALLBACK_VOICES
        try:
            eng = ElevenLabsEngine(api_key=key, model=config.tts.elevenlabs.model)
            return eng._fetch_voices()
        except Exception:
            return list(_FALLBACK_VOICES)

    cls = _get_engine_class(engine_name)
    return list(cls.VOICES)


def list_engines() -> list[str]:
    """Return names of all available TTS engines."""
    return ["kokoro", "piper", "openai_tts", "elevenlabs"]
