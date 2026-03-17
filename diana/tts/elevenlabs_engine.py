import asyncio
import logging

from diana.tts.base import TTSVoice

logger = logging.getLogger(__name__)

# Fallback voices shown when the API is unreachable or key is missing
_FALLBACK_VOICES = [
    TTSVoice("21m00Tcm4TlvDq8ikWAM", "Rachel", "en", "female"),
    TTSVoice("AZnzlk1XvdvUeBnXmlld", "Domi", "en", "female"),
    TTSVoice("EXAVITQu4vr4xnSDxMaL", "Bella", "en", "female"),
    TTSVoice("ErXwobaYiN019PkySvjV", "Antoni", "en", "male"),
    TTSVoice("MF3mGyEYCl7XYWbV9V6O", "Elli", "en", "female"),
    TTSVoice("TxGEqnHWrfWFTfGW9XjX", "Josh", "en", "male"),
    TTSVoice("VR6AewLTigWG4xSOukaG", "Arnold", "en", "male"),
    TTSVoice("pNInz6obpgDQGcFmaJgB", "Adam", "en", "male"),
    TTSVoice("yoZ06aMxZJJ28mfd3POQ", "Sam", "en", "male"),
]

_API_BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsEngine:
    """ElevenLabs cloud TTS engine.

    Fetches available voices from the API on initialize().
    Falls back to a hardcoded list if the API is unreachable.
    Returns MP3 bytes.
    """

    name = "elevenlabs"

    def __init__(self, api_key: str, model: str = "eleven_monolingual_v1"):
        self._api_key = api_key
        self._model = model or "eleven_monolingual_v1"
        self._voices: list[TTSVoice] = list(_FALLBACK_VOICES)

    def initialize(self) -> None:
        if not self._api_key or self._api_key.startswith("${"):
            raise ValueError(
                "ElevenLabs API key is not configured. "
                "Add it in Settings under 'ElevenLabs'."
            )
        try:
            import requests  # noqa: F401
        except ImportError:
            raise RuntimeError("requests package is not installed. Run: pip install requests")

        self._voices = self._fetch_voices()

    def _fetch_voices(self) -> list[TTSVoice]:
        try:
            import requests
            resp = requests.get(
                f"{_API_BASE}/voices",
                headers={"xi-api-key": self._api_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            voices = []
            for v in data.get("voices", []):
                labels = v.get("labels", {})
                gender = labels.get("gender", "unknown").lower()
                voices.append(TTSVoice(
                    id=v["voice_id"],
                    name=v["name"],
                    language="en",
                    gender=gender,
                ))
            return voices or list(_FALLBACK_VOICES)
        except Exception as exc:
            logger.warning("Failed to fetch ElevenLabs voices: %s. Using fallback list.", exc)
            return list(_FALLBACK_VOICES)

    async def synthesize(self, text: str, voice: str, speed: float = 1.0) -> bytes:
        import requests as req_mod
        # ElevenLabs uses speaking_rate for speed (0.7–1.2 typical range)
        speaking_rate = max(0.7, min(1.2, speed))

        def _call() -> bytes:
            resp = req_mod.post(
                f"{_API_BASE}/text-to-speech/{voice}",
                headers={
                    "xi-api-key": self._api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": text,
                    "model_id": self._model,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "speaking_rate": speaking_rate,
                    },
                },
                timeout=120,
            )
            if resp.status_code == 402:
                raise RuntimeError(
                    "ElevenLabs quota exceeded. Please check your subscription."
                )
            resp.raise_for_status()
            return resp.content

        return await asyncio.to_thread(_call)

    def list_voices(self) -> list[TTSVoice]:
        return list(self._voices)

    def shutdown(self) -> None:
        pass
