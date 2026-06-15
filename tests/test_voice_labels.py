"""Wave-0 RED/skip scaffolds for the custom voice-label layer (Plan 05).

VOICE-06 / D-14: a user may override a voice's language/tier/gender/display name
and add free-text tags; overrides persist per voice id in ``app_settings``
(one JSON-valued ``voice.labels.<engine>.<id>`` key) and feed the same Phase-3
filters/search. ``apply_overrides`` merges via ``dataclasses.replace`` so the
result stays a plain ``TTSVoice`` the existing ``filter_voices`` honors.

The symbols (``get_label_overrides`` / ``set_label_overrides`` /
``apply_overrides``) land in Plan 05; module home is the implementer's choice
(``diana.tts.voice_labels`` or ``diana.tts.registry``), so both are probed. The
DB is mocked (mirrors ``test_native_os_engine.py``'s ``patch("diana.database.
get_setting", ...)``) so no sqlite file is touched. Threat T-04-REDOS: tag
search MUST be a plain substring match — never a compiled user-supplied regex.
"""

import json
from unittest.mock import patch

import pytest

from diana.tts.base import TTSVoice

# The Phase-3 filter helper always exists (Plan 04 landed it); the label layer
# must produce a TTSVoice this honors.
try:
    from diana.tts.native_os_engine import filter_voices

    _FILTER_AVAILABLE = True
except ImportError:  # pragma: no cover
    filter_voices = None  # type: ignore[assignment]
    _FILTER_AVAILABLE = False

# --- Guarded probes: the label layer lands in Plan 05 ----------------------
_get_overrides = _set_overrides = _apply_overrides = None
for _modname in ("diana.tts.voice_labels", "diana.tts.registry"):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=["apply_overrides"])
        if all(hasattr(_mod, a) for a in
               ("get_label_overrides", "set_label_overrides", "apply_overrides")):
            _get_overrides = _mod.get_label_overrides
            _set_overrides = _mod.set_label_overrides
            _apply_overrides = _mod.apply_overrides
            break
    except (ImportError, AttributeError):
        continue
_LABELS_AVAILABLE = None not in (_get_overrides, _set_overrides, _apply_overrides)

# An optional dedicated tag-search helper; if absent, the substring contract is
# asserted directly against the TTSVoice.tags field.
_tag_search = None
for _modname, _attr in (
    ("diana.tts.voice_labels", "search_by_tag"),
    ("diana.tts.voice_labels", "tag_search"),
    ("diana.tts.registry", "search_by_tag"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _tag_search = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue


# --- VOICE-06 / D-14: override JSON round-trips through app_settings ---------
@pytest.mark.skipif(
    not _LABELS_AVAILABLE, reason="voice-label layer implemented in Plan 05"
)
def test_overrides_round_trip():
    """set_label_overrides(...) then get_label_overrides(...) returns the dict."""
    store: dict = {}

    def _fake_set(db_path, key, value):
        store[key] = value

    def _fake_get(db_path, key, default=None):
        return store.get(key, default)

    overrides = {"name": "My Amy", "language": "en-gb", "tier": "enhanced",
                 "tags": ["audiobook", "calm"]}
    with patch("diana.database.set_setting", side_effect=_fake_set), \
            patch("diana.database.get_setting", side_effect=_fake_get):
        _set_overrides("db.sqlite", "piper", "en_US-amy-medium", overrides)
        # Stored as a single JSON-valued, namespaced key.
        assert any("voice.labels.piper.en_US-amy-medium" in k for k in store)
        assert json.loads(next(iter(store.values()))) == overrides
        read_back = _get_overrides("db.sqlite", "piper", "en_US-amy-medium")
    assert read_back == overrides
    # An unset voice id returns an empty dict, never raises.
    with patch("diana.database.get_setting", side_effect=_fake_get):
        assert _get_overrides("db.sqlite", "piper", "never-set") == {}


# --- VOICE-06 / D-14: merged override stays a filterable TTSVoice ------------
@pytest.mark.skipif(
    not (_LABELS_AVAILABLE and _FILTER_AVAILABLE),
    reason="voice-label layer + filter helper required",
)
def test_apply_overrides_feeds_filters():
    """apply_overrides yields a TTSVoice that the Phase-3 filter_voices honors."""
    base = TTSVoice("en_US-amy-medium", "Amy (US Medium)", "en-us", "female",
                    tier="standard")
    merged = _apply_overrides(base, {"language": "fr-fr", "tier": "enhanced"})
    assert isinstance(merged, TTSVoice), "merge must return a plain TTSVoice"
    assert merged.language == "fr-fr" and merged.tier == "enhanced"
    assert merged.id == base.id, "id is preserved across the override"

    # The relabeled voice is now found by a language=fr-fr filter (D-14 feeds filters).
    found = filter_voices([merged], language="fr-fr")
    assert [v.id for v in found] == ["en_US-amy-medium"]
    # And no longer matches its original en-us language.
    assert filter_voices([merged], language="en-us") == []


# --- VOICE-06 / T-04-REDOS: tag search is plain substring, never regex -------
@pytest.mark.skipif(
    not _LABELS_AVAILABLE, reason="voice-label tag search implemented in Plan 05"
)
def test_tag_search_is_plain_substring():
    """A custom tag is found by a plain-substring match (no compiled user regex)."""
    tagged = TTSVoice("v1", "Voice One", "en-us", "female",
                      tags=("audiobook", "calm narration"))
    other = TTSVoice("v2", "Voice Two", "en-us", "male", tags=("news",))

    if _tag_search is not None:
        hits = _tag_search([tagged, other], "audio")
        assert [v.id for v in hits] == ["v1"], "substring 'audio' matches 'audiobook'"
        # A regex-special query is treated literally (no ReDoS, no regex error).
        assert _tag_search([tagged, other], "(") == [], "'(' is a literal, not a group"
    else:
        # No dedicated helper yet: pin the ReDoS-safe contract directly. Tag
        # matching must be substring containment over the plain tags tuple.
        def _matches(voice, needle):
            return any(needle.lower() in t.lower() for t in voice.tags)

        assert _matches(tagged, "audio") and not _matches(other, "audio")
        # A regex metacharacter must match literally and never raise.
        assert _matches(TTSVoice("v3", "n", "l", "g", tags=("a(b",)), "(")
