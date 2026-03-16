from diana.config import DianaConfig
from diana.tts.kokoro_engine import KokoroEngine


def create_engine(config: DianaConfig):
    """Create and initialize the configured TTS engine."""
    engine_name = config.tts.engine

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


def list_engines() -> list[str]:
    """Return names of all available TTS engines."""
    return ["kokoro", "piper"]
