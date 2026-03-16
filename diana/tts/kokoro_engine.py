import asyncio
import io
from pathlib import Path

import soundfile as sf

from diana.tts.base import TTSVoice


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
                "Download it with:\n"
                "  wget -P data/models/ https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
            )
        if not voices.exists():
            raise FileNotFoundError(
                f"Kokoro voices not found at {voices}. "
                "Download it with:\n"
                "  wget -P data/models/ https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
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
