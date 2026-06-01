"""Native OS text-to-speech engine — one class, internal sys.platform branch.

The zero-download default engine (D-01): it speaks through the operating system's
own voices, so a fresh install makes audio with no model files (NATIVE-04). One
``NativeOSEngine`` class branches on ``sys.platform`` — the macOS path shells the
``say`` binary (implemented here); the Windows WinRT path is stubbed and lands in
Plan 05. There is deliberately NO module-top ``winrt`` import (it is a Windows-only
C-extension that fails to build on macOS); WinRT is lazy-imported inside the win32
branch only.

macOS synthesis uses ``say -o out.wav --data-format=LEI16@22050`` (the format flag
is REQUIRED — omitting it fails with ``fmt?``). An empty voice id means "no ``-v``",
i.e. the OS system default voice (D-02). Document text is appended as the FINAL
argv element so it is data, never interpolated into a command string (T-03-06, V5);
the temp WAV is always unlinked (T-03-08, V12).
"""

import asyncio
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

from diana.tts.base import TTSVoice

logger = logging.getLogger(__name__)

# Neutral macOS baseline speaking rate (WPM). `say` default voices speak ~175-200
# WPM; speed 0.5-2.0 maps to ~88-350 WPM via round(_BASE_WPM * speed).
_BASE_WPM = 175


class NativeOSEngine:
    """OS-native TTS — macOS ``say`` here; Windows WinRT in Plan 05.

    One class, internal ``sys.platform`` branch (not two registered engines): the
    registry, config, and picker all key off the single name ``"native_os"``.
    """

    name = "native_os"

    def __init__(self) -> None:
        self._platform = sys.platform   # "darwin" | "win32" | other
        self._voice_cache: list[TTSVoice] | None = None

    def initialize(self) -> None:
        if self._platform == "darwin":
            # `say` ships on every Mac; a cheap probe keeps the failure legible.
            if not Path("/usr/bin/say").exists():
                raise RuntimeError("macOS 'say' binary not found at /usr/bin/say.")
        elif self._platform == "win32":
            try:
                import winrt.windows.media.speechsynthesis  # noqa: F401
            except ImportError as e:
                raise RuntimeError(
                    "Windows native TTS requires the winrt packages. Install with: "
                    "pip install winrt-Windows.Media.SpeechSynthesis winrt-runtime"
                ) from e
        else:
            raise RuntimeError(
                f"native_os TTS unsupported on platform: {self._platform}"
            )

    async def synthesize(self, text: str, voice: str = "", speed: float = 1.0) -> bytes:
        if self._platform == "darwin":
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._say_synth, text, voice, speed
            )
        if self._platform == "win32":
            return await self._winrt_synth(text, voice, speed)
        raise RuntimeError(
            f"native_os TTS unsupported on platform: {self._platform}"
        )

    def _say_synth(self, text: str, voice: str, speed: float) -> bytes:
        """Synthesize one chunk via macOS ``say`` and return WAV bytes.

        List-argv subprocess (never ``shell=True``); the document text is the final
        argv element so it is treated as data, not a command (T-03-06, V5). The
        ``--data-format`` flag is REQUIRED — `say` fails (``fmt?``) without it.
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        try:
            cmd = ["/usr/bin/say", "-o", tmp_path, "--data-format=LEI16@22050"]
            if voice:                       # empty id => OS system default (D-02)
                cmd += ["-v", voice]
            cmd += ["-r", str(round(_BASE_WPM * speed))]
            cmd.append(text)                # text is data — final argv element (V5)
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"say failed: {proc.stderr.strip()}")
            return Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def list_voices(self) -> list[TTSVoice]:
        if self._voice_cache is None:
            if self._platform == "darwin":
                from diana.tts.native_voices_macos import enumerate_macos_voices
                self._voice_cache = enumerate_macos_voices()
            elif self._platform == "win32":
                self._voice_cache = self._winrt_list_voices()
            else:
                self._voice_cache = []
        return list(self._voice_cache)

    def default_voice(self) -> str:
        """Return the OS system default voice id (D-02).

        macOS: an empty string — `say` with no ``-v`` uses the OS default, so the
        default is never snapshotted to a concrete id (the OS may change it later).
        Windows: the WinRT ``DefaultVoice`` id (Plan 05).
        """
        if self._platform == "darwin":
            return ""
        if self._platform == "win32":
            return self._winrt_default_voice_id()
        return ""

    def shutdown(self) -> None:
        self._voice_cache = None

    # --- Windows WinRT path: stubbed here, implemented in Plan 05 --------------
    # The macOS path above is complete and importable on a Mac with no winrt
    # installed. These methods fill in next slice (same file). Plan 05: replace
    # the NotImplementedError bodies with the RESEARCH Pattern 3/4 WinRT calls
    # (bytearray(buffer); get_all_voices(); "OneCore" in id tier inference).

    async def _winrt_synth(self, text: str, voice: str, speed: float) -> bytes:
        raise NotImplementedError("Windows WinRT path implemented in Plan 05")

    def _winrt_list_voices(self) -> list[TTSVoice]:
        raise NotImplementedError("Windows WinRT path implemented in Plan 05")

    def _winrt_default_voice_id(self) -> str:
        raise NotImplementedError("Windows WinRT path implemented in Plan 05")
