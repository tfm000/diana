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
    else:
        raise ValueError(f"Unknown TTS engine: {engine_name}")

    engine.initialize()
    return engine


def get_engine_voices(engine_name: str, config: DianaConfig | None = None) -> list[TTSVoice]:
    """Return available voices for an engine.

    Returns the static VOICES class attribute for the engine.
    """
    cls = _get_engine_class(engine_name)
    return list(cls.VOICES)


def resolve_engine_name(saved: str) -> str:
    """Return the saved engine if still available, else the local default ("kokoro").

    Pure helper for the stale-engine fallback (D-05): a config naming a removed
    engine resolves to kokoro instead of crashing. The one-time UI notice lives
    in the dashboard pages, not here.
    """
    return saved if saved in list_engines() else "kokoro"


def list_engines() -> list[str]:
    """Return names of all available TTS engines."""
    return ["kokoro", "piper"]
