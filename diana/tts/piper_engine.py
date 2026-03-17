import asyncio
import io
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from diana.tts.base import TTSVoice

logger = logging.getLogger(__name__)


class PiperEngine:
    """Piper TTS engine — fast, lightweight, local inference.

    Uses the piper-tts Python package if available, otherwise falls back
    to invoking the standalone piper binary via subprocess.
    """

    name = "piper"

    VOICES = [
        TTSVoice("en_US-lessac-medium", "Lessac (US Medium)", "en-us", "male"),
        TTSVoice("en_US-lessac-high", "Lessac (US High)", "en-us", "male"),
        TTSVoice("en_US-amy-medium", "Amy (US Medium)", "en-us", "female"),
        TTSVoice("en_US-ryan-medium", "Ryan (US Medium)", "en-us", "male"),
        TTSVoice("en_GB-alan-medium", "Alan (GB Medium)", "en-gb", "male"),
    ]

    def __init__(self, model_path: str):
        self._model_path = model_path
        self._model_dir = str(Path(model_path).parent)
        self._piper_binary: str | None = None
        self._use_python_api = False
        self._voice_cache: dict = {}  # voice_id → loaded PiperVoice

    def _resolve_model_path(self, voice: str) -> str:
        """Resolve a voice ID to a model file path.

        Checks for a voice-specific model in the model directory first,
        then falls back to the configured default model path.
        """
        voice_model = Path(self._model_dir) / f"{voice}.onnx"
        if voice_model.exists():
            return str(voice_model)
        return self._model_path

    def initialize(self) -> None:
        model = Path(self._model_path)
        if not model.exists():
            raise FileNotFoundError(
                f"Piper model not found at {model}. "
                "Download a model from https://huggingface.co/rhasspy/piper-voices"
            )

        # Try the Python package first
        try:
            import piper  # noqa: F401
            self._use_python_api = True
            logger.info("Using piper Python API")
            return
        except ImportError:
            pass

        # Fall back to binary
        binary = shutil.which("piper")
        if binary:
            self._piper_binary = binary
            logger.info("Using piper binary at %s", binary)
            return

        raise RuntimeError(
            "Piper TTS not available. Install via 'pip install piper-tts' "
            "or place the piper binary on your PATH."
        )

    async def synthesize(self, text: str, voice: str = "en_US-lessac-medium", speed: float = 1.0) -> bytes:
        if self._use_python_api:
            return await self._synthesize_python(text, voice, speed)
        return await self._synthesize_binary(text, voice, speed)

    async def _synthesize_python(self, text: str, voice: str, speed: float) -> bytes:
        import piper as piper_mod

        loop = asyncio.get_event_loop()
        model_path = self._resolve_model_path(voice)

        def _run():
            # Use cached voice model if available
            if model_path not in self._voice_cache:
                self._voice_cache[model_path] = piper_mod.PiperVoice.load(model_path)
            tts = self._voice_cache[model_path]
            syn_config = piper_mod.config.SynthesisConfig(
                length_scale=1.0 / speed,
            )
            buf = io.BytesIO()
            import wave
            with wave.open(buf, "wb") as wav:
                tts.synthesize_wav(text, wav, syn_config=syn_config)
            return buf.getvalue()

        return await loop.run_in_executor(None, _run)

    async def _synthesize_binary(self, text: str, voice: str, speed: float) -> bytes:
        model_path = self._resolve_model_path(voice)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        loop = asyncio.get_event_loop()

        def _run():
            cmd = [
                self._piper_binary,
                "--model", model_path,
                "--output_file", tmp_path,
                "--length-scale", str(1.0 / speed),
            ]
            proc = subprocess.run(
                cmd, input=text, capture_output=True, text=True, timeout=300,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"Piper failed: {proc.stderr}")
            return Path(tmp_path).read_bytes()

        try:
            data = await loop.run_in_executor(None, _run)
            return data
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def list_voices(self) -> list[TTSVoice]:
        return list(self.VOICES)

    def shutdown(self) -> None:
        self._voice_cache.clear()
