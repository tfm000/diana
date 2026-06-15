"""Interaction-level AppTest pre-check for the Orpheus vertical slice (05-04, HEAVY-01).

The active UI policy (the post-Phase-4 standing requirement: drive the REAL flow through
``streamlit.testing.v1.AppTest`` and assert on the resulting widgets, because shallow
"renders without exception" tests missed real logic bugs at earlier checkpoints). These
cover the two load-bearing surfaces of the Orpheus slice WHILE ORPHEUS IS UNINSTALLED
(the real on-CI state — no multi-GB venv, no heavy SDK):

  * Upload (D-16 fail-fast): selecting the Orpheus engine surfaces the actionable
    "install … in Settings ▸ Voices" prompt, and the exact gate wired into the Convert
    button's ``disabled=`` (``registry.heavy_engine_failfast``) returns that message for
    uninstalled Orpheus and ``None`` for a light engine.
  * Settings ▸ Voices (install row): the "Heavy opt-in engines" subsection renders the
    Orpheus install row with the itemized deps-vs-model footprint confirm and an Install
    action — no exception, and NO ``orpheus_cpp``/``llama_cpp``/``torch`` imported.

Everything is deterministic + OFFLINE: the heavy per-user dirs point at ``tmp_path`` (so
``heavy_engine_installed('orpheus')`` reads False — uninstalled), the config singleton
points at a tmp sqlite DB, and the cached voice enumerators are stubbed so no real
``say`` shell / network / Kokoro work runs. No real install is performed.
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
_UPLOAD = str(_PAGES / "1_Upload.py")
_SETTINGS = str(_PAGES / "5_Settings.py")

_HEAVY_SDKS = ("orpheus_cpp", "llama_cpp", "torch")


def _tmp_heavy_paths(monkeypatch, tmp_path):
    """Point every heavy per-user dir at tmp so Orpheus reads as NOT installed."""
    for name in ("venvs_dir", "hf_cache_dir", "model_dir", "voices_dir"):
        sub = tmp_path / name.replace("_dir", "")
        sub.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(P, name, lambda _d=sub: _d, raising=False)


def _tmp_config(monkeypatch, tmp_path, engine="native_os"):
    """A config singleton on a tmp DB; stub the cached enumerators (offline)."""
    db_path = str(tmp_path / "diana.db")
    init_db(db_path)
    cfg = C.load_config()
    cfg.storage.database_path = db_path
    cfg.tts.engine = engine
    monkeypatch.setattr(C, "get_config", lambda *a, **k: cfg)
    monkeypatch.setattr(VC, "get_config", lambda *a, **k: cfg)
    # Tiny deterministic voice lists so neither page shells `say` or hits the network.
    nat = [TTSVoice("nat-0", "Native 0", "en-us", "male")]
    orph = [TTSVoice("tara", "Tara (Female)", "en-us", "female", "enhanced")]
    monkeypatch.setattr(
        VC, "cached_voices",
        lambda engine_name: list(orph) if engine_name == "orpheus" else list(nat),
    )
    monkeypatch.setattr(
        VC, "cached_all_engine_voices",
        lambda: [("native_os", nat[0]), ("orpheus", orph[0])],
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


# --- D-16: selecting uninstalled Orpheus surfaces the actionable install prompt ----
def test_upload_orpheus_selection_shows_install_prompt(monkeypatch, tmp_path):
    """Upload: choosing Orpheus (uninstalled) shows the 'Settings ▸ Voices' readiness note."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    _tmp_config(monkeypatch, tmp_path, engine="native_os")

    before = {m for m in _HEAVY_SDKS if m in sys.modules}
    at = AppTest.from_file(_UPLOAD, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    # Select the Orpheus engine in the Engine selectbox and re-run.
    engine_sel = next((s for s in at.selectbox if "Engine" in (s.label or "")), None)
    assert engine_sel is not None, "Engine selectbox not found"
    engine_sel.set_value("orpheus").run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    text = _captions(at)
    assert "Settings" in text and "Voices" in text, (
        f"expected an install-in-Settings-Voices readiness note, got:\n{text}"
    )
    # The cheap readiness/badge path must not import the heavy SDK.
    newly = {m for m in _HEAVY_SDKS if m in sys.modules} - before
    assert not newly, f"Upload selection imported heavy SDK(s): {newly}"


# --- D-16: the exact gate wired into the Convert button's disabled= ---------------
def test_heavy_engine_failfast_gate_drives_convert_disable(monkeypatch, tmp_path):
    """``heavy_engine_failfast`` (the Convert ``disabled=`` source) gates uninstalled Orpheus."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    from diana.tts.registry import heavy_engine_failfast

    msg = heavy_engine_failfast("orpheus")
    assert msg and "Settings" in msg and "Voices" in msg, (
        f"uninstalled Orpheus must yield an actionable install message, got: {msg!r}"
    )
    # A light engine is never heavy-gated -> Convert stays enabled.
    assert heavy_engine_failfast("native_os") is None
    assert heavy_engine_failfast("kokoro") is None


# --- Settings ▸ Voices: the Orpheus install row renders (footprint confirm + Install) --
def test_settings_orpheus_install_row_renders(monkeypatch, tmp_path):
    """Settings: the Heavy opt-in engines Orpheus row renders with footprint + Install."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    _tmp_config(monkeypatch, tmp_path, engine="native_os")

    before = {m for m in _HEAVY_SDKS if m in sys.modules}
    at = AppTest.from_file(_SETTINGS, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    text = _captions(at)
    # The subsection header + the itemized deps-vs-model footprint confirm.
    assert "Heavy opt-in engines" in text, f"missing Heavy opt-in engines section:\n{text}"
    assert "Orpheus" in text, "Orpheus row not rendered"
    assert "dependencies" in text and "model" in text and "total" in text, (
        f"expected an itemized deps + model footprint confirm, got:\n{text}"
    )

    # An Install action exists on the Orpheus row.
    install_btns = [b for b in at.button if b.key in ("orpheus_install_confirm", "orpheus_install")]
    assert install_btns, "no Orpheus Install button rendered"

    # Rendering the row imported NO heavy SDK (ENGINE-01 / D-17).
    newly = {m for m in _HEAVY_SDKS if m in sys.modules} - before
    assert not newly, f"Settings row imported heavy SDK(s): {newly}"
