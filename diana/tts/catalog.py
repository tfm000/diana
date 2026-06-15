"""Piper voice catalog: parse the rhasspy/piper-voices manifest into TTSVoice.

Pure transform (``parse_manifest``) plus thin I/O wrappers
(``load_bundled_manifest`` reads the bundled snapshot offline;
``refresh_catalog`` is the ONLY network touch — the explicit "Refresh catalog"
action, D-02, never an auto-fetch on load). Mirrors ``native_voices_macos.py``:
one fixture-testable pure parser + thin wrappers, module-level functions, a
top docstring, ``%``-style logging.

The verified manifest schema (RESEARCH lines 452-502) maps each entry to a
``TTSVoice``: ``id=key``, ``language["code"]`` folded ``en_US -> en-us`` (the same
fold ``native_voices_macos`` does), ``quality -> tier``. The on-disk footprint is
the sum of the ``.onnx`` + ``.onnx.json`` ``size_bytes`` (NOT the MODEL_CARD), and
the download URL is the HF ``resolve/main/`` prefix + the repo-relative path (the
manifest ``files`` key already carries the full path).

Filtering/ordering reuse the Phase-3 ``filter_voices`` / ``order_by_quality``
helpers (D-03) — this module does NOT define its own filter functions.
"""

import json
import logging
from functools import lru_cache
from importlib import resources

import requests

from diana.tts.base import TTSVoice

logger = logging.getLogger(__name__)

# Piper quality tokens (the trailing segment of a `{lang}-{name}-{quality}` id) ->
# the TTSVoice quality tier. Used only when an installed voice id is NOT in the
# bundled manifest, so a hand-imported voice still gets a sensible tier label.
_PIPER_QUALITY_TIERS = {"x_low", "low", "medium", "high"}

# The live manifest (D-02 "Refresh catalog" only) and the per-file raw-download
# prefix. The manifest `files` key is already the full repo-relative path, so the
# download URL is just this prefix + that path.
_MANIFEST_URL = "https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json"
_HF_RESOLVE_PREFIX = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"

# The bundled curated snapshot ships as package data under diana/data/ (D-02).
_BUNDLED_PACKAGE = "diana.data"
_BUNDLED_RESOURCE = "piper_voices_curated.json"


def _entry_to_voice(key: str, entry: dict) -> TTSVoice | None:
    """Map one manifest entry to a TTSVoice; return None for a malformed entry.

    Best-effort — a garbage entry is skipped, never crashed on (mirrors the
    ``if not m: continue`` discipline in ``parse_say_voices``).
    """
    try:
        code = entry["language"]["code"]
    except (KeyError, TypeError):
        return None
    language = code.replace("_", "-").lower()  # en_US -> en-us
    return TTSVoice(
        id=key,
        name=entry.get("name", key),
        language=language,
        gender="unknown",          # the Piper manifest does not expose gender
        tier=entry.get("quality", "standard"),
        bilingual=False,
    )


def parse_manifest(manifest: "str | dict") -> list[TTSVoice]:
    """Parse a rhasspy/piper-voices manifest into a list of TTSVoice objects.

    Pure (no I/O) so it is unit-testable from a fixture. ``manifest`` may be the
    raw JSON text or the already-decoded ``dict`` of ``{voice_id: entry}``. Every
    well-formed entry becomes one TTSVoice; malformed entries are skipped.
    """
    data = json.loads(manifest) if isinstance(manifest, str) else manifest
    voices: list[TTSVoice] = []
    for key, entry in data.items():
        voice = _entry_to_voice(key, entry)
        if voice is not None:
            voices.append(voice)
    return voices


def voice_footprint_bytes(entry: dict) -> int:
    """Sum the ``.onnx`` + ``.onnx.json`` ``size_bytes`` for one manifest entry.

    The MODEL_CARD and any other files are excluded — the footprint is what gets
    downloaded and lands on disk (the model + its sibling config).
    """
    total = 0
    for path, meta in entry.get("files", {}).items():
        if path.endswith(".onnx") or path.endswith(".onnx.json"):
            total += int(meta.get("size_bytes", 0))
    return total


def download_url(file_path: str) -> str:
    """Build the HF raw-download URL for a manifest ``files`` key (already a path)."""
    return f"{_HF_RESOLVE_PREFIX}{file_path}"


def load_bundled_manifest() -> list[TTSVoice]:
    """Read and parse the bundled curated snapshot (offline default browse, D-02)."""
    raw = resources.files(_BUNDLED_PACKAGE).joinpath(_BUNDLED_RESOURCE).read_text(
        encoding="utf-8")
    data = json.loads(raw)
    # The snapshot carries a top-level "provenance" key alongside the voice map;
    # parse only the "voices" sub-map when present, else the whole object.
    voices = data.get("voices", data) if isinstance(data, dict) else data
    return parse_manifest(voices)


def refresh_catalog() -> list[TTSVoice]:
    """GET the live voices.json; on any failure log a warning and fall back (D-02).

    This is the explicit "Refresh catalog" action — the only network touch in this
    module. A network/parse failure never crashes the page: it degrades to the
    bundled snapshot.
    """
    try:
        r = requests.get(_MANIFEST_URL, timeout=30)
        r.raise_for_status()
        return parse_manifest(r.json())
    except Exception as e:  # noqa: BLE001 — any failure degrades to the bundled snapshot
        logger.warning("Catalog refresh failed (%s); using bundled snapshot", e)
        return load_bundled_manifest()


def curated_subset(voices: list[TTSVoice]) -> list[TTSVoice]:
    """Best-per-language flat list for the curated default view (D-01).

    Keeps the first voice seen per language code, preserving input order, so the
    bundled snapshot's curation order is the curated view.
    """
    seen: set[str] = set()
    subset: list[TTSVoice] = []
    for v in voices:
        lang = (v.language or "").strip().lower()
        if lang in seen:
            continue
        seen.add(lang)
        subset.append(v)
    return subset


def group_by_language(voices: list[TTSVoice]) -> dict[str, list[TTSVoice]]:
    """Bucket voices by folded language code for the collapsible show-all view (D-03).

    Partitions the full list — every input voice lands in exactly one bucket.
    """
    grouped: dict[str, list[TTSVoice]] = {}
    for v in voices:
        lang = (v.language or "").strip().lower()
        grouped.setdefault(lang, []).append(v)
    return grouped


@lru_cache(maxsize=1)
def _bundled_voices_by_id() -> dict[str, TTSVoice]:
    """``{voice_id: TTSVoice}`` from the bundled snapshot, parsed once and cached.

    Keeps enumeration cheap: labeling an installed voice from the catalog must not
    re-read+re-parse the package-data JSON on every keystroke. A read/parse failure
    degrades to an empty map (the id-convention derivation then takes over) rather
    than crashing voice enumeration.
    """
    try:
        return {v.id: v for v in load_bundled_manifest()}
    except Exception as e:  # noqa: BLE001 — degrade to derive-from-id, never crash enumeration
        logger.warning("Bundled catalog unreadable (%s); labeling installed voices by id", e)
        return {}


def _derive_piper_voice(voice_id: str) -> TTSVoice:
    """Derive a readable TTSVoice from the Piper ``{lang}-{name}-{quality}`` id.

    Pure fallback for an installed voice that is NOT in the bundled manifest (e.g.
    a hand-imported one). Splits ``en_US-lessac-medium`` into language ``en-us``
    (the same ``en_US -> en-us`` fold the manifest parser uses), a readable name,
    and a quality tier from the trailing ``x_low|low|medium|high`` token. A
    non-conforming id still yields a usable voice (id as name, ``standard`` tier),
    so enumeration never crashes on an unexpected filename.
    """
    parts = voice_id.split("-")
    language = "unknown"
    tier = "standard"
    name = voice_id

    if len(parts) >= 3:
        # Trailing token is the quality tier when it is a known Piper quality.
        if parts[-1] in _PIPER_QUALITY_TIERS:
            tier = parts[-1]
            name_token = parts[-2]
        else:
            name_token = parts[-1]
        language = parts[0].replace("_", "-").lower()  # en_US -> en-us
        readable = name_token.replace("_", " ").strip().title()
        region = parts[0].split("_")[-1].upper() if "_" in parts[0] else ""
        name = f"{readable} ({region} {tier.title()})" if region else f"{readable} ({tier.title()})"

    return TTSVoice(
        id=voice_id,
        name=name,
        language=language,
        gender="unknown",   # the Piper id convention does not encode gender
        tier=tier,
        bilingual=False,
    )


def voice_label_for_id(voice_id: str) -> TTSVoice:
    """Best available TTSVoice label for an installed Piper voice id (pure/cheap).

    Prefers the richer bundled-manifest entry when the id is catalogued; otherwise
    derives a sensible label from the Piper ``{lang}-{name}-{quality}`` convention
    (``_derive_piper_voice``). Reuses the catalog parse via a cached by-id map — it
    does NOT re-parse inline, and touches no engine SDK (ENGINE-01).
    """
    catalogued = _bundled_voices_by_id().get(voice_id)
    if catalogued is not None:
        return catalogued
    return _derive_piper_voice(voice_id)
