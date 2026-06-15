"""Interaction-level AppTest pre-check for the Custom Voices slice (05-06, HEAVY-02).

The active UI policy (drive the REAL flow through ``streamlit.testing.v1.AppTest`` and
assert on the resulting widgets — shallow "renders without exception" tests missed real
logic bugs at earlier checkpoints). These cover the load-bearing surfaces of the
engine-agnostic Custom Voices section (D-11..D-14) WHILE the heavy engines are UNINSTALLED
(the real on-CI state — no multi-GB torch venv, no heavy SDK):

  * Settings ▸ Voices renders the Custom Voices section with BOTH input methods — an
    upload path (audio file_uploader + a transcript) AND an in-app capture path
    (``st.audio_input`` + a typed transcript) — D-11.
  * Clip validation rejects bad input with a clear message and NEVER crashes the page:
    an empty transcript and an unreadable clip both return ``(False, msg)`` (D-13).
  * A saved custom voice appears in ``registry.get_engine_voices("f5")`` (the Upload
    picker source) AND ``registry.all_engine_voices()`` (the cross-engine browser
    source), and is removable — D-14.

Everything is deterministic + OFFLINE: the heavy per-user dirs (incl. ``custom_voices_dir``)
point at ``tmp_path``, the config singleton points at a tmp sqlite DB, the cached voice
enumerators are stubbed so no real ``say`` shell / network runs, and NO torch is imported.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

import diana.config as C
import diana.dashboard.voice_cache as VC
import diana.paths as P
from diana.database import init_db
from diana.tts.base import TTSVoice

try:
    from streamlit.testing.v1 import AppTest
    _APPTEST = True
except ImportError:  # pragma: no cover - AppTest ships with the pinned Streamlit
    _APPTEST = False

pytestmark = pytest.mark.skipif(not _APPTEST, reason="streamlit AppTest unavailable")

_PAGES = Path(__file__).resolve().parent.parent / "diana" / "dashboard" / "pages"
_SETTINGS = str(_PAGES / "5_Settings.py")

# Assert NONE of these reach the app interpreter on the cheap path (ENGINE-01 / D-17).
_HEAVY_SDKS = ("torch", "f5_tts", "torchaudio", "vocos")


def _tmp_heavy_paths(monkeypatch, tmp_path):
    """Point every heavy per-user dir (incl. custom_voices) at tmp (uninstalled, isolated)."""
    for name in ("venvs_dir", "hf_cache_dir", "model_dir", "voices_dir",
                 "custom_voices_dir"):
        sub = tmp_path / name.replace("_dir", "")
        sub.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(P, name, lambda _d=sub: _d, raising=False)


def _tmp_config(monkeypatch, tmp_path, engine="native_os"):
    """A config singleton on a tmp DB; stub the cached enumerators (offline). Returns (cfg, db)."""
    db_path = str(tmp_path / "diana.db")
    init_db(db_path)
    cfg = C.load_config()
    cfg.storage.database_path = db_path
    cfg.tts.engine = engine
    monkeypatch.setattr(C, "get_config", lambda *a, **k: cfg)
    monkeypatch.setattr(VC, "get_config", lambda *a, **k: cfg)
    nat = [TTSVoice("nat-0", "Native 0", "en-us", "male")]
    f5 = [TTSVoice("f5_default", "Default (F5)", "en-us", "neutral", "enhanced")]
    monkeypatch.setattr(
        VC, "cached_voices",
        lambda engine_name: list(f5) if engine_name == "f5" else list(nat),
    )
    monkeypatch.setattr(
        VC, "cached_all_engine_voices",
        lambda: [("native_os", nat[0]), ("f5", f5[0])],
    )
    monkeypatch.setattr(VC, "clear_voice_cache", Mock(name="clear_voice_cache"))
    return cfg, db_path


def _texts(at) -> str:
    """All caption/markdown/error/success/subheader text on the page, concatenated."""
    chunks = []
    for coll in (at.caption, at.markdown, at.error, at.success, at.warning,
                 at.info, at.subheader):
        for el in coll:
            chunks.append(str(getattr(el, "value", "")))
    return "\n".join(chunks)


# --- D-11: the Custom Voices section renders BOTH input methods ----------------------
def test_settings_custom_voices_section_renders_both_inputs(monkeypatch, tmp_path):
    """Settings ▸ Voices shows the Custom Voices section with upload AND in-app capture."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    _tmp_config(monkeypatch, tmp_path, engine="native_os")

    before = {m for m in _HEAVY_SDKS if m in sys.modules}
    at = AppTest.from_file(_SETTINGS, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    text = _texts(at)
    assert "Custom Voices" in text, f"missing Custom Voices section:\n{text}"

    # UPLOAD path: the "Add custom voice" button + the audio file_uploader exist.
    upload_btns = [b for b in at.button if b.key == "cv_upload_add"]
    assert upload_btns, "no 'Add custom voice' (upload) button rendered"
    # CAPTURE path: the in-app recorder ('cv_record_audio') + the "Add recorded voice".
    record_btns = [b for b in at.button if b.key == "cv_record_add"]
    assert record_btns, "no 'Add recorded voice' (in-app capture) button rendered"
    # The transcript is always user-provided (D-12): a text_area for each path exists.
    ta_keys = {ta.key for ta in at.text_area}
    assert "cv_upload_transcript" in ta_keys, "no upload transcript text_area"
    assert "cv_record_transcript" in ta_keys, "no record transcript text_area"

    # The cheap path imported no heavy SDK (ENGINE-01 / D-17).
    newly = {m for m in _HEAVY_SDKS if m in sys.modules} - before
    assert not newly, f"Custom Voices section imported heavy SDK(s): {newly}"


# --- D-13: clip validation rejects bad input with a message, never crashing ----------
def test_validate_clip_rejects_bad_input_with_message(monkeypatch, tmp_path):
    """The validation the section calls rejects empty-transcript + unreadable clips cleanly."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    from diana.tts import custom_voices

    import numpy as np
    import soundfile as sf

    good = tmp_path / "good.wav"
    sf.write(str(good), np.zeros(16000 * 3, dtype="float32"), 16000, format="WAV")

    # Empty transcript -> rejected with a message (D-12 transcript required).
    ok, msg = custom_voices.validate_clip(str(good), "   ")
    assert ok is False and msg

    # Unreadable/junk clip -> rejected, NEVER raises (the import-rejection discipline).
    junk = tmp_path / "junk.wav"
    junk.write_bytes(b"not real audio")
    try:
        ok2, msg2 = custom_voices.validate_clip(str(junk), "a valid transcript")
    except Exception as e:  # noqa: BLE001 - contract is "never raises"
        pytest.fail(f"validate_clip must never raise, got {e!r}")
    assert ok2 is False and msg2

    # A good 16 kHz clip + a real transcript is ACCEPTED (sub-24 kHz OK, Pitfall 5).
    ok3, msg3 = custom_voices.validate_clip(str(good), "the exact words spoken")
    assert ok3 is True and msg3


# --- D-14: a saved custom voice appears in the picker + cross-engine browser, removable
def test_saved_custom_voice_in_picker_and_browser_then_removable(monkeypatch, tmp_path):
    """save -> appears in get_engine_voices('f5') + all_engine_voices(); remove -> gone."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    cfg, db = _tmp_config(monkeypatch, tmp_path, engine="native_os")

    import numpy as np
    import soundfile as sf

    import diana.tts.registry as R
    from diana.tts import custom_voices

    clip = tmp_path / "ref.wav"
    sf.write(str(clip), np.zeros(16000 * 3, dtype="float32"), 16000, format="WAV")

    before = {m for m in _HEAVY_SDKS if m in sys.modules}

    ok, _msg = custom_voices.save_custom_voice(
        db, None, "My Test Voice", str(clip), "the exact words spoken in the clip"
    )
    assert ok is True, f"save_custom_voice failed: {_msg}"

    # Appears in the Upload picker source (dynamic F5 branch — D-14).
    f5_ids = [v.id for v in R.get_engine_voices("f5")]
    assert "f5_default" in f5_ids, "the bundled default must still be present"
    assert "my-test-voice" in f5_ids, f"saved voice missing from F5 picker: {f5_ids}"

    # Appears in the cross-engine browser source (all_engine_voices — D-14).
    browser = [(eng, v.id) for eng, v in R.all_engine_voices(cfg)]
    assert ("f5", "my-test-voice") in browser, (
        f"saved voice missing from the cross-engine browser: {browser}"
    )

    # The dynamic enumeration imported no heavy SDK (ENGINE-01 / D-17).
    newly = {m for m in _HEAVY_SDKS if m in sys.modules} - before
    assert not newly, f"voice enumeration imported heavy SDK(s): {newly}"

    # Removable like any other voice (not in use here -> deletes cleanly, D-14).
    freed = custom_voices.remove_custom_voice(db, None, "my-test-voice")
    assert freed >= 0
    f5_ids_after = [v.id for v in R.get_engine_voices("f5")]
    assert "my-test-voice" not in f5_ids_after, "removed voice still in the picker"
