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


def resolve_selected_voice_id(
    voice_options: dict[str, str], selected_name: str | None
) -> str:
    """Map a picker's selected display name to its voice id, None/empty-safe.

    The Streamlit voice ``selectbox`` returns ``None`` when its option list is
    empty (i.e. the language/quality filters or the name search matched no voice).
    Indexing ``voice_options[None]`` would then raise ``KeyError: None`` and crash
    the page. This helper resolves the id defensively: it returns the mapped id
    only when ``selected_name`` is truthy AND present in ``voice_options``;
    otherwise it returns ``""`` — the "use the engine/OS system default" sentinel
    (D-02), so conversion still has a sane fallback instead of crashing.

    Pure: no streamlit, no I/O — just a guarded dict lookup, so the empty/None
    path is unit-testable without a Streamlit ScriptRunContext.
    """
    if not selected_name:
        return ""
    return voice_options.get(selected_name, "")


class NativeOSEngine:
    """OS-native TTS — macOS ``say`` here; Windows WinRT in Plan 05.

    One class, internal ``sys.platform`` branch (not two registered engines): the
    registry, config, and picker all key off the single name ``"native_os"``.
    """

    name = "native_os"

    def __init__(self) -> None:
        self._platform = sys.platform   # "darwin" | "win32" | other
        self._voice_cache: list[TTSVoice] | None = None
        # D-11: set True by _winrt_list_voices when no OneCore (neural) voice is
        # present, so the Windows picker can surface the visible SAPI5-only note.
        self._sapi5_only = False

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

    # --- Windows WinRT path (RESEARCH Patterns 3-4) ----------------------------
    # The macOS path above is complete and importable on a Mac with no winrt
    # installed. The three methods below speak through the Windows WinRT
    # SpeechSynthesizer: synth via `await synthesize_text_to_stream_async` +
    # `bytes(bytearray(buffer))` (the Python buffer protocol — the maintainer-
    # recommended path, avoiding the slow stream-reader helper, and a bare await
    # rather than wrapping the awaitable in a task); enumeration mapping
    # VoiceInformation -> TTSVoice with tier inferred from "OneCore" in the voice
    # Id; default = the `default_voice` property.
    #
    # PINNED (was ASSUMPTION A1): the two static-member spellings are now fixed.
    # `all_voices` and `default_voice` are metaclass PROPERTIES declared on
    # `SpeechSynthesizer_Static` (SpeechSynthesizer carries
    # `metaclass=SpeechSynthesizer_Static`), so they are class-attribute READS —
    # no `get_` prefix and no call parentheses.
    #
    # Evidence: the official winrt-Windows.Media.SpeechSynthesis 3.2.1 wheel stubs
    # (`_winrt_windows_media_speechsynthesis.pyi`, `class SpeechSynthesizer_Static`:
    # `@_property def all_voices(cls)`, `@_property def default_voice(cls)`),
    # corroborated by the first-ever Windows CI run (quick-260807-3yx), where every
    # windows job failed 39 tests on the old guess.
    #
    # HISTORY — do not re-guess: this code previously assumed the `get_`-PREFIXED,
    # PARENTHESISED METHOD forms of those same two members, i.e. `get_` + `all_voices()`
    # and `get_` + `default_voice()`. They looked documented, but they were WRONG —
    # no such names exist on the projection. Reading them raised AttributeError, which
    # took down the whole Settings page (the probe runs at page module level) and
    # cascaded into ~32 test failures. (The two bad names are spelled with a `+` above
    # on purpose: a repo gate greps `diana/` and `tests/` and asserts ZERO literal
    # occurrences of them, so writing them out verbatim here — even in a comment —
    # would trip it. Keep the history; keep it unspellable.)
    #
    # Everything ELSE in this branch is stub-CONFIRMED correct and must not be
    # "fixed": `synthesize_text_to_stream_async`, the `synth.voice` getter/setter,
    # `options.speaking_rate`, `VoiceInformation.display_name`/`.gender`/`.id`/
    # `.language`, `SpeechSynthesisStream.size`, `Buffer(capacity)` + the buffer
    # protocol, `stream.read_async(...)`, and `VoiceGender.FEMALE == 1`.
    #
    # winrt imports are LAZY inside each method (never module-top) — matches
    # Diana's lazy-SDK convention and the `; sys_platform == 'win32'` gating, so
    # `import diana.tts.native_os_engine` stays clean on macOS/Linux.

    async def _winrt_synth(self, text: str, voice: str, speed: float) -> bytes:
        """Synthesize one chunk via Windows WinRT and return WAV bytes.

        A bare ``await`` is used on the WinRT awaitable (PyWinRT ``_async``
        methods are awaitable but not real coroutines, so they must not be
        wrapped in a task). Bytes are read out of the ``SpeechSynthesisStream``
        via the Python buffer protocol (``bytes(bytearray(buf))``) rather than a
        stream-reader helper (maintainer guidance,
        github.com/pywinrt/python-winsdk#41). The stream is already a WAV
        container, so the bytes are written straight to a ``.wav`` chunk.
        """
        from winrt.windows.media.speechsynthesis import SpeechSynthesizer
        from winrt.windows.storage.streams import Buffer, InputStreamOptions

        synth = SpeechSynthesizer()
        if voice:                                   # empty id => OS default (D-02)
            for v in SpeechSynthesizer.all_voices:
                if v.id == voice:
                    synth.voice = v
                    break
        # speed 0.5-2.0 maps directly into SpeakingRate's 0.5-6.0 range (default 1.0).
        synth.options.speaking_rate = max(0.5, min(6.0, speed))

        stream = await synth.synthesize_text_to_stream_async(text)   # bare await
        size = stream.size
        buf = Buffer(size)
        await stream.read_async(buf, size, InputStreamOptions.NONE)
        return bytes(bytearray(buf))                 # Python buffer protocol read

    def _winrt_list_voices(self) -> list[TTSVoice]:
        """Enumerate Windows voices, inferring tier from the voice Id (D-06).

        Maps each ``VoiceInformation`` to a ``TTSVoice``. ``VoiceInformation`` has
        no quality/tier property, so tier is inferred from the registry path
        carried in the Id: OneCore neural voices register under ``Speech_OneCore``
        => "standard"; legacy SAPI5 voices under ``Speech\\Voices`` => "compact".
        Sets the D-11 ``self._sapi5_only`` flag when no OneCore voice is present.
        """
        from winrt.windows.media.speechsynthesis import SpeechSynthesizer, VoiceGender

        voices: list[TTSVoice] = []
        for v in SpeechSynthesizer.all_voices:
            vid = v.id or ""
            voices.append(TTSVoice(
                id=vid,
                name=v.display_name,
                language=(v.language or "").lower(),       # e.g. "en-us"
                gender="female" if v.gender == VoiceGender.FEMALE else "male",
                tier="standard" if "OneCore" in vid else "compact",
                bilingual=False,                            # WinRT voices single-language
            ))
        # D-11: flag SAPI5-only (no neural OneCore voice present) for the UI note.
        self._sapi5_only = self.is_sapi5_only(voices)
        return voices

    def _winrt_default_voice_id(self) -> str:
        """Return the OS system default voice id (D-02)."""
        from winrt.windows.media.speechsynthesis import SpeechSynthesizer

        # A Windows image with no installed voices yields the D-02 empty string
        # (let the OS choose) rather than an AttributeError on a None default.
        default = SpeechSynthesizer.default_voice
        if default is None:
            return ""
        return default.id or ""

    @staticmethod
    def is_sapi5_only(voices: list[TTSVoice]) -> bool:
        """True when NO voice is a neural OneCore voice (D-11 SAPI5-only state).

        A clean Windows image may ship only legacy SAPI5 voices (David/Zira),
        whose Ids live under ``Speech\\Voices`` and contain no ``OneCore`` token.
        When that is the case the picker surfaces the visible D-11 note and the
        D-10 download hint, while still producing audio (NATIVE-04).
        """
        return not any("OneCore" in (v.id or "") for v in voices)
