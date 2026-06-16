"""Fish Audio S2 Pro heavy engine — GPU-gated zero-shot voice cloning (HEAVY-03, D-01/D-10/D-17).

The FINAL slice of the three-engine lineup (D-01). Fish, like F5, has NO baked-in voices:
it clones a voice from a reference clip + that clip's exact transcript (RESEARCH A6, treated
as zero-shot clone). This module surfaces the SAME bundled, license-clean default voice F5
ships (D-15) so "install -> synthesize" works out of the box, MERGED with the shared
engine-agnostic Custom Voices pool (D-11). Synthesis runs OUT OF PROCESS in the SHARED
``torch`` venv (D-03 / Q-B): F5 installs torch there, Fish reuses it. The app interpreter
NEVER imports torch / fish_speech.

The Fish DELTA over the F5 sibling is the GPU gate (D-09 corrected / D-10). The gate now
allows TWO capable tiers via ``gpu_probe.fish_capability()`` (torch-free): a capable NVIDIA
GPU (~12+ GB VRAM, tier "cuda", FULL support) AND capable Apple Silicon (>=16 GB unified,
tier "apple", EXPERIMENTAL via Metal/MPS — fish-speech has native MPS support, PR #461, so
the earlier "effectively unsupported on Apple Silicon" framing was false). ``initialize()``
gates on BOTH ``heavy_engine_installed("fish")`` AND ``fish_capability()`` resolving to a
capable tier ({"cuda","apple"}). On any other machine (tier "none") the engine refuses with
the honest reason (needs NVIDIA OR Apple Silicon), and the Settings row is SHOWN BUT DISABLED
with that same reason (D-10) — never silently hidden.

Three disciplines, mirrored verbatim from the F5 sibling (05-05/06):

  1. **No heavy import on the cheap path (ENGINE-01 / D-17).** This module's top imports are
     stdlib + ``TTSVoice`` ONLY — never ``torch`` / ``fish_speech``. Enumerating the bundled
     default + custom voices and rendering a badge/gate pulls in nothing heavy; the SDK lives
     ONLY in ``heavy_workers/fish_worker.py``, run by the torch venv's own python.
  2. **Out-of-process subprocess synth (T-05-CMD, the native_os/Orpheus/F5 precedent).**
     ``synthesize`` shells ``[<torch-venv-python>, fish_worker.py]`` and passes the reference
     clip path, the reference transcript, and the gen text as stdin JSON DATA — never
     interpolated into the argv / a shell string. The temp WAV is always unlinked.
     ``HF_HOME`` points the worker at Diana's per-user cache so weights resolve where the
     installer put them (Pitfall 8 / D-07).
  3. **Defence-in-depth GPU gate (T-05-GPU).** ``initialize()`` AND the Settings row BOTH
     gate on ``fish_capability()``; the engine-level gate means even a programmatic
     ``create_engine("fish")`` on an unsupported (tier "none") box refuses before any synth
     (D-10/D-16).

``initialize()`` is a cheap fail-fast (D-16): it consults the filesystem install-state probe
and the torch-free GPU gate ONLY — it never imports ``fish_speech``/``torch`` to find out.
The bundled default clip is a fixed PACKAGE resource resolved via ``importlib.resources``
(never user input — T-05-PATH); custom-clip path safety lives in ``custom_voices`` (05-06).
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

# The bundled default reference voice id. Fish REUSES F5's bundled license-clean default
# clip (D-15 / A6): both are zero-shot clones, so the same self-generated, license-clean
# reference works for either engine. Custom voices (D-11) merge in alongside it.
_DEFAULT_VOICE_ID = "f5_default"

# Conservative footprint estimates (GB) feeding the D-04 itemized confirm + the has_space
# pre-check. Fish reuses the shared torch deps (F5 installs torch; Fish only adds its own
# git+fish-speech package) plus the s2-pro checkpoint (weights); the Settings row reads the
# exact live sizes at download time — these only need to be in the right ballpark.
_GB = 1024 ** 3


def _is_win() -> bool:
    """True on Windows (the venv interpreter is ``Scripts/python.exe`` vs ``bin/python``)."""
    return sys.platform == "win32"


def _bundled_default_clip() -> Path:
    """Resolve the bundled default reference clip (a SHIPPED package resource — T-05-PATH).

    The clip is package-DATA under ``diana/data/voices/f5_default.wav`` (D-15), resolved
    from the installed package via ``importlib.resources`` — a fixed path, never user
    input. Fish reuses F5's bundled clip (both are zero-shot clones — A6); self-generated
    on-device (license-clean by construction).
    """
    return Path(str(resources.files("diana.data").joinpath("voices", "f5_default.wav")))


def _bundled_default_transcript() -> str:
    """The EXACT transcript of the bundled default clip (D-15), shipped beside the WAV.

    A zero-shot clone needs the reference clip's exact transcript (``ref_text``) — no STT
    (D-12). Read from the bundled ``diana/data/voices/f5_default.txt`` package resource.
    """
    return resources.files("diana.data").joinpath(
        "voices", "f5_default.txt"
    ).read_text(encoding="utf-8").strip()


def fish_install_spec():
    """The Fish install recipe (deps + weights), code-pinned (the F5/Orpheus precedent).

    Returns a :class:`~diana.tts.heavy_install.HeavyInstallSpec` the Settings install row
    consumes verbatim, so no repo IDs / pins are hardcoded in the page. ``packages`` is the
    exact 05-03-verified pin (``fish-speech @ git+https://github.com/fishaudio/fish-speech``
    at a pinned COMMIT SHA — T-05-SC, supply-chain hygiene) installed into the SHARED
    ``torch`` venv (D-03 / Q-B): F5 installs torch there and Fish reuses it, adding only its
    own git package + the s2-pro weights. ``prefetch_argv`` is the venv-python worker command
    that warms the ``fishaudio/s2-pro`` checkpoint into ``HF_HOME`` (Phase B). ``heavy_install``
    is imported lazily so this module's cheap path never pulls the provisioner in.

    Q-B fallback (verified only at real-install time on a CUDA machine — deferred): if
    installing fish-speech into the shared ``torch`` venv conflicts with F5's torch CUDA
    requirement, switch ``venv_name`` to a dedicated ``"fish"`` and update the
    ``install_state`` venv mapping. The default below is the shared ``torch`` venv (D-03).
    """
    from diana.tts.heavy_install import HeavyInstallSpec, _BUILTIN_SPECS

    # Reuse the single code-pinned spec from heavy_install (Task 1 / 05-03 verified): the
    # git+SHA fish-speech package, shared torch venv, and footprint estimates live there so
    # there is ONE source of truth for the pin (no repo ID / SHA duplicated in this module
    # or the Settings page). prefetch_argv is overridden to the bundled worker's --prefetch
    # (the heavy_install built-in uses a module entrypoint; the F5/Fish worker convention is
    # the package-data worker script run by path — paths.heavy_worker). A fresh spec object
    # is returned so mutating prefetch_argv never rewrites the shared module-level built-in.
    base = _BUILTIN_SPECS["fish"]
    return HeavyInstallSpec(
        engine=base.engine,
        venv_name=base.venv_name,
        packages=list(base.packages),
        extra_index=base.extra_index,
        prefetch_argv=[str(paths.heavy_worker("fish_worker.py")), "--prefetch"],
        deps_bytes=base.deps_bytes,
        weights_bytes=base.weights_bytes,
    )


class FishEngine:
    name = "fish"

    # Fish has no baked-in voices (zero-shot clone — A6). It surfaces the bundled
    # license-clean default (D-15, reusing F5's clip) MERGED with the shared engine-agnostic
    # Custom Voices pool (D-11). tier "enhanced" so the quality ordering ranks it with the
    # best OS/neural voices.
    VOICES = [
        TTSVoice(_DEFAULT_VOICE_ID, "Default (Fish)", "en-us", "neutral", "enhanced"),
    ]

    def initialize(self) -> None:
        """Cheap fail-fast: refuse unless installed AND a capable tier (cuda|apple) (D-10/D-16).

        Consults the filesystem install-state probe + the torch-free tri-state GPU gate
        ONLY — NO ``fish_speech``/``torch`` import. Both ``install_state`` and ``gpu_probe``
        are imported lazily so even constructing/initializing the engine never pulls a heavy
        SDK onto the app interpreter (ENGINE-01). Raises a ``FileNotFoundError`` pointing at
        Settings ▸ Voices when not installed (D-16). The hardware gate now allows BOTH a
        capable NVIDIA GPU (>=12 GB, tier "cuda", full support) AND capable Apple Silicon
        (>=16 GB unified, tier "apple", EXPERIMENTAL via MPS); only tier "none" raises a
        ``RuntimeError`` carrying the honest reason (needs NVIDIA OR Apple Silicon — the same
        reason the Settings row shows shown-but-disabled). This engine-level gate is
        defence-in-depth on top of the Settings shown-but-disabled row (T-05-GPU).
        """
        from diana.tts import gpu_probe, install_state

        if not install_state.heavy_engine_installed("fish"):
            raise FileNotFoundError(
                "Fish S2 Pro not installed — open Settings ▸ Voices and click Install."
            )
        tier, _label, reason = gpu_probe.fish_capability()
        if tier not in ("cuda", "apple"):
            raise RuntimeError(
                f"Fish S2 Pro {reason}." if reason else "Fish S2 Pro requires a capable GPU."
            )

    def _resolve_ref(self, voice: str) -> tuple[str, str]:
        """Map a voice id to its ``(ref_file, ref_text)`` clone reference (import-light).

        For the bundled default (``f5_default``) this returns the package-resource clip
        path + its shipped exact transcript (D-15). Any OTHER id is a saved custom voice
        (D-14): it is resolved through ``custom_voices.custom_voice_ref`` to that voice's
        ``custom_voices_dir()/<id>.wav`` clip + ``<id>.txt`` transcript — the one shared
        engine-agnostic pool (D-11). An id with no clip on disk raises ``ValueError`` so a
        stale selection fails legibly rather than synthesizing silence. ``custom_voices``
        is imported lazily so this stays import-light (NO torch — D-17).
        """
        if voice == _DEFAULT_VOICE_ID:
            return str(_bundled_default_clip()), _bundled_default_transcript()
        from diana.tts import custom_voices

        try:
            return custom_voices.custom_voice_ref(voice)
        except ValueError as e:
            raise ValueError(f"Unknown Fish voice: {voice!r}") from e

    async def synthesize(
        self, text: str, voice: str = _DEFAULT_VOICE_ID, speed: float = 1.0
    ) -> bytes:
        """Synthesize one chunk OUT OF PROCESS in the torch venv, return WAV bytes.

        Offloads the blocking subprocess to the default executor so the worker thread's
        asyncio loop is never blocked (the native_os/piper/Orpheus/F5 precedent).
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._subprocess_synth, text, voice, speed
        )

    def _subprocess_synth(self, text: str, voice: str, speed: float) -> bytes:
        """Shell ``[<torch-venv-python>, fish_worker.py]`` with the request as stdin JSON.

        T-05-CMD: list argv, ``shell=False``; the gen text, the reference clip path, and
        the reference transcript travel as stdin DATA (a JSON object), NEVER interpolated
        into the command. The venv python and worker paths come from ``paths`` (not PATH —
        T-05-EXE); Fish reuses the SHARED ``torch`` venv (D-03 / Q-B). ``HF_HOME`` points
        the worker at Diana's per-user cache so the weights resolve where the installer put
        them (Pitfall 8). The temp WAV is always unlinked.
        """
        vpy = paths.venvs_dir() / "torch" / (
            "Scripts/python.exe" if _is_win() else "bin/python"
        )
        worker = paths.heavy_worker("fish_worker.py")
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
                raise RuntimeError(f"Fish synth failed: {(p.stderr or '').strip()}")
            return Path(out).read_bytes()
        finally:
            Path(out).unlink(missing_ok=True)

    def list_voices(self) -> list[TTSVoice]:
        """The bundled default (D-15) MERGED with every saved custom voice (D-14).

        Fish has no baked-in voices: it surfaces the bundled license-clean default plus the
        shared engine-agnostic Custom Voices pool (D-11), deduped by id. ``custom_voices``
        is a cheap filesystem/``app_settings`` read imported lazily, so enumeration stays
        import-light (NO torch — D-17). A missing/empty pool just yields the default.
        """
        from diana.tts import custom_voices

        voices = list(self.VOICES)
        seen = {v.id for v in voices}
        for v in custom_voices.list_custom_voices():
            if v.id not in seen:
                seen.add(v.id)
                voices.append(v)
        return voices

    def default_voice(self) -> str:
        return _DEFAULT_VOICE_ID

    def shutdown(self) -> None:
        return None
