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
import os
from functools import lru_cache
from importlib import resources
from pathlib import Path

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


def sample_url_for(voice_dir_path: str) -> str:
    """Build the HF preview-sample URL for a voice (D-12; RESEARCH line 494).

    Every Piper voice ships one preview clip at ``<voice-dir>/samples/speaker_0.mp3``
    (~84 KB). ``voice_dir_path`` is the voice's repo-relative directory — i.e. the
    PARENT of a manifest ``files`` key (the ``files`` key carries the full repo path,
    so ``en/en_US/lessac/medium/en_US-lessac-medium.onnx`` -> the voice dir
    ``en/en_US/lessac/medium``). For convenience a full ``.onnx``/``.onnx.json`` file
    path is also accepted and reduced to its parent dir, so callers may pass either.
    Pure/Streamlit-free.
    """
    p = voice_dir_path.strip().strip("/")
    # Accept either a voice dir or a full file path; reduce a file to its parent dir.
    if p.endswith(".onnx") or p.endswith(".onnx.json"):
        p = p.rsplit("/", 1)[0] if "/" in p else ""
    return f"{_HF_RESOLVE_PREFIX}{p}/samples/speaker_0.mp3"


def fetch_sample(voice_dir_path: str, cache_dir: "Path | None" = None) -> Path:
    """Download + cache a voice's preview clip; return the cached path (D-12).

    Thin wrapper over ``downloader.download_file``: fetches ``speaker_0.mp3`` from
    ``sample_url_for(voice_dir_path)`` into the per-user sample cache (default
    ``paths.data_dir()/"samples"``) under a flattened, collision-free filename, and
    returns the cached path. A repeat call returns the already-cached file WITHOUT a
    network touch, so re-previews are instant/offline (D-12). ``download_file`` is
    imported lazily so this catalog module keeps a minimal top-of-file import surface
    and never pulls the downloader at import time (D-19). No md5 is verified — the
    sample is non-executable preview audio (T-04-INT: low value); HTTPS + default TLS
    verify still apply. Raises (propagates ``requests``/``download_file`` errors,
    e.g. a 404 on a moved voice) so the UI can message Pitfall 6 gracefully.
    """
    # Derive the voice dir (strip a file path to its parent) so the cache key is the
    # voice dir, shared by every file of the pair.
    voice_dir = voice_dir_path.strip().strip("/")
    if voice_dir.endswith(".onnx") or voice_dir.endswith(".onnx.json"):
        voice_dir = voice_dir.rsplit("/", 1)[0] if "/" in voice_dir else ""

    if cache_dir is None:
        from diana import paths
        cache_dir = paths.data_dir() / "samples"
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Flatten the voice dir into a single safe filename (no nested dirs in the cache).
    cached = cache_dir / f"{voice_dir.replace('/', '_')}_speaker_0.mp3"
    if cached.exists():
        return cached  # already cached — offline/instant re-preview (D-12)

    from diana.downloads.downloader import download_file
    download_file(sample_url_for(voice_dir), cached)
    return cached


def safe_voice_dest(uploaded_name: str) -> Path:
    """Resolve a SAFE on-disk destination for a manually imported voice file.

    HARD-03 / VOICE-04 / T-04-PATH: the manual-import path accepts an untrusted
    filename (from ``file_uploader`` or a user-typed path). This reuses the exact
    guard already proven in ``1_Upload.py:268-284`` (RESEARCH Pattern 5):

      1. ``os.path.basename`` strips any directory components (neutralizing ``../``
         and absolute paths — only the leaf name survives).
      2. An extension allow-list rejects anything not ending in ``.onnx`` or
         ``.onnx.json`` (no ``.sh``/``.txt``/etc. ever lands).
      3. A resolved-prefix containment check confirms the destination still resolves
         INSIDE ``paths.model_dir()`` — defence-in-depth against any residual
         traversal/zip-slip after the basename strip.

    Returns the safe ``Path`` (under ``model_dir()``) where the file may be written;
    raises ``ValueError`` on a disallowed extension or a containment-escape. Pure
    apart from reading ``paths.model_dir()`` (lazy import keeps the module
    import-light and lets tests monkeypatch the path). Streamlit-free.
    """
    from diana import paths

    base = os.path.basename(uploaded_name)  # strip any path components (../, absolute)
    if not (base.endswith(".onnx") or base.endswith(".onnx.json")):
        raise ValueError("Only .onnx and .onnx.json files are accepted.")
    dest_dir = paths.model_dir()
    dest = dest_dir / base
    if not str(dest.resolve()).startswith(str(dest_dir.resolve())):
        raise ValueError("Invalid filename.")  # traversal/zip-slip blocked
    return dest


def load_bundled_manifest() -> list[TTSVoice]:
    """Read and parse the bundled curated snapshot (offline default browse, D-02)."""
    raw = resources.files(_BUNDLED_PACKAGE).joinpath(_BUNDLED_RESOURCE).read_text(
        encoding="utf-8")
    data = json.loads(raw)
    # The snapshot carries a top-level "provenance" key alongside the voice map;
    # parse only the "voices" sub-map when present, else the whole object.
    voices = data.get("voices", data) if isinstance(data, dict) else data
    return parse_manifest(voices)


def _load_bundled_raw() -> dict:
    """The RAW bundled snapshot ``{voice_id: entry}`` (offline fallback for refresh).

    Mirrors ``load_bundled_manifest`` but returns the raw entry map (with the
    per-file ``size_bytes``/``md5_digest``/path needed to build a download URL and
    verify bytes) rather than parsed ``TTSVoice`` objects.
    """
    raw = resources.files(_BUNDLED_PACKAGE).joinpath(_BUNDLED_RESOURCE).read_text(
        encoding="utf-8")
    data = json.loads(raw)
    return data.get("voices", data) if isinstance(data, dict) else data


def refresh_catalog_raw() -> dict:
    """GET the live voices.json and return the RAW ``{voice_id: entry}`` map (D-02).

    This is the explicit "Refresh catalog" action — the only network touch in this
    module. The raw map (not parsed ``TTSVoice`` objects) is returned so the caller
    keeps each entry's ``files`` (path + ``size_bytes`` + ``md5_digest``) for the
    on-demand install of any browsed voice, and can derive the display list via
    ``parse_manifest``. A network/parse failure never crashes the page: it degrades
    to the raw bundled snapshot.
    """
    try:
        r = requests.get(_MANIFEST_URL, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:  # noqa: BLE001 — any failure degrades to the bundled snapshot
        logger.warning("Catalog refresh failed (%s); using bundled snapshot", e)
        return _load_bundled_raw()


def refresh_catalog() -> list[TTSVoice]:
    """GET the live voices.json, parsed into ``TTSVoice`` objects (D-02).

    The parsed view of ``refresh_catalog_raw`` (the single network touch). A
    network/parse failure degrades to the bundled snapshot rather than crashing.
    """
    return parse_manifest(refresh_catalog_raw())


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


def _format_piper_name(speaker_token: str, region: str, tier_token: str) -> str:
    """Pure formatter for a Piper voice display name: ``"<Speaker> (<REGION> <Quality>)"``.

    Matches the static ``PiperEngine.VOICES`` convention EXACTLY (Title-cased speaker,
    space before the parenthetical, REGION uppercased, quality Title-cased, NO comma):
    ``("lessac", "US", "medium") -> "Lessac (US Medium)"`` and
    ``("northern_english_male", "GB", "high") -> "Northern English Male (GB High)"``.
    With no region the parenthetical carries the quality alone.
    """
    readable = speaker_token.replace("_", " ").strip().title()
    quality = tier_token.title()
    if region:
        return f"{readable} ({region} {quality})"
    return f"{readable} ({quality})"


def _parse_piper_id(voice_id: str) -> tuple[str, str, str, str] | None:
    """Split a Piper ``{lang}-{name}-{quality}`` id into ``(language, speaker, tier, region)``.

    Pure id-convention parse shared by ``_derive_piper_voice`` and the catalogued
    branch of ``voice_label_for_id``. Folds the language the same way the manifest
    parser does (``en_US -> en-us``); the trailing token is the quality tier only
    when it is a known Piper quality (``x_low|low|medium|high``), otherwise it is
    treated as part of the speaker name and the tier defaults to ``standard``. The
    region is the uppercased country sub-tag of the first part (``en_US -> US``),
    or ``""`` when the language has no ``_`` sub-tag. Returns ``None`` for a
    non-conforming id (fewer than 3 ``-``-separated parts), so callers can fall back
    gracefully without crashing.
    """
    parts = voice_id.split("-")
    if len(parts) < 3:
        return None
    if parts[-1] in _PIPER_QUALITY_TIERS:
        tier = parts[-1]
        speaker_token = parts[-2]
    else:
        tier = "standard"
        speaker_token = parts[-1]
    language = parts[0].replace("_", "-").lower()  # en_US -> en-us
    region = parts[0].split("_")[-1].upper() if "_" in parts[0] else ""
    return language, speaker_token, tier, region


def _derive_piper_voice(voice_id: str) -> TTSVoice:
    """Derive a readable TTSVoice from the Piper ``{lang}-{name}-{quality}`` id.

    Pure fallback for an installed voice that is NOT in the bundled manifest (e.g.
    a hand-imported one). Splits ``en_US-lessac-medium`` into language ``en-us``
    (the same ``en_US -> en-us`` fold the manifest parser uses), a readable name in
    the static ``PiperEngine.VOICES`` format (``_format_piper_name``), and a quality
    tier from the trailing ``x_low|low|medium|high`` token. A non-conforming id still
    yields a usable voice (id as name, ``standard`` tier), so enumeration never
    crashes on an unexpected filename.
    """
    parsed = _parse_piper_id(voice_id)
    if parsed is None:
        return TTSVoice(
            id=voice_id,
            name=voice_id,
            language="unknown",
            gender="unknown",
            tier="standard",
            bilingual=False,
        )

    language, speaker_token, tier, region = parsed
    return TTSVoice(
        id=voice_id,
        name=_format_piper_name(speaker_token, region, tier),
        language=language,
        gender="unknown",   # the Piper id convention does not encode gender
        tier=tier,
        bilingual=False,
    )


def voice_label_for_id(voice_id: str) -> TTSVoice:
    """Best available TTSVoice label for an installed Piper voice id (pure/cheap).

    The DISPLAY name is ALWAYS built from the Piper ``{lang}-{name}-{quality}`` id
    convention (``_format_piper_name``) so installed voices read uniformly and match
    the static ``PiperEngine.VOICES`` format ("Lessac (US Medium)"), whether or not
    the id is catalogued — the bundled manifest's raw ``name`` ("lessac") is NOT used
    for display. When the id IS catalogued the richer/accurate ``language``/``tier``/
    ``gender``/``bilingual`` from the catalog entry are kept; only ``name`` is
    overridden with the formatted one. A non-conforming id that cannot be parsed
    falls back to the catalog name (or the id) and never crashes. Reuses the catalog
    parse via a cached by-id map and touches no engine SDK (ENGINE-01).
    """
    catalogued = _bundled_voices_by_id().get(voice_id)
    if catalogued is None:
        return _derive_piper_voice(voice_id)

    parsed = _parse_piper_id(voice_id)
    if parsed is None:
        # Non-conforming id: keep the catalog entry as-is (its name, or the id).
        return catalogued
    _language, speaker_token, tier, region = parsed
    # Keep the catalog's richer fields; override only the display name with the
    # formatted, static-matching form built from the id convention.
    return TTSVoice(
        id=catalogued.id,
        name=_format_piper_name(speaker_token, region, catalogued.tier or tier),
        language=catalogued.language,
        gender=catalogued.gender,
        tier=catalogued.tier,
        bilingual=catalogued.bilingual,
    )
