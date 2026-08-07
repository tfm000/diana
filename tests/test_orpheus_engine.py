"""Wave-0 RED/skip scaffold for the Orpheus engine (Plan 04, HEAVY-01).

Orpheus is the torch-free, CPU-viable engine: 8 named voices (Kokoro-style D-19),
synthesized OUT OF PROCESS by the orpheus venv's own python running a worker
script (RESEARCH Pattern 2). The app interpreter NEVER imports ``orpheus_cpp``
(ENGINE-01 / D-17). These tests mock ``subprocess.run`` and assert:

  - ``OrpheusEngine.VOICES`` is a static list of 8 ``TTSVoice`` enumerable with NO
    heavy import (``orpheus_cpp`` absent from ``sys.modules``);
  - ``initialize()`` raises ``FileNotFoundError`` naming "Settings ▸ Voices" when
    the engine is not installed (D-16 fail-fast);
  - ``synthesize`` shells ``[<venv-python>, orpheus_worker.py]`` with the text passed
    as stdin JSON (``{"text","voice_id","out"}`` — DATA, never a shell string,
    T-05-CMD), ``HF_HOME`` set in env (Pitfall 8), and returns the worker's WAV bytes.

``OrpheusEngine`` lands in Wave 2; collection stays GREEN until then.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from diana.tts.base import TTSVoice

# --- Guarded import: OrpheusEngine lands in Wave 2 --------------------------
try:
    from diana.tts.orpheus_engine import OrpheusEngine

    _ORPHEUS_AVAILABLE = True
except ImportError:
    OrpheusEngine = None  # type: ignore[assignment]
    _ORPHEUS_AVAILABLE = False


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


# --- HEAVY-01 / ENGINE-01: 8 static voices, no heavy import -----------------
@pytest.mark.skipif(not _ORPHEUS_AVAILABLE, reason="OrpheusEngine lands in Wave 2")
def test_voices_static_eight_no_heavy_import():
    """8 named ``TTSVoice``, enumerable without importing orpheus_cpp (D-17/D-19)."""
    voices = list(OrpheusEngine.VOICES)
    assert len(voices) == 8
    assert all(isinstance(v, TTSVoice) for v in voices)
    assert all(v.id for v in voices)
    assert "orpheus_cpp" not in sys.modules, "enumerating voices must not import the SDK"


# --- D-16: initialize refuses (actionably) when not installed ---------------
@pytest.mark.skipif(not _ORPHEUS_AVAILABLE, reason="OrpheusEngine lands in Wave 2")
def test_initialize_refuses_when_not_installed(monkeypatch):
    """`initialize` raises FileNotFoundError pointing at Settings ▸ Voices (D-16)."""
    _force_heavy_installed(monkeypatch, False, "diana.tts.orpheus_engine")
    eng = OrpheusEngine()
    with pytest.raises(FileNotFoundError) as exc:
        eng.initialize()
    msg = str(exc.value)
    assert "Settings" in msg and "Voices" in msg


# --- HEAVY-01 / T-05-CMD: subprocess synth, text as stdin JSON --------------
@pytest.mark.skipif(not _ORPHEUS_AVAILABLE, reason="OrpheusEngine lands in Wave 2")
@pytest.mark.asyncio
async def test_synthesize_subprocess_cmd_and_stdin_json(tmp_data_paths, fake_venv,
                                                       monkeypatch):
    """`synthesize` runs [venv-python, orpheus_worker.py] with text as stdin JSON."""
    fake_venv("orpheus")
    _force_heavy_installed(monkeypatch, True, "diana.tts.orpheus_engine")

    captured: dict = {}
    riff = b"RIFF\x00\x00\x00\x00WAVEfmt "

    def _fake_run(cmd, *a, **k):
        captured["cmd"] = list(cmd)
        captured["input"] = k.get("input")
        captured["env"] = k.get("env") or {}
        req = json.loads(k.get("input"))
        Path(req["out"]).write_bytes(riff)  # the worker writes the WAV here
        return MagicMock(returncode=0, stderr="", stdout="")

    eng = OrpheusEngine()
    with patch("diana.tts.orpheus_engine.subprocess.run", side_effect=_fake_run):
        data = await eng.synthesize("hello world", voice="tara", speed=1.0)

    # Bytes round-trip from the worker's temp WAV.
    assert bytes(data[:4]) == b"RIFF" and bytes(data[8:12]) == b"WAVE"
    # argv = [<venv python>, <orpheus_worker.py>]
    # Match on path COMPONENTS, not a "bin/python" suffix: Windows renders
    # str(Path) with backslashes, so a forward-slash suffix never matches there.
    _py = Path(str(captured["cmd"][0]))
    assert _py.name in ("python", "python.exe") and _py.parent.name in ("bin", "Scripts")
    assert str(captured["cmd"][1]).endswith("orpheus_worker.py")
    # Text is DATA on stdin, never interpolated into argv (T-05-CMD).
    assert "hello world" not in " ".join(str(c) for c in captured["cmd"])
    req = json.loads(captured["input"])
    assert req["text"] == "hello world"
    assert req["voice_id"] == "tara"
    assert "out" in req
    # HF_HOME points the worker at Diana's per-user cache (Pitfall 8).
    assert "HF_HOME" in captured["env"]
