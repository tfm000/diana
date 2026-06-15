"""Interaction-level AppTest pre-check for the Fish S2 Pro vertical slice (05-07, HEAVY-03).

The active UI policy (drive the REAL flow through ``streamlit.testing.v1.AppTest`` and
assert on the resulting widgets, because shallow "renders without exception" tests missed
real logic bugs at earlier checkpoints). Fish is the FINAL engine and the GPU-gated one
(D-10), so these cover the load-bearing surfaces on the LIVE no-capable-GPU path — the real
state of almost every verifying machine (macOS / no ``nvidia-smi``):

  * Settings ▸ Voices (D-10 shown-but-disabled): on a machine WITHOUT a capable NVIDIA GPU
    the Fish row is SHOWN with a DISABLED "Install" button + the VRAM reason caption — it is
    NOT hidden, and NO license/footprint/Install-flow control appears (no download can
    start). This is asserted on the LIVE gate (this box has no nvidia-smi), not a mock.
  * Upload (D-16 / D-10 fail-fast): selecting Fish surfaces an actionable readiness note,
    and the exact gate wired into the Convert button's ``disabled=``
    (``registry.heavy_engine_failfast``) returns an install message for uninstalled Fish
    and ``None`` for a light engine.
  * Settings ▸ Voices (D-08, GPU mocked ok): with ``capable_nvidia_gpu`` monkeypatched to
    ``(True, 24, "")``, the Fish row then shows the Fish Audio Research License /
    CC-BY-NC-SA-4.0 non-commercial disclosure + an "I accept" button BEFORE any Install
    control — the GPU gate having opened, the license gate is the next barrier.

Everything is deterministic + OFFLINE: the heavy per-user dirs point at ``tmp_path`` (so
``heavy_engine_installed('fish')`` reads False — uninstalled), the config singleton points
at a tmp sqlite DB, and the cached voice enumerators are stubbed so no real ``say`` shell /
network / Kokoro work runs. No real install is performed and NO torch/fish_speech is imported.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

import diana.config as C
import diana.dashboard.voice_cache as VC
import diana.paths as P
import diana.tts.gpu_probe as GP
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

# Fish shares the torch venv; assert NONE of these reach the app interpreter (ENGINE-01).
_HEAVY_SDKS = ("torch", "fish_speech", "f5_tts", "torchaudio")


def _tmp_heavy_paths(monkeypatch, tmp_path):
    """Point every heavy per-user dir at tmp so Fish reads as NOT installed."""
    for name in ("venvs_dir", "hf_cache_dir", "model_dir", "voices_dir"):
        sub = tmp_path / name.replace("_dir", "")
        sub.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(P, name, lambda _d=sub: _d, raising=False)


def _no_gpu(monkeypatch):
    """Force the torch-free GPU gate to the LIVE no-capable-GPU result (D-10).

    Most CI/dev boxes have no ``nvidia-smi`` so this already holds, but pinning it makes the
    shown-but-disabled assertions deterministic regardless of where the suite runs.
    """
    monkeypatch.setattr(
        GP, "capable_nvidia_gpu",
        lambda *a, **k: (False, 0, "requires an NVIDIA GPU with ~12+ GB VRAM (none detected)"),
    )


def _gpu_ok(monkeypatch):
    """Force a capable GPU so the GPU gate opens and the license gate becomes the barrier."""
    monkeypatch.setattr(GP, "capable_nvidia_gpu", lambda *a, **k: (True, 24, ""))


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
    fish = [TTSVoice("f5_default", "Default (Fish)", "en-us", "neutral", "enhanced")]
    monkeypatch.setattr(
        VC, "cached_voices",
        lambda engine_name: list(fish) if engine_name == "fish" else list(nat),
    )
    monkeypatch.setattr(
        VC, "cached_all_engine_voices",
        lambda: [("native_os", nat[0]), ("fish", fish[0])],
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


# --- D-10: WITHOUT a capable GPU the Fish row is SHOWN-but-DISABLED (never hidden) ---
def test_settings_fish_shown_but_disabled_without_gpu(monkeypatch, tmp_path):
    """Settings: no capable GPU -> Fish row SHOWN with a DISABLED Install + VRAM reason."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    _no_gpu(monkeypatch)
    _tmp_config(monkeypatch, tmp_path, engine="native_os")

    before = {m for m in _HEAVY_SDKS if m in sys.modules}
    at = AppTest.from_file(_SETTINGS, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    text = _captions(at)
    assert "Heavy opt-in engines" in text, f"missing Heavy opt-in engines section:\n{text}"
    # The row is SHOWN (Fish title) — never hidden (D-10).
    assert "Fish" in text, f"the Fish row must be SHOWN even without a GPU, got:\n{text}"
    # The VRAM reason caption is present.
    assert "VRAM" in text or "GPU" in text, (
        f"expected the GPU/VRAM reason on the shown-disabled Fish row, got:\n{text}"
    )

    # A DISABLED Install button is rendered for Fish (shown-but-disabled, D-10).
    disabled_btns = [
        b for b in at.button if b.key == "fish_install_disabled"
    ]
    assert disabled_btns, "expected a DISABLED Fish Install button (shown-but-disabled, D-10)"
    assert disabled_btns[0].disabled, "the shown Fish Install button must be DISABLED"

    # NO download can start: neither the license-accept nor the enabled Install/confirm
    # controls appear while the GPU gate is closed (D-10 — acceptance/footprint never shown).
    assert not [b for b in at.button if b.key == "fish_accept_license"], (
        "no license-accept control may appear while Fish is GPU-disabled (D-10)"
    )
    assert not [
        b for b in at.button if b.key in ("fish_install_confirm", "fish_install")
    ], "no enabled Fish Install/confirm may appear while the GPU gate is closed (D-10)"

    newly = {m for m in _HEAVY_SDKS if m in sys.modules} - before
    assert not newly, f"the shown-disabled Fish row imported heavy SDK(s): {newly}"


# --- D-16/D-10: selecting uninstalled Fish surfaces an actionable readiness note -----
def test_upload_fish_selection_shows_actionable_note(monkeypatch, tmp_path):
    """Upload: choosing Fish (uninstalled, no GPU) shows an actionable readiness note."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    _no_gpu(monkeypatch)
    _tmp_config(monkeypatch, tmp_path, engine="native_os")

    before = {m for m in _HEAVY_SDKS if m in sys.modules}
    at = AppTest.from_file(_UPLOAD, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    engine_sel = next((s for s in at.selectbox if "Engine" in (s.label or "")), None)
    assert engine_sel is not None, "Engine selectbox not found"
    engine_sel.set_value("fish").run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    text = _captions(at)
    # On a GPU-less box the readiness note surfaces the GPU/VRAM reason (D-10) — the user
    # sees WHY Fish is unavailable rather than a blank/Ready badge.
    assert "GPU" in text or "VRAM" in text, (
        f"expected the Fish GPU-gate reason on the Upload readiness note, got:\n{text}"
    )
    newly = {m for m in _HEAVY_SDKS if m in sys.modules} - before
    assert not newly, f"Upload Fish selection imported heavy SDK(s): {newly}"


# --- D-16: the exact gate wired into the Convert button's disabled= -----------------
def test_heavy_engine_failfast_gate_drives_convert_disable_fish(monkeypatch, tmp_path):
    """``heavy_engine_failfast`` (the Convert ``disabled=`` source) gates uninstalled Fish."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    from diana.tts.registry import heavy_engine_failfast

    msg = heavy_engine_failfast("fish")
    assert msg and "Settings" in msg and "Voices" in msg, (
        f"uninstalled Fish must yield an actionable install message, got: {msg!r}"
    )
    # A light engine is never heavy-gated -> Convert stays enabled.
    assert heavy_engine_failfast("native_os") is None
    assert heavy_engine_failfast("kokoro") is None


# --- D-08: with the GPU gate OPEN, the NC-license disclosure precedes any Install ----
def test_settings_fish_license_gate_after_gpu_ok(monkeypatch, tmp_path):
    """Settings: GPU mocked ok -> Fish row shows the NC license + 'I accept', NO Install yet."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    _gpu_ok(monkeypatch)
    cfg, db = _tmp_config(monkeypatch, tmp_path, engine="native_os")

    # Sanity: the Fish license is NOT accepted out of the box.
    assert get_setting(db, "license.accepted.fish", None) is None

    before = {m for m in _HEAVY_SDKS if m in sys.modules}
    at = AppTest.from_file(_SETTINGS, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    text = _captions(at)
    assert "Heavy opt-in engines" in text, f"missing Heavy opt-in engines section:\n{text}"
    # The Fish non-commercial disclosure + the actual model-card link must be shown.
    assert "non-commercial" in text.lower(), (
        f"expected the Fish CC-BY-NC-SA non-commercial disclosure, got:\n{text}"
    )
    assert "fishaudio/s2-pro" in text, "expected the Fish model-card license link"

    # The Fish "I accept" button exists; NO Fish Install control before acceptance (D-08).
    accept_btns = [b for b in at.button if b.key == "fish_accept_license"]
    assert accept_btns, "no 'I accept' license button rendered on the Fish row"
    install_btns = [
        b for b in at.button if b.key in ("fish_install_confirm", "fish_install")
    ]
    assert not install_btns, (
        "Fish Install must NOT appear before the license is accepted (D-08)"
    )
    # With the GPU gate open, the shown-disabled button is gone (the row fell through).
    assert not [b for b in at.button if b.key == "fish_install_disabled"], (
        "the shown-disabled Install must be gone once the GPU gate is open"
    )

    newly = {m for m in _HEAVY_SDKS if m in sys.modules} - before
    assert not newly, f"Settings Fish license gate imported heavy SDK(s): {newly}"


# --- D-08/D-10: GPU ok AND license accepted -> the footprint confirm + Install appear -
def test_settings_fish_install_appears_after_gpu_and_accept(monkeypatch, tmp_path):
    """Settings: GPU ok + accept-once flag set -> the Fish footprint confirm + Install show."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    _gpu_ok(monkeypatch)
    cfg, db = _tmp_config(monkeypatch, tmp_path, engine="native_os")

    # Simulate the user having accepted the Fish license (persisted in app_settings, D-08).
    set_setting(db, "license.accepted.fish", "1")
    assert get_setting(db, "license.accepted.fish", None) == "1"

    at = AppTest.from_file(_SETTINGS, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    text = _captions(at)
    # The itemized deps-vs-model footprint confirm now shows for Fish.
    assert "dependencies" in text and "model" in text and "total" in text, (
        f"expected an itemized deps + model footprint confirm after accept, got:\n{text}"
    )
    # The Install action exists now; the "I accept" gate is gone (acceptance persisted).
    install_btns = [
        b for b in at.button if b.key in ("fish_install_confirm", "fish_install")
    ]
    assert install_btns, "no Fish Install button after the license was accepted"
    assert not [b for b in at.button if b.key == "fish_accept_license"], (
        "the 'I accept' gate must be gone once accepted (D-08)"
    )
