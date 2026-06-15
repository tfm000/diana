"""F5-TTS heavy engine — zero-shot reference-audio voice cloning (HEAVY-02, D-01/D-15/D-17).

F5 has NO baked-in voices: it clones a voice from a reference clip + that clip's exact
transcript. This slice surfaces a single bundled, license-clean DEFAULT voice (D-15) so
"install -> synthesize" works out of the box; saved custom voices (D-14) are merged in by
the next slice (05-06). Synthesis runs OUT OF PROCESS in the SHARED ``torch`` venv (D-03):
F5 installs torch there, Fish reuses it. The app interpreter NEVER imports torch.

Two disciplines, mirrored verbatim from the Orpheus sibling (05-04) and the light engines:

  1. **No heavy import on the cheap path (ENGINE-01 / D-17).** This module's top imports
     are stdlib + ``TTSVoice`` ONLY — never ``torch`` / ``f5_tts``. Enumerating the bundled
     default and rendering a badge pulls in nothing heavy; the SDK lives ONLY in
     ``heavy_workers/f5_worker.py``, run by the torch venv's own python.
  2. **Out-of-process subprocess synth (T-05-CMD, the native_os/Orpheus precedent).**
     ``synthesize`` shells ``[<torch-venv-python>, f5_worker.py]`` and passes the reference
     clip path, the reference transcript, and the gen text as stdin JSON DATA — never
     interpolated into the argv / a shell string. The temp WAV is always unlinked.
     ``HF_HOME`` points the worker at Diana's per-user cache so weights resolve where the
     installer put them (Pitfall 8 / D-07).

``initialize()`` is a cheap fail-fast: it consults the filesystem install-state probe and,
when F5 is not installed, raises a ``FileNotFoundError`` pointing the user at Settings ▸
Voices (D-16) — it never imports ``f5_tts`` to find out. The bundled default clip is a
fixed PACKAGE resource resolved via ``importlib.resources`` (never user input — T-05-PATH);
custom-clip path safety is handled in 05-06.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from importlib import resources
from pathlib import Path

from diana.tts.base import TTSVoice

from diana import paths

# The bundled default reference voice id (D-15). Custom voices (05-06) merge in alongside
# it; this slice surfaces only the bundled default so install -> synthesize works at once.
_DEFAULT_VOICE_ID = "f5_default"

# Conservative footprint estimates (GB) feeding the D-04 itemized confirm + the has_space
# pre-check. F5 pulls torch/torchaudio/vocos/transformers (deps) plus the F5TTS_v1_Base
# checkpoint (weights); the Settings row reads the exact live sizes at download time — these
# only need to be in the right ballpark for the disk-space gate.
_GB = 1024 ** 3


def _is_win() -> bool:
    """True on Windows (the venv interpreter is ``Scripts/python.exe`` vs ``bin/python``)."""
    return sys.platform == "win32"


def _bundled_default_clip() -> Path:
    """Resolve the bundled default reference clip (a SHIPPED package resource — T-05-PATH).

    The clip is package-DATA under ``diana/data/voices/f5_default.wav`` (D-15), resolved
    from the installed package via ``importlib.resources`` — a fixed path, never user
    input. Self-generated on-device (license-clean by construction); the user may swap it.
    """
    return Path(str(resources.files("diana.data").joinpath("voices", "f5_default.wav")))


def _bundled_default_transcript() -> str:
    """The EXACT transcript of the bundled default clip (D-15), shipped beside the WAV.

    F5 needs the reference clip's exact transcript (``ref_text``) — no STT (D-12). Read
    from the bundled ``diana/data/voices/f5_default.txt`` package resource.
    """
    return resources.files("diana.data").joinpath(
        "voices", "f5_default.txt"
    ).read_text(encoding="utf-8").strip()


def f5_install_spec():
    """The F5 install recipe (deps + weights), code-pinned (the Orpheus precedent).

    Returns a :class:`~diana.tts.heavy_install.HeavyInstallSpec` the Settings install row
    consumes verbatim, so no repo IDs / pins are hardcoded in the page. ``packages`` is the
    exact 05-03-verified pin (``f5-tts==1.1.20``, which pulls torch/torchaudio/vocos/
    transformers) installed from PyPI; the venv is the SHARED ``torch`` venv (D-03), so F5
    installs torch there and Fish reuses it. ``prefetch_argv`` is the venv-python worker
    command that warms the F5TTS_v1_Base checkpoint into ``HF_HOME`` (Phase B).
    ``heavy_install`` is imported lazily so this module's cheap path never pulls the
    provisioner in.
    """
    from diana.tts.heavy_install import HeavyInstallSpec

    return HeavyInstallSpec(
        engine="f5",
        venv_name="torch",
        packages=["f5-tts==1.1.20"],
        extra_index=None,
        prefetch_argv=[str(paths.heavy_worker("f5_worker.py")), "--prefetch"],
        deps_bytes=int(3.0 * _GB),
        weights_bytes=int(1.4 * _GB),
    )


class F5Engine:
    name = "f5"

    # F5 has no baked-in voices (zero-shot clone). It surfaces the bundled license-clean
    # default (D-15); saved custom voices (D-14) are MERGED in by 05-06. tier "enhanced" so
    # the quality ordering ranks it with the best OS/neural voices.
    VOICES = [
        TTSVoice(_DEFAULT_VOICE_ID, "Default (F5)", "en-us", "neutral", "enhanced"),
    ]

    def initialize(self) -> None:
        """Cheap fail-fast: refuse (actionably) when F5 is not installed (D-16).

        Consults the filesystem install-state probe ONLY — NO ``f5_tts``/``torch`` import.
        ``install_state`` is imported lazily so even constructing/initializing the engine
        never pulls a heavy SDK onto the app interpreter (ENGINE-01).
        """
        from diana.tts import install_state

        if not install_state.heavy_engine_installed("f5"):
            raise FileNotFoundError(
                "F5-TTS not installed — open Settings ▸ Voices and click Install."
            )

    def _resolve_ref(self, voice: str) -> tuple[str, str]:
        """Map a voice id to its ``(ref_file, ref_text)`` clone reference (import-light).

        For the bundled default (``f5_default``) this returns the package-resource clip
        path + its shipped exact transcript (D-15). Custom-voice ids are added in 05-06.
        An unknown id raises ``ValueError`` so a stale selection fails legibly rather than
        synthesizing silence.
        """
        if voice == _DEFAULT_VOICE_ID:
            return str(_bundled_default_clip()), _bundled_default_transcript()
        raise ValueError(f"Unknown F5 voice: {voice!r}")

    async def synthesize(
        self, text: str, voice: str = _DEFAULT_VOICE_ID, speed: float = 1.0
    ) -> bytes:
        """Synthesize one chunk OUT OF PROCESS in the torch venv, return WAV bytes.

        Offloads the blocking subprocess to the default executor so the worker thread's
        asyncio loop is never blocked (the native_os/piper/Orpheus precedent).
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._subprocess_synth, text, voice, speed
        )

    def _subprocess_synth(self, text: str, voice: str, speed: float) -> bytes:
        """Shell ``[<torch-venv-python>, f5_worker.py]`` with the request as stdin JSON.

        T-05-CMD: list argv, ``shell=False``; the gen text, the reference clip path, and
        the reference transcript travel as stdin DATA (a JSON object), NEVER interpolated
        into the command. The venv python and worker paths come from ``paths`` (not PATH —
        T-05-EXE). ``HF_HOME`` points the worker at Diana's per-user cache so the weights
        resolve where the installer put them (Pitfall 8). The temp WAV is always unlinked.
        """
        vpy = paths.venvs_dir() / "torch" / (
            "Scripts/python.exe" if _is_win() else "bin/python"
        )
        worker = paths.heavy_worker("f5_worker.py")
        ref_file, ref_text = self._resolve_ref(voice)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            out = f.name
        try:
            req = json.dumps({
                "ref_file": ref_file,
                "ref_text": ref_text,
                "gen_text": text,
                "out": out,
                "speed": speed,
                "hf_cache": str(paths.hf_cache_dir()),
            })
            p = subprocess.run(
                [str(vpy), str(worker)],
                input=req,
                text=True,
                capture_output=True,
                timeout=600,
                env={**os.environ, "HF_HOME": str(paths.hf_cache_dir())},
            )
            if p.returncode != 0:
                raise RuntimeError(f"F5 synth failed: {(p.stderr or '').strip()}")
            return Path(out).read_bytes()
        finally:
            Path(out).unlink(missing_ok=True)

    def list_voices(self) -> list[TTSVoice]:
        return list(self.VOICES)

    def default_voice(self) -> str:
        return _DEFAULT_VOICE_ID

    def shutdown(self) -> None:
        return None
