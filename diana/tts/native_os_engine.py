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
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from diana.tts.base import TTSVoice

logger = logging.getLogger(__name__)

# Neutral macOS baseline speaking rate (WPM). `say` default voices speak ~175-200
# WPM; speed 0.5-2.0 maps to ~88-350 WPM via round(_BASE_WPM * speed).
_BASE_WPM = 175

# Quality-tier ranking for D-09 "auto-prefer best installed voice" ordering. Lower
# rank sorts first (best first): enhanced/neural/premium/siri/standard > compact >
# novelty. Unknown tiers sort just after the named good tiers (treated as standard).
_TIER_RANK = {
    "enhanced": 0,
    "premium": 0,
    "neural": 0,
    "siri": 0,
    "standard": 1,
    "compact": 2,
    "novelty": 3,
}
_TIER_RANK_DEFAULT = 1   # unknown/unlabelled tier ~ standard (D-06 fallback)


# --- Pure, Streamlit-free helpers (unit-testable; no I/O, no streamlit, no DB) ---
# Filtering / ordering / default-voice resolution over a list[TTSVoice]. The UI
# (1_Upload.py / 5_Settings.py) wires these in; the engine module stays import-clean
# on every platform (no streamlit, no winrt at module top).

def _fold(text: str) -> str:
    """Lowercase and strip diacritics so a name search is accent-insensitive.

    A non-technical user typing "amel" should still match "Amélie" — they should
    not have to type accented characters. NFKD-decompose, drop combining marks,
    then casefold.
    """
    decomposed = unicodedata.normalize("NFKD", text or "")
    no_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return no_marks.casefold()


def filter_voices(
    voices: list[TTSVoice],
    language: str | None = None,
    tier: str | None = None,
    query: str | None = None,
) -> list[TTSVoice]:
    """Filter a voice list by language, quality tier, and a name substring (D-07).

    Predicates are ANDed; any argument left as ``None`` is ignored (pass-through).
    ``language`` and ``tier`` match the corresponding field case-insensitively. A
    bilingual voice passes a ``language`` filter if the filter language appears in
    its ``language`` field (which, for bilingual voices, may list more than one
    locale). ``query`` matches ``name`` case-insensitively as a substring. The
    input list is never mutated; a new list is returned.
    """
    result = list(voices)
    if language is not None:
        lang = language.strip().lower()
        result = [v for v in result if _matches_language(v, lang)]
    if tier is not None:
        want = tier.strip().lower()
        result = [v for v in result if (v.tier or "").strip().lower() == want]
    if query is not None:
        needle = _fold(query.strip())
        if needle:
            result = [v for v in result if needle in _fold(v.name or "")]
    return result


def _matches_language(voice: TTSVoice, lang: str) -> bool:
    """True if voice speaks ``lang`` (handles bilingual voices listing >1 locale)."""
    field = (voice.language or "").strip().lower()
    if not lang:
        return True
    if field == lang:
        return True
    # Bilingual voices may store multiple locales; match any whitespace/comma/slash
    # separated token so e.g. "en-us, fr-fr" passes a language="fr-fr" filter (D-05).
    if getattr(voice, "bilingual", False):
        tokens = re.split(r"[\s,/]+", field)
        return lang in (t for t in tokens if t)
    return False


def order_by_quality(voices: list[TTSVoice]) -> list[TTSVoice]:
    """Sort voices best-quality-first (D-09), stable within a tier.

    Ranking: enhanced/neural/premium/siri/standard > compact > novelty. The sort is
    stable, so any pre-existing order within a tier (e.g. a system-language-first
    arrangement the UI applies — D-08) is preserved. The input is not mutated.
    """
    return sorted(
        voices,
        key=lambda v: _TIER_RANK.get((v.tier or "").strip().lower(), _TIER_RANK_DEFAULT),
    )


def resolve_default_voice(
    remembered: str, voices: list[TTSVoice], engine_default: str
) -> str:
    """Resolve the per-engine default voice id, never preselecting a missing one.

    Returns ``remembered`` only when it is present in the live enumerated ``voices``
    list; otherwise returns ``engine_default`` (the engine's own default — for
    native_os the OS system default, an empty string). This is the D-03 / Pitfall 5
    correctness control: a stale remembered id (e.g. a voice that was uninstalled,
    or a voice id from a different engine) is never fed to synthesis.

    Pure: takes the already-read ``remembered`` value, does no DB I/O. The DB-aware
    wrapper that reads ``remembered`` from ``app_settings`` lives in the registry.
    """
    valid_ids = {v.id for v in voices}
    if remembered and remembered in valid_ids:
        return remembered
    return engine_default


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
