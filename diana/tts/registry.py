from diana.config import DianaConfig
from diana.tts.base import TTSVoice
from diana.tts.kokoro_engine import KokoroEngine


_ENGINE_CLASSES = {
    "kokoro": KokoroEngine,
}

# Whether each engine's tokenizer requires pure ASCII. Static name->bool map,
# queried with NO engine import so pipeline.py/llm_cleaner.py can resolve an
# engine's character capability without pulling onnxruntime/piper onto the
# cleaning path. native_os (Phase 3) will be False (the OS voices speak UTF-8).
_ASCII_ONLY_ENGINES = {
    "kokoro": True,
    "piper": False,
    "native_os": False,   # OS voices speak UTF-8 — no cleaner transliteration (Phase 2)
}


def _get_engine_class(engine_name: str):
    if engine_name == "piper":
        from diana.tts.piper_engine import PiperEngine
        return PiperEngine
    if engine_name == "native_os":
        from diana.tts.native_os_engine import NativeOSEngine
        return NativeOSEngine
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
    elif engine_name == "native_os":
        from diana.tts.native_os_engine import NativeOSEngine
        engine = NativeOSEngine()   # no config — OS-provided voices
    else:
        raise ValueError(f"Unknown TTS engine: {engine_name}")

    engine.initialize()
    return engine


def get_engine_voices(engine_name: str, config: DianaConfig | None = None) -> list[TTSVoice]:
    """Return available voices for an engine.

    Most engines expose a static VOICES class attribute. native_os is the
    exception (D-04): its voices are enumerated dynamically from the OS at
    runtime, so it constructs a short-lived engine, initializes it, and returns
    its live list_voices(). UI callers cache this across Streamlit reruns.
    """
    if engine_name == "native_os":
        from diana.tts.native_os_engine import NativeOSEngine
        eng = NativeOSEngine()
        eng.initialize()
        try:
            return eng.list_voices()
        finally:
            eng.shutdown()
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
    """Return names of all available TTS engines (native_os first — it is the default)."""
    return ["native_os", "kokoro", "piper"]


def engine_is_ascii_only(engine_name: str) -> bool:
    """Whether an engine's tokenizer requires pure ASCII. Cheap: no engine import.

    Drives the cleaner's engine-conditional transliteration/ASCII net (CLEAN-07):
    ASCII-only engines (kokoro) get café->cafe, UTF-8-capable engines (piper)
    keep café. Unknown engines default to ASCII-only — the safe,
    lossy-but-never-crashing side. native_os (Phase 3) will be False.
    """
    return _ASCII_ONLY_ENGINES.get(engine_name, True)
