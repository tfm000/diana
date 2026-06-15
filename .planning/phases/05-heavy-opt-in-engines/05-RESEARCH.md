# Phase 5: Heavy Opt-In Engines - Research

**Researched:** 2026-06-15
**Domain:** On-demand local neural TTS (Orpheus / F5-TTS / Fish S2 Pro), isolated-venv Python-dependency provisioning from inside an eventually-frozen desktop app, GPU/license gating, reference-audio voice cloning
**Confidence:** MEDIUM-HIGH (architecture HIGH; model IDs / wheel availability / inference signatures MEDIUM — fast-moving, verification steps provided)

## Summary

This phase layers three heavy neural TTS engines onto the proven Phase-4 download/cache/install/badge/uninstall substrate. The single load-bearing technical question — "how does a no-terminal, eventually-PyInstaller-frozen app provision an isolated venv and pip-install torch / llama-cpp-python with zero terminal use?" — has a clean, verified answer: **bundle the `uv` standalone binary and drive it via `subprocess`**. `uv` is a single self-contained executable that needs no system Python, downloads its own standalone CPython (python-build-standalone), creates venvs, and pip-installs — identically on Windows and macOS. A PyInstaller-frozen app **cannot** bootstrap pip/venv from `sys.executable` (it points at the bootloader, not a real Python), so a bundled provisioner like `uv` is mandatory, not optional.

The second architectural keystone is **running each heavy engine out-of-process**. The heavy venv's Python (pinned to 3.11/3.12 where prebuilt wheels exist) will differ in ABI from the frozen app's interpreter, and the isolation decision (D-05) forbids polluting the core runtime. So the heavy `TTSEngine` classes never import torch/llama-cpp in-process — they shell out to a tiny worker script run by the venv's own Python and read back WAV bytes. This is exactly Diana's existing `native_os` (`say`) and `piper` binary pattern, makes ENGINE-01/D-17 lazy-import compliance trivial (the heavy SDK is *never* in the app interpreter), and sidesteps every PyInstaller-frozen-import hazard.

Engine specifics verified: **Orpheus** runs torch-free via `orpheus-cpp` (onnxruntime SNAC decoder) + `llama-cpp-python` (prebuilt CPU/Metal wheels), with 8 named voices — genuinely CPU-viable. **F5-TTS** (`pip install f5-tts`) needs torch + a CC-BY-NC weights checkpoint and clones from a reference clip + user transcript. **Fish S2 Pro** (`fishaudio/s2-pro`) is non-commercial, NVIDIA-CUDA-focused (~12-24 GB VRAM), and effectively unsupported on Apple Silicon — so the GPU gate is "NVIDIA ≥12 GB VRAM," detected torch-free via `nvidia-smi`.

**Primary recommendation:** Build a shared heavy-engine install scaffold — (1) a bundled `uv` binary + an `install_manager` that runs `uv venv` / `uv pip install` on a UI background thread with two-phase progress, (2) per-engine isolated venvs under `paths`, (3) out-of-process subprocess `synthesize`, (4) accept-once license gate + torch-free `nvidia-smi` GPU gate, (5) a reusable Custom Voices section — then land one vertical slice per engine (Orpheus first: torch-free, lowest risk, proves the scaffold end-to-end).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Provision isolated venv + pip install | UI background thread (off worker) | bundled `uv` subprocess | ENGINE-04/D-07: installs are UI-triggered, never in the JobWorker; `uv` does the actual work |
| Heavy model weight download | UI background thread | `huggingface_hub` in venv subprocess (or `download_file`) | D-07/ENGINE-04; weights land in the per-user HF cache with disk pre-check |
| Heavy synthesis (torch/llama-cpp inference) | venv subprocess (out-of-process) | Diana `TTSEngine` class builds cmd + reads WAV | ABI isolation + D-05 (no core-runtime pollution) + D-17 (no heavy import in app interpreter) |
| Install-state / footprint badge | App interpreter (cheap filesystem probe) | — | ENGINE-01/D-17: filesystem-only, no torch/llama-cpp import |
| GPU capability gate (Fish) | App interpreter (`nvidia-smi` subprocess) | torch.cuda inside venv at synth time | ENGINE-01: must detect VRAM **without** importing torch on the badge path |
| License accept-once gate | App interpreter (`app_settings` read) | — | D-08: persisted flag, blocking before first download |
| Custom-voice capture/validation | App interpreter (Streamlit + pure validators) | `paths.custom_voices_dir()` + `app_settings` | D-11/D-13/D-14: clip upload/record + transcript, validated, saved & named |
| Engine/voice selection + fail-fast | App interpreter (`registry` + `resolve_default_voice`) | cheap install-state probe | D-16: refuse uninstalled heavy engine with an actionable prompt, never mid-job |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Scope & build order**
- **D-01:** All three engines (Orpheus, F5-TTS, Fish S2 Pro) ship as in-app installs this phase — all must-have, no fallback slip. No mandated "first" engine; recommended **shared heavy-engine install scaffold first, then one vertical slice per engine** (MVP mode = vertical slices: install → select → synthesize end-to-end per engine).
- **D-02:** The lightweight default install is untouched. Heavy engines + their Python deps + weights are fetched only on opt-in; nothing heavy is added to the base bundle (consistent with PKG-02 "torch excluded from base").

**Heavy-engine install UX (HEAVY-01/02/03, ENGINE-02/03/04)**
- **D-03:** One-action install per engine. A single "Install" button handles BOTH the Python runtime deps (torch ~2-3 GB for F5/Fish; a llama-cpp-python wheel for Orpheus) AND the model weights, with combined status — no terminal. Shared-torch optimization: once F5 installs torch, Fish only needs its own model.
- **D-04:** Itemized footprint confirm + disk pre-check before any bytes. The confirm breaks out deps vs model (e.g. "torch 2.4 GB + model 1.1 GB"), plus a free-vs-needed disk check (reuse `diana/downloads/downloader.py::has_space`), extending Phase-4 D-04's >200 MB confirm. Refuse to start if space is insufficient (Phase-4 D-05).
- **D-05:** Heavy Python deps install into an isolated venv — never the global/system environment. *(RESEARCH FLAG — resolved below: bundled `uv` + per-engine venvs; out-of-process execution. Intersects Phase 6 / PKG-02.)*
- **D-06:** No-terminal is non-negotiable. The in-app installer must do everything (deps + weights) with zero terminal use. No documented-command fallback.
- **D-07:** Reuse the Phase-4 download substrate for weights (download_file / `.part` / md5 / atomic os.replace; byte progress via `dl_state` + `@st.fragment`; UI-triggered-only, off the worker — ENGINE-04; per-user cache via `paths.py`), and extend it for Python-package installation (the genuinely new capability vs Phase 4).

**License + GPU gates (HEAVY-02/03)**
- **D-08:** Accept-once-per-engine NC-license gate (blocking). First install of F5 / Fish shows the non-commercial license and requires explicit "I accept" before any download; acceptance persisted in `app_settings`. Disclosure names "non-commercial / personal use only" and links the actual license text.
- **D-09:** Fish "capable GPU" definition is deferred to research. *(RESEARCH FLAG — resolved below: NVIDIA CUDA, effectively not Apple-MPS; ~12 GB VRAM floor.)*
- **D-10:** Fish is SHOWN BUT DISABLED with a reason when no capable GPU is detected (e.g. "requires a capable GPU (~12+ GB VRAM)") — NOT hidden. ⚠️ **This REFINES HEAVY-03 + ROADMAP SC#3 ("hidden" → "shown-but-disabled-with-reason"). ACTION: reconcile `REQUIREMENTS.md` HEAVY-03 and `ROADMAP.md` SC#3 wording** so the verifier checks the intended behavior. (See Open Questions Q-A.)

**F5 voice cloning + reusable "Custom Voices" section (HEAVY-02)**
- **D-11:** A reusable, engine-agnostic "Custom Voices" section in Settings ▸ Voices — built for F5 cloning now and reusable by future cloning-capable models. Two input methods: **Upload** (audio mp3 + text file transcript); **In-app capture** (record via microphone — likely `st.audio_input` — + a text box transcript).
- **D-12:** The transcript is always user-provided (file or typed) — no auto-transcribe, no extra speech-to-text dependency.
- **D-13:** Clip validation: validate audio format + length and require a non-empty transcript; reject bad input with a clear message (reuse the Phase-4 import-rejection pattern — never crash). Exact bounds = Claude's discretion, research-informed.
- **D-14:** Custom voices are saved & named — appear in the per-job voice picker and the cross-engine browser, reusable across jobs, removable like any other voice (reuse Phase-4 uninstall + `voice_labels`). A real, persistent library.
- **D-15:** F5 ships one bundled, license-clean default voice so the engine works out of the box ("install → synthesize" satisfied); uploading/recording a custom voice enhances it.

**Fail-fast & engine plumbing (success criterion #4, ENGINE-01)**
- **D-16:** Fail-fast when a heavy engine's deps/model are not installed. Selectable only when installed; choosing an uninstalled engine surfaces an actionable prompt ("Install it in Settings ▸ Voices") and refuses to start — never errors mid-job. Builds on ENGINE-03 badges + Phase-3 `resolve_default_voice` backstop.
- **D-17:** Each heavy engine implements the existing `TTSEngine` Protocol (`name` / `initialize` / `async synthesize` / `list_voices` / `default_voice` / `shutdown`) with lazy SDK imports — no torch/llama-cpp on the cheap enumeration/badge path (ENGINE-01) — and registers in `diana/tts/registry.py` (`_ENGINE_CLASSES`, `create_engine`, `get_engine_voices`, `all_engine_voices`, `_ASCII_ONLY_ENGINES`). They surface in the cross-engine browser like Kokoro/Piper.

### Claude's Discretion
- **Orpheus voice model shape:** mirror the Kokoro single-model precedent (engine-level model install with named voices baked in — Phase-4 D-19); pick a sensible default GGUF quantization (footprint confirm via D-04 if large); exposing a quantization choice is optional.
- **Fish voice model** (preset voices vs cloning) — resolve during research alongside the GPU gate.
- Exact venv mechanism, model repo IDs/revisions, inference signatures, wheel sources/index URLs — all research/plan.
- Custom-voice metadata storage shape (candidate: `app_settings` + a per-user `custom_voices` dir under `voices_dir()`) and where the bundled F5 default reference voice + sample clip live (package data).
- Concurrent-install policy (serialize vs parallel) for the big downloads; how a heavy install reports progress for the pip/venv phase vs the weight-download phase.

### Deferred Ideas (OUT OF SCOPE)
- Heavy-engine packaging/freezing, ffmpeg bundling, Windows CI → **Phase 6** (but the venv-in-frozen-app feasibility is researched here because it gates heavy installs).
- Production hardening (worker lifetime, SQLite retry, XSS/traversal, offline smoke test) → **Phase 7**.
- Auto-transcription of reference clips (local STT) — explicitly rejected this phase (D-12).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **HEAVY-01** | Orpheus engine available (llama-cpp-python + GGUF, CPU-viable) with named voices | `orpheus-cpp` (torch-free, onnxruntime SNAC) + `llama-cpp-python` prebuilt CPU/Metal wheels; default GGUF `isaiahbjork/orpheus-3b-0.1-ft-Q4_K_M-GGUF`; 8 named voices (tara…zoe); API `OrpheusCpp().tts(text, options={"voice_id": ...})` → `(24000, int16[])`. See Standard Stack + Code Examples. |
| **HEAVY-02** | F5-TTS engine (on-demand torch) with reference-audio voice cloning + clip validation, behind an in-app non-commercial license disclosure before download | `f5-tts` 1.1.20 (torch ≥2.0); weights `SWivid/F5-TTS` `F5TTS_v1_Base` are **CC-BY-NC** (code MIT) → D-08 disclosure accurate; API `F5TTS().infer(ref_file, ref_text, gen_text, …)`; reference clip ≤~12 s + user transcript → D-13 bounds. Custom Voices section (D-11) + bundled default (D-15). |
| **HEAVY-03** | Fish Audio S2 Pro engine, GPU-gated, opt-in, with non-commercial license disclosure | `fishaudio/s2-pro` weights under **Fish Audio Research License / CC-BY-NC-SA-4.0** (non-commercial) → D-08 accurate; NVIDIA-CUDA, ~12-24 GB VRAM; effectively not Apple-MPS. Torch-free `nvidia-smi` gate (D-09/D-10). ⚠️ wording reconciliation pending (Q-A). |
</phase_requirements>

## Standard Stack

> Versions verified via `pip index versions` (network) on 2026-06-15. Model IDs / wheel availability are MEDIUM confidence and MUST be re-verified at plan/install time (see verification step + Open Questions).

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **uv** (binary) | latest (Astral) | The bundled provisioner: create isolated venvs, download standalone CPython, pip-install heavy deps — no system Python | Single self-contained binary, no Python dependency; identical on Win/macOS; uses python-build-standalone. The only mechanism that satisfies D-05/D-06 from a frozen app. [VERIFIED: docs.astral.sh] |
| **orpheus-cpp** | 0.0.3 | Orpheus engine: llama-cpp + onnxruntime SNAC decode, torch-free | Only maintained pip path that runs Orpheus CPU-viable **without torch** (deps: huggingface-hub, onnxruntime, transformers, numpy≥2). [VERIFIED: github.com/freddyaboulton/orpheus-cpp] |
| **llama-cpp-python** | 0.3.29 | GGUF LLM inference for Orpheus | Prebuilt CPU/Metal wheels avoid source compilation (CPU-viable hard req). [VERIFIED: github.com/abetlen/llama-cpp-python] |
| **f5-tts** | 1.1.20 | F5-TTS engine: zero-shot reference-audio voice cloning | Official package (`SWivid/F5-TTS`); pulls torch/torchaudio/vocos/transformers; `F5TTS` API. [VERIFIED: pypi.org/project/f5-tts] |
| **fish-speech** (`fishaudio/s2-pro`) | repo HEAD (no PyPI package) | Fish S2 Pro engine (GPU-gated) | Open-weights, self-host via `git clone` + `pip install -e` or HTTP-API server; weights via `hf download fishaudio/s2-pro`. [CITED: github.com/fishaudio/fish-speech] |
| **torch / torchaudio** | ≥2.0 (platform wheel) | Neural inference backend for F5 + Fish | Installed **inside the heavy venv only** (D-02/D-05); macOS = CPU/MPS wheel (~250 MB), Windows = CUDA wheel (~2.5 GB) for Fish. [VERIFIED: pytorch.org] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **onnxruntime** | latest | SNAC 24 kHz decoder for Orpheus (torch-free audio reconstruction) | Pulled transitively by `orpheus-cpp`; in the Orpheus venv |
| **snac** | 1.2.1 | (Reference) SNAC neural codec — *only if not using orpheus-cpp's onnx path* | Avoid: prefer orpheus-cpp's onnx decoder so the Orpheus venv stays torch-free |
| **vocos** | 0.1.0 | Vocoder used by F5-TTS | Pulled transitively by `f5-tts`; in the torch venv |
| **huggingface-hub** | latest | Resumable, hash-verified weight downloads into the per-user HF cache | In each venv; `snapshot_download` / `hf_hub_download` with `HF_HOME` pointed at Diana's cache (D-07/ENGINE-04) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Bundled `uv` provisioner | Bundle a python-build-standalone interpreter + stdlib `venv` + `python -m pip` | Works, but reimplements what `uv` does in one binary; slower, more moving parts. **Use as fallback only** if `uv` proves problematic. |
| Bundled `uv` | Point pip at the user's system Python | ❌ Violates "no Python install for end users" (PROJECT.md). Rejected. |
| Out-of-process subprocess engines | In-process `sys.path` injection of the venv's site-packages | ❌ C-extension ABI must match the frozen app's exact CPython; numpy≥2 collides with base deps; PyInstaller frozen-import hazards. Rejected for heavy engines. |
| `orpheus-cpp` (torch-free) | `orpheus-speech` (canopyai, vLLM/torch) | vLLM/torch is GPU-oriented and heavy — defeats Orpheus's "CPU-viable, lightest" role. |
| `download_file` for weights | `huggingface_hub` download inside venv | HF libraries auto-fetch their exact file set/revision and are themselves resumable + hash-verified; `download_file` is better for single known-URL+md5 assets. Use HF download for the multi-file model repos; keep `has_space` pre-check (D-04/D-05). |

**Installation (what the in-app installer runs, per engine — no terminal; via `subprocess` → bundled `uv`):**
```bash
# Shared scaffold: one venv per engine family under paths.venvs_dir()
# --- Orpheus venv (torch-FREE, CPU-viable) ---
uv venv --python 3.12  <data>/venvs/orpheus
uv pip install --python <data>/venvs/orpheus/bin/python  orpheus-cpp
uv pip install --python <data>/venvs/orpheus/bin/python  \
    llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
#   macOS GPU: swap the index for .../whl/metal

# --- Torch venv (shared by F5 now, Fish later — D-03 shared-torch) ---
uv venv --python 3.12  <data>/venvs/torch
uv pip install --python <data>/venvs/torch/bin/python  f5-tts      # pulls torch+torchaudio+vocos+transformers
#   Fish later: git+install fishaudio/fish-speech into the SAME venv (reuses torch)

# Weights (in the venv subprocess, HF_HOME=<data>/hf-cache) — disk pre-check first via has_space():
#   Orpheus: hf_hub_download("isaiahbjork/orpheus-3b-0.1-ft-Q4_K_M-GGUF", "...q4_k_m.gguf")
#            hf_hub_download("onnx-community/snac_24khz-ONNX", "onnx/decoder_model.onnx")  (orpheus-cpp does this automatically)
#   F5:      F5TTS(model="F5TTS_v1_Base", hf_cache_dir=<data>/hf-cache)  (downloads on first construct)
#   Fish:    hf download fishaudio/s2-pro
```

**Version verification (run before writing plan tasks — versions/model IDs are fast-moving):**
```bash
pip index versions orpheus-cpp llama-cpp-python f5-tts          # confirm latest + existence
# Confirm prebuilt-wheel availability for the PINNED venv Python (3.11/3.12) on BOTH macOS-arm64 + Windows:
#   open https://abetlen.github.io/llama-cpp-python/whl/cpu  and  .../whl/metal  → check cp311/cp312 wheels
# Confirm model repos still resolve:
#   isaiahbjork/orpheus-3b-0.1-ft-Q4_K_M-GGUF · onnx-community/snac_24khz-ONNX · SWivid/F5-TTS · fishaudio/s2-pro
```

## Package Legitimacy Audit

> `slopcheck` 0.6.1 is installed, but its `install` subcommand couples the check with an actual install (which would pull multi-GB torch/llama wheels into this researcher's env). Legitimacy was instead established by (1) `pip index versions` confirming each package exists with a multi-release history, and (2) discovering every package from its **official GitHub repository** (not a bare WebSearch hit). All entries below are `[CITED]` from authoritative sources + registry-verified.

| Package | Registry | Age / History | Source Repo | Verdict | Disposition |
|---------|----------|---------------|-------------|---------|-------------|
| llama-cpp-python | PyPI | 0.3.29, 100+ releases since 2023 | github.com/abetlen/llama-cpp-python | established, high-trust | Approved |
| f5-tts | PyPI | 1.1.20, 17 releases since 2024-10 | github.com/SWivid/F5-TTS | established | Approved |
| orpheus-cpp | PyPI | 0.0.3, 4 releases (young) | github.com/freddyaboulton/orpheus-cpp (MIT; HF/Gradio-team author) | young but legitimate source | Approved — verify source repo at plan time |
| snac | PyPI | 1.2.1, 5 releases | github.com/hubertsiuzdak/snac (official SNAC) | established | Approved (likely unused — onnx path preferred) |
| vocos | PyPI | 0.1.0, 5 releases | github.com/gemelo-ai/vocos (official Vocos) | established | Approved (transitive via f5-tts) |
| uv | standalone binary | Astral, widely adopted | github.com/astral-sh/uv | high-trust | Approved (bundle the signed release binary) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none — but `orpheus-cpp` is young (0.0.x); the planner should pin the exact version and keep the existing **D-04 footprint confirm + D-08 license accept** as the human gates before any heavy install (these already function as `checkpoint:human-verify` equivalents). Pin every package to an exact version in the install commands (supply-chain hygiene; see Security Domain).

## Architecture Patterns

### System Architecture Diagram

```text
                         ┌───────────────────────── Diana (frozen app interpreter) ─────────────────────────┐
                         │                                                                                   │
  User ── Settings ▸ ───►│  Voices tab: heavy-engine install rows + Custom Voices section                    │
  Voices / Upload        │      │                          │                         │                       │
                         │      │ (cheap, no heavy import)  │                         │                       │
                         │      ▼                           ▼                         ▼                       │
                         │  install_state probe        license gate              GPU gate                     │
                         │  (filesystem: venv python?  (app_settings              (subprocess nvidia-smi,     │
                         │   weight file? .marker?)     accepted flag, D-08)       torch-FREE, D-09/D-10)      │
                         │      │                                                                             │
                         │      │ click "Install"  ──► spawn UI BACKGROUND THREAD (off JobWorker, ENGINE-04)  │
                         │      ▼                                                                             │
                         │   has_space() disk pre-check (D-04/D-05) ──► dl_state dict ◄── @st.fragment poller │
                         │      │                                                                             │
                         └──────┼─────────────────────────────────────────────────────────────────────────┘
                                │  subprocess
                ┌───────────────┼────────────────────────────────────────────────────┐
                │   PHASE A: provision (bundled `uv`)        PHASE B: weights          │
                │   uv venv --python 3.12 <venv>             huggingface_hub in venv,  │
                │   uv pip install <pkgs> [--extra-index]    HF_HOME=<data>/hf-cache   │
                │   (progress: parse uv stdout lines)        (progress: HF tqdm)       │
                └───────────────┬────────────────────────────────────────────────────┘
                                ▼
                   <data>/venvs/{orpheus,torch}/  +  <data>/hf-cache/  +  .installed marker

  ── Synthesis (JobWorker → pipeline → synthesize_chunk → engine.synthesize) ──
                         ┌───────────── HeavyEngine (in app interpreter) ─────────────┐
   chunk text ─────────►│  async synthesize(text, voice, speed):                      │
                         │     build cmd = [<venv>/bin/python, worker.py, --json …]   │  NO torch/llama
                         │     run in executor ──► subprocess ───────────────────┐    │  import here (D-17)
                         └───────────────────────────────────────────────────────┼────┘
                                                                                  ▼
                            <venv>/bin/python  worker.py  (orpheus_cpp / f5_tts / fish)
                            reads JSON request (text, voice/ref_file/ref_text) ─► writes WAV ─► path
                                                                                  │
                            HeavyEngine reads WAV bytes ◄─────────────────────────┘ ──► pipeline merges
```

### Recommended Project Structure
```text
diana/
├── tts/
│   ├── registry.py                 # + orpheus/f5/fish branches (lazy, no heavy import)
│   ├── install_state.py            # + heavy_engine_installed(), heavy_footprint_bytes() (filesystem only)
│   ├── gpu_probe.py                # NEW: torch-free nvidia-smi VRAM detection (D-09/D-10)
│   ├── heavy_install.py            # NEW: uv-driven venv provisioner (Phase A) + weight download (Phase B)
│   ├── orpheus_engine.py           # NEW: TTSEngine, subprocess → orpheus venv (static named VOICES)
│   ├── f5_engine.py                # NEW: TTSEngine, subprocess → torch venv (bundled default + custom voices)
│   ├── fish_engine.py              # NEW: TTSEngine, subprocess → torch venv (GPU-gated)
│   ├── custom_voices.py            # NEW: capture/validate/save/name reference voices (D-11..D-15)
│   └── heavy_workers/              # NEW: plain .py run BY the venv python (package-data, NOT frozen-imported)
│       ├── orpheus_worker.py       #   import orpheus_cpp; stdin JSON → WAV file
│       ├── f5_worker.py            #   import f5_tts; ref_file+ref_text+gen_text → WAV file
│       └── fish_worker.py          #   import fish_speech; ref/gen → WAV file
├── paths.py                        # + venvs_dir(), custom_voices_dir(), hf_cache_dir(), uv_binary()
├── data/
│   ├── bin/uv-{macos,windows}      # bundled uv binary (Phase 6 packages the right one)
│   └── voices/f5_default.{wav,txt} # bundled license-clean F5 default voice + transcript (D-15)
└── dashboard/pages/5_Settings.py   # + heavy install rows + Custom Voices section (Voices tab)
```

### Pattern 1: Bundled `uv` provisioner (Phase A — the load-bearing mechanism)
**What:** Drive a bundled `uv` binary by `subprocess` to create an isolated venv with a pinned standalone Python and pip-install heavy deps. No system Python, no terminal.
**When to use:** Every heavy-engine install. This is the answer to the D-05/D-06 RESEARCH FLAG.
**Example:**
```python
# Source: docs.astral.sh/uv/concepts/python-versions + pip-interface (VERIFIED 2026-06-15)
import subprocess
from diana import paths

def provision_venv(venv_path, packages, extra_index=None, py="3.12", on_line=None):
    uv = str(paths.uv_binary())               # bundled binary; NOT pip/uv from PATH
    # 1) create venv with a managed standalone CPython (uv downloads it if absent)
    _run([uv, "venv", "--python", py, str(venv_path)], on_line)
    vpy = venv_path / ("Scripts/python.exe" if _is_win() else "bin/python")
    # 2) install into THAT venv (ABI pinned to the venv's python, not the frozen app)
    cmd = [uv, "pip", "install", "--python", str(vpy), *packages]
    if extra_index:
        cmd += ["--extra-index-url", extra_index]
    _run(cmd, on_line)
    return vpy

def _run(cmd, on_line):
    # Stream stdout so the UI thread can show the current step/package (Phase-A progress).
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        if on_line: on_line(line.rstrip())    # writes into dl_state; @st.fragment renders it
    if proc.wait() != 0:
        raise RuntimeError("install step failed (see log)")
```

### Pattern 2: Out-of-process heavy synthesis (mirrors `piper`/`native_os` subprocess engines)
**What:** The heavy `TTSEngine.synthesize` shells out to the venv's own Python running a tiny worker; reads back WAV bytes. The heavy SDK is never imported in the app interpreter.
**When to use:** All three heavy engines. Makes ENGINE-01/D-17 trivially true.
**Example:**
```python
# Pattern mirrors diana/tts/piper_engine.py::_synthesize_binary + native_os_engine._say_synth
import asyncio, json, subprocess, tempfile
from pathlib import Path
from diana import paths

class OrpheusEngine:
    name = "orpheus"
    VOICES = [TTSVoice("tara","Tara (Female)","en-us","female","enhanced"), ...]  # 8 named (Kokoro-style, D-19)

    def initialize(self):  # cheap: just verify the venv+model exist (NO orpheus_cpp import here)
        if not install_state.heavy_engine_installed("orpheus"):
            raise FileNotFoundError("Orpheus not installed — open Settings ▸ Voices and click Install.")

    async def synthesize(self, text, voice="tara", speed=1.0) -> bytes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._subprocess_synth, text, voice, speed)

    def _subprocess_synth(self, text, voice, speed):
        vpy = paths.venvs_dir() / "orpheus" / ("Scripts/python.exe" if _is_win() else "bin/python")
        worker = paths.heavy_worker("orpheus_worker.py")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f: out = f.name
        try:
            req = json.dumps({"text": text, "voice_id": voice, "out": out})   # text is DATA (stdin), never shell
            p = subprocess.run([str(vpy), str(worker)], input=req, text=True,
                               capture_output=True, timeout=600,
                               env={**os.environ, "HF_HOME": str(paths.hf_cache_dir())})
            if p.returncode != 0: raise RuntimeError(f"Orpheus synth failed: {p.stderr.strip()}")
            return Path(out).read_bytes()
        finally:
            Path(out).unlink(missing_ok=True)
```

### Pattern 3: Two-phase install progress (cross-cutting Q5)
**What:** Phase A (venv + pip) has no clean byte totals → stream `uv` stdout lines as step labels into `dl_state`; Phase B (weights) has clean byte counts → reuse the Phase-4 `download_file` + `dl_state` byte progress OR `huggingface_hub`'s tqdm. Both write to the shared `dl_state` dict polled by `@st.fragment` (the exact Phase-4 thread→fragment pattern; worker thread never calls `st.*` — T-04-SRC).
**When to use:** The shared install scaffold. Reuse `_new_dl_state`, `_render_download_progress`, `_can_spawn_download` from `5_Settings.py`, extended with a `phase`/`step` field.

### Pattern 4: Torch-free GPU gate (Fish, D-09/D-10)
**What:** Detect a capable NVIDIA GPU on the cheap badge path **without importing torch** by probing `nvidia-smi`.
**Example:**
```python
# diana/tts/gpu_probe.py — cheap, ENGINE-01-safe (no torch on the badge path)
import shutil, subprocess

FISH_MIN_VRAM_GB = 12   # floor from fish-speech 1.5/S2 docs (12 GB min, 24 GB recommended)

def capable_nvidia_gpu():
    """Return (ok, vram_gb, reason) using nvidia-smi only (no torch import)."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return False, 0, "requires an NVIDIA GPU with ~12+ GB VRAM (none detected)"
    try:
        out = subprocess.run([smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10)
        vram_gb = max(int(x) for x in out.stdout.split()) / 1024
    except Exception:
        return False, 0, "could not query GPU memory"
    ok = vram_gb >= FISH_MIN_VRAM_GB
    return ok, vram_gb, ("" if ok else f"requires ~{FISH_MIN_VRAM_GB}+ GB VRAM (found ~{vram_gb:.0f} GB)")
```
Apple Silicon has no `nvidia-smi` → Fish is **shown-but-disabled** with the reason string (D-10). MPS is technically detectable but fish-speech is effectively unsupported on macOS and the VRAM floor exceeds typical Mac unified-memory budgets — so the gate intentionally requires CUDA.

### Anti-Patterns to Avoid
- **Bootstrapping pip/venv from `sys.executable` in the frozen app.** It points at the PyInstaller bootloader, not a Python — `python -m venv` / `ensurepip` will not work. Always go through the bundled `uv` (or bundled standalone Python).
- **Importing torch / llama-cpp / orpheus_cpp / f5_tts anywhere in the app interpreter.** Breaks D-02/D-05 isolation and ENGINE-01/D-17. They live only in the venv, reached by subprocess.
- **`sys.path`-injecting the venv's site-packages into the frozen interpreter.** ABI/numpy/import-hook hazards. Use subprocess.
- **Calling `torch.cuda.is_available()` on the badge/enumeration path.** Requires torch (not in base) and is slow. Use the `nvidia-smi` probe.
- **Running installs inside the JobWorker.** ENGINE-04/D-07 — installs are UI-triggered, on a background thread, off the worker.
- **Interpolating chunk/transcript text into a shell string.** Pass as stdin/argv data (T-03-06 precedent in `native_os_engine`).
- **Bundling the model weights in the installer.** Out of scope (PROJECT.md) and they're NC-licensed — download on demand only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Provision a Python runtime + venv with no system Python | A custom downloader for CPython + manual venv layout | **bundled `uv`** (`uv venv --python`, `uv pip install --python`) | uv ships python-build-standalone, handles platform/arch, resumable, one binary |
| Resumable, hash-verified weight download | Reimplement HF blob/cache layout over `download_file` | `huggingface_hub.snapshot_download` / `hf_hub_download` (in venv) | Knows the exact file set/revision; resumable + integrity built in; just set `HF_HOME` + run `has_space` first |
| SNAC audio-code → waveform decode (Orpheus) | A hand-written SNAC decoder | `orpheus-cpp` (onnxruntime SNAC) | Torch-free, maintained, CPU-viable |
| Zero-shot voice cloning inference | Anything custom | `f5-tts` `F5TTS().infer(...)` | The model + vocoder pipeline is non-trivial |
| GPU VRAM detection without torch | Parsing `/proc`, WMI, registry | `nvidia-smi --query-gpu=memory.total` | One cross-platform command, no heavy dep |
| Microphone capture in-app | A custom JS recorder component | `st.audio_input` (Streamlit ≥1.40) | First-party widget; returns an uploaded WAV (D-11) |
| Reference-clip duration/format read | Manual WAV header parsing | `soundfile.info()` (already a dep) | `soundfile` is installed; gives frames/samplerate cheaply for D-13 |

**Key insight:** The genuinely new capability vs Phase 4 is **provisioning a Python environment**, not downloading files — and that problem is fully solved by `uv`. Everything else (download substrate, badges, uninstall, dl_state/fragment progress, license/footprint confirms) already exists in Phase 4 and should be reused, not rebuilt.

## Common Pitfalls

### Pitfall 1: Frozen app cannot create a venv from itself
**What goes wrong:** `subprocess.run([sys.executable, "-m", "venv", ...])` or `[sys.executable, "-m", "pip", ...]` fails or runs the Streamlit app again, because in a PyInstaller bundle `sys.executable` is the bootloader, not Python.
**Why it happens:** PyInstaller freezes the interpreter; there is no standalone `python` to invoke.
**How to avoid:** Provision through the **bundled `uv` binary** (or a bundled standalone Python). Never assume a Python on PATH.
**Warning signs:** Install "works in dev" (real venv Python present) but fails in the packaged app — catch this in Phase 6, but design for it now.

### Pitfall 2: llama-cpp-python / torch have no prebuilt wheel for the venv's Python version
**What goes wrong:** `pip install llama-cpp-python` with no wheel triggers a from-source build (needs a C/C++ toolchain) → fails on a clean user machine. Prebuilt Metal wheels are documented for **Python 3.10-3.12**, not 3.13.
**Why it happens:** Wheel coverage lags new CPython releases; Diana's dev env is 3.13.
**How to avoid:** Pin the **venv** Python to a version with confirmed wheels (3.11 or 3.12) via `uv venv --python 3.12` — independent of the app's frozen Python. Always pass `--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/{cpu,metal}`. Verify cp311/cp312 wheels exist for macOS-arm64 AND Windows at plan time.
**Warning signs:** install log shows "Building wheel for llama-cpp-python" or "Metal" / "cmake" — that means no wheel matched.

### Pitfall 3: Orpheus accidentally pulls torch
**What goes wrong:** Using `orpheus-speech`/`snac` (torch) instead of `orpheus-cpp` (onnx) bloats the "CPU-viable, lightest" engine to a multi-GB torch install.
**Why it happens:** Most Orpheus tutorials assume vLLM/torch.
**How to avoid:** Use **`orpheus-cpp`** (deps: huggingface-hub, onnxruntime, transformers, numpy — no torch) + `llama-cpp-python`. Keep the Orpheus venv separate from the torch venv. Verify at plan time that `orpheus-cpp` still imports/runs without torch (transformers is used for tokenization only).
**Warning signs:** `pip install` log lists `torch` in the Orpheus venv.

### Pitfall 4: Fish treated as Apple-Silicon-capable
**What goes wrong:** Gating on `torch.backends.mps.is_available()` would "enable" Fish on Macs where it doesn't realistically run (no native macOS support; 12-24 GB VRAM floor; CUDA/SGLang-oriented).
**Why it happens:** torch reports MPS available on any Apple Silicon Mac.
**How to avoid:** Gate on **NVIDIA + ≥12 GB VRAM via `nvidia-smi`** (Pattern 4). On macOS → shown-but-disabled with the reason (D-10).
**Warning signs:** Fish enabled on a MacBook; install attempted then fails deep in inference.

### Pitfall 5: `st.audio_input` not available
**What goes wrong:** D-11 in-app microphone capture uses `st.audio_input`, added in **Streamlit 1.40.0** (Nov 2024). `requirements.txt`/`pyproject.toml` pin `streamlit>=1.30.0`.
**How to avoid:** Bump the floor to `streamlit>=1.40.0`. The captured clip defaults to 16 kHz mono WAV — fine for F5 (resamples to 24 kHz internally), but factor 16 kHz into D-13 validation (don't reject sub-24 kHz).
**Warning signs:** `AttributeError: module 'streamlit' has no attribute 'audio_input'`.

### Pitfall 6: Worker thread touches `st.*` (Streamlit ScriptRunContext leak)
**What goes wrong:** The install/synthesis background thread calling `st.*` crashes/НЕcorrupts the app (the exact T-04-SRC pitfall handled in Phase-4 `_download_piper_voice`).
**How to avoid:** Background thread writes only to the shared `dl_state` dict; all `st.*` runs in the `@st.fragment` poller on the script thread. Reuse the proven Phase-4 machinery verbatim.

### Pitfall 7: Reference clip too long / silent-tail truncation (F5)
**What goes wrong:** F5 clips reference audio to ~12 s; a long clip is cut mid-word, degrading the clone; a clip with no trailing silence can truncate.
**How to avoid:** D-13 validation: accept ~2-12 s clips (warn/auto-trim >12 s), require a non-empty transcript, recommend ~1 s trailing silence. Reject <~1 s or empty-transcript with a clear message (never crash — Phase-4 import-rejection pattern).
**Warning signs:** garbled or cut-off cloned speech.

### Pitfall 8: Weights not landing in the per-user cache
**What goes wrong:** HF libraries default to `~/.cache/huggingface`, not Diana's per-user dir → ENGINE-04/D-08 violated, uninstall can't find them.
**How to avoid:** Set `HF_HOME=<data>/hf-cache` in the subprocess env for both install and synth; F5 also accepts `hf_cache_dir=`. Run `has_space()` before download (D-04/D-05).

## Code Examples

### Orpheus worker (runs in the orpheus venv — torch-free)
```python
# diana/tts/heavy_workers/orpheus_worker.py — executed by <venv>/bin/python, NOT the frozen app
# Source: github.com/freddyaboulton/orpheus-cpp README (VERIFIED 2026-06-15)
import json, sys, numpy as np, soundfile as sf
from orpheus_cpp import OrpheusCpp

req = json.loads(sys.stdin.read())
orpheus = OrpheusCpp()                                  # auto-downloads GGUF + SNAC onnx to HF_HOME
sr, audio = orpheus.tts(req["text"], options={"voice_id": req["voice_id"]})  # -> (24000, int16[])
sf.write(req["out"], audio, sr, format="WAV")
```

### F5 worker (runs in the torch venv)
```python
# diana/tts/heavy_workers/f5_worker.py
# Source: github.com/SWivid/F5-TTS src/f5_tts/api.py (VERIFIED 2026-06-15)
import json, sys, soundfile as sf
from f5_tts.api import F5TTS

req = json.loads(sys.stdin.read())   # {ref_file, ref_text, gen_text, out, device}
f5 = F5TTS(model="F5TTS_v1_Base", device=req.get("device"), hf_cache_dir=req["hf_cache"])
wav, sr, _ = f5.infer(ref_file=req["ref_file"], ref_text=req["ref_text"],
                      gen_text=req["gen_text"], speed=req.get("speed", 1.0), remove_silence=True)
sf.write(req["out"], wav, sr, format="WAV")
```

### Cheap install-state probe (ENGINE-01 — no heavy import)
```python
# diana/tts/install_state.py (additions)
from diana import paths

def heavy_engine_installed(engine: str) -> bool:
    """venv python + .installed marker exist — pure filesystem, NO torch/llama import."""
    venv = paths.venvs_dir() / ("orpheus" if engine == "orpheus" else "torch")
    py = venv / ("Scripts/python.exe" if _is_win() else "bin/python")
    marker = paths.venvs_dir() / f".{engine}.installed"     # written at end of a successful install
    return py.exists() and marker.exists()
```

### Registry wiring (D-17)
```python
# diana/tts/registry.py (additions, all lazy — no heavy import at module top)
_ASCII_ONLY_ENGINES = {"kokoro": True, "piper": False, "native_os": False,
                       "orpheus": False, "f5": False, "fish": False}   # neural → UTF-8 capable

def list_engines() -> list[str]:
    return ["native_os", "kokoro", "piper", "orpheus", "f5", "fish"]   # heavy ones badge/gate cheaply

def _get_engine_class(engine_name):
    if engine_name == "orpheus":
        from diana.tts.orpheus_engine import OrpheusEngine; return OrpheusEngine
    if engine_name == "f5":
        from diana.tts.f5_engine import F5Engine; return F5Engine
    if engine_name == "fish":
        from diana.tts.fish_engine import FishEngine; return FishEngine
    ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pyenv`+`virtualenv`+`pip`+`pipx` for env bootstrap | **`uv`** single binary, no system Python | 2024-2025 | Makes no-terminal venv provisioning in a frozen app feasible |
| Orpheus via vLLM/torch (GPU) | `orpheus-cpp` (llama.cpp + onnx SNAC), torch-free CPU | 2025 | Orpheus genuinely CPU-viable, lightest of the three |
| F5-TTS auto-transcribe ref via Whisper | Explicit `ref_text` (no STT) | always supported | Aligns with D-12 (no extra STT dependency) |
| Fish-speech CC-BY-NC-SA "research" models | OpenAudio S1/S2 (`fishaudio/s2-pro`) still non-commercial (Fish Audio Research License / CC-BY-NC-SA-4.0) | 2025-2026 | D-08 NC disclosure remains correct (a stray SEO claim of "MIT" was wrong) |
| llama-cpp-python from source | Prebuilt CPU/Metal wheels via abetlen index | ongoing | Avoids a C toolchain on user machines (CPU-viable hard req) |

**Deprecated/outdated:**
- Relying on a system Python for end-user installs — incompatible with Diana's no-Python-install constraint.
- `edge-tts`/cloud paths — already excluded (TTS local-only).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `orpheus-cpp` runs fully torch-free at runtime (transformers used only for tokenization) | Standard Stack / Pitfall 3 | If transformers lazily needs a torch backend, the "lightest, CPU-only" Orpheus story breaks → larger footprint; verify by installing into a torch-free venv and synthesizing |
| A2 | Prebuilt llama-cpp-python wheels exist for cp311/cp312 on macOS-arm64 AND Windows | Pitfall 2 | If absent, install needs a compiler → violates no-terminal; verify the abetlen index at plan time, else pin a version/Python that has wheels |
| A3 | Default Orpheus GGUF `isaiahbjork/orpheus-3b-0.1-ft-Q4_K_M-GGUF` (~2.3 GB) + SNAC `onnx-community/snac_24khz-ONNX` still resolve | Standard Stack | Repo could move/gate → install fails; verify repo IDs + that the GGUF is ungated (no HF token) |
| A4 | F5 reference-clip bounds (≤~12 s, ~1 s trailing silence) and 16 kHz capture acceptable | Pitfall 7 / Validation | Wrong bounds → poor clones or false rejections; bounds are research-informed, confirm against F5 docs at plan time |
| A5 | `fishaudio/s2-pro` is non-commercial AND requires NVIDIA ≥12 GB VRAM (not Apple-MPS-viable) | HEAVY-03 / Pitfall 4 | If S2 Pro shifted to a permissive license or gained real MPS support, D-08/D-10 wording changes; verify the s2-pro model-card license string + install docs at plan time |
| A6 | Fish S2 Pro voice shape is zero-shot reference cloning (no Orpheus-style named voices) → reuses Custom Voices + a bundled default | Architecture / D-15 | If Fish ships preset named voices, `get_engine_voices("fish")` becomes static instead of dynamic |
| A7 | torch footprints: macOS CPU/MPS ~250 MB installed; Windows CUDA ~2.5 GB; Fish s2-pro weights large (multi-GB) | Standard Stack / D-04 | Footprint-confirm numbers off → confirm exact wheel + HF repo sizes at install time (D-04 reads them live) |
| A8 | A bundled `uv` + runtime-downloaded standalone Python won't trigger extra Gatekeeper/SmartScreen prompts beyond Diana's documented unsigned bypass | Open Questions | If quarantine blocks runtime binaries, installs fail on first run → Phase-6 verification item; design the install to surface a clear error |

**If any A# proves false at plan time, treat it as a blocking input to the plan, not a silent assumption.**

## Open Questions

1. **Q-A [ACTION REQUIRED — D-10 reconciliation]: HEAVY-03 / ROADMAP SC#3 say "hidden unless a capable GPU is detected"; D-10 refines this to "shown-but-disabled-with-reason."**
   - What we know: the user deliberately chose shown-but-disabled (better discoverability, same protection).
   - What's unclear: which wording the phase verifier will check.
   - Recommendation: update `REQUIREMENTS.md` HEAVY-03 and `ROADMAP.md` Phase-5 SC#3 from "hidden" → "shown but disabled with a 'requires a capable GPU (~12+ GB VRAM)' reason" before verification. The planner/orchestrator should make this edit; the plan-checker should confirm it landed.

2. **Q-B: One shared torch venv (F5+Fish) vs. separate venvs?**
   - What we know: D-03 wants shared-torch ("F5 installs torch, Fish reuses"). Orpheus is torch-free → its own venv regardless.
   - What's unclear: whether F5 and Fish pin conflicting torch/transformers versions.
   - Recommendation: default to **2 venvs** (`orpheus` torch-free; `torch` shared by F5+Fish) to honor D-03; if a dependency conflict surfaces at install, fall back to **3 venvs** (per-engine). Decide at plan time after a trial `uv pip install f5-tts` then adding fish-speech to the same venv.

3. **Q-C: Weight download — `huggingface_hub` (in venv) vs. Diana's `download_file`?**
   - Recommendation: use `huggingface_hub` for the multi-file model repos (resumable + hash-verified + knows revisions), with `HF_HOME` set to the per-user cache and a `has_space()` pre-check first (satisfies D-04/D-05/ENGINE-04). Reserve `download_file` for any single known-URL+md5 asset. Document this as the D-07 interpretation ("weights land in the per-user cache, disk-checked, resumable" — provided by HF's own mechanism).

4. **Q-D: Fish install method (no PyPI package).**
   - What we know: fish-speech installs via `git clone` + `pip install -e .` or Docker; provides an HTTP-API server entrypoint and CLI.
   - What's unclear: cleanest no-terminal install into a uv venv (uv can `uv pip install git+https://github.com/fishaudio/fish-speech` at a pinned commit).
   - Recommendation: `uv pip install "fish-speech @ git+https://github.com/fishaudio/fish-speech@<pinned-sha>"` into the torch venv; verify it builds with wheels (no source-only C deps) at plan time. If it needs SGLang/flash-attn (CUDA-only build tools), gate Fish install behind the GPU check so it's only attempted on capable machines.

5. **Q-E: Bundled F5 default voice (D-15) provenance.**
   - Recommendation: ship a short (~6-10 s) **public-domain or self-recorded** clip + its exact transcript as package-data (`diana/data/voices/f5_default.wav` + `.txt`). Do NOT reuse an NC/unknown-licensed sample. The planner should source/record a clean clip; flag for human confirmation.

## Environment Availability

| Dependency | Required By | Available (researcher env) | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` binary | venv provisioning (Phase A) | ✗ (must be bundled) | latest | Bundle python-build-standalone + stdlib `venv`+`pip` |
| Python 3.12 (managed) | heavy venv Python (wheels) | via uv at runtime | 3.12.x | uv downloads it; no system Python needed |
| `nvidia-smi` | Fish GPU gate | ✗ on this macOS host (expected) | — | macOS → Fish shown-disabled (correct) |
| Network (PyPI/HF) | all heavy installs | ✓ (verified) | — | Installs require connectivity (acceptable; one-time opt-in) |
| `soundfile` | clip-duration read (D-13) | ✓ (already a dep) | ≥0.12 | `wave` stdlib for WAV-only |
| Streamlit ≥1.40 | `st.audio_input` (D-11) | ⚠️ floor is `>=1.30` | check installed | Bump floor to ≥1.40.0 |
| C/C++ toolchain | only if no prebuilt wheel | ✗ (and must NOT be required) | — | Pin venv Python to a version WITH wheels (Pitfall 2) |

**Missing dependencies with no fallback:** none that block — but the `uv` binary MUST be bundled (Phase 6) and the install requires network (one-time, opt-in).
**Missing dependencies with fallback:** `uv` → bundled standalone Python; Streamlit <1.40 → bump the floor.

## Validation Architecture

> `nyquist_validation` is enabled (config.json). Heavy engines cannot run torch/llama in CI, so tests **mock the subprocess/venv layer**; real synthesis is manual/integration UAT.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (`asyncio_mode = "auto"`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `-m 'not network'` default) |
| Quick run command | `/Users/tyler/Repos/diana/.venv/bin/python -m pytest tests/ -x -q` |
| Full suite command | `/Users/tyler/Repos/diana/.venv/bin/python -m pytest tests/ -q` (461 currently passing) |

### Phase Requirements → Test Map
| Req | Behavior | Test Type | Automated Command | File |
|-----|----------|-----------|-------------------|------|
| Scaffold | `provision_venv` builds correct `uv` argv per OS | unit (mock subprocess) | `pytest tests/test_heavy_install.py -x` | ❌ Wave 0 |
| Scaffold | two-phase progress: uv-line → dl_state; weight bytes → dl_state | unit | `pytest tests/test_heavy_install.py::test_progress -x` | ❌ Wave 0 |
| HEAVY-01 | Orpheus static named VOICES (8) enumerate with NO heavy import | unit | `pytest tests/test_orpheus_engine.py::test_voices_no_import -x` | ❌ Wave 0 |
| HEAVY-01 | `synthesize` builds correct subprocess cmd; parses WAV (mock) | unit | `pytest tests/test_orpheus_engine.py::test_subprocess_synth -x` | ❌ Wave 0 |
| HEAVY-02 | clip validation: format/duration/empty-transcript reject paths | unit (pure) | `pytest tests/test_custom_voices.py -x` | ❌ Wave 0 |
| HEAVY-02 | license accept-once gate persists in app_settings; re-install no re-prompt | unit | `pytest tests/test_license_gate.py -x` | ❌ Wave 0 |
| HEAVY-03 | `capable_nvidia_gpu` parses nvidia-smi; absent → disabled+reason | unit (mock) | `pytest tests/test_gpu_probe.py -x` | ❌ Wave 0 |
| SC#4 | uninstalled heavy engine → actionable refusal, never mid-job | unit | `pytest tests/test_heavy_failfast.py -x` | ❌ Wave 0 |
| D-17 | registry: list_engines/_ASCII_ONLY/get_engine_voices include heavy; no heavy import | unit | `pytest tests/test_registry_heavy.py -x` | ❌ Wave 0 |
| install-state | `heavy_engine_installed` is filesystem-only (no torch import) | unit | `pytest tests/test_install_state_heavy.py -x` | ❌ Wave 0 |
| HEAVY-01/02/03 | real install + synthesize end-to-end | manual UAT | (human, real machine) | n/a |

### Sampling Rate
- **Per task commit:** `pytest tests/test_<touched>.py -x -q`
- **Per wave merge:** full suite `pytest tests/ -q` (must stay green; currently 461 pass)
- **Phase gate:** full suite green + manual install/synthesis UAT per engine before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_heavy_install.py` — uv argv/order, two-phase progress (mock subprocess)
- [ ] `tests/test_gpu_probe.py` — nvidia-smi parse + absent path (mock)
- [ ] `tests/test_custom_voices.py` — clip validation bounds + transcript (pure)
- [ ] `tests/test_license_gate.py` — accept-once persistence
- [ ] `tests/test_orpheus_engine.py` / `test_f5_engine.py` / `test_fish_engine.py` — voices + subprocess cmd (mock)
- [ ] `tests/test_heavy_failfast.py` — fail-fast resolution
- [ ] `tests/test_registry_heavy.py` + `test_install_state_heavy.py` — registration + cheap probe (assert no torch import via `sys.modules`)
- [ ] `tests/conftest.py` — fixtures: fake venv dir, mock `subprocess.run`/`Popen`, fake nvidia-smi output, temp clip files
- Framework install: none (pytest+asyncio already present)

## Security Domain

> `security_enforcement` not explicitly disabled in config → treated as enabled.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Clip format/duration + transcript validation (D-13); reject, never crash. Voice IDs validated against the static VOICES set before reaching the subprocess. |
| V12 File & Resource | yes | Custom-voice + bundled-default file paths: reuse Phase-4 `catalog.safe_voice_dest` (basename + extension allow-list + resolved-prefix under the per-user dir). Temp WAVs always unlinked (`native_os` precedent). |
| V10 Malicious Code / Supply Chain | yes | Pin every package to an exact version; install only from PyPI + the abetlen wheel index + pinned HF repos / git SHAs. The legitimacy audit + D-04/D-08 confirms are the human gates. |
| V6 Cryptography | partial | Don't hand-roll integrity — rely on HF hash-verified downloads / `download_file` md5 where available. |
| V2/V3/V4 Auth/Session/Access | no | Local single-user desktop app; no auth layer. |

### Known Threat Patterns for {subprocess + on-demand pip + reference audio}
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Command injection via chunk/transcript/gen text | Tampering / Elevation | Pass text as **stdin/argv data**, never a shell string; `shell=False` (native_os T-03-06 precedent) |
| Path traversal via custom-voice filename | Tampering | `safe_voice_dest`-style basename + extension allow-list + containment under `custom_voices_dir()` |
| Supply-chain (typosquat / malicious wheel, incl. postinstall) | Tampering / Elevation | Exact-version pins; trusted indices only; legitimacy audit; `orpheus-cpp` (young) version-pinned + human-gated by D-04/D-08 |
| Untrusted GGUF/weights | Tampering | Pinned HF repo + revision; HF hash verification; ungated repos only (no token handling) |
| Resource exhaustion (multi-GB install fills disk) | DoS | `has_space()` pre-check before any byte (D-04/D-05); serialize installs |
| Worker-thread `st.*` ScriptRunContext leak | DoS (app crash) | Background thread writes only to `dl_state`; `@st.fragment` renders (Pitfall 6 / T-04-SRC) |

## Sources

### Primary (HIGH confidence)
- github.com/freddyaboulton/orpheus-cpp (README + pyproject.toml + src/orpheus_cpp/model.py) — torch-free deps, `OrpheusCpp.tts` API, default GGUF `isaiahbjork/orpheus-3b-0.1-ft-Q4_K_M-GGUF`, SNAC `onnx-community/snac_24khz-ONNX`, 8 named voices, 24 kHz
- github.com/SWivid/F5-TTS (README + src/f5_tts/api.py) — `F5TTS(model="F5TTS_v1_Base", device, hf_cache_dir)`, `infer(ref_file, ref_text, gen_text, …) -> (wav, sr, spec)`, weights CC-BY-NC / code MIT, ref clip ≤~12 s
- github.com/abetlen/llama-cpp-python — prebuilt wheel indices `…/whl/cpu` and `…/whl/metal`, macOS 11+, Python 3.10-3.12
- github.com/fishaudio/fish-speech + huggingface.co/fishaudio/openaudio-s1-mini — Fish Audio Research License / CC-BY-NC-SA-4.0 (non-commercial), NVIDIA/CUDA, `fishaudio/s2-pro`
- docs.astral.sh/uv/concepts/python-versions — `uv python install`, `uv venv --python`, `uv pip install --python`, managed standalone CPython, no system Python required
- docs.streamlit.io/develop/api-reference/widgets/st.audio_input — added 1.40.0, 16 kHz default
- pypi.org `pip index versions` (2026-06-15) — orpheus-cpp 0.0.3 · f5-tts 1.1.20 · llama-cpp-python 0.3.29 · snac 1.2.1 · vocos 0.1.0
- Diana codebase: `diana/downloads/downloader.py`, `diana/tts/{registry,base,install_state,kokoro_engine,piper_engine,native_os_engine,voice_labels}.py`, `diana/dashboard/pages/{1_Upload,5_Settings}.py`, `diana/paths.py`, `diana/database.py`, `diana/processing/synthesizer.py`, `.planning/codebase/ARCHITECTURE.md`

### Secondary (MEDIUM confidence)
- pyinstaller.org/en/stable/runtime-information.html — `sys.executable` is the bootloader in a frozen app (venv-bootstrap impossibility)
- fish.audio blog (S2 open-sourcing) + Spheron/aipedia TTS guides — VRAM 12 GB min / 24 GB recommended (cross-checked)
- F5-TTS SHARED.md / community guides — reference clip <12 s + ~1 s trailing silence guidance

### Tertiary (LOW confidence — flagged for plan-time verification)
- Approximate footprints (torch macOS ~250 MB, Windows CUDA ~2.5 GB, Orpheus GGUF ~2.3 GB, Fish weights multi-GB) — confirm exact at install time (D-04 reads live)
- Exact `fishaudio/s2-pro` install command line + whether it needs CUDA-only build deps (flash-attn/SGLang)

## Metadata

**Confidence breakdown:**
- venv/pip mechanism (uv + out-of-process): HIGH — verified across uv docs, PyInstaller docs, and Diana's existing subprocess-engine precedent
- Standard stack (package names + APIs): HIGH for existence/API shape (official repos + PyPI), MEDIUM for exact model IDs/revisions (fast-moving)
- Wheel availability for pinned Python: MEDIUM — abetlen index documents 3.10-3.12; confirm cp311/cp312 on both OSes at plan time
- Licenses (F5 CC-BY-NC, Fish non-commercial): HIGH — confirmed on official README/model cards (D-08 holds)
- Fish GPU/MPS reality + VRAM floor: MEDIUM-HIGH — multiple sources agree NVIDIA-CUDA, 12-24 GB, not Apple-viable
- Footprints: LOW-MEDIUM — ranges only; D-04 reads exact sizes live

**Research date:** 2026-06-15
**Valid until:** 2026-07-06 (7 days for the fast-moving model IDs / wheel availability; re-verify at plan time per the ROADMAP research note. Architecture findings stable ~30 days.)
