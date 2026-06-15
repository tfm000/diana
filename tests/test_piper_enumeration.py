"""Installed-Piper-voice enumeration so "install -> use" works (VOICE-05).

Reproduces the 04-03 human-verify defect: a Piper voice installed from Settings
did NOT appear in the Upload (or Settings Default Voice) picker, because
``get_engine_voices("piper")`` returned only the static ``PiperEngine.VOICES``.
The fix makes the static list MERGE with every installed ``{id}.onnx`` on disk.

Discovery MUST stay a cheap filesystem probe (ENGINE-01): every test monkeypatches
``diana.paths.model_dir`` to ``tmp_path`` and touches fake ``.onnx`` files there —
the real per-user cache is never read or written, and no onnxruntime/piper import
happens on the enumeration path.
"""

from diana.tts.base import TTSVoice
from diana.tts.catalog import (
    _format_piper_name,
    _parse_piper_id,
    voice_label_for_id,
)
from diana.tts.install_state import list_installed_piper_voice_ids
from diana.tts.piper_engine import PiperEngine
from diana.tts.registry import get_engine_voices


# --- ENGINE-01: the installed-voice lister is a cheap *.onnx glob -----------
def test_list_installed_piper_voice_ids_excludes_kokoro(tmp_path, monkeypatch):
    """Lists installed Piper ``{id}.onnx`` stems, excluding Kokoro model files."""
    monkeypatch.setattr("diana.paths.model_dir", lambda: tmp_path)

    (tmp_path / "en_US-lessac-medium.onnx").write_bytes(b"fake-onnx")
    (tmp_path / "en_GB-northern_english_male-medium.onnx").write_bytes(b"fake-onnx")
    # Kokoro model + sidecar files MUST NOT be returned as Piper voices (D-19).
    (tmp_path / "kokoro-v1.0.onnx").write_bytes(b"fake-kokoro")
    (tmp_path / "kokoro-v1.0.int8.onnx").write_bytes(b"fake-kokoro")
    (tmp_path / "voices-v1.0.bin").write_bytes(b"fake-voices")
    # Non-onnx sidecars (the Piper config) are not voice ids either.
    (tmp_path / "en_US-lessac-medium.onnx.json").write_bytes(b"{}")

    ids = list_installed_piper_voice_ids()

    assert ids == ["en_GB-northern_english_male-medium", "en_US-lessac-medium"]  # sorted
    assert "kokoro-v1.0" not in ids
    assert "kokoro-v1.0.int8" not in ids
    assert "voices-v1.0" not in ids


def test_list_installed_piper_voice_ids_empty_when_no_dir(tmp_path, monkeypatch):
    """A fresh install (model dir absent) yields an empty list, not a crash."""
    missing = tmp_path / "does-not-exist"
    monkeypatch.setattr("diana.paths.model_dir", lambda: missing)

    assert list_installed_piper_voice_ids() == []


# --- VOICE-05: get_engine_voices("piper") merges installed voices -----------
def test_get_engine_voices_piper_includes_installed(tmp_path, monkeypatch):
    """An installed voice appears in the picker, labeled, deduped, no Kokoro leak."""
    monkeypatch.setattr("diana.paths.model_dir", lambda: tmp_path)

    # An installed catalogued voice NOT in the static list, plus a Kokoro model.
    (tmp_path / "de_DE-thorsten-medium.onnx").write_bytes(b"fake-onnx")
    (tmp_path / "kokoro-v1.0.onnx").write_bytes(b"fake-kokoro")

    voices = get_engine_voices("piper")
    by_id = {v.id: v for v in voices}

    # The static curated VOICES are still present.
    for static in PiperEngine.VOICES:
        assert static.id in by_id, f"static voice {static.id} missing"

    # The installed voice now shows up, labeled (from the catalog) with its
    # language + quality tier rather than being invisible.
    assert "de_DE-thorsten-medium" in by_id
    thorsten = by_id["de_DE-thorsten-medium"]
    assert isinstance(thorsten, TTSVoice)
    assert thorsten.language == "de-de"
    assert thorsten.tier == "medium"

    # The Kokoro model file is NOT surfaced as a Piper voice (D-19).
    assert "kokoro-v1.0" not in by_id

    # Deduped by id — no voice id appears twice.
    ids = [v.id for v in voices]
    assert len(ids) == len(set(ids))


def test_get_engine_voices_piper_dedups_static_install(tmp_path, monkeypatch):
    """A voice installed on disk that is ALSO static keeps its richer static label."""
    monkeypatch.setattr("diana.paths.model_dir", lambda: tmp_path)

    # en_US-lessac-medium is in the static VOICES with the label "Lessac (US Medium)".
    (tmp_path / "en_US-lessac-medium.onnx").write_bytes(b"fake-onnx")

    voices = get_engine_voices("piper")
    matches = [v for v in voices if v.id == "en_US-lessac-medium"]

    assert len(matches) == 1, "static + installed must not duplicate"
    assert matches[0].name == "Lessac (US Medium)"  # static (richer) label preserved


def test_get_engine_voices_piper_includes_uncatalogued_installed(tmp_path, monkeypatch):
    """A hand-imported voice (not static, not catalogued) is enumerable + derived."""
    monkeypatch.setattr("diana.paths.model_dir", lambda: tmp_path)

    (tmp_path / "en_GB-northern_english_male-high.onnx").write_bytes(b"fake-onnx")

    by_id = {v.id: v for v in get_engine_voices("piper")}

    assert "en_GB-northern_english_male-high" in by_id
    derived = by_id["en_GB-northern_english_male-high"]
    assert derived.language == "en-gb"
    assert derived.tier == "high"


def test_get_engine_voices_piper_no_installed_returns_static(tmp_path, monkeypatch):
    """With nothing installed, the picker shows exactly the static curated voices."""
    monkeypatch.setattr("diana.paths.model_dir", lambda: tmp_path)

    voices = get_engine_voices("piper")

    assert {v.id for v in voices} == {v.id for v in PiperEngine.VOICES}


# --- Labeling: catalog fields kept, display name ALWAYS id-formatted (04-03 fix) --
def test_voice_label_for_id_uses_bundled_catalog():
    """A catalogued id keeps the catalog's language/tier but the DISPLAY name is the
    uniform static-matching form built from the id, NOT the raw manifest name."""
    voice = voice_label_for_id("en_US-lessac-medium")

    assert voice.id == "en_US-lessac-medium"
    assert voice.language == "en-us"
    assert voice.tier == "medium"        # manifest "quality" -> tier (kept from catalog)
    # 04-03 Bug B: even though this id IS catalogued (raw manifest name "lessac"),
    # the display name matches the static PiperEngine.VOICES format exactly.
    assert voice.name == "Lessac (US Medium)"


def test_voice_label_for_id_derives_when_not_catalogued():
    """An uncatalogued id is parsed from the Piper {lang}-{name}-{quality} form."""
    voice = voice_label_for_id("en_GB-northern_english_male-high")

    assert voice.id == "en_GB-northern_english_male-high"
    assert voice.language == "en-gb"
    assert voice.tier == "high"
    # Readable name derived from the name token + region/quality, never the raw id.
    assert voice.name != "en_GB-northern_english_male-high"
    assert "high" in voice.name.lower()


def test_voice_label_for_id_tolerates_nonconforming_id():
    """A non-conforming filename still yields a usable voice (never crashes)."""
    voice = voice_label_for_id("customvoice")

    assert voice.id == "customvoice"
    assert voice.name == "customvoice"   # id used as-is when it can't be parsed
    assert voice.tier == "standard"


# --- 04-03 Bug B: uniform display name matching the static format -------------
def test_voice_label_catalogued_name_matches_static_format():
    """A catalogued voice's DISPLAY name matches the static PiperEngine.VOICES form.

    Regression for the 04-03 defect: catalogued installed voices showed the raw
    lowercase manifest name ("lessac") with no "(REGION Quality)" descriptor instead
    of the static "Lessac (US Medium)". The static and catalogued labels must agree.
    """
    voice = voice_label_for_id("en_US-lessac-medium")
    static = {v.id: v for v in PiperEngine.VOICES}["en_US-lessac-medium"]
    assert voice.name == static.name == "Lessac (US Medium)"


def test_voice_label_catalogued_keeps_catalog_tier_in_name():
    """A catalogued x_low voice formats its real tier (kept from the catalog entry)."""
    voice = voice_label_for_id("it_IT-riccardo-x_low")
    assert voice.name == "Riccardo (IT X_Low)"
    assert voice.tier == "x_low"          # catalog tier preserved, not overwritten
    assert voice.language == "it-it"      # catalog language preserved


def test_format_piper_name_multi_token_speaker():
    """The pure formatter Title-cases a multi-token speaker and matches the format."""
    assert (
        _format_piper_name("northern_english_male", "GB", "high")
        == "Northern English Male (GB High)"
    )
    # No region -> the parenthetical carries the quality alone (graceful).
    assert _format_piper_name("lessac", "", "medium") == "Lessac (Medium)"


def test_voice_label_derived_multi_token_speaker_matches_format():
    """A derived (uncatalogued) multi-token id formats exactly like the static voices."""
    voice = voice_label_for_id("en_GB-northern_english_male-high")
    assert voice.name == "Northern English Male (GB High)"
    assert voice.tier == "high"
    assert voice.language == "en-gb"


def test_parse_piper_id_returns_none_for_nonconforming():
    """The shared id parser returns None for an id with fewer than 3 parts (no crash)."""
    assert _parse_piper_id("customvoice") is None
    assert _parse_piper_id("foo-bar") is None
    # A conforming id parses into (language, speaker, tier, region).
    assert _parse_piper_id("en_US-lessac-medium") == ("en-us", "lessac", "medium", "US")
