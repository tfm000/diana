from dataclasses import dataclass
from typing import Protocol


@dataclass
class TTSVoice:
    """Describes an available voice."""
    id: str
    name: str
    language: str
    gender: str


class TTSEngine(Protocol):
    """Protocol that all TTS backends must implement.

    To add a new engine:
    1. Create a new file in diana/tts/ implementing this protocol
    2. Register it in diana/tts/registry.py
    """

    @property
    def name(self) -> str:
        """Human-readable engine name."""
        ...

    def initialize(self) -> None:
        """Load models, validate config. Called once at startup."""
        ...

    async def synthesize(self, text: str, voice: str, speed: float = 1.0) -> bytes:
        """Convert text to audio bytes (WAV or MP3 format)."""
        ...

    def list_voices(self) -> list[TTSVoice]:
        """Return available voices for this engine."""
        ...

    def shutdown(self) -> None:
        """Release resources."""
        ...
