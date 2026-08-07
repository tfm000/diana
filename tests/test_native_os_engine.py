"""Wave-0 RED/skip scaffolds for NativeOSEngine + voice picker helpers.

The symbols under test land in later plans:
  - ``diana.tts.native_os_engine.NativeOSEngine`` (sys.platform dispatch, macOS
    `say` synth, WinRT branch, default_voice) — Plans 03/05.
  - the pure ``filter_voices(voices, language=, tier=, query=)`` helper — Plan 04.
  - the per-engine default-voice resolver over ``app_settings`` (D-03) — Plan 03/04.

Collection stays GREEN in Wave 0: every future symbol is import-guarded and the
dependent tests are ``skipif``-gated with a real assertion body, so they flip to
live regression gates as each plan lands (no edits needed here).

The WinRT branch is exercised on this macOS box exactly like ``test_piper_engine``
mocks an absent SDK: ``patch.dict("sys.modules", {...})`` + forcing the engine's
``_platform = "win32"``. Real WinRT behavior is Windows-only UAT (see VALIDATION).

Requirements: NATIVE-01 (macOS synth/default), NATIVE-02 (WinRT + SAPI5 fallback),
NATIVE-05 (default-voice validation, filter/search).
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from diana.tts.base import TTSVoice

# --- Guarded imports: these land in Plans 03/04/05 --------------------------
try:
    from diana.tts.native_os_engine import NativeOSEngine  # noqa: F401

    _ENGINE_AVAILABLE = True
except ImportError:
    NativeOSEngine = None  # type: ignore[assignment]
    _ENGINE_AVAILABLE = False

# The pure filter helper (Plan 04). Probe the likely homes (engine module or a
# dedicated voices/UI-helper module) so the scaffold binds wherever it lands.
_filter_voices = None
for _modname, _attr in (
    ("diana.tts.native_os_engine", "filter_voices"),
    ("diana.tts.native_voices_macos", "filter_voices"),
    ("diana.dashboard.voice_picker", "filter_voices"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _filter_voices = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue
_FILTER_AVAILABLE = _filter_voices is not None

# The per-engine default-voice resolver (D-03). Probe likely homes.
_resolve_default_voice = None
for _modname, _attr in (
    ("diana.tts.registry", "resolve_default_voice"),
    ("diana.tts.native_os_engine", "resolve_default_voice"),
    ("diana.dashboard.voice_picker", "resolve_default_voice"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _resolve_default_voice = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue
_RESOLVER_AVAILABLE = _resolve_default_voice is not None

# The None/empty-safe picker glue (Plan 04 checkpoint regression): maps a
# selectbox's selected display name to a voice id without crashing when the
# filtered option list is empty (selectbox returns None -> KeyError: None).
_resolve_selected_voice_id = None
for _modname, _attr in (
    ("diana.tts.native_os_engine", "resolve_selected_voice_id"),
    ("diana.dashboard.voice_picker", "resolve_selected_voice_id"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _resolve_selected_voice_id = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue
_SELECT_RESOLVER_AVAILABLE = _resolve_selected_voice_id is not None

# TTSVoice tier/bilingual fields (Plan 02) — needed for filter-by-tier.
_HAS_TIER_FIELDS = hasattr(TTSVoice("i", "n", "l", "g"), "tier")


def _sample_voices():
    """A small TTSVoice list for pure-helper tests (tier/bilingual when present)."""
    if _HAS_TIER_FIELDS:
        return [
            TTSVoice("Samantha", "Samantha", "en-us", "female", tier="compact"),
            TTSVoice("Daniel", "Daniel", "en-gb", "male", tier="enhanced"),
            TTSVoice("Amelie", "Amélie", "fr-ca", "female", tier="compact"),
            TTSVoice("Zarvox", "Zarvox", "en-us", "male", tier="novelty"),
        ]
    return [
        TTSVoice("Samantha", "Samantha", "en-us", "female"),
        TTSVoice("Daniel", "Daniel", "en-gb", "male"),
        TTSVoice("Amelie", "Amélie", "fr-ca", "female"),
        TTSVoice("Zarvox", "Zarvox", "en-us", "male"),
    ]


# --- NATIVE-01: macOS synth returns a WAV (mock subprocess) -----------------
@pytest.mark.skipif(
    not _ENGINE_AVAILABLE, reason="NativeOSEngine implemented in Plan 03"
)
@pytest.mark.asyncio
async def test_macos_synthesize_returns_wav(tmp_path):
    """macOS branch shells `say` and returns bytes with a RIFF/WAVE header."""
    eng = NativeOSEngine()
    eng._platform = "darwin"
    riff = b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt "

    def _fake_run(cmd, *a, **k):
        # The output path is the argv element following '-o'.
        out = cmd[cmd.index("-o") + 1]
        from pathlib import Path as _P

        _P(out).write_bytes(riff)
        return MagicMock(returncode=0, stderr="")

    with patch("diana.tts.native_os_engine.subprocess.run", side_effect=_fake_run):
        data = await eng.synthesize("hello world", voice="Samantha", speed=1.0)
    assert isinstance(data, (bytes, bytearray))
    assert bytes(data[:4]) == b"RIFF" and bytes(data[8:12]) == b"WAVE"


# --- NATIVE-04: macOS real synth smoke (real `say`) -------------------------
@pytest.mark.skipif(
    not _ENGINE_AVAILABLE, reason="NativeOSEngine implemented in Plan 03"
)
@pytest.mark.asyncio
async def test_macos_real_synth_smoke():
    """Real `say` synth -> non-empty, pydub-readable WAV (macOS-only smoke)."""
    if sys.platform != "darwin":
        pytest.skip("real `say` synthesis is macOS-only")
    import io

    from pydub import AudioSegment

    eng = NativeOSEngine()
    eng.initialize()
    try:
        data = await eng.synthesize("Diana smoke test.", voice="", speed=1.0)
    finally:
        eng.shutdown()
    assert data, "synthesis must return non-empty bytes"
    seg = AudioSegment.from_file(io.BytesIO(data), format="wav")
    assert len(seg) > 0


# --- WinRT fakes: REAL classes, deliberately NOT MagicMock ------------------
# A MagicMock auto-creates ANY attribute, so the previous fakes pinned nothing:
# `SpeechSynthesizer.get_all_voices()` silently "worked" and returned an iterable
# MagicMock, and the first-ever Windows CI run (quick-260807-3yx) then failed 39
# tests on two names that do not exist on the real projection.
#
# A plain Python class with plain CLASS attributes reads identically to a
# metaclass property from the caller's side (`SpeechSynthesizer.all_voices`),
# AND raises AttributeError on the wrong spelling — so the fake becomes a real
# gate on the pinned API surface instead of a rubber stamp.

_ONECORE_ID = r"HKEY_LOCAL_MACHINE\...\Speech_OneCore\Voices\Tokens\MSTTS_V110_enUS_AriaM"
_SAPI5_ID = r"HKEY_LOCAL_MACHINE\...\Speech\Voices\Tokens\TTS_MS_EN-US_DAVID_11.0"


class _FakeVoiceInfo:
    """The four ``VoiceInformation`` properties the engine reads."""

    def __init__(self, id, display_name, language, gender):
        self.id = id
        self.display_name = display_name
        self.language = language
        self.gender = gender


class _FakeVoiceGender:
    """Real WinRT IntEnum values from the winrt-* 3.2.1 stubs (MALE=0, FEMALE=1)."""

    MALE = 0
    FEMALE = 1


class _FakeSpeechSynthesizer:
    """Stand-in for the WinRT ``SpeechSynthesizer``.

    ``all_voices`` and ``default_voice`` are plain CLASS attributes, which read
    exactly like the ``@_property`` members the real ``SpeechSynthesizer_Static``
    metaclass exposes — and raise AttributeError for any other spelling.
    """

    all_voices = [
        _FakeVoiceInfo(_ONECORE_ID, "Aria", "en-US", _FakeVoiceGender.FEMALE),
        _FakeVoiceInfo(_SAPI5_ID, "David", "en-US", _FakeVoiceGender.MALE),
    ]
    default_voice = _FakeVoiceInfo(
        _ONECORE_ID, "Aria", "en-US", _FakeVoiceGender.FEMALE
    )

    def __init__(self):
        self.voice = None                       # settable, like the real setter
        self.options = SimpleNamespace(speaking_rate=1.0)

    async def synthesize_text_to_stream_async(self, text):  # pragma: no cover
        raise AssertionError("synth tests must supply their own stream fake")


def _winrt_fake_modules(synth_cls=None):
    """Build the six-key winrt ``sys.modules`` map for ``patch.dict``.

    Only the two SYMBOLS that pin the API (``SpeechSynthesizer``, ``VoiceGender``)
    are real classes; the module objects themselves stay MagicMocks. The stream
    fakes are unchanged — ``Buffer(size)`` is a real ``bytearray`` so the
    buffer-protocol read stays the thing that produces the returned bytes.
    """
    speech_mod = MagicMock()
    speech_mod.SpeechSynthesizer = synth_cls or _FakeSpeechSynthesizer
    speech_mod.VoiceGender = _FakeVoiceGender

    streams_mod = MagicMock()
    streams_mod.Buffer = lambda size: bytearray(size)
    streams_mod.InputStreamOptions = MagicMock()

    return {
        "winrt": MagicMock(),
        "winrt.windows": MagicMock(),
        "winrt.windows.media": MagicMock(),
        "winrt.windows.media.speechsynthesis": speech_mod,
        "winrt.windows.storage": MagicMock(),
        "winrt.windows.storage.streams": streams_mod,
    }


# --- NATIVE-02: WinRT branch reads the buffer (mocked, no Windows box) -------
@pytest.mark.skipif(
    not _ENGINE_AVAILABLE, reason="NativeOSEngine implemented in Plans 03/05"
)
@pytest.mark.asyncio
async def test_winrt_synth_reads_buffer():
    """win32 branch awaits the WinRT synth API and returns bytes via the buffer.

    Mirrors test_piper_engine's mock-the-SDK approach: inject fake winrt modules
    and force `_platform='win32'`, then assert the branch produces bytes via the
    `bytes(bytearray(buffer))` path (NOT DataReader) without a real Windows
    runtime. The fake `synthesize_text_to_stream_async` / `read_async` are async
    so the branch's bare `await` (NOT create_task) is exercised, and the fake
    `Buffer` is a real `bytearray` so the buffer-protocol read is what produces
    the returned bytes — a DataReader path would never touch this buffer.
    """
    payload = b"RIFF\x00\x00\x00\x00WAVEfmt "

    async def _fake_synth_to_stream(_text):
        stream = MagicMock()
        stream.size = len(payload)

        async def _fake_read_async(buf, _size, _opts):
            # WinRT read_async fills the passed buffer in place; our fake Buffer
            # is a bytearray, so write the payload into it (buffer-protocol path).
            buf[: len(payload)] = payload
            return MagicMock()

        stream.read_async = _fake_read_async
        return stream

    class _SynthFake(_FakeSpeechSynthesizer):
        """Records its instances so the test can inspect the assigned voice."""

        instances = []

        def __init__(self):
            super().__init__()
            self.synthesize_text_to_stream_async = _fake_synth_to_stream
            type(self).instances.append(self)

    eng = NativeOSEngine()
    eng._platform = "win32"
    # A NON-empty voice id exercises the `all_voices` loop (an empty id
    # short-circuits it), so the pinned property spelling is actually read.
    with patch.dict(sys.modules, _winrt_fake_modules(_SynthFake)):
        data = await eng.synthesize("hi", voice=_ONECORE_ID, speed=1.0)
    assert isinstance(data, (bytes, bytearray))
    assert bytes(data) == payload          # bytes came from the bytearray(buffer) path
    # The matched VoiceInformation was assigned through the `voice` setter — this
    # is what fails (AttributeError) if the `all_voices` spelling regresses.
    assert _SynthFake.instances[-1].voice is _FakeSpeechSynthesizer.all_voices[0]


# --- NATIVE-02: enumeration reads the `all_voices` PROPERTY (pinned A1) ------
@pytest.mark.skipif(
    not _ENGINE_AVAILABLE, reason="NativeOSEngine implemented in Plans 03/05"
)
def test_winrt_list_voices_uses_all_voices_property():
    """`_winrt_list_voices` reads the class-attribute property, not a `get_*()`.

    Also pins the VoiceInformation -> TTSVoice mapping: tier inferred from the
    registry path in the Id (D-06), language lowercased, gender via the real
    VoiceGender IntEnum values, and the D-11 SAPI5-only flag left False when a
    OneCore voice is present.
    """
    eng = NativeOSEngine()
    eng._platform = "win32"
    with patch.dict(sys.modules, _winrt_fake_modules()):
        voices = eng.list_voices()

    assert [v.id for v in voices] == [_ONECORE_ID, _SAPI5_ID]
    assert [v.name for v in voices] == ["Aria", "David"]
    assert [v.language for v in voices] == ["en-us", "en-us"]   # lowercased
    assert [v.gender for v in voices] == ["female", "male"]     # via VoiceGender
    assert [v.tier for v in voices] == ["standard", "compact"]  # OneCore vs SAPI5
    assert all(v.bilingual is False for v in voices)
    assert eng._sapi5_only is False                             # D-11: OneCore present


# --- NATIVE-02: default voice reads the `default_voice` PROPERTY (pinned A1) --
@pytest.mark.skipif(
    not _ENGINE_AVAILABLE, reason="NativeOSEngine implemented in Plans 03/05"
)
def test_winrt_default_voice_id_uses_default_voice_property():
    """`default_voice()` returns the id off the class-attribute property."""
    eng = NativeOSEngine()
    eng._platform = "win32"
    with patch.dict(sys.modules, _winrt_fake_modules()):
        assert eng.default_voice() == _ONECORE_ID


# --- NATIVE-02: a voice-less Windows image degrades to the D-02 empty id ------
@pytest.mark.skipif(
    not _ENGINE_AVAILABLE, reason="NativeOSEngine implemented in Plans 03/05"
)
def test_winrt_default_voice_id_none_is_empty():
    """A None `default_voice` yields "" (OS default, D-02), never AttributeError."""

    class _NoVoiceFake(_FakeSpeechSynthesizer):
        all_voices = []
        default_voice = None

    eng = NativeOSEngine()
    eng._platform = "win32"
    with patch.dict(sys.modules, _winrt_fake_modules(_NoVoiceFake)):
        assert eng.default_voice() == ""


# --- NATIVE-02: SAPI5-only detection sets the D-11 flag (mocked) -------------
@pytest.mark.skipif(
    not _ENGINE_AVAILABLE, reason="NativeOSEngine implemented in Plans 03/05"
)
def test_sapi5_only_flagged():
    """A voice list with no `OneCore` id is flagged SAPI5-only (D-11)."""
    sapi5_only = [
        TTSVoice(r"HKLM\...\Speech\Voices\Tokens\TTS_MS_EN-US_DAVID_11.0",
                 "David", "en-us", "male"),
        TTSVoice(r"HKLM\...\Speech\Voices\Tokens\TTS_MS_EN-US_ZIRA_11.0",
                 "Zira", "en-us", "female"),
    ]
    eng = NativeOSEngine()
    eng._platform = "win32"
    flagger = getattr(eng, "is_sapi5_only", None) or getattr(eng, "_is_sapi5_only", None)
    if flagger is None:
        pytest.skip("SAPI5-only detection helper lands with the WinRT branch (Plan 05)")
    assert flagger(sapi5_only) is True
    has_onecore = sapi5_only + [
        TTSVoice(r"HKLM\...\Speech_OneCore\Voices\Tokens\MSTTS_V110_enUS_AriaM",
                 "Aria", "en-us", "female"),
    ]
    assert flagger(has_onecore) is False


# --- NATIVE-05: per-engine default never preselects a missing voice (D-03) ---
@pytest.mark.skipif(
    not _RESOLVER_AVAILABLE,
    reason="per-engine default-voice resolver implemented in Plan 03/04",
)
def test_default_voice_validation():
    """A remembered id absent from the live list is NOT preselected; uses default."""
    voices = _sample_voices()
    live_ids = {v.id for v in voices}
    engine_default = "Samantha"

    with patch("diana.database.get_setting", return_value="GhostVoice") as _gs:
        resolved = _resolve_default_voice(
            "db.sqlite", "native_os", voices, engine_default
        )
    assert resolved not in {"GhostVoice"}
    assert resolved == engine_default  # falls back to engine/system default (D-02)

    with patch("diana.database.get_setting", return_value="Daniel"):
        resolved2 = _resolve_default_voice(
            "db.sqlite", "native_os", voices, engine_default
        )
    assert resolved2 == "Daniel" and resolved2 in live_ids  # honored only if valid


# --- NATIVE-05: pure filter/search over the voice list ----------------------
@pytest.mark.skipif(
    not _FILTER_AVAILABLE, reason="filter_voices helper implemented in Plan 04"
)
def test_voice_filter_search():
    """`filter_voices` filters by language/tier and searches by name."""
    voices = _sample_voices()

    # Language filter.
    en = _filter_voices(voices, language="en-us")
    assert {v.id for v in en} == {"Samantha", "Zarvox"}

    # Name search (case-insensitive substring), incl. non-ASCII display name.
    found = _filter_voices(voices, query="amel")
    assert [v.id for v in found] == ["Amelie"]

    # No filters -> full list unchanged.
    assert len(_filter_voices(voices)) == len(voices)

    # Tier filter (only when the tier field exists).
    if _HAS_TIER_FIELDS:
        novelty = _filter_voices(voices, tier="novelty")
        assert {v.id for v in novelty} == {"Zarvox"}


# --- NATIVE-05 checkpoint regression: empty-filter picker must not crash -----
@pytest.mark.skipif(
    not _SELECT_RESOLVER_AVAILABLE,
    reason="resolve_selected_voice_id picker glue implemented in Plan 04",
)
def test_resolve_selected_voice_id_empty_filter_no_crash():
    """An empty filtered list (selectbox -> None) yields the empty-id fallback.

    Reproduces the live KeyError: None crash on the Upload/Settings voice picker
    when the language/quality filters or the name search match no voice. The old
    glue did ``voice_options[selected_name]``; with an empty option list the
    selectbox returns ``None`` and indexing raised. The fix must return ``""``
    (use the engine/OS default) instead of raising.
    """
    # Empty options + None selection (the exact crash scenario) -> "" , no raise.
    assert _resolve_selected_voice_id({}, None) == ""

    # A non-empty catalog but a None selection (filters narrowed to empty on this
    # rerun while a stale dict lingers) must also be None-safe, never KeyError.
    voice_options = {v.name: v.id for v in _sample_voices()}
    assert _resolve_selected_voice_id(voice_options, None) == ""

    # An empty-string selection is treated as "no selection" -> "".
    assert _resolve_selected_voice_id(voice_options, "") == ""

    # A name absent from the options (cross-engine / stale) -> "" , not KeyError.
    assert _resolve_selected_voice_id(voice_options, "GhostVoice") == ""

    # The happy path still resolves a real selection to its id.
    assert _resolve_selected_voice_id(voice_options, "Amélie") == "Amelie"
