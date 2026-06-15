"""Out-of-process F5-TTS worker — run BY the shared torch venv's OWN python, never the app.

This is the ONE place the heavy SDK (``f5_tts`` -> ``torch`` / ``torchaudio`` / ``vocos``)
is allowed to be imported (RESEARCH Pattern 2 / D-17 / ENGINE-01). The app interpreter
shells ``[<torch-venv-python>, f5_worker.py]`` and passes the synth request as stdin JSON
DATA (never a shell string — T-05-CMD); this script imports ``f5_tts`` freely because it
executes under the isolated ``torch`` venv created by the bundled-uv provisioner (05-03),
NOT the frozen app interpreter (which must stay torch-free — D-02/D-17).

F5 is zero-shot voice cloning: it has no baked-in voices. Synthesis is driven by a
reference clip (``ref_file``) + that clip's exact transcript (``ref_text``) plus the text
to speak (``gen_text``) — all three travel as JSON DATA, never interpolated into argv.

Two modes:

  * ``--prefetch`` (Phase B of install): construct ``F5TTS(model="F5TTS_v1_Base", ...)``
    once, which pulls the ``SWivid/F5-TTS`` ``F5TTS_v1_Base`` checkpoint (CC-BY-NC) into
    ``HF_HOME`` (set by the installer), then exit 0. No stdin, no synthesis — just warm
    the cache so the first real synth is offline.
  * default (synthesis): read ``{"ref_file","ref_text","gen_text","out","speed","hf_cache",
    "device"?}`` from stdin, run ``F5TTS(...).infer(...)`` -> ``(wav, sr, spec)``, and write
    the samples to the ``out`` path as a WAV via soundfile.

There is deliberately NO ``diana/tts/heavy_workers/__init__.py``: the directory is
package-DATA invoked by path (``paths.heavy_worker``), never imported by the frozen
app — so its heavy imports can never reach the app interpreter (D-17).

Source: github.com/SWivid/F5-TTS src/f5_tts/api.py (VERIFIED 2026-06-15) —
``F5TTS(model="F5TTS_v1_Base", device, hf_cache_dir).infer(ref_file, ref_text, gen_text,
speed=1.0, remove_silence=True) -> (wav, sr, spec)``.
"""

import json
import os
import sys


def _prefetch() -> int:
    """Warm the HF cache by constructing F5TTS once (downloads the F5TTS_v1_Base checkpoint)."""
    from f5_tts.api import F5TTS

    # Constructing F5TTS resolves + downloads the F5TTS_v1_Base checkpoint into HF_HOME
    # (the installer sets HF_HOME -> Diana's per-user hf-cache, Pitfall 8 / D-07).
    F5TTS(model="F5TTS_v1_Base", hf_cache_dir=os.environ.get("HF_HOME"))
    return 0


def _synthesize() -> int:
    """Read a JSON synth request from stdin and write the cloned WAV to ``out``."""
    import soundfile as sf
    from f5_tts.api import F5TTS

    req = json.loads(sys.stdin.read())
    f5 = F5TTS(
        model="F5TTS_v1_Base",
        device=req.get("device"),
        hf_cache_dir=req.get("hf_cache") or os.environ.get("HF_HOME"),
    )
    wav, sr, _ = f5.infer(
        ref_file=req["ref_file"],
        ref_text=req["ref_text"],
        gen_text=req["gen_text"],
        speed=req.get("speed", 1.0),
        remove_silence=True,
    )
    sf.write(req["out"], wav, sr, format="WAV")
    return 0


def main() -> int:
    if "--prefetch" in sys.argv[1:]:
        return _prefetch()
    return _synthesize()


if __name__ == "__main__":
    sys.exit(main())
