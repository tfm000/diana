"""Wave-0 RED/skip scaffold for the Fish Audio S2 Pro engine (Plan 07, HEAVY-03).

Fish is GPU-gated (D-09/D-10): it runs only when BOTH installed AND a capable
NVIDIA GPU is present. It is the F5 sibling — shares the torch venv and synthesizes
OUT OF PROCESS via a worker (RESEARCH A6 / Pattern 2). The app interpreter NEVER
imports torch (ENGINE-01 / D-17). These tests mock the GPU probe + ``subprocess.run``
and assert:

  - ``initialize()`` raises an actionable error when NOT (installed AND GPU-capable)
    — both the no-GPU and not-installed cases refuse (D-16 fail-fast);
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


def _force_gpu(monkeypatch, ok, reason="", *modnames):
    """Force ``capable_nvidia_gpu`` -> (ok, vram, reason) at source + engine binding."""
    retval = (ok, (16 if ok else 0), reason)
    # gpu_probe lands (Wave 6) before FishEngine (Wave 7); suppress the import miss
    # in the interim so this helper is import-safe without a bare ``pass`` body.
    with contextlib.suppress(ImportError):
        import diana.tts.gpu_probe as _gp

        monkeypatch.setattr(_gp, "capable_nvidia_gpu",
                            lambda *a, **k: retval, raising=False)
    for name in modnames:
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "capable_nvidia_gpu"):
            monkeypatch.setattr(mod, "capable_nvidia_gpu",
                                lambda *a, **k: retval, raising=False)


# --- D-09/D-10/D-16: refuse unless installed AND GPU-capable ----------------
@pytest.mark.skipif(not _FISH_AVAILABLE, reason="FishEngine lands in Wave 7")
def test_initialize_requires_install_and_gpu(monkeypatch):
    """Both 'no capable GPU' and 'not installed' raise an actionable error (D-16)."""
    # Installed but NO capable GPU -> refuse.
    _force_heavy_installed(monkeypatch, True, "diana.tts.fish_engine")
    _force_gpu(monkeypatch, False, "requires ~12+ GB VRAM", "diana.tts.fish_engine")
    with pytest.raises((RuntimeError, FileNotFoundError)) as exc:
        FishEngine().initialize()
    assert str(exc.value), "the GPU-gate refusal must carry an actionable message"

    # Capable GPU but NOT installed -> refuse.
    _force_heavy_installed(monkeypatch, False, "diana.tts.fish_engine")
    _force_gpu(monkeypatch, True, "", "diana.tts.fish_engine")
    with pytest.raises((RuntimeError, FileNotFoundError)) as exc2:
        FishEngine().initialize()
    assert str(exc2.value)


# --- HEAVY-03 / T-05-CMD: subprocess synth, text as data --------------------
@pytest.mark.skipif(not _FISH_AVAILABLE, reason="FishEngine lands in Wave 7")
@pytest.mark.asyncio
async def test_synthesize_subprocess_shape(tmp_data_paths, fake_venv, monkeypatch):
    """`synthesize` runs [venv-python, fish_worker.py] with the text as stdin data."""
    fake_venv("fish")
    _force_heavy_installed(monkeypatch, True, "diana.tts.fish_engine")
    _force_gpu(monkeypatch, True, "", "diana.tts.fish_engine")

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
