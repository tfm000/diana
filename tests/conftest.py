"""Shared fixtures for the Phase-5 heavy-engine Wave-0 test scaffold.

Heavy engines (Orpheus / F5 / Fish) run torch/llama-cpp OUT OF PROCESS in a
per-engine venv, so they cannot run in CI; every Wave-0 test instead MOCKS the
subprocess/venv layer (RESEARCH "Validation Architecture"). These fixtures are
the shared mock surface:

  - ``tmp_data_paths``  — redirect every heavy per-user dir (venvs / hf-cache /
    custom-voices / models) to a tmp subfolder so probes never touch the real
    per-user cache (threat T-04-01). Uses ``raising=False`` so it binds even
    before ``paths.venvs_dir`` / ``hf_cache_dir`` / ``custom_voices_dir`` land
    (Waves 2/3) — the dependent tests are ``skipif``-gated until then.
  - ``fake_venv``       — lay down a fake installed venv (``bin/python`` +
    ``.{engine}.installed`` marker) so ``install_state.heavy_engine_installed``
    resolves True (RESEARCH install-state example: orpheus -> 'orpheus' venv;
    f5/fish -> the shared 'torch' venv).
  - ``mock_uv``         — patch ``subprocess.Popen`` (streaming) + ``subprocess.run``
    so the bundled-``uv`` provisioner (Pattern 1) never spawns a real process;
    returns the recorded argv list so a test can assert the uv argv/order.
  - ``fake_nvidia_smi`` — factory simulating ``nvidia-smi``: absent / below-floor /
    above-floor VRAM, by patching the stdlib ``shutil.which`` + ``subprocess.run``
    the torch-free GPU gate shells (Pattern 4) — so no torch is ever imported.
  - ``temp_clip``       — factory writing a REAL (silent) WAV via soundfile at a
    chosen duration/samplerate + a sibling ``.txt`` transcript. The default is
    16 kHz mono (the ``st.audio_input`` default) because clip validation MUST
    accept sub-24 kHz (Pitfall 5/7).

All fixtures are import-light and Streamlit-free; none import a heavy SDK.
"""

import sys
from unittest.mock import MagicMock

import numpy as np
import pytest
import soundfile as sf

# The two heavy venv homes (RESEARCH install-state example / D-03 shared-torch):
# Orpheus is torch-free in its own venv; F5 + Fish share the 'torch' venv.
_VENV_FOR = {"orpheus": "orpheus", "f5": "torch", "fish": "torch"}


def _venv_python_rel() -> str:
    """The interpreter path inside a venv, per OS (matches RESEARCH probe)."""
    return "Scripts/python.exe" if sys.platform == "win32" else "bin/python"


@pytest.fixture
def tmp_data_paths(tmp_path, monkeypatch):
    """Redirect the heavy per-user dirs to tmp subfolders; return their Paths.

    Monkeypatches ``diana.paths.{venvs_dir,hf_cache_dir,custom_voices_dir,model_dir}``
    to freshly-created subdirs of ``tmp_path``. ``raising=False`` lets the three
    not-yet-landed resolvers bind before their Wave-2/3 implementation exists;
    once they land, this override takes precedence so a test reads tmp, never the
    real ``~/Library/Application Support/Diana`` cache (T-04-01).
    """
    from diana import paths

    roots: dict[str, "object"] = {}
    for name in ("venvs_dir", "hf_cache_dir", "custom_voices_dir", "model_dir"):
        sub = tmp_path / name.replace("_dir", "")
        sub.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(paths, name, lambda _d=sub: _d, raising=False)
        roots[name] = sub
    return roots


@pytest.fixture
def fake_venv(tmp_data_paths):
    """Factory: build a fake installed heavy-engine venv + its marker.

    ``fake_venv(engine)`` lays down ``venvs_dir()/<venv>/<bin/python>`` plus the
    ``venvs_dir()/.<engine>.installed`` marker so ``heavy_engine_installed(engine)``
    resolves True (pure filesystem probe — no SDK import). Returns the venv dir.
    """
    venvs = tmp_data_paths["venvs_dir"]

    def _make(engine: str = "orpheus"):
        venv_dir = venvs / _VENV_FOR.get(engine, "torch")
        py = venv_dir / _venv_python_rel()
        py.parent.mkdir(parents=True, exist_ok=True)
        py.write_text("#!fake venv python\n", encoding="utf-8")
        (venvs / f".{engine}.installed").write_text("1", encoding="utf-8")
        return venv_dir

    return _make


@pytest.fixture
def mock_uv(monkeypatch):
    """Patch ``subprocess.Popen`` + ``subprocess.run`` for the bundled-uv driver.

    ``Popen`` returns a fake process whose ``stdout`` iterates a few uv-style lines
    then exits 0 (so the streaming ``_run`` in Pattern 1 sees progress lines);
    ``run`` returns ``MagicMock(returncode=0, stderr="")``. Both record their argv
    into the returned ``calls`` list so a test can assert the uv argv + venv->install
    ORDER without spawning a real process.
    """
    import subprocess as _subprocess

    calls: list[list] = []

    class _FakeProc:
        def __init__(self, lines):
            self.stdout = iter(lines)
            self.returncode = 0

        def wait(self):
            return 0

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _fake_popen(cmd, *a, **k):
        calls.append(list(cmd))
        return _FakeProc(["Resolved 1 package in 12ms",
                          "Installed 1 package in 30ms", "Done"])

    def _fake_run(cmd, *a, **k):
        calls.append(list(cmd))
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(_subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(_subprocess, "run", _fake_run)
    return calls


@pytest.fixture
def fake_nvidia_smi(monkeypatch):
    """Factory simulating ``nvidia-smi`` for the torch-free GPU gate (Pattern 4).

    ``fake_nvidia_smi(total_mib, returncode=0)``:
      - ``None``  -> no GPU: ``shutil.which('nvidia-smi')`` returns ``None``.
      - integer   -> a present GPU whose ``--query-gpu=memory.total`` CSV is that
        many MiB (``subprocess.run(...).stdout`` -> ``"<mib>\\n"``).
      - ``returncode`` (default 0) -> the exit code returned by the fake nvidia-smi;
        pass a non-zero value to simulate a degraded driver that exits with an error.
    Patches the stdlib ``shutil.which`` / ``subprocess.run`` (which the gate shells)
    so NO torch is imported on the badge path. Returns ``total_mib`` for convenience.
    """
    import shutil as _shutil
    import subprocess as _subprocess

    def _install(total_mib=None, returncode=0):
        if total_mib is None:
            monkeypatch.setattr(_shutil, "which", lambda _name: None)
        else:
            monkeypatch.setattr(_shutil, "which", lambda name: f"/usr/bin/{name}")

            def _fake_run(cmd, *a, **k):
                return MagicMock(returncode=returncode,
                                 stdout=f"{int(total_mib)}\n",
                                 stderr="")

            monkeypatch.setattr(_subprocess, "run", _fake_run)
        return total_mib

    return _install


@pytest.fixture
def temp_clip(tmp_path):
    """Factory: write a REAL WAV clip + a sibling ``.txt`` transcript.

    ``temp_clip(seconds=3.0, samplerate=16000, transcript=..., suffix='.wav')``
    writes a real (silent) mono WAV via soundfile and a transcript file, returning
    ``(wav_path, txt_path)``. The default 16 kHz is deliberate: it is the
    ``st.audio_input`` capture rate, and clip validation must NOT reject sub-24 kHz
    (Pitfall 5/7).
    """
    counter = {"n": 0}

    def _make(seconds: float = 3.0, samplerate: int = 16000,
              transcript: str = "A short reference clip for cloning.",
              suffix: str = ".wav"):
        counter["n"] += 1
        wav = tmp_path / f"clip_{counter['n']}{suffix}"
        frames = max(1, int(samplerate * seconds))
        sf.write(str(wav), np.zeros(frames, dtype="float32"), samplerate,
                 format="WAV")
        txt = wav.with_suffix(".txt")
        txt.write_text(transcript, encoding="utf-8")
        return wav, txt

    return _make
