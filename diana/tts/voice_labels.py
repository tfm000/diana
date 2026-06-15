"""Custom per-voice label/tag overrides — the editable half of VOICE-06 (D-14/D-15).

A user may rename a voice and override its language / quality tier / gender, plus
add free-text tags, for ANY voice in the cross-engine browser (native_os, Kokoro,
Piper alike — D-15). Each voice's overrides persist as ONE JSON-valued
``app_settings`` key, namespaced ``voice.labels.<engine>.<voice_id>`` — UI-only,
surviving restart without any file editing (the Phase-1 durable-prefs pattern,
matching ``registry.resolve_default_voice``). No schema change: ``set_setting``'s
``ON CONFLICT`` upsert already owns the key/value table.

``apply_overrides`` is the pure merge layered onto ``registry.get_engine_voices``
output: it returns a NEW ``TTSVoice`` via ``dataclasses.replace`` so the result
stays a plain ``TTSVoice`` the existing Phase-3 ``filter_voices`` /
``order_by_quality`` honor unchanged — an overridden language filters correctly and
a custom tag becomes searchable. Mirrors ``native_voices_macos`` / ``catalog``: one
pure transform (``apply_overrides`` / ``search_by_tag``, import-clean and Streamlit-
free) plus thin DB wrappers that lazy-import ``get_setting`` / ``set_setting`` to
keep the DB dependency off module import.

Threat T-04-REDOS: tag and label search is a plain accent-folded substring match
(``_fold`` reused from the Phase-3 helper) — user free-text is NEVER compiled as a
regex. Threat T-04-LBLJSON: ``get_label_overrides`` tolerates an absent/empty/
malformed value (returns ``{}``) and ``apply_overrides`` only replaces known fields,
so a bad stored value can never crash voice enumeration.
"""

import json
import logging
from dataclasses import replace

from diana.tts.base import TTSVoice
from diana.tts.native_os_engine import _fold

logger = logging.getLogger(__name__)

# The TTSVoice fields a user may override via the label editor (D-14). ``id`` is
# deliberately NOT overridable — it is the storage key and the synth handle.
_OVERRIDABLE_FIELDS = ("name", "language", "gender", "tier")


def _label_key(engine: str, voice_id: str) -> str:
    """The namespaced app_settings key for one voice's overrides (D-14)."""
    return f"voice.labels.{engine}.{voice_id}"


def get_label_overrides(db_path: str, engine: str, voice_id: str) -> dict:
    """Return the stored override dict for a voice, or ``{}`` when absent (D-14).

    Reads the single JSON-valued ``voice.labels.<engine>.<voice_id>`` key from
    ``app_settings``. An absent key, an empty value, OR a malformed/corrupt JSON
    value all degrade to ``{}`` rather than raising (T-04-LBLJSON) — a bad stored
    value must never crash the cross-engine browser's enumeration. ``get_setting``
    is imported lazily so the DB dependency stays off module import (mirrors
    ``registry.resolve_default_voice``).
    """
    from diana.database import get_setting

    raw = get_setting(db_path, _label_key(engine, voice_id), None)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "Malformed label override for %s/%s; ignoring", engine, voice_id
        )
        return {}
    return parsed if isinstance(parsed, dict) else {}


def set_label_overrides(
    db_path: str, engine: str, voice_id: str, overrides: dict
) -> None:
    """Persist a voice's override dict as the JSON-valued app_settings key (D-14).

    ``json.dumps`` the dict into ``voice.labels.<engine>.<voice_id>`` via the
    idempotent ``set_setting`` upsert (no schema change). The store is UI-only and
    survives restart. ``set_setting`` is imported lazily (DB dep off module import).
    """
    from diana.database import set_setting

    set_setting(db_path, _label_key(engine, voice_id), json.dumps(overrides))


def apply_overrides(voice: TTSVoice, overrides: dict) -> TTSVoice:
    """Merge stored overrides onto a voice, returning a NEW plain ``TTSVoice`` (D-14).

    For any of ``name`` / ``language`` / ``gender`` / ``tier`` present (and truthy)
    in ``overrides`` the corresponding field is replaced via ``dataclasses.replace``;
    a ``tags`` list in ``overrides`` is merged into ``voice.tags`` as a de-duplicated
    tuple (order-preserving — existing tags first, then any new ones). An empty/absent
    ``overrides`` is a no-op (returns an equivalent voice). The result is a plain
    ``TTSVoice`` so the Phase-3 ``filter_voices`` / ``order_by_quality`` honor the
    overridden attributes unchanged: an overridden ``language`` filters correctly and
    a merged tag becomes searchable via :func:`search_by_tag`. Pure / Streamlit-free /
    no I/O — unit-testable.
    """
    if not overrides:
        return replace(voice)

    merged = {
        field: overrides[field]
        for field in _OVERRIDABLE_FIELDS
        if overrides.get(field)
    }

    new_tags = overrides.get("tags")
    if new_tags:
        combined: list[str] = list(voice.tags)
        seen = {t for t in combined}
        for tag in new_tags:
            text = str(tag).strip()
            if text and text not in seen:
                seen.add(text)
                combined.append(text)
        merged["tags"] = tuple(combined)

    return replace(voice, **merged)


def search_by_tag(voices: list[TTSVoice], query: str) -> list[TTSVoice]:
    """Filter voices whose custom tags contain ``query`` as a plain substring (D-14).

    Accent-insensitive (``_fold``, reused from the Phase-3 helper) substring
    containment over each voice's ``tags`` tuple — so a search for "audio" finds a
    voice tagged "audiobook". Threat T-04-REDOS: the query is matched with ``in``
    over folded strings and is NEVER compiled as a regex, so a regex-special query
    (e.g. ``"("``) is treated literally and can neither raise nor cause ReDoS. An
    empty/whitespace query matches nothing (so the caller can OR it with a separate
    name search). The input list is never mutated; a new list is returned.
    """
    needle = _fold((query or "").strip())
    if not needle:
        return []
    return [v for v in voices if any(needle in _fold(t) for t in v.tags)]
