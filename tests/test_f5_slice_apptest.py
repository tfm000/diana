"""Interaction-level AppTest pre-check for the F5 vertical slice (05-05, HEAVY-02).

The active UI policy (the post-Phase-4 standing requirement: drive the REAL flow through
``streamlit.testing.v1.AppTest`` and assert on the resulting widgets, because shallow
"renders without exception" tests missed real logic bugs at earlier checkpoints). These
cover the three load-bearing surfaces of the F5 slice WHILE F5 IS UNINSTALLED (the real
on-CI state — no multi-GB torch venv, no heavy SDK):

  * Upload (D-16 fail-fast): selecting the F5 engine surfaces the actionable "install …
    in Settings ▸ Voices" readiness note, and the exact gate wired into the Convert
    button's ``disabled=`` (``registry.heavy_engine_failfast``) returns that message for
    uninstalled F5 and ``None`` for a light engine.
  * Settings ▸ Voices (license gate BEFORE install, D-08): the F5 row shows the CC-BY-NC
    non-commercial disclosure + an "I accept" button and NO Install control before the
    license is accepted.
  * Settings ▸ Voices (accept persists, D-08): once the license-accepted flag is set in
    ``app_settings``, the F5 row shows the itemized footprint confirm + an Install action.

Everything is deterministic + OFFLINE: the heavy per-user dirs point at ``tmp_path`` (so
``heavy_engine_installed('f5')`` reads False — uninstalled), the config singleton points
at a tmp sqlite DB, and the cached voice enumerators are stubbed so no real ``say`` shell
/ network / Kokoro work runs. No real install is performed and NO torch is imported.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

import diana.config as C
import diana.dashboard.voice_cache as VC
import diana.paths as P
from diana.database import get_setting, init_db, set_setting
from diana.tts.base import TTSVoice

try:
    from streamlit.testing.v1 import AppTest
    _APPTEST = True
except ImportError:  # pragma: no cover - AppTest ships with the pinned Streamlit
    _APPTEST = False

pytestmark = pytest.mark.skipif(not _APPTEST, reason="streamlit AppTest unavailable")

_PAGES = Path(__file__).resolve().parent.parent / "diana" / "dashboard" / "pages"
_UPLOAD = str(_PAGES / "1_Upload.py")
_SETTINGS = str(_PAGES / "5_Settings.py")

# F5 shares the torch venv; assert NONE of these reach the app interpreter (ENGINE-01).
_HEAVY_SDKS = ("torch", "f5_tts", "torchaudio", "vocos")


def _tmp_heavy_paths(monkeypatch, tmp_path):
    """Point every heavy per-user dir at tmp so F5 reads as NOT installed."""
    for name in ("venvs_dir", "hf_cache_dir", "model_dir", "voices_dir"):
        sub = tmp_path / name.replace("_dir", "")
        sub.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(P, name, lambda _d=sub: _d, raising=False)


def _tmp_config(monkeypatch, tmp_path, engine="native_os"):
    """A config singleton on a tmp DB; stub the cached enumerators (offline). Returns db."""
    db_path = str(tmp_path / "diana.db")
    init_db(db_path)
    cfg = C.load_config()
    cfg.storage.database_path = db_path
    cfg.tts.engine = engine
    monkeypatch.setattr(C, "get_config", lambda *a, **k: cfg)
    monkeypatch.setattr(VC, "get_config", lambda *a, **k: cfg)
    # Tiny deterministic voice lists so neither page shells `say` or hits the network.
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


def _captions(at) -> str:
    """All caption/markdown/error/success text on the page, concatenated."""
    chunks = []
    for coll in (at.caption, at.markdown, at.error, at.success, at.warning, at.info):
        for el in coll:
            chunks.append(str(getattr(el, "value", "")))
    return "\n".join(chunks)


# --- D-16: selecting uninstalled F5 surfaces the actionable install prompt ----------
def test_upload_f5_selection_shows_install_prompt(monkeypatch, tmp_path):
    """Upload: choosing F5 (uninstalled) shows the 'Settings ▸ Voices' readiness note."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    _tmp_config(monkeypatch, tmp_path, engine="native_os")

    before = {m for m in _HEAVY_SDKS if m in sys.modules}
    at = AppTest.from_file(_UPLOAD, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    engine_sel = next((s for s in at.selectbox if "Engine" in (s.label or "")), None)
    assert engine_sel is not None, "Engine selectbox not found"
    engine_sel.set_value("f5").run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    text = _captions(at)
    assert "Settings" in text and "Voices" in text, (
        f"expected an install-in-Settings-Voices readiness note, got:\n{text}"
    )
    newly = {m for m in _HEAVY_SDKS if m in sys.modules} - before
    assert not newly, f"Upload selection imported heavy SDK(s): {newly}"


# --- D-16: the exact gate wired into the Convert button's disabled= -----------------
def test_heavy_engine_failfast_gate_drives_convert_disable_f5(monkeypatch, tmp_path):
    """``heavy_engine_failfast`` (the Convert ``disabled=`` source) gates uninstalled F5."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    from diana.tts.registry import heavy_engine_failfast

    msg = heavy_engine_failfast("f5")
    assert msg and "Settings" in msg and "Voices" in msg, (
        f"uninstalled F5 must yield an actionable install message, got: {msg!r}"
    )
    # A light engine is never heavy-gated -> Convert stays enabled.
    assert heavy_engine_failfast("native_os") is None
    assert heavy_engine_failfast("kokoro") is None


# --- D-08: the license gate shows BEFORE any Install control (unaccepted) -----------
def test_settings_f5_license_gate_before_install(monkeypatch, tmp_path):
    """Settings: the F5 row shows the CC-BY-NC disclosure + 'I accept' and NO Install yet."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    cfg, db = _tmp_config(monkeypatch, tmp_path, engine="native_os")

    # Sanity: the license is NOT accepted out of the box.
    assert get_setting(db, "license.accepted.f5", None) is None

    before = {m for m in _HEAVY_SDKS if m in sys.modules}
    at = AppTest.from_file(_SETTINGS, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    text = _captions(at)
    assert "Heavy opt-in engines" in text, f"missing Heavy opt-in engines section:\n{text}"
    # The non-commercial disclosure + the actual license link must be shown.
    assert "non-commercial" in text.lower(), (
        f"expected the CC-BY-NC non-commercial disclosure, got:\n{text}"
    )
    assert "SWivid/F5-TTS" in text, "expected the actual F5 license link (SWivid/F5-TTS)"

    # The "I accept" button exists; NO F5 Install control before acceptance (D-08).
    accept_btns = [b for b in at.button if b.key == "f5_accept_license"]
    assert accept_btns, "no 'I accept' license button rendered on the F5 row"
    f5_install_btns = [
        b for b in at.button if b.key in ("f5_install_confirm", "f5_install")
    ]
    assert not f5_install_btns, (
        "F5 Install must NOT appear before the license is accepted (D-08)"
    )

    # The license gate did not import any heavy SDK (ENGINE-01 / D-17).
    newly = {m for m in _HEAVY_SDKS if m in sys.modules} - before
    assert not newly, f"Settings license gate imported heavy SDK(s): {newly}"


# --- D-08: once accepted (persisted), the footprint confirm + Install appear --------
def test_settings_f5_install_appears_after_accept(monkeypatch, tmp_path):
    """Settings: after the accept-once flag is set, the F5 footprint confirm + Install show."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    cfg, db = _tmp_config(monkeypatch, tmp_path, engine="native_os")

    # Simulate the user having accepted the license (persisted in app_settings, D-08).
    set_setting(db, "license.accepted.f5", "1")
    assert get_setting(db, "license.accepted.f5", None) == "1"

    before = {m for m in _HEAVY_SDKS if m in sys.modules}
    at = AppTest.from_file(_SETTINGS, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    text = _captions(at)
    # The itemized deps-vs-model footprint confirm now shows for F5.
    assert "dependencies" in text and "model" in text and "total" in text, (
        f"expected an itemized deps + model footprint confirm after accept, got:\n{text}"
    )
    # The Install action exists now; the "I accept" gate is gone (acceptance persisted).
    install_btns = [
        b for b in at.button if b.key in ("f5_install_confirm", "f5_install")
    ]
    assert install_btns, "no F5 Install button after the license was accepted"
    accept_btns = [b for b in at.button if b.key == "f5_accept_license"]
    assert not accept_btns, "the 'I accept' gate must be gone once accepted (D-08)"

    newly = {m for m in _HEAVY_SDKS if m in sys.modules} - before
    assert not newly, f"Settings install row imported heavy SDK(s): {newly}"
