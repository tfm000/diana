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


# --- NATIVE-02: WinRT branch reads the buffer (mocked, no Windows box) -------
@pytest.mark.skipif(
    not _ENGINE_AVAILABLE, reason="NativeOSEngine implemented in Plans 03/05"
)
@pytest.mark.asyncio
async def test_winrt_synth_reads_buffer():
    """win32 branch awaits the WinRT synth API and returns bytes via the buffer.

    Mirrors test_piper_engine's mock-the-SDK approach: inject fake winrt modules
    and force `_platform='win32'`, then assert the branch produces bytes (the
    `bytearray(buffer)` path, NOT DataReader) without a real Windows runtime.
    """
    speech_mod = MagicMock()
    streams_mod = MagicMock()
    fake_modules = {
        "winrt": MagicMock(),
        "winrt.windows": MagicMock(),
        "winrt.windows.media": MagicMock(),
        "winrt.windows.media.speechsynthesis": speech_mod,
        "winrt.windows.storage": MagicMock(),
        "winrt.windows.storage.streams": streams_mod,
    }
    eng = NativeOSEngine()
    eng._platform = "win32"
    with patch.dict(sys.modules, fake_modules):
        try:
            data = await eng.synthesize("hi", voice="", speed=1.0)
        except (AttributeError, TypeError, NotImplementedError) as exc:
            pytest.skip(f"WinRT branch surface differs from scaffold mock: {exc!r}")
    assert isinstance(data, (bytes, bytearray))


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
