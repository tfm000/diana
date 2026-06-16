"""Fish Audio S2 Pro engine tests — TRI-STATE GPU gate (Plan 07 + quick-260616-hk6).

Fish is GPU-gated (D-09 corrected / D-10): it runs when installed AND the host is a capable
NVIDIA GPU (tier "cuda", full support) OR capable Apple Silicon (tier "apple", EXPERIMENTAL
via MPS). It is the F5 sibling — shares the torch venv and synthesizes OUT OF PROCESS via a
worker (RESEARCH A6 / Pattern 2). The app interpreter NEVER imports torch (ENGINE-01 / D-17).
These tests mock the tri-state ``fish_capability`` probe + ``subprocess.run`` and assert:

  - ``initialize()`` raises an actionable error when NOT installed (regardless of tier) and
    when installed on tier "none" (D-16 fail-fast); installed + tier "cuda" OR "apple" passes;
  - ``synthesize`` shells ``[<venv-python>, fish_worker.py]`` with the text passed as
    stdin JSON data (never a shell string), ``HF_HOME`` set in env.

``FishEngine`` lands in Wave 7; collection stays GREEN until then.
"""

import contextlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from diana.tts.base import TTSVoice

# --- Guarded import: FishEngine lands in Wave 7 -----------------------------
try:
    from diana.tts.fish_engine import FishEngine

    _FISH_AVAILABLE = True
except ImportError:
    FishEngine = None  # type: ignore[assignment]
    _FISH_AVAILABLE = False


def _force_heavy_installed(monkeypatch, value, *modnames):
    import diana.tts.install_state as _ist

    monkeypatch.setattr(_ist, "heavy_engine_installed",
                        lambda *a, **k: value, raising=False)
    for name in modnames:
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "heavy_engine_installed"):
            monkeypatch.setattr(mod, "heavy_engine_installed",
                                lambda *a, **k: value, raising=False)


def _force_fish_capability(monkeypatch, tier, reason="", *modnames):
    """Force ``fish_capability`` -> (tier, label, reason) at source + engine binding.

    Mirrors the dual-patch pattern: patch the ``gpu_probe`` source AND any module that may
    have already bound ``fish_capability`` (the engine imports it lazily inside
    ``initialize()``, so source-patching is enough, but the modname loop keeps parity with
    the install-state helper).
    """
    retval = (tier, tier, reason)
    # gpu_probe lands (Wave 6) before FishEngine (Wave 7); suppress the import miss
    # in the interim so this helper is import-safe without a bare ``pass`` body.
    with contextlib.suppress(ImportError):
        import diana.tts.gpu_probe as _gp

        monkeypatch.setattr(_gp, "fish_capability",
                            lambda *a, **k: retval, raising=False)
    for name in modnames:
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "fish_capability"):
            monkeypatch.setattr(mod, "fish_capability",
                                lambda *a, **k: retval, raising=False)


# --- D-09(corrected)/D-10/D-16: refuse unless installed AND a capable tier --
@pytest.mark.skipif(not _FISH_AVAILABLE, reason="FishEngine lands in Wave 7")
def test_initialize_requires_install_and_gpu(monkeypatch):
    """Install + tri-state tier gate: none/not-installed raise; cuda + apple pass (D-16)."""
    # Installed but tier "none" -> refuse with the honest reason.
    _force_heavy_installed(monkeypatch, True, "diana.tts.fish_engine")
    _force_fish_capability(
        monkeypatch, "none",
        "requires an NVIDIA GPU (~12+ GB VRAM) or Apple Silicon (16+ GB unified memory)",
        "diana.tts.fish_engine",
    )
    with pytest.raises((RuntimeError, FileNotFoundError)) as exc:
        FishEngine().initialize()
    assert str(exc.value), "the GPU-gate refusal must carry an actionable message"

    # Capable tier ("cuda") but NOT installed -> refuse (install gate first).
    _force_heavy_installed(monkeypatch, False, "diana.tts.fish_engine")
    _force_fish_capability(monkeypatch, "cuda", "", "diana.tts.fish_engine")
    with pytest.raises((RuntimeError, FileNotFoundError)) as exc2:
        FishEngine().initialize()
    assert str(exc2.value)

    # Installed + tier "cuda" -> no raise (NVIDIA full support, unchanged).
    _force_heavy_installed(monkeypatch, True, "diana.tts.fish_engine")
    _force_fish_capability(monkeypatch, "cuda", "", "diana.tts.fish_engine")
    FishEngine().initialize()  # must not raise

    # Installed + tier "apple" -> no raise (NEW: Apple Silicon now allowed, experimental).
    _force_fish_capability(
        monkeypatch, "apple",
        "experimental on Apple Silicon — runs via Metal/MPS",
        "diana.tts.fish_engine",
    )
    FishEngine().initialize()  # must not raise


# --- HEAVY-03 / T-05-CMD: subprocess synth, text as data --------------------
@pytest.mark.skipif(not _FISH_AVAILABLE, reason="FishEngine lands in Wave 7")
@pytest.mark.asyncio
async def test_synthesize_subprocess_shape(tmp_data_paths, fake_venv, monkeypatch):
    """`synthesize` runs [venv-python, fish_worker.py] with the text as stdin data."""
    fake_venv("fish")
    _force_heavy_installed(monkeypatch, True, "diana.tts.fish_engine")
    _force_fish_capability(monkeypatch, "cuda", "", "diana.tts.fish_engine")

    captured: dict = {}
    riff = b"RIFF\x00\x00\x00\x00WAVEfmt "

    def _fake_run(cmd, *a, **k):
        captured["cmd"] = list(cmd)
        captured["input"] = k.get("input")
        captured["env"] = k.get("env") or {}
        req = json.loads(k.get("input"))
        Path(req["out"]).write_bytes(riff)
        return MagicMock(returncode=0, stderr="", stdout="")

    eng = FishEngine()
    voices = eng.list_voices()
    voice_id = voices[0].id if voices else ""
    assert all(isinstance(v, TTSVoice) for v in voices)
    with patch("diana.tts.fish_engine.subprocess.run", side_effect=_fake_run):
        data = await eng.synthesize("read this aloud", voice=voice_id, speed=1.0)

    assert bytes(data[:4]) == b"RIFF" and bytes(data[8:12]) == b"WAVE"
    assert str(captured["cmd"][1]).endswith("fish_worker.py")
    req = json.loads(captured["input"])
    # Fish mirrors F5's clone JSON (A6); accept either gen_text or a plain text key.
    assert "gen_text" in req or "text" in req
    assert "read this aloud" not in " ".join(str(c) for c in captured["cmd"])
    assert "HF_HOME" in captured["env"]
