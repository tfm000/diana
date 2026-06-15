---
phase: 05-heavy-opt-in-engines
reviewed: 2026-06-15T00:00:00Z
depth: deep
files_reviewed: 14
files_reviewed_list:
  - diana/tts/heavy_install.py
  - diana/tts/gpu_probe.py
  - diana/tts/orpheus_engine.py
  - diana/tts/f5_engine.py
  - diana/tts/fish_engine.py
  - diana/tts/heavy_workers/orpheus_worker.py
  - diana/tts/heavy_workers/f5_worker.py
  - diana/tts/heavy_workers/fish_worker.py
  - diana/tts/custom_voices.py
  - diana/tts/install_state.py
  - diana/tts/registry.py
  - diana/paths.py
  - diana/dashboard/pages/5_Settings.py
  - diana/dashboard/pages/1_Upload.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: fixed
fixed_at: 2026-06-15T00:00:00Z
fixes_applied:
  - CR-01: diana/tts/gpu_probe.py — check returncode before parsing
  - CR-02: diana/tts/custom_voices.py — preserve real audio extension on save
  - WR-01: diana/tts/heavy_install.py — cancel interrupts Phase-A subprocess
  - WR-02: diana/tts/heavy_install.py — timeout added to _run()
  - WR-03: diana/tts/heavy_install.py — uv error text captured in failure message
  - WR-04: diana/tts/heavy_install.py — fish prefetch_argv corrected to worker script form
fixes_skipped:
  - IN-01: asyncio.get_event_loop() — info-only, not in fix scope
  - IN-02: Popen context manager — info-only, not in fix scope
  - IN-03: fish_worker.py inference API — deferred to human UAT on CUDA machine
---

# Phase 05: Code Review Report

**Reviewed:** 2026-06-15
**Depth:** deep
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Phase 05 adds three opt-in heavy neural engines (Orpheus, F5, Fish) via a bundled-uv venv provisioner, plus engine-agnostic custom voice cloning. The architectural discipline is strong: D-17 (no torch/heavy import in the app interpreter) is rigorously upheld across all 14 files, T-05-CMD (list argv, shell=False) is correctly applied everywhere, and T-05-EXE (venv python from paths, not PATH) holds. The uninstall scoping and shared-venv logic are correct. Path traversal protection in `custom_voices.safe_custom_voice_dest` is sound.

Two blockers are present. First, the `gpu_probe.capable_nvidia_gpu()` function does not check `nvidia-smi`'s return code before parsing stdout — a degraded NVIDIA driver that exits non-zero but emits numeric-looking partial output could cause Fish to appear GPU-capable when it is not, letting a Fish synthesis job launch and fail mid-conversion. Second, `save_custom_voice` always saves the uploaded audio to a `.wav`-named file regardless of the input format; when the user uploads an MP3, raw MP3 bytes land in `<id>.wav`. `soundfile.info()` reads magic bytes and therefore validates the clip successfully, but `f5-tts` (and fish-speech) may use the file extension to choose their audio decoder and fail to open the reference clip, producing a cryptic synthesis error after the save appeared to succeed.

Four warnings cover a non-interruptible Phase-A cancel (the uv subprocess runs to completion even when the user clicks Cancel), a missing timeout on the `_run()` Popen wrapper (Phase-A uv commands can hang indefinitely), the uninformative error message from `_run()` on failure (uv's actual error text is streamed as step labels but lost by the time `state["error"]` is set), and a dead/incorrect `_BUILTIN_SPECS["fish"].prefetch_argv` entry that would silently misfire if `install_engine("fish")` is ever called with a string key instead of the spec object.

---

## Critical Issues

### CR-01: `gpu_probe.capable_nvidia_gpu()` ignores `nvidia-smi` exit code — GPU may be falsely reported capable

**File:** `diana/tts/gpu_probe.py:36-42`

**Issue:** `subprocess.run()` is called to query VRAM but `out.returncode` is never checked before parsing `out.stdout`. If `nvidia-smi` exits non-zero (driver fault, query timeout on a partially-initialised GPU) yet emits partial numeric output on stdout, `max(int(x) for x in out.stdout.split())` succeeds and the function returns `(True, vram_gb, "")` — telling both the Settings row and `FishEngine.initialize()` that a capable GPU is present. Fish synthesis then launches in the worker venv, encounters the real hardware error there, and the user gets an opaque "Fish synth failed" message deep in the pipeline rather than the actionable "requires ~12+ GB VRAM" gate at start.

```python
# Current (line 36–42):
out = subprocess.run(
    [smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
    capture_output=True, text=True, timeout=10,
)
vram_gb = max(int(x) for x in out.stdout.split()) / 1024

# Fix — check returncode BEFORE parsing:
out = subprocess.run(
    [smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
    capture_output=True, text=True, timeout=10,
)
if out.returncode != 0:
    return False, 0, "could not query GPU memory"
vram_gb = max(int(x) for x in out.stdout.split()) / 1024
```

---

### CR-02: MP3 uploads stored with `.wav` extension — reference clip silently broken for synthesis

**File:** `diana/tts/custom_voices.py:241,250,255`

**Issue:** `save_custom_voice` computes `wav_dest = safe_custom_voice_dest(f"{voice_id}.wav")` regardless of whether the uploaded audio is WAV or MP3, then writes the raw input bytes to that `.wav`-named path. `validate_clip` calls `soundfile.info()` which reads the file's magic bytes (not the extension) and correctly identifies MP3 content, so the save appears to succeed with a passing validation. When F5-TTS (or fish-speech) later opens the reference clip, the library selects its audio decoder from the `.wav` extension, finds MP3 frame headers where WAV RIFF chunks are expected, and fails — producing a synthesis error that gives no indication the root cause is the misnamed file.

The fix is to preserve the original extension when saving, or to transcode MP3 to WAV before writing. The simplest safe approach is to save under the original extension and update `custom_voice_ref` + the glob in `list_custom_voices` to handle both:

```python
# custom_voices.save_custom_voice — derive extension from the source, not always .wav:
import mimetypes

def _ext_for_src(audio_src) -> str:
    """Derive the audio extension from the source, defaulting to .wav."""
    name = getattr(audio_src, "name", None)
    if name:
        ext = Path(name).suffix.lower()
        if ext in (".mp3", ".wav"):
            return ext
    return ".wav"

# Then in save_custom_voice:
ext = _ext_for_src(audio_src)
wav_dest = safe_custom_voice_dest(f"{voice_id}{ext}")
```

And update `custom_voice_ref` to probe `<id>.wav` then `<id>.mp3`:
```python
def custom_voice_ref(voice_id: str, db_path=None) -> tuple[str, str]:
    cv_dir = paths.custom_voices_dir()
    for ext in (".wav", ".mp3"):
        wav = cv_dir / f"{voice_id}{ext}"
        if wav.exists():
            txt = cv_dir / f"{voice_id}.txt"
            ref_text = txt.read_text(encoding="utf-8").strip() if txt.exists() else ""
            return str(wav), ref_text
    raise ValueError(f"Unknown custom voice: {voice_id!r}")
```

Alternatively, the most conservative fix is to only accept `.wav` in the UI upload widget (changing `type=["wav", "mp3"]` to `type=["wav"]`) until transcoding is supported.

---

## Warnings

### WR-01: Cancel during Phase A (deps install) does not interrupt the running `uv` subprocess

**File:** `diana/tts/heavy_install.py:140-156, 240-248`

**Issue:** `_run()` drives the `uv venv` and `uv pip install` commands via `Popen` without accepting a cancel signal. The `_cancelled()` check in `install_engine` is evaluated only BETWEEN phases (before Phase A at line 240, after Phase A returns at line 251, after Phase B at line 270). If the user clicks Cancel while `uv pip install` is running for F5 (a ~3 GB download), the worker thread is uninterruptible until uv finishes: `state["cancel"]` is True, the UI correctly shows "Cancelling…" on the action button, but the download continues to completion before the thread acknowledges the cancel and sets `state["cancelled"]`. This can mean a multi-minute wait after clicking Cancel.

**Fix:** Pass a cancel callable into `_run()` and poll it between line reads; when set, terminate `proc` with `proc.terminate()` / `proc.kill()`:

```python
def _run(cmd: list[str], on_line=None, cancel=None) -> None:
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    if proc.stdout is not None:
        for line in proc.stdout:
            line = line.rstrip()
            if cancel and cancel():
                proc.terminate()
                proc.wait()
                raise RuntimeError("install cancelled by user")
            if on_line and line:
                on_line(line)
    if proc.wait() != 0:
        raise RuntimeError(f"install step failed: {' '.join(cmd[:2])} ... (see log)")
```

And thread the cancel callable through `provision_venv` → `_run`.

---

### WR-02: `_run()` has no timeout — a stalled `uv` command blocks the install thread indefinitely

**File:** `diana/tts/heavy_install.py:147-156`

**Issue:** `_run()` uses `subprocess.Popen` with no `timeout` argument and calls `proc.wait()` unconditionally. If `uv pip install` stalls (e.g., network hang during PyPI metadata fetch) or `uv venv` hangs on a managed CPython download, the install daemon thread blocks forever. The UI fragment keeps showing the last step label; there is no way for the user or the app to recover without a full restart. Phase B (`subprocess.run(... timeout=3600)`) is protected; Phase A is not.

**Fix:** Add a wall-clock timeout to `provision_venv`'s `_run` calls, consistent with Phase B's 3600s limit. One approach is to replace the bare `Popen` in `_run` with `subprocess.run(..., timeout=...)`, or add an explicit `threading.Timer` that calls `proc.terminate()` when the deadline is exceeded.

```python
def _run(cmd: list[str], on_line=None, timeout: int = 3600) -> None:
    """..."""
    import time
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    deadline = time.monotonic() + timeout
    if proc.stdout is not None:
        for line in proc.stdout:
            if time.monotonic() > deadline:
                proc.terminate()
                proc.wait()
                raise RuntimeError(f"install step timed out: {' '.join(cmd[:2])}")
            line = line.rstrip()
            if on_line and line:
                on_line(line)
    if proc.wait() != 0:
        raise RuntimeError(f"install step failed: {' '.join(cmd[:2])} ... (see log)")
```

---

### WR-03: `_run()` failure message is uninformative — the actual `uv` error is discarded

**File:** `diana/tts/heavy_install.py:155-156`

**Issue:** When `uv pip install` fails (e.g., a package pin no longer resolves, ABI mismatch, or a dependency conflict), `_run()` raises:
`RuntimeError("install step failed: <uv> pip ... (see log)")`
The actual error output from `uv` was streamed as `on_line` step labels (visible momentarily in `state["step"]`) but is not captured, so the final `state["error"]` shown to the user gives no actionable reason. A user who sees "install step failed: /path/to/uv pip … (see log)" has no idea what to fix.

**Fix:** Capture the last N lines of uv output and include them in the error:

```python
def _run(cmd: list[str], on_line=None) -> None:
    from collections import deque
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    tail = deque(maxlen=20)  # retain last 20 lines for the error message
    if proc.stdout is not None:
        for line in proc.stdout:
            line = line.rstrip()
            tail.append(line)
            if on_line and line:
                on_line(line)
    if proc.wait() != 0:
        detail = "\n".join(tail) or "(no output)"
        raise RuntimeError(
            f"install step failed: {' '.join(cmd[:2])} …\n{detail}"
        )
```

---

### WR-04: `_BUILTIN_SPECS["fish"].prefetch_argv` is incorrect and would fail if resolved by string key

**File:** `diana/tts/heavy_install.py:101`

**Issue:** `_BUILTIN_SPECS["fish"].prefetch_argv = ["-m", "fish_speech", "--prefetch"]`. This assumes fish-speech ships a `__main__` module that accepts `--prefetch`, which it does not. The correct prefetch command is the bundled `fish_worker.py --prefetch` (correctly set by `fish_install_spec()` via override). Settings always passes the spec object, not the string key, so this path is never executed today. However, the dead entry creates a trap: any future test or code path that calls `install_engine("fish")` (with a string, using the built-in spec resolution at line 188) would run the wrong prefetch command, silently download weights into the wrong location or fail with a cryptic `fish_speech` module-not-found error.

There is also a secondary inconsistency: `_BUILTIN_SPECS["orpheus"].prefetch_argv = ["-m", "orpheus_cpp", "--prefetch"]` and `orpheus_install_spec().prefetch_argv = [str(paths.heavy_worker("orpheus_worker.py")), "--prefetch"]` — two different but both potentially valid approaches (the module entrypoint form vs. the script form). For fish, there is only one valid form (the script), making the built-in wrong.

**Fix:** Update `_BUILTIN_SPECS["fish"]` to use the same worker-script pattern that the spec functions use, or remove `_BUILTIN_SPECS["f5"]` and `_BUILTIN_SPECS["fish"]` entirely since the authoritative specs live in the engine modules:

```python
# In _BUILTIN_SPECS["fish"]:
prefetch_argv=[str(paths.heavy_worker("fish_worker.py")), "--prefetch"],
```

Or add a note that `_BUILTIN_SPECS` is for testing/reference only and should not be called with engine-string resolution for fish.

---

## Info

### IN-01: `asyncio.get_event_loop()` should be replaced with `asyncio.get_running_loop()`

**File:** `diana/tts/orpheus_engine.py:119`, `diana/tts/f5_engine.py:156`, `diana/tts/fish_engine.py:193`

**Issue:** All three engine `synthesize()` methods call `asyncio.get_event_loop()` inside an `async def`, then call `loop.run_in_executor()`. In Python 3.10+ the idiomatic and explicit form is `asyncio.get_running_loop()`, which raises `RuntimeError` if there is no running loop (making the bug visible) rather than silently returning a different or newly-created loop. `get_event_loop()` in an async context works correctly today but is deprecated for this usage in the stdlib docs.

**Fix:**
```python
# Replace in all three synthesize() methods:
loop = asyncio.get_running_loop()
return await loop.run_in_executor(None, self._subprocess_synth, text, voice, speed)
```

---

### IN-02: `_run()` does not use `Popen` as a context manager — stdout pipe fd not explicitly closed on error paths

**File:** `diana/tts/heavy_install.py:147-156`

**Issue:** `subprocess.Popen` is constructed without the `with` statement. When `RuntimeError` is raised at line 156 (non-zero exit), `proc.stdout` is left open until garbage collection. In CPython this is handled by reference counting, but it is technically a resource leak that would surface under PyPy or in long-running processes. The pipe fd remains open until `proc` is collected.

**Fix:**
```python
with subprocess.Popen(
    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
) as proc:
    if proc.stdout is not None:
        for line in proc.stdout:
            line = line.rstrip()
            if on_line and line:
                on_line(line)
    if proc.wait() != 0:
        raise RuntimeError(f"install step failed: {' '.join(cmd[:2])} ... (see log)")
```

---

### IN-03: `fish_worker.py` inference API is marked medium-confidence and is unverified against the pinned commit

**File:** `diana/tts/heavy_workers/fish_worker.py:25-33,70-122`

**Issue:** The module docstring explicitly flags that the fish-speech inference call (`TTSInferenceEngine`, `launch_thread_safe_queue`, `load_model`, `ServeTTSRequest`, `ServeReferenceAudio`) is "MEDIUM CONFIDENCE" and "could NOT be pinned at plan time." The worker was written against a documented API description, not against the actual pinned commit `e5e292632cb11e7a27b2b7487f58f612bc101e13`. The imports (`fish_speech.inference_engine`, `fish_speech.models.text2semantic.inference`, `fish_speech.models.vqgan.inference`, `fish_speech.utils.schema`) and the `result.audio` tuple unpacking (`sample_rate, audio = result.audio`) may not match the real module structure in that commit.

This means the Fish engine will fail at first real installation on a CUDA machine, not due to a logic error in this codebase but because the worker's API calls need to be verified and potentially adjusted. This is documented as deferred to human UAT. No fix can be made without a CUDA machine, but the risk should be surfaced prominently for Phase 6.

**Recommended action:** Before shipping, run the worker under the pinned venv on a CUDA machine and adjust the import paths and inference call signature to match the actual module structure in commit `e5e292632cb11e7a27b2b7487f58f612bc101e13`.

---

_Reviewed: 2026-06-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
