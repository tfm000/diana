"""Wave-0 RED/skip scaffolds for the macOS `say -v '?'` voice parser (Plan 02).

The symbols under test (``enumerate_macos_voices`` and the curated tier/bilingual
prelabel logic in ``diana.tts.native_voices_macos``, plus the ``tier``/``bilingual``
fields on ``diana.tts.base.TTSVoice``) do NOT exist yet — they land in Plan 02.

Collection must stay GREEN in Wave 0, so every symbol import is guarded and the
symbol-dependent tests are ``skipif``-gated. Each test carries a real assertion
body (not ``pass``), so the moment Plan 02 implements the parser the ``skipif``
predicate flips to False and these become meaningful regression gates with zero
test-file edits.

Fixture: ``tests/fixtures/say_voices.txt`` (captured live, 184 voices, incl.
nested-parenthetical names like "Eddy (English (US))" and non-ASCII names).
Requirements: NATIVE-03 (dynamic enumeration / parser), NATIVE-05 (attributes).
"""

from pathlib import Path

import pytest

# --- Guarded imports: the parser module lands in Plan 02 ---------------------
try:
    from diana.tts.native_voices_macos import enumerate_macos_voices  # noqa: F401

    _PARSER_AVAILABLE = True
except ImportError:
    enumerate_macos_voices = None  # type: ignore[assignment]
    _PARSER_AVAILABLE = False

# A pure string -> list[TTSVoice] parse step is the testability seam (RESEARCH
# "Macros for testability"). Plan 02 may expose it under either of these names;
# probe both so this scaffold binds to whichever the implementer chooses.
try:  # pragma: no cover - import probe
    from diana.tts.native_voices_macos import parse_say_voices as _parse_say  # type: ignore
except ImportError:  # pragma: no cover - import probe
    try:
        from diana.tts.native_voices_macos import _parse_say_output as _parse_say  # type: ignore
    except ImportError:
        _parse_say = None  # type: ignore[assignment]

# TTSVoice always exists; the tier/bilingual *fields* are added in Plan 02.
from diana.tts.base import TTSVoice

_HAS_TIER_FIELDS = hasattr(TTSVoice("i", "n", "l", "g"), "tier") and hasattr(
    TTSVoice("i", "n", "l", "g"), "bilingual"
)

_FIXTURE = Path(__file__).parent / "fixtures" / "say_voices.txt"


def _parse_fixture():
    """Feed the captured fixture text to whichever parse seam Plan 02 exposes.

    Prefers the pure ``parse_say_voices(text)`` seam (no subprocess); falls back
    to mocking ``subprocess.run`` so the public ``enumerate_macos_voices()`` is
    driven from the fixture instead of the live machine.
    """
    text = _FIXTURE.read_text(encoding="utf-8")
    if _parse_say is not None:
        return _parse_say(text)
    # Fall back to driving the public entry point off the fixture via a mock.
    from unittest.mock import MagicMock, patch

    completed = MagicMock(stdout=text, returncode=0)
    with patch("diana.tts.native_voices_macos.subprocess.run", return_value=completed):
        return enumerate_macos_voices()


# --- Fixture sanity (runs in Wave 0 regardless of implementation) -----------
def test_fixture_present_and_shaped():
    """The committed say fixture exists and carries the parser's edge cases."""
    assert _FIXTURE.is_file(), "tests/fixtures/say_voices.txt must be committed"
    lines = [ln for ln in _FIXTURE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) >= 30, "stock-Mac say -v '?' yields well over 30 voices"
    # Every non-blank line is a voice line ending in a '# <sample>' delimiter.
    assert all("#" in ln for ln in lines)
    # At least one nested-parenthetical name (the case naive .split() breaks on).
    assert any("(" in ln.split("#")[0] for ln in lines)


# --- NATIVE-03: parser maps every line -> TTSVoice --------------------------
@pytest.mark.skipif(
    not (_PARSER_AVAILABLE and (_parse_say is not None or enumerate_macos_voices)),
    reason="diana.tts.native_voices_macos parser implemented in Plan 02",
)
def test_parse_say_output():
    """Every non-blank `say -v '?'` line parses to a TTSVoice; parens survive."""
    voices = _parse_fixture()
    non_blank = [ln for ln in _FIXTURE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(voices) == len(non_blank), "every non-blank line -> exactly one voice"
    assert all(isinstance(v, TTSVoice) for v in voices)
    # A nested-parenthetical name keeps its name and extracts a real locale.
    eddy = next((v for v in voices if v.name.startswith("Eddy (English (US))")), None)
    assert eddy is not None, "parenthetical-name voice must parse (no .split() bug)"
    assert eddy.language.replace("_", "-").lower().startswith("en-us")
    # Non-ASCII display names round-trip intact.
    assert any(any(ord(c) > 127 for c in v.name) for v in voices)


# --- NATIVE-05: TTSVoice carries tier/bilingual -----------------------------
@pytest.mark.skipif(
    not _HAS_TIER_FIELDS,
    reason="TTSVoice.tier/.bilingual fields added in Plan 02",
)
def test_voice_has_tier():
    """A parsed voice exposes the new `.tier` and `.bilingual` attributes."""
    voices = _parse_fixture() if _PARSER_AVAILABLE else [TTSVoice("i", "n", "l", "g")]
    v = voices[0]
    assert hasattr(v, "tier") and isinstance(v.tier, str)
    assert hasattr(v, "bilingual") and isinstance(v.bilingual, bool)


# --- NATIVE-05: tier classification of known macOS names --------------------
@pytest.mark.skipif(
    not (_PARSER_AVAILABLE and _HAS_TIER_FIELDS),
    reason="tier classification implemented in Plan 02",
)
def test_tier_classification():
    """Known novelty names -> 'novelty'; a plain preinstalled voice -> 'compact'."""
    voices = _parse_fixture()
    by_name = {v.name: v for v in voices}
    # Novelty group (RESEARCH Pattern 5): Zarvox / Bells / Bahh etc.
    novelty = next(
        (by_name[n] for n in ("Zarvox", "Bells", "Bahh", "Boing") if n in by_name),
        None,
    )
    assert novelty is not None, "fixture should contain a known novelty voice"
    assert novelty.tier == "novelty"
    # A plain, non-novelty preinstalled voice classifies as 'compact'.
    plain = next(
        (by_name[n] for n in ("Samantha", "Daniel", "Karen", "Moira") if n in by_name),
        None,
    )
    assert plain is not None, "fixture should contain a plain compact voice"
    assert plain.tier in {"compact", "enhanced"}
    assert plain.tier != "novelty"


# --- NATIVE-04: macOS smoke (real subprocess) -------------------------------
@pytest.mark.skipif(
    not _PARSER_AVAILABLE,
    reason="enumerate_macos_voices() implemented in Plan 02",
)
def test_enumerate_real_say():
    """On a real Mac, live `say -v '?'` enumeration returns >= 1 voice."""
    import sys

    if sys.platform != "darwin":
        pytest.skip("real `say` enumeration is macOS-only")
    voices = enumerate_macos_voices()
    assert len(voices) >= 1
    assert all(isinstance(v, TTSVoice) for v in voices)
