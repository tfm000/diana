import asyncio
import logging

from diana.tts.base import TTSVoice

logger = logging.getLogger(__name__)


class OpenAITTSEngine:
    """OpenAI cloud TTS engine.

    Returns MP3 bytes directly (OpenAI TTS outputs MP3, not WAV).
    Speed range: 0.25–4.0 (OpenAI native range).
    """

    name = "openai_tts"

    VOICES = [
        TTSVoice("alloy", "Alloy", "en", "neutral"),
        TTSVoice("echo", "Echo", "en", "male"),
        TTSVoice("fable", "Fable", "en", "male"),
        TTSVoice("onyx", "Onyx", "en", "male"),
        TTSVoice("nova", "Nova", "en", "female"),
        TTSVoice("shimmer", "Shimmer", "en", "female"),
    ]

    def __init__(self, api_key: str, model: str = "tts-1"):
        self._api_key = api_key
        self._model = model or "tts-1"

    def initialize(self) -> None:
        if not self._api_key or self._api_key.startswith("${"):
            raise ValueError(
                "OpenAI TTS API key is not configured. "
                "Add it in Settings under 'OpenAI TTS'."
            )
        try:
            import openai  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "openai package is not installed. Run: pip install openai"
            )

    async def synthesize(self, text: str, voice: str = "alloy", speed: float = 1.0) -> bytes:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self._api_key)
        # OpenAI speed range is 0.25–4.0
        clamped_speed = max(0.25, min(4.0, speed))
        response = await client.audio.speech.create(
            model=self._model,
            voice=voice,
            input=text,
            speed=clamped_speed,
            response_format="mp3",
        )
        return await asyncio.to_thread(response.read)

    def list_voices(self) -> list[TTSVoice]:
        return list(self.VOICES)

    def shutdown(self) -> None:
        pass
