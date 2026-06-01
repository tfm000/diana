"""macOS `say -v '?'` voice catalog parser and curated prelabel map.

Turns the macOS `say` voice listing into ``list[TTSVoice]`` with descriptive
attributes (NATIVE-03 dynamic enumeration, NATIVE-05 attributes/labels, D-04/D-06).

The `say -v '?'` line format is ``<name><2+ spaces><locale><2+ spaces># <sample>``.
Names may contain spaces and nested parentheses ("Eddy (English (US))") and
non-ASCII characters ("Amélie"), so the catalog is parsed with a locale-anchored
regex (``_SAY_LINE``) — never ``.split()``, which breaks on parenthetical names.

`say` does not expose a quality tier, so known voices are prelabelled from a
curated map (D-06): the novelty gimmick voices (``_NOVELTY``) and the classic
enhanced voices (``_ENHANCED``); every other preinstalled voice falls back to
``compact``. Parsing is pure and unit-testable against a captured fixture via
``parse_say_voices(text)``; ``enumerate_macos_voices()`` shells real `say`.
"""

import re
import subprocess

from diana.tts.base import TTSVoice

# Each `say -v '?'` line: a free-form name (may include spaces / nested parens /
# non-ASCII), then 2+ spaces, a locale token (ll[_-RR], e.g. en_US, fr_CA, yue_CN),
# then 2+ spaces, '#', and a sample sentence. Anchoring on the locale token is what
# makes parenthetical names like "Eddy (English (US))" parse correctly.
_SAY_LINE = re.compile(
    r"^(?P<name>.+?)\s+(?P<locale>[a-z]{2,3}(?:[_-][A-Za-z0-9]{2,4})?)\s+#\s*(?P<sample>.*)$"
)

# Curated quality-tier prelabels (D-06). Keys are the `say` base names (the region
# in parentheses, if any, is stripped before lookup). Novelty = the gimmick voices
# Apple groups under "English (United States) - Novelty"; enhanced = the classic
# higher-quality voice(s). Everything else preinstalled => "compact" (the fallback).
_NOVELTY = {
    "Albert", "Bad News", "Bahh", "Bells", "Boing", "Bubbles", "Cellos",
    "Good News", "Jester", "Organ", "Superstar", "Trinoids", "Whisper",
    "Wobble", "Zarvox", "Junior", "Ralph", "Kathy", "Fred", "Deranged",
}
_ENHANCED = {"Alex"}


def _tier_for(base_name: str) -> str:
    """Classify a voice's quality tier from its base name (D-06 prelabel map)."""
    if base_name in _NOVELTY:
        return "novelty"
    if base_name in _ENHANCED:
        return "enhanced"
    return "compact"


def parse_say_voices(text: str) -> list[TTSVoice]:
    """Parse `say -v '?'` output text into a list of tiered TTSVoice objects.

    Pure (no subprocess) so it is unit-testable from a captured fixture. Every
    non-blank line that matches ``_SAY_LINE`` becomes one TTSVoice; malformed
    lines are skipped (best-effort — a garbage line is dropped, not crashed on).
    """
    voices: list[TTSVoice] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        m = _SAY_LINE.match(line)
        if not m:
            continue
        name = m.group("name").strip()
        locale = m.group("locale").replace("_", "-").lower()   # en_US -> en-us
        base = name.split(" (")[0]                              # strip "(English (US))"
        voices.append(TTSVoice(
            id=name,                # `say -v <name>` accepts the display name as the id
            name=name,
            language=locale,
            gender="unknown",       # `say` does not expose gender
            tier=_tier_for(base),
            bilingual=False,        # `say` voices are single-language
        ))
    return voices


def enumerate_macos_voices() -> list[TTSVoice]:
    """Shell macOS `say -v '?'` and return its voice catalog as tiered TTSVoice objects.

    Uses list-argv ``subprocess.run`` (never ``shell=True``) with a timeout so no
    input can inject shell metacharacters and a hung `say` is bounded (T-03-03/04).
    """
    proc = subprocess.run(
        ["/usr/bin/say", "-v", "?"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return parse_say_voices(proc.stdout)
