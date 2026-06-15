from diana.config import DianaConfig
from diana.tts.base import TTSVoice
from diana.tts.kokoro_engine import KokoroEngine


_ENGINE_CLASSES = {
    "kokoro": KokoroEngine,
}

# The heavy, opt-in neural engines (Phase 5). They badge/gate/fail-fast cheaply
# here (filesystem + nvidia-smi only), but are NOT added to list_engines() or
# _get_engine_class in this slice — each engine joins those seams in its OWN wave
# so all_engine_voices never tries to import a not-yet-built engine (D-17).
_HEAVY_ENGINES = {"orpheus", "f5", "fish"}

# Whether each engine's tokenizer requires pure ASCII. Static name->bool map,
# queried with NO engine import so pipeline.py/llm_cleaner.py can resolve an
# engine's character capability without pulling onnxruntime/piper onto the
# cleaning path. native_os (Phase 3) will be False (the OS voices speak UTF-8).
# The heavy neural engines (orpheus/f5/fish) are UTF-8 capable -> False (D-17).
_ASCII_ONLY_ENGINES = {
    "kokoro": True,
    "piper": False,
    "native_os": False,   # OS voices speak UTF-8 — no cleaner transliteration (Phase 2)
    "orpheus": False,
    "f5": False,
    "fish": False,
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

    Most engines expose a static VOICES class attribute. Two engines enumerate
    dynamically:

    - native_os (D-04): voices come from the OS at runtime, so it constructs a
      short-lived engine, initializes it, and returns its live list_voices().
    - piper: the static curated VOICES MERGED with every voice the user has
      installed on disk (so an "install -> use" voice appears in the Upload and
      Settings pickers — VOICE-05). Discovery is a cheap ``*.onnx`` filesystem
      glob (ENGINE-01: NO onnxruntime/piper import on the enumeration path).

    UI callers cache this across Streamlit reruns.
    """
    if engine_name == "native_os":
        from diana.tts.native_os_engine import NativeOSEngine
        eng = NativeOSEngine()
        eng.initialize()
        try:
            return eng.list_voices()
        finally:
            eng.shutdown()
    if engine_name == "piper":
        return _piper_voices()
    cls = _get_engine_class(engine_name)
    return list(cls.VOICES)


def _piper_voices() -> list[TTSVoice]:
    """Static curated Piper voices merged with installed-on-disk voices (VOICE-05).

    The static ``PiperEngine.VOICES`` come first (their hand-curated labels are the
    richer ones); each installed voice id NOT already in that static set is appended,
    labeled via the catalog (bundled-manifest entry when known, else derived from the
    Piper id convention). Deduped by id — a voice present both statically and on disk
    keeps its static label. Installed Kokoro ``.onnx`` variants are excluded by the
    install-state lister, so they never appear here as Piper voices.

    Cheap by design: a ``*.onnx`` glob plus a cached catalog lookup — no engine SDK
    import (ENGINE-01). ``install_state`` / ``catalog`` are imported lazily so the
    cleaning path (``engine_is_ascii_only``) never pulls them in.
    """
    from diana.tts.catalog import voice_label_for_id
    from diana.tts.install_state import list_installed_piper_voice_ids
    from diana.tts.piper_engine import PiperEngine

    voices = list(PiperEngine.VOICES)
    seen = {v.id for v in voices}
    for vid in list_installed_piper_voice_ids():
        if vid in seen:
            continue
        seen.add(vid)
        voices.append(voice_label_for_id(vid))
    return voices


def resolve_default_voice(
    db_path: str,
    engine_name: str,
    voices: list[TTSVoice],
    engine_default: str,
) -> str:
    """Resolve the remembered per-engine default voice id from durable prefs (D-03).

    Reads the remembered choice from ``app_settings`` (key
    ``tts.default_voice.<engine_name>``) and validates it against the live
    enumerated ``voices`` list: a remembered id still present in the list is
    honored; an absent/stale id (uninstalled voice, or an id from a different
    engine) falls back to ``engine_default`` — never preselecting a missing voice
    (Pitfall 5). The remembered choice survives restart and engine switching
    because it is keyed per engine in the durable store.

    The membership/validation logic is the pure ``resolve_default_voice`` in
    native_os_engine; this wrapper only adds the ``app_settings`` read. ``get_setting``
    is imported lazily so the durable-prefs dependency stays off module import.
    """
    from diana.database import get_setting
    from diana.tts.native_os_engine import resolve_default_voice as _resolve_pure

    remembered = get_setting(db_path, f"tts.default_voice.{engine_name}", None) or ""
    return _resolve_pure(remembered, voices, engine_default)


def all_engine_voices(config: DianaConfig | None = None) -> list[tuple[str, TTSVoice]]:
    """Aggregate every engine's voices into ``(engine_name, voice)`` pairs (D-10).

    The cross-engine browser source: iterates ``list_engines()`` and, for each, the
    existing ``get_engine_voices(engine, config)`` — so native_os's dynamic OS
    enumeration, Piper's static-curated-plus-installed merge, and Kokoro's baked-in
    voices all flow through here unchanged (no engine re-enumeration logic is
    reimplemented). Each voice is tagged with the engine it came from so the UI can
    show an engine column, offer an engine filter, and key per-voice label overrides
    by ``(engine, voice.id)``. Returns a flat list (not a generator) so the Streamlit
    caller can reuse it across reruns. Cheap by design: ``get_engine_voices`` already
    avoids heavy SDK imports on the enumeration path (ENGINE-01).
    """
    pairs: list[tuple[str, TTSVoice]] = []
    for engine_name in list_engines():
        for voice in get_engine_voices(engine_name, config):
            pairs.append((engine_name, voice))
    return pairs


# --- Thin install-state shims (ENGINE-01) ----------------------------------------
# Re-exposed from install_state so the UI imports ONE place for the readiness/footprint
# badges. The cheap-probe logic stays in install_state (a pure filesystem probe — NO
# onnxruntime/piper/kokoro import on the badge path); these wrappers only forward, and
# lazy-import install_state so the cleaning path (engine_is_ascii_only) never pulls it.

def piper_voice_installed(voice_id: str) -> bool:
    """True iff a Piper voice's ``{id}.onnx`` is on disk (cheap probe; ENGINE-01)."""
    from diana.tts.install_state import piper_voice_installed as _probe
    return _probe(voice_id)


def piper_footprint_bytes(voice_id: str) -> int:
    """On-disk size of an installed Piper voice, else 0 (cheap probe; ENGINE-01)."""
    from diana.tts.install_state import piper_footprint_bytes as _probe
    return _probe(voice_id)


def kokoro_model_installed() -> bool:
    """True iff the Kokoro model + voices bin are on disk (cheap probe; ENGINE-01)."""
    from diana.tts.install_state import kokoro_model_installed as _probe
    return _probe()


def heavy_engine_failfast(engine_name: str) -> str | None:
    """Pre-flight refusal for an uninstalled heavy engine, else ``None`` (D-16).

    The fail-fast contract for success-criterion #4: a heavy engine chosen for a job
    is checked UP FRONT — when it is one of the heavy engines (orpheus/f5/fish) AND
    its deps/model are not installed, this returns an actionable string telling the
    user to install it in Settings ▸ Voices, so the job NEVER starts and never errors
    mid-conversion. Returns ``None`` for an installed heavy engine (the job may start)
    and for any non-heavy engine (native_os/kokoro/piper — never heavy-gated).

    Cheap by design: the install check is a pure filesystem probe; ``install_state``
    is imported lazily so the cleaning/enumeration path never pulls it, and NO
    torch/llama-cpp/orpheus_cpp/f5_tts is imported here (ENGINE-01 / D-17).
    """
    if engine_name not in _HEAVY_ENGINES:
        return None
    from diana.tts.install_state import heavy_engine_installed
    if heavy_engine_installed(engine_name):
        return None
    return (f"{engine_name.capitalize()} isn't installed — "
            "open Settings ▸ Voices and click Install.")


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
