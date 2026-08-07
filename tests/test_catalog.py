"""Wave-0 RED/skip scaffolds for the Piper voice catalog parser (Plan 02).

The symbols under test live in ``diana.tts.catalog`` and land in Plan 02; this
scaffold's ``skipif`` predicates flip to live gates the moment they do, with no
edits here. Mirrors ``test_native_voices_macos.py`` exactly: a fixture-driven
pure-parse seam (``parse_manifest``), guarded imports, real assertion bodies.

Fixture: ``tests/fixtures/voices_manifest.json`` (a 3-entry excerpt of the real
rhasspy/piper-voices manifest, incl. one multi-speaker voice — committed this
plan). The verified schema (RESEARCH lines 452-502) maps each entry to a
``TTSVoice``: id=key, language ``en_US -> en-us``, tier from ``quality``, plus a
footprint (sum of ``.onnx`` + ``.onnx.json`` ``size_bytes``) and a download URL
built as ``https://huggingface.co/rhasspy/piper-voices/resolve/main/{path}``.

VOICE-01, D-01/D-03.
"""

import json
from pathlib import Path

import pytest

from diana.tts.base import TTSVoice

_FIXTURE = Path(__file__).parent / "fixtures" / "voices_manifest.json"
_HF_PREFIX = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"

# --- Guarded import: the catalog module lands in Plan 02 --------------------
try:
    from diana.tts.catalog import parse_manifest  # noqa: F401

    _CATALOG_AVAILABLE = True
except ImportError:
    parse_manifest = None  # type: ignore[assignment]
    _CATALOG_AVAILABLE = False

# Footprint + download-URL builders: module home is the implementer's choice.
# Probe the likely names/homes so the scaffold binds wherever they land.
_footprint = None
for _modname, _attr in (
    ("diana.tts.catalog", "manifest_footprint_bytes"),
    ("diana.tts.catalog", "footprint_bytes"),
    ("diana.tts.catalog", "voice_footprint_bytes"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _footprint = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue

_download_url = None
for _modname, _attr in (
    ("diana.tts.catalog", "build_download_url"),
    ("diana.tts.catalog", "download_url"),
    ("diana.tts.catalog", "voice_download_url"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _download_url = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue

# Curated-subset + group-by-language helpers (D-01/D-03), planner's choice.
_curated = None
for _modname, _attr in (
    ("diana.tts.catalog", "curated_subset"),
    ("diana.tts.catalog", "curated_voices"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _curated = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue

_group_by_language = None
for _modname, _attr in (
    ("diana.tts.catalog", "group_by_language"),
    ("diana.tts.catalog", "group_voices_by_language"),
):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=[_attr])
        _group_by_language = getattr(_mod, _attr)
        break
    except (ImportError, AttributeError):
        continue


# --- Fixture sanity (runs in Wave 0 regardless of implementation) -----------
def test_fixture_present_and_shaped():
    """The committed manifest fixture is valid and carries a multi-speaker voice."""
    assert _FIXTURE.is_file(), "tests/fixtures/voices_manifest.json must be committed"
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert len(data) >= 2, "fixture needs >= 2 voice entries"
    # At least one populated speaker_id_map (the multi-speaker case).
    assert any(e.get("speaker_id_map") for e in data.values())
    # Each entry carries the .onnx + .onnx.json files with size_bytes + md5.
    for entry in data.values():
        files = entry["files"]
        assert any(p.endswith(".onnx") for p in files)
        assert any(p.endswith(".onnx.json") for p in files)
        for meta in files.values():
            assert "size_bytes" in meta and "md5_digest" in meta


# --- VOICE-01: manifest entry -> TTSVoice + footprint + URL ------------------
@pytest.mark.skipif(
    not _CATALOG_AVAILABLE, reason="diana.tts.catalog.parse_manifest implemented in Plan 02"
)
def test_parse_manifest_entry():
    """The lessac entry maps to a TTSVoice with folded language + correct tier."""
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    voices = parse_manifest(data)
    assert all(isinstance(v, TTSVoice) for v in voices)
    assert len(voices) == len(data), "every manifest entry -> exactly one voice"

    by_id = {v.id: v for v in voices}
    lessac = by_id.get("en_US-lessac-medium")
    assert lessac is not None, "id must be the manifest key"
    # en_US -> en-us (the exact fold native_voices_macos does).
    assert lessac.language == "en-us"
    # tier derives from the manifest `quality` field.
    assert "medium" in lessac.tier.lower() or lessac.tier.lower() in {
        "standard", "compact", "enhanced",
    }

    # Footprint = sum of .onnx + .onnx.json size_bytes (NOT MODEL_CARD).
    if _footprint is not None:
        fp = _footprint(data["en_US-lessac-medium"])
        assert fp == 63201294 + 4885, "footprint sums .onnx + .onnx.json only"

    # Download URL is the HF resolve/main/ prefix + the repo-relative path.
    if _download_url is not None:
        onnx_path = next(
            p for p in data["en_US-lessac-medium"]["files"] if p.endswith(".onnx")
        )
        url = _download_url(onnx_path)
        assert url.startswith(_HF_PREFIX)
        assert url.endswith("en_US-lessac-medium.onnx")


# --- VOICE-01 / D-01-D-03: curated subset + group-by-language ----------------
@pytest.mark.skipif(
    not _CATALOG_AVAILABLE, reason="catalog curation helpers implemented in Plan 02"
)
def test_curated_subset():
    """A curated selector returns a small flat subset; group-by-language buckets."""
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    voices = parse_manifest(data)

    if _curated is not None:
        subset = _curated(voices)
        assert isinstance(subset, list)
        assert all(isinstance(v, TTSVoice) for v in subset)
        assert 0 < len(subset) <= len(voices), "curated view is a flat subset"
    else:
        pytest.skip("curated_subset helper lands with the catalog (Plan 02)")

    if _group_by_language is not None:
        grouped = _group_by_language(voices)
        assert isinstance(grouped, dict)
        # Keyed by folded language; the British + US entries are distinct buckets.
        assert "en-us" in grouped and "en-gb" in grouped
        flat = [v for bucket in grouped.values() for v in bucket]
        assert len(flat) == len(voices), "grouping partitions the full list"
    else:
        pytest.skip("group_by_language helper lands with the catalog (Plan 02)")
