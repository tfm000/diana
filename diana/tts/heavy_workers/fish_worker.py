"""Out-of-process Fish Audio S2 Pro worker — run BY the shared torch venv's OWN python.

This is the ONE place the heavy SDK (``fish_speech`` -> ``torch`` / CUDA) is allowed to be
imported (RESEARCH Pattern 2 / D-17 / ENGINE-01). The app interpreter shells
``[<torch-venv-python>, fish_worker.py]`` and passes the synth request as stdin JSON DATA
(never a shell string — T-05-CMD); this script imports ``fish_speech`` freely because it
executes under the isolated SHARED ``torch`` venv created by the bundled-uv provisioner
(05-03, where F5 installs torch and Fish adds its own git package), NOT the frozen app
interpreter (which must stay torch-free — D-02/D-17).

Fish S2 Pro is zero-shot voice cloning (RESEARCH A6): it has no baked-in voices. Synthesis
is driven by a reference clip (``ref_file``) + that clip's exact transcript (``ref_text``)
plus the text to speak (``gen_text``) — all three travel as JSON DATA, never interpolated
into argv. Mirrors the F5 worker's clone shape exactly.

Two modes:

  * ``--prefetch`` (Phase B of install): load the ``fishaudio/s2-pro`` checkpoint once,
    which pulls the weights into ``HF_HOME`` (set by the installer), then exit 0. No stdin,
    no synthesis — just warm the cache so the first real synth is offline.
  * default (synthesis): read ``{"ref_file","ref_text","gen_text","out","speed","hf_cache"}``
    from stdin, run the fish-speech reference-clone inference (ref audio + ref text + gen
    text -> waveform), and write the samples to the ``out`` path as a WAV via soundfile.

⚠️ INFERENCE SIGNATURE — MEDIUM CONFIDENCE (RESEARCH Q-D / A6): fish-speech has NO PyPI
package and a fast-moving repo HEAD, so unlike F5 (whose ``F5TTS().infer(...)`` signature is
VERIFIED) the exact fish-speech inference call could NOT be pinned at plan time. The call
below follows fish-speech's documented ``load_model`` + ``TTSInferenceEngine`` /
``inference()`` shape (github.com/fishaudio/fish-speech ``tools/`` API) mirrored onto the F5
worker's clone contract. It MUST be confirmed against the pinned commit
``e5e292632cb11e7a27b2b7487f58f612bc101e13`` at REAL-INSTALL time on an NVIDIA ≥12 GB GPU
machine (deferred to 05-HUMAN-UAT.md — no CUDA box was available at execution). Adjust this
single function to the real fish-speech API if it differs; the engine/JSON contract is fixed.

There is deliberately NO ``diana/tts/heavy_workers/__init__.py``: the directory is
package-DATA invoked by path (``paths.heavy_worker``), never imported by the frozen app —
so its heavy imports can never reach the app interpreter (D-17).
"""

import json
import os
import sys


def _checkpoint_dir() -> str:
    """The s2-pro checkpoint dir inside HF_HOME (set by the installer — Pitfall 8 / D-07).

    fish-speech loads from a local checkpoint directory rather than a bare HF repo id; the
    installer prefetched ``fishaudio/s2-pro`` into ``HF_HOME``, so the snapshot lives under
    the HF cache. ``huggingface_hub.snapshot_download`` resolves (or, on prefetch, fetches)
    that snapshot path. Imported here (in the venv) so the app interpreter never sees it.
    """
    from huggingface_hub import snapshot_download

    return snapshot_download(
        repo_id="fishaudio/s2-pro",
        cache_dir=os.environ.get("HF_HOME"),
    )


def _prefetch() -> int:
    """Warm the HF cache by downloading the s2-pro checkpoint (Phase B of install)."""
    # snapshot_download fetches the full s2-pro snapshot into HF_HOME and returns its path;
    # constructing the inference engine below would also pull it, but the explicit download
    # keeps prefetch torch-free-fast (no model graph build) and is the documented warm step.
    _checkpoint_dir()
    return 0


def _synthesize() -> int:
    """Read a JSON synth request from stdin and write the cloned WAV to ``out``.

    ⚠️ MEDIUM-CONFIDENCE fish-speech call (see module docstring) — confirm at real install.
    """
    import soundfile as sf
    import torch
    from fish_speech.inference_engine import TTSInferenceEngine
    from fish_speech.models.text2semantic.inference import launch_thread_safe_queue
    from fish_speech.models.vqgan.inference import load_model as load_decoder_model
    from fish_speech.utils.schema import ServeReferenceAudio, ServeTTSRequest

    req = json.loads(sys.stdin.read())
    ckpt = _checkpoint_dir()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Build the two-stage fish-speech pipeline (text2semantic LLAMA queue + VQGAN decoder)
    # and wrap them in the inference engine. The decoder weights + config live in the
    # downloaded s2-pro snapshot; the precise filenames are confirmed at real-install time.
    llama_queue = launch_thread_safe_queue(
        checkpoint_path=ckpt, device=device, precision=torch.bfloat16, compile=False,
    )
    decoder_model = load_decoder_model(
        config_name="modded_dac_vq",
        checkpoint_path=os.path.join(ckpt, "codec.pth"),
        device=device,
    )
    engine = TTSInferenceEngine(
        llama_queue=llama_queue,
        decoder_model=decoder_model,
        precision=torch.bfloat16,
        compile=False,
    )

    # Zero-shot clone: the reference clip + its exact transcript condition the voice; gen
    # text is what gets spoken. Mirrors the F5 worker's (ref_file, ref_text, gen_text) shape.
    with open(req["ref_file"], "rb") as fh:
        ref_audio_bytes = fh.read()
    tts_request = ServeTTSRequest(
        text=req["gen_text"],
        references=[ServeReferenceAudio(audio=ref_audio_bytes, text=req["ref_text"])],
        format="wav",
    )

    # The engine yields streaming segments; the final segment carries the full waveform.
    sample_rate = decoder_model.sample_rate
    audio = None
    for result in engine.inference(tts_request):
        if getattr(result, "code", None) == "final" and result.audio is not None:
            sample_rate, audio = result.audio
    if audio is None:
        raise RuntimeError("fish-speech produced no audio")
    sf.write(req["out"], audio, sample_rate, format="WAV")
    return 0


def main() -> int:
    if "--prefetch" in sys.argv[1:]:
        return _prefetch()
    return _synthesize()


if __name__ == "__main__":
    sys.exit(main())
