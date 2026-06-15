"""Orpheus heavy engine — the first opt-in neural voice (HEAVY-01, D-01/D-17).

Orpheus is the lowest-risk heavy engine: torch-FREE (``orpheus-cpp`` decodes SNAC via
onnxruntime and runs the GGUF through prebuilt ``llama-cpp-python`` CPU/Metal wheels),
CPU-viable, with 8 named voices baked in (the Kokoro single-model precedent — one
engine-level model, many voices, D-19). It proves the whole heavy-engine scaffold
end-to-end: install (05-03 bundled-uv provisioner) -> select -> synthesize.

Two disciplines, mirrored verbatim from the proven light engines:

  1. **No heavy import on the cheap path (ENGINE-01 / D-17).** This module's top imports
     are stdlib + ``TTSVoice`` ONLY — never ``orpheus_cpp`` / ``llama_cpp`` / ``torch``.
     Enumerating the 8 voices and rendering a badge pulls in nothing heavy; the SDK
     lives ONLY in ``heavy_workers/orpheus_worker.py``, run by the venv's own python.
  2. **Out-of-process subprocess synth (T-05-CMD, the native_os precedent).**
     ``synthesize`` shells ``[<venv-python>, orpheus_worker.py]`` and passes the chunk
     text as stdin JSON DATA — never interpolated into the argv / a shell string. The
     temp WAV is always unlinked. ``HF_HOME`` points the worker at Diana's per-user
     cache so weights resolve where the installer put them (Pitfall 8 / D-07).

``initialize()`` is a cheap fail-fast: it consults the filesystem install-state probe
and, when Orpheus is not installed, raises a ``FileNotFoundError`` pointing the user at
Settings ▸ Voices (D-16) — it never imports ``orpheus_cpp`` to find out.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from diana.tts.base import TTSVoice

from diana import paths

# llama-cpp-python ships ABI-agnostic ``py3-none-<platform>`` wheels on the abetlen
# index for macOS arm64 (cpu+metal) AND win_amd64 (cpu), so one pin works on every
# supported CPython 3.x with no source build (05-03 Task 1). macOS uses the metal
# index for GPU acceleration; every other OS uses the cpu index.
_ABETLEN_CPU = "https://abetlen.github.io/llama-cpp-python/whl/cpu"
_ABETLEN_METAL = "https://abetlen.github.io/llama-cpp-python/whl/metal"

# Conservative footprint estimates (GB) feeding the D-04 itemized confirm + the
# has_space pre-check. The Settings row reads the exact live sizes at download time
# (the GGUF is ~2.3 GB Q4_K_M, plus the SNAC ONNX decoder); these only need to be in
# the right ballpark for the disk-space gate.
_GB = 1024 ** 3


def _is_win() -> bool:
    """True on Windows (the venv interpreter is ``Scripts/python.exe`` vs ``bin/python``)."""
    return sys.platform == "win32"


def orpheus_install_spec():
    """The Orpheus install recipe (deps + weights), code-pinned (the Kokoro-asset precedent).

    Returns a :class:`~diana.tts.heavy_install.HeavyInstallSpec` the Settings install
    row consumes verbatim, so no repo IDs / pins are hardcoded in the page. ``packages``
    are the exact 05-03-verified pins installed ONLY from PyPI + the abetlen wheel index;
    ``prefetch_argv`` is the venv-python worker command that warms the GGUF + SNAC weights
    into ``HF_HOME`` (Phase B). The abetlen index is selected per-OS: ``metal`` on Apple
    Silicon for GPU acceleration, ``cpu`` everywhere else. ``heavy_install`` is imported
    lazily so this module's cheap path never pulls the provisioner in.
    """
    from diana.tts.heavy_install import HeavyInstallSpec

    extra_index = _ABETLEN_METAL if sys.platform == "darwin" else _ABETLEN_CPU
    return HeavyInstallSpec(
        engine="orpheus",
        venv_name="orpheus",
        packages=["orpheus-cpp==0.0.3", "llama-cpp-python==0.3.29"],
        extra_index=extra_index,
        prefetch_argv=[str(paths.heavy_worker("orpheus_worker.py")), "--prefetch"],
        deps_bytes=int(0.4 * _GB),
        weights_bytes=int(2.6 * _GB),
    )


class OrpheusEngine:
    name = "orpheus"

    # 8 named voices baked into the Orpheus 3B finetune (D-19: one engine-level model,
    # many voices — the Kokoro precedent). Genders per the orpheus-cpp voice set; tier
    # "enhanced" so the quality ordering ranks them with the best OS/neural voices.
    VOICES = [
        TTSVoice("tara", "Tara (Female)", "en-us", "female", "enhanced"),
        TTSVoice("leah", "Leah (Female)", "en-us", "female", "enhanced"),
        TTSVoice("jess", "Jess (Female)", "en-us", "female", "enhanced"),
        TTSVoice("mia", "Mia (Female)", "en-us", "female", "enhanced"),
        TTSVoice("zoe", "Zoe (Female)", "en-us", "female", "enhanced"),
        TTSVoice("leo", "Leo (Male)", "en-us", "male", "enhanced"),
        TTSVoice("dan", "Dan (Male)", "en-us", "male", "enhanced"),
        TTSVoice("zac", "Zac (Male)", "en-us", "male", "enhanced"),
    ]

    def initialize(self) -> None:
        """Cheap fail-fast: refuse (actionably) when Orpheus is not installed (D-16).

        Consults the filesystem install-state probe ONLY — NO ``orpheus_cpp`` import.
        ``install_state`` is imported lazily so even constructing/initializing the
        engine never pulls a heavy SDK onto the app interpreter (ENGINE-01).
        """
        from diana.tts import install_state

        if not install_state.heavy_engine_installed("orpheus"):
            raise FileNotFoundError(
                "Orpheus not installed — open Settings ▸ Voices and click Install."
            )

    async def synthesize(self, text: str, voice: str = "tara", speed: float = 1.0) -> bytes:
        """Synthesize one chunk OUT OF PROCESS in the orpheus venv, return WAV bytes.

        Offloads the blocking subprocess to the default executor so the worker thread's
        asyncio loop is never blocked (the native_os/piper precedent).
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._subprocess_synth, text, voice, speed
        )

    def _subprocess_synth(self, text: str, voice: str, speed: float) -> bytes:
        """Shell ``[<venv-python>, orpheus_worker.py]`` with the request as stdin JSON.

        T-05-CMD: list argv, ``shell=False``; the document text + voice id travel as
        stdin DATA (a JSON object), NEVER interpolated into the command. The venv python
        and worker paths come from ``paths`` (not PATH — T-05-EXE). ``HF_HOME`` points
        the worker at Diana's per-user cache so the weights resolve where the installer
        put them (Pitfall 8). The temp WAV is always unlinked.
        """
        vpy = paths.venvs_dir() / "orpheus" / (
            "Scripts/python.exe" if _is_win() else "bin/python"
        )
        worker = paths.heavy_worker("orpheus_worker.py")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            out = f.name
        try:
            req = json.dumps({"text": text, "voice_id": voice, "out": out})
            p = subprocess.run(
                [str(vpy), str(worker)],
                input=req,
                text=True,
                capture_output=True,
                timeout=600,
                env={**os.environ, "HF_HOME": str(paths.hf_cache_dir())},
            )
            if p.returncode != 0:
                raise RuntimeError(f"Orpheus synth failed: {(p.stderr or '').strip()}")
            return Path(out).read_bytes()
        finally:
            Path(out).unlink(missing_ok=True)

    def list_voices(self) -> list[TTSVoice]:
        return list(self.VOICES)

    def default_voice(self) -> str:
        return "tara"

    def shutdown(self) -> None:
        return None
