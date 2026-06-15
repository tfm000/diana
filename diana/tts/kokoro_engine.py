import asyncio
import io
from pathlib import Path

import soundfile as sf

from diana.tts.base import TTSVoice

# Kokoro model assets on the upstream GitHub release (URLs/sizes VERIFIED live —
# 04-RESEARCH.md:497-501). Exposed here so the in-UI download (D-19) routes through
# the generic downloads layer WITHOUT hardcoding URLs in the Settings page. Kokoro is
# ONE model with many baked-in voices (D-19), so this is an engine-level "model
# installed?" download, not per-voice rows. The three ``.onnx`` variants trade size
# for fidelity; ``voices-v1.0.bin`` is shared by all of them and is always required.
_KOKORO_RELEASE = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
)

# variant key -> (filename, url, approx_size_bytes, label). ``int8`` (~88 MB) is the
# smallest viable model and the sensible default; ``f32`` (~310 MB) crosses the D-04
# >200 MB footprint-confirm threshold. Sizes are approximate (the exact total comes
# from the manifest/Content-Range at download time); ``voices-v1.0.bin`` is exact.
KOKORO_MODEL_VARIANTS: dict[str, dict] = {
    "int8": {
        "filename": "kokoro-v1.0.int8.onnx",
        "url": f"{_KOKORO_RELEASE}/kokoro-v1.0.int8.onnx",
        "size_bytes": 88_000_000,
        "label": "int8 — smallest (~88 MB), good quality",
    },
    "fp16": {
        "filename": "kokoro-v1.0.fp16.onnx",
        "url": f"{_KOKORO_RELEASE}/kokoro-v1.0.fp16.onnx",
        "size_bytes": 169_000_000,
        "label": "fp16 — balanced (~169 MB)",
    },
    "f32": {
        "filename": "kokoro-v1.0.onnx",
        "url": f"{_KOKORO_RELEASE}/kokoro-v1.0.onnx",
        "size_bytes": 310_000_000,
        "label": "f32 — full precision (~310 MB)",
    },
}

# The shared voices file every variant needs (size VERIFIED exact — T-04-INT).
KOKORO_VOICES_ASSET: dict = {
    "filename": "voices-v1.0.bin",
    "url": f"{_KOKORO_RELEASE}/voices-v1.0.bin",
    "size_bytes": 28_214_398,
}

# The sensible default variant for the one-confirm download (smallest viable).
KOKORO_DEFAULT_VARIANT = "int8"


def kokoro_download_assets(variant: str = KOKORO_DEFAULT_VARIANT) -> list[dict]:
    """The asset records to download for one Kokoro install: the chosen model + voices.

    Returns ``[model_variant, voices]`` — each a dict with ``filename``, ``url`` and
    ``size_bytes`` — so the UI download row (D-19) builds the generic-layer download
    without hardcoding any URL. An unknown ``variant`` falls back to the default.
    Pure/Streamlit-free; no network touch (just the static asset table).
    """
    model = KOKORO_MODEL_VARIANTS.get(variant, KOKORO_MODEL_VARIANTS[KOKORO_DEFAULT_VARIANT])
    return [model, KOKORO_VOICES_ASSET]


class KokoroEngine:
    name = "kokoro"

    # Available voices (subset — Kokoro supports many more)
    VOICES = [
        TTSVoice("af_heart", "Heart (Female)", "en-us", "female"),
        TTSVoice("af_bella", "Bella (Female)", "en-us", "female"),
        TTSVoice("af_nicole", "Nicole (Female)", "en-us", "female"),
        TTSVoice("af_sarah", "Sarah (Female)", "en-us", "female"),
        TTSVoice("af_sky", "Sky (Female)", "en-us", "female"),
        TTSVoice("am_adam", "Adam (Male)", "en-us", "male"),
        TTSVoice("am_michael", "Michael (Male)", "en-us", "male"),
        TTSVoice("bf_emma", "Emma (Female, British)", "en-gb", "female"),
        TTSVoice("bm_george", "George (Male, British)", "en-gb", "male"),
    ]

    def __init__(self, model_path: str, voices_path: str):
        self._model_path = model_path
        self._voices_path = voices_path
        self._kokoro = None

    def initialize(self) -> None:
        model = Path(self._model_path)
        voices = Path(self._voices_path)

        if not model.exists():
            raise FileNotFoundError(
                f"Kokoro model not found at {model}. "
                "Download it from the app: open Settings ▸ Voices and click "
                "“Download model” on the Kokoro row — no terminal needed."
            )
        if not voices.exists():
            raise FileNotFoundError(
                f"Kokoro voices not found at {voices}. "
                "Download it from the app: open Settings ▸ Voices and click "
                "“Download model” on the Kokoro row — no terminal needed."
            )

        from kokoro_onnx import Kokoro
        self._kokoro = Kokoro(str(model), str(voices))

    async def synthesize(self, text: str, voice: str = "af_heart", speed: float = 1.0) -> bytes:
        if self._kokoro is None:
            raise RuntimeError("Engine not initialized. Call initialize() first.")

        loop = asyncio.get_event_loop()
        samples, sample_rate = await loop.run_in_executor(
            None,
            lambda: self._kokoro.create(text, voice=voice, speed=speed, lang="en-us"),
        )

        buf = io.BytesIO()
        sf.write(buf, samples, sample_rate, format="WAV")
        return buf.getvalue()

    def list_voices(self) -> list[TTSVoice]:
        return list(self.VOICES)

    def shutdown(self) -> None:
        self._kokoro = None
