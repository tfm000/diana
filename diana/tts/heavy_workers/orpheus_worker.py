"""Out-of-process Orpheus worker — run BY the orpheus venv's OWN python, never the app.

This is the ONE place the heavy SDK (``orpheus_cpp`` -> ``llama_cpp``) is allowed to
be imported (RESEARCH Pattern 2 / D-17 / ENGINE-01). The app interpreter shells
``[<venv-python>, orpheus_worker.py]`` and passes the chunk text as stdin JSON DATA
(never a shell string — T-05-CMD); this script imports ``orpheus_cpp`` freely because
it executes under the isolated venv created by the bundled-uv provisioner (05-03).

Two modes:

  * ``--prefetch`` (Phase B of install): construct ``OrpheusCpp()`` once, which pulls
    the GGUF + SNAC ONNX weights into ``HF_HOME`` (set by the installer), then exit 0.
    No stdin, no synthesis — just warm the cache so the first real synth is offline.
  * default (synthesis): read ``{"text","voice_id","out"}`` from stdin, run
    ``OrpheusCpp().tts(text, options={"voice_id": ...})`` -> ``(24000, int16[])``, and
    write the samples to the ``out`` path as a WAV via soundfile.

There is deliberately NO ``diana/tts/heavy_workers/__init__.py``: the directory is
package-DATA invoked by path (``paths.heavy_worker``), never imported by the frozen
app — so its heavy imports can never reach the app interpreter (D-17).

Source: github.com/freddyaboulton/orpheus-cpp README (VERIFIED 2026-06-15).
"""

import json
import sys


def _prefetch() -> int:
    """Warm the HF cache by constructing OrpheusCpp once (downloads GGUF + SNAC)."""
    from orpheus_cpp import OrpheusCpp

    OrpheusCpp()  # constructing triggers the GGUF + SNAC ONNX download into HF_HOME
    return 0


def _synthesize() -> int:
    """Read a JSON synth request from stdin and write the WAV to ``out``."""
    import soundfile as sf
    from orpheus_cpp import OrpheusCpp

    req = json.loads(sys.stdin.read())
    orpheus = OrpheusCpp()
    sr, audio = orpheus.tts(req["text"], options={"voice_id": req["voice_id"]})
    sf.write(req["out"], audio, sr, format="WAV")
    return 0


def main() -> int:
    if "--prefetch" in sys.argv[1:]:
        return _prefetch()
    return _synthesize()


if __name__ == "__main__":
    sys.exit(main())
