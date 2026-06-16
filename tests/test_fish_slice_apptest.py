"""Interaction-level AppTest pre-check for the Fish S2 Pro vertical slice (05-07, HEAVY-03).

The active UI policy (drive the REAL flow through ``streamlit.testing.v1.AppTest`` and
assert on the resulting widgets, because shallow "renders without exception" tests missed
real logic bugs at earlier checkpoints). Fish is the FINAL engine and the GPU-gated one
(D-09 corrected / D-10), now a TRI-STATE (``fish_capability`` -> {cuda, apple, none}). The
LIVE path on THIS box is tier "apple" (an M-series Mac with >=16 GB unified), so the Fish
row is ENABLED-experimental here — these tests therefore PIN the tier explicitly rather than
relying on the live result:

  * Settings ▸ Voices (D-10 shown-but-disabled, tier "none" pinned): on an unsupported host
    the Fish row is SHOWN with a DISABLED "Install" button + the honest NVIDIA-or-Apple
    reason caption — it is NOT hidden, and NO license/footprint/Install-flow control appears.
  * Settings ▸ Voices (tier "apple" pinned): on capable Apple Silicon the Fish row is SHOWN
    and ENABLED-experimental — the EXPERIMENTAL (Metal/MPS) caption is present and (license
    not yet accepted) the NC-license disclosure + "I accept" appears with NO disabled button.
  * Upload (D-16 / D-10 fail-fast): selecting Fish surfaces an actionable readiness note,
    and the exact gate wired into the Convert button's ``disabled=``
    (``registry.heavy_engine_failfast``) returns an install message for uninstalled Fish
    and ``None`` for a light engine.
  * Settings ▸ Voices (D-08, tier "cuda" pinned): with ``fish_capability`` monkeypatched to
    tier "cuda", the Fish row shows the Fish Audio Research License / CC-BY-NC-SA-4.0
    non-commercial disclosure + an "I accept" button BEFORE any Install control — the GPU
    gate having opened, the license gate is the next barrier.

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


def _force_tier(monkeypatch, tier, reason):
    """Pin ``fish_capability`` to a fixed (tier, label, reason) on the imported GP module.

    The Settings/Upload pages call ``gpu_probe.fish_capability()``; patching it on ``GP``
    (the module both pages import) makes every tier assertion deterministic regardless of
    the host — critical here because the LIVE result on this M-series box is tier "apple".
    """
    monkeypatch.setattr(GP, "fish_capability", lambda *a, **k: (tier, tier, reason))


def _tier_none(monkeypatch):
    """Pin tier 'none' (unsupported host) -> the shown-but-disabled row + honest dual reason."""
    _force_tier(
        monkeypatch, "none",
        "requires an NVIDIA GPU (~12+ GB VRAM) or Apple Silicon (16+ GB unified memory)",
    )


def _tier_apple(monkeypatch):
    """Pin tier 'apple' (capable Apple Silicon) -> enabled-experimental behind the license."""
    _force_tier(
        monkeypatch, "apple",
        "experimental on Apple Silicon — runs via Metal/MPS, slower than NVIDIA, "
        "unsupported upstream",
    )


def _tier_cuda(monkeypatch):
    """Pin tier 'cuda' (capable NVIDIA GPU) -> enabled, full support; license is next barrier."""
    _force_tier(monkeypatch, "cuda", "")


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


# --- D-10: tier "none" -> the Fish row is SHOWN-but-DISABLED (never hidden) ---
def test_settings_fish_shown_but_disabled_without_gpu(monkeypatch, tmp_path):
    """Settings: tier 'none' -> Fish row SHOWN with a DISABLED Install + honest dual reason.

    The tier is PINNED to "none" (not the live result): this box is tier "apple" (enabled),
    so the disabled-path assertion must mock an unsupported host to stay meaningful.
    """
    _tmp_heavy_paths(monkeypatch, tmp_path)
    _tier_none(monkeypatch)
    _tmp_config(monkeypatch, tmp_path, engine="native_os")

    before = {m for m in _HEAVY_SDKS if m in sys.modules}
    at = AppTest.from_file(_SETTINGS, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    text = _captions(at)
    assert "Heavy opt-in engines" in text, f"missing Heavy opt-in engines section:\n{text}"
    # The row is SHOWN (Fish title) — never hidden (D-10).
    assert "Fish" in text, f"the Fish row must be SHOWN even without a GPU, got:\n{text}"
    # The honest dual reason names BOTH an NVIDIA GPU and Apple Silicon (no flat NVIDIA-only).
    assert "NVIDIA" in text and "Apple Silicon" in text, (
        f"expected the honest NVIDIA-or-Apple reason on the disabled Fish row, got:\n{text}"
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


# --- tier "apple": capable Apple Silicon -> SHOWN + ENABLED-experimental -------------
def test_settings_fish_apple_silicon_enabled_experimental(monkeypatch, tmp_path):
    """Settings: tier 'apple' -> Fish row ENABLED-experimental (caption + license, no disabled)."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    _tier_apple(monkeypatch)
    cfg, db = _tmp_config(monkeypatch, tmp_path, engine="native_os")

    # Sanity: the Fish license is NOT accepted out of the box, so the license gate shows.
    assert get_setting(db, "license.accepted.fish", None) is None

    before = {m for m in _HEAVY_SDKS if m in sys.modules}
    at = AppTest.from_file(_SETTINGS, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    text = _captions(at)
    assert "Fish" in text, f"the Fish row must be SHOWN on Apple Silicon, got:\n{text}"
    # The EXPERIMENTAL Metal/MPS caption is present on the enabled row.
    low = text.lower()
    assert "experimental" in low and ("mps" in low or "metal" in low), (
        f"expected the EXPERIMENTAL Metal/MPS caption on the Apple Silicon Fish row, got:\n{text}"
    )
    # The row FELL THROUGH to the license gate: 'I accept' appears, NO disabled button.
    assert [b for b in at.button if b.key == "fish_accept_license"], (
        "expected the NC-license 'I accept' on the enabled Apple-Silicon Fish row"
    )
    assert not [b for b in at.button if b.key == "fish_install_disabled"], (
        "the shown-disabled Install must be ABSENT once the GPU gate opens (tier apple)"
    )
    # License not yet accepted -> no Install control yet (D-08 precedes any byte).
    assert not [
        b for b in at.button if b.key in ("fish_install_confirm", "fish_install")
    ], "no Install control may appear before the license is accepted (D-08)"

    newly = {m for m in _HEAVY_SDKS if m in sys.modules} - before
    assert not newly, f"the enabled Apple-Silicon Fish row imported heavy SDK(s): {newly}"


# --- D-16/D-10: selecting uninstalled Fish surfaces an actionable readiness note -----
def test_upload_fish_selection_shows_actionable_note(monkeypatch, tmp_path):
    """Upload: choosing Fish (uninstalled, tier 'none') shows the honest dual-reason note.

    The tier is PINNED to "none" so the disabled-reason assertion is meaningful regardless
    of host (this box is tier "apple", which would instead show the experimental note).
    """
    _tmp_heavy_paths(monkeypatch, tmp_path)
    _tier_none(monkeypatch)
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
    # On an unsupported host the readiness note surfaces the honest dual reason (D-10) — the
    # user sees WHY Fish is unavailable (NVIDIA OR Apple Silicon), not a flat NVIDIA-only claim.
    assert "NVIDIA" in text and "Apple Silicon" in text, (
        f"expected the honest NVIDIA-or-Apple reason on the Upload readiness note, got:\n{text}"
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


# --- D-08: with the GPU gate OPEN (tier cuda), the NC-license disclosure precedes Install -
def test_settings_fish_license_gate_after_gpu_ok(monkeypatch, tmp_path):
    """Settings: tier 'cuda' -> Fish row shows the NC license + 'I accept', NO Install yet."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    _tier_cuda(monkeypatch)
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


# --- D-08/D-10: tier cuda AND license accepted -> the footprint confirm + Install appear -
def test_settings_fish_install_appears_after_gpu_and_accept(monkeypatch, tmp_path):
    """Settings: tier 'cuda' + accept-once flag set -> the Fish footprint confirm + Install show."""
    _tmp_heavy_paths(monkeypatch, tmp_path)
    _tier_cuda(monkeypatch)
    cfg, db = _tmp_config(monkeypatch, tmp_path, engine="native_os")

    # Simulate the user having accepted the Fish license (persisted in app_settings, D-08).
    set_setting(db, "license.accepted.fish", "1")
    assert get_setting(db, "license.accepted.fish", None) == "1"

    at = AppTest.from_file(_SETTINGS, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"

    text = _captions(at)
    # Step 1: the Install button shows now; the "I accept" gate is gone (acceptance persisted).
    install_btns = [b for b in at.button if b.key == "fish_install_confirm"]
    assert install_btns, "no Fish Install button after the license was accepted"
    assert not [b for b in at.button if b.key == "fish_accept_license"], (
        "the 'I accept' gate must be gone once accepted (D-08)"
    )

    # Step 2: clicking Install reveals the itemized deps-vs-model footprint + Confirm.
    install_btns[0].click().run()
    assert at.exception is None or len(at.exception) == 0, f"page raised after click: {at.exception}"
    text = _captions(at)
    assert "dependencies" in text and "model" in text and "total" in text, (
        f"expected an itemized deps + model footprint confirm after clicking Install, got:\n{text}"
    )
    assert [b for b in at.button if b.key == "fish_install"], (
        "no 'Confirm — download' button after clicking Install"
    )
