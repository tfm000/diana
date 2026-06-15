"""Wave-0 RED/skip scaffold for the F5-TTS engine (Plan 05, HEAVY-02).

F5 is zero-shot voice cloning: it has no baked-in voices — it surfaces a bundled
license-clean default (D-15) plus any saved custom voices (D-14), and synthesizes
OUT OF PROCESS by the shared torch venv running a worker (RESEARCH Pattern 2 / F5
worker example). The app interpreter NEVER imports torch (ENGINE-01 / D-17). These
tests mock ``subprocess.run`` and assert:

  - ``list_voices()`` includes at least the bundled default, enumerable with NO
    torch import;
  - ``synthesize`` shells ``[<venv-python>, f5_worker.py]`` carrying
    ``ref_file`` / ``ref_text`` / ``gen_text`` as stdin JSON (gen_text = the text to
    speak, DATA never a shell string), ``HF_HOME`` set in env.

``F5Engine`` lands in Wave 4; collection stays GREEN until then.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from diana.tts.base import TTSVoice

# --- Guarded import: F5Engine lands in Wave 4 -------------------------------
try:
    from diana.tts.f5_engine import F5Engine

    _F5_AVAILABLE = True
except ImportError:
    F5Engine = None  # type: ignore[assignment]
    _F5_AVAILABLE = False


def _force_heavy_installed(monkeypatch, value, *modnames):
    """Force ``heavy_engine_installed`` -> ``value`` at the source + any engine binding."""
    import diana.tts.install_state as _ist

    monkeypatch.setattr(_ist, "heavy_engine_installed",
                        lambda *a, **k: value, raising=False)
    for name in modnames:
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "heavy_engine_installed"):
            monkeypatch.setattr(mod, "heavy_engine_installed",
                                lambda *a, **k: value, raising=False)


# --- HEAVY-02 / D-15: bundled default voice, enumerable without torch -------
@pytest.mark.skipif(not _F5_AVAILABLE, reason="F5Engine lands in Wave 4")
def test_list_voices_has_bundled_default_no_torch(tmp_data_paths):
    """`list_voices()` surfaces >=1 voice (the bundled default) and imports no torch."""
    eng = F5Engine()
    voices = eng.list_voices()
    assert len(voices) >= 1  # the bundled license-clean default (D-15)
    assert all(isinstance(v, TTSVoice) for v in voices)
    assert "torch" not in sys.modules, "voice enumeration must not import torch (D-17)"


# --- HEAVY-02 / T-05-CMD: subprocess synth carries ref + gen text -----------
@pytest.mark.skipif(not _F5_AVAILABLE, reason="F5Engine lands in Wave 4")
@pytest.mark.asyncio
async def test_synthesize_carries_ref_and_gen_text(tmp_data_paths, fake_venv,
                                                  monkeypatch):
    """`synthesize` runs [venv-python, f5_worker.py] with ref_file/ref_text/gen_text."""
    fake_venv("f5")
    _force_heavy_installed(monkeypatch, True, "diana.tts.f5_engine")

    captured: dict = {}
    riff = b"RIFF\x00\x00\x00\x00WAVEfmt "

    def _fake_run(cmd, *a, **k):
        captured["cmd"] = list(cmd)
        captured["input"] = k.get("input")
        captured["env"] = k.get("env") or {}
        req = json.loads(k.get("input"))
        Path(req["out"]).write_bytes(riff)
        return MagicMock(returncode=0, stderr="", stdout="")

    eng = F5Engine()
    voice_id = eng.list_voices()[0].id  # the bundled default's clone reference
    with patch("diana.tts.f5_engine.subprocess.run", side_effect=_fake_run):
        data = await eng.synthesize("clone this sentence", voice=voice_id, speed=1.0)

    assert bytes(data[:4]) == b"RIFF" and bytes(data[8:12]) == b"WAVE"
    assert str(captured["cmd"][0]).endswith(("bin/python", "Scripts/python.exe"))
    assert str(captured["cmd"][1]).endswith("f5_worker.py")
    req = json.loads(captured["input"])
    assert req.get("gen_text") == "clone this sentence"  # text to speak
    assert "ref_file" in req and "ref_text" in req       # the clone reference
    assert "clone this sentence" not in " ".join(str(c) for c in captured["cmd"])
    assert "HF_HOME" in captured["env"]
