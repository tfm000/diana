---
phase: 05-heavy-opt-in-engines
plan: 03
subsystem: tts
tags: [uv, venv, subprocess, heavy-install, two-phase, has-space, license-gate, supply-chain, lazy-import, hf-cache]

# Dependency graph
requires:
  - phase: 04-engine-management-voice-catalog
    provides: downloader.has_space (ancestor-walk disk pre-check) + dl_state/@st.fragment download-thread discipline (_download_piper_voice writes only the shared state dict)
  - phase: 05-heavy-opt-in-engines (05-01)
    provides: Wave-0 conftest fixtures (tmp_data_paths, mock_uv, fake_venv) + RED/skip scaffolds (test_heavy_install, test_license_gate)
  - phase: 05-heavy-opt-in-engines (05-02)
    provides: paths.venvs_dir/hf_cache_dir/uv_binary resolvers + install_state.heavy_engine_installed marker probe + app_settings get_setting/set_setting
provides:
  - "diana/tts/heavy_install.py::provision_venv — bundled-uv driver: uv venv --python 3.12 then uv pip install --python <vpy> [--extra-index-url], streams uv stdout to on_line (Pattern 1)"
  - "diana/tts/heavy_install.py::install_engine — two-phase (deps->weights) thread target; has_space pre-check before any byte; HF_HOME-scoped prefetch; .{engine}.installed marker; cancel/cancelled contract; state-dict-only (no st.*)"
  - "diana/tts/heavy_install.py::HeavyInstallSpec + _BUILTIN_SPECS — Task-1-verified exact pins for orpheus/f5/fish the engine slices consume verbatim"
  - "diana/tts/heavy_install.py::license_accepted/accept_license — accept-once NC-license gate persisted in app_settings (D-08)"
  - "Confirmed plan-time supply-chain pins + wheel/repo/license re-verification (Task 1, A1-A8)"
affects: [05-orpheus-slice, 05-f5-slice, 05-fish-slice, 06-packaging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bundled-uv provisioner (RESEARCH Pattern 1): drive the standalone uv binary over subprocess to create an isolated venv + pip-install heavy deps with NO system Python (D-05/D-06); uv resolved from paths.uv_binary() with a dev-only PATH fallback (T-05-EXE)"
    - "Two-phase install progress (Pattern 3): Phase-A uv stdout lines stream as step labels into the shared state dict (no clean byte totals); Phase-B weight prefetch via the venv's own python with HF_HOME set (D-07/Pitfall 8) — worker thread NEVER calls st.* (T-05-SRC)"
    - "has_space disk pre-check before any byte (D-04/D-05), reusing downloader.has_space verbatim against a fresh venvs_dir()"
    - "List-argv subprocess, shell=False; package/version values code-pinned (Task 1), never user input (T-05-CMD); subprocess.Popen/run accessed via the module so the mock_uv monkeypatch is seen"
    - "install_engine accepts either a HeavyInstallSpec OR a built-in engine name (_resolve_spec) — satisfies both the spec-driven plan API and the engine-name test contract"

key-files:
  created:
    - diana/tts/heavy_install.py
    - .planning/phases/05-heavy-opt-in-engines/05-03-SUMMARY.md
  modified: []

key-decisions:
  - "install_engine's first positional arg accepts a string engine name (the test contract: install_engine('orpheus', state={})) as well as a HeavyInstallSpec (the plan API) via _resolve_spec + _BUILTIN_SPECS — reconciles the PLAN's install_engine(spec,...) wording with the authoritative Wave-0 scaffold signature without a test edit"
  - "abetlen wheels are py3-none-<platform> (ABI-agnostic across all CPython 3.x), NOT cp311/cp312 as research A2 assumed — so a single llama-cpp-python pin needs NO source build on macOS-arm64 OR win_amd64; Pitfall 2 cleared more strongly than expected, no blocker"
  - "Weight Phase-B uses a venv-python `-m <pkg> --prefetch` argv placeholder per engine (prefetch_argv); the exact prefetch entrypoint/worker is finalized in each engine slice — install_engine only orchestrates the subprocess + HF_HOME, mocked here"
  - "Footprint deps_bytes/weights_bytes are conservative code estimates feeding has_space + the D-04 itemized confirm; the Settings row reads exact live sizes at install time (D-04), so estimates need not be exact"
  - "has_space called via `from diana.downloads import downloader; downloader.has_space(...)` (module ref, lazy) so the test's monkeypatch on diana.downloads.downloader.has_space always gates BEFORE any uv subprocess (precheck test asserts mock_uv == [])"

patterns-established:
  - "Heavy-import-free + streamlit-free module-top contract for the provisioner, asserted by grep AND by sys.modules after import (no torch/llama_cpp/orpheus_cpp/f5_tts/streamlit leak)"
  - "Per-OS venv python path via _venv_python(): Scripts/python.exe (win) vs bin/python — matches install_state.heavy_engine_installed and the conftest fake_venv layout"

requirements-completed: [HEAVY-01, HEAVY-02, HEAVY-03]

# Metrics
duration: ~40min
completed: 2026-06-15
tasks: 2
files: 1
---

# Phase 5 Plan 03: Bundled-uv Heavy-Engine Provisioner Summary

The load-bearing D-05/D-06 mechanism landed as real, tested code: `diana/tts/heavy_install.py` drives a bundled `uv` standalone binary over `subprocess` to create an isolated per-engine venv with a pinned standalone CPython 3.12 and `uv pip install` the heavy deps (Phase A), then prefetches model weights via the venv's own Python with `HF_HOME` pointed at the per-user cache (Phase B) — gated by a `has_space` disk pre-check before any byte, streaming two-phase progress into the shared `dl_state` dict, importing no heavy SDK and never calling `st.*`. Plus accept-once NC-license helpers (D-08) and a full plan-time supply-chain re-verification of the fast-moving stack.

## What Was Built

**Task 1 — supply-chain re-verification (A1-A8, no source file).** Re-confirmed the MEDIUM-confidence research facts at plan time and recorded exact pins (see "Confirmed pins" below). The single biggest finding: the abetlen `llama-cpp-python` wheels are tagged `py3-none-<platform>` (ABI-agnostic across all CPython 3.x), so one pin works with NO source build on every supported OS — a stronger result than research A2's cp311/cp312 concern. No wheel-availability showstopper surfaced; no blocker.

**Task 2 — `diana/tts/heavy_install.py`.**
- `provision_venv(venv_path, packages, extra_index=None, py="3.12", on_line=None) -> vpy` — RESEARCH Pattern 1. Resolves `uv` via `paths.uv_binary()` (dev `shutil.which("uv")` fallback only when the bundled binary is absent), runs `uv venv --python 3.12 <venv>` then `uv pip install --python <vpy> *packages [--extra-index-url ...]`, streaming each `uv` stdout line to `on_line` via a `_run` Popen helper that raises on non-zero exit.
- `HeavyInstallSpec` dataclass + `_BUILTIN_SPECS` (orpheus / f5 / fish) carrying the Task-1 exact pins, `extra_index`, `prefetch_argv`, and `deps_bytes`/`weights_bytes` footprints.
- `install_engine(spec_or_engine, state=None, *, on_line=None, cancel=None)` — two-phase thread target: `has_space(venvs_dir(), deps+weights)` first (clear "need X / only Y free" on failure), Phase A `provision_venv`, Phase B `[vpy, *prefetch_argv]` with `HF_HOME=hf_cache_dir()`, then the `.{engine}.installed` marker + `state["done"]=True`. Honors `cancel()`/`state["cancel"]` between phases (sets terminal `state["cancelled"]`); any exception lands in `state["error"]` — never raises off the thread; writes ONLY the shared `state` dict.
- `license_accepted` / `accept_license` — accept-once gate over `app_settings` (`license.accepted.{engine}` == "1"), lazy DB import.

## Confirmed pins (Task 1 — copy verbatim into the engine slices 05-04/05/07)

> Re-verified 2026-06-15 against PyPI `pip index versions`, the abetlen wheel index, the HuggingFace model API, and the fish-speech GitHub API. Research baseline held on every version.

**Exact package pins**
- `orpheus-cpp==0.0.3` (latest; torch-free Orpheus) — Orpheus venv
- `llama-cpp-python==0.3.29` (latest) via `--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu` (macOS GPU: swap to `.../whl/metal`) — Orpheus venv
- `f5-tts==1.1.20` (latest; pulls torch/torchaudio/vocos/transformers) — shared `torch` venv
- `fish-speech @ git+https://github.com/fishaudio/fish-speech@e5e292632cb11e7a27b2b7487f58f612bc101e13` (pinned SHA, `main` HEAD 2026-06-09) — shared `torch` venv

**Wheel availability (A2 — the install-killer, CLEARED)**
- abetlen **cpu** index, `llama-cpp-python 0.3.29`: `llama_cpp_python-0.3.29-py3-none-macosx_11_0_arm64.whl` AND `...-py3-none-win_amd64.whl` both present.
- abetlen **metal** index: `...-py3-none-macosx_11_0_arm64.whl` present (Windows correctly absent — Metal is macOS-only).
- Wheels are `py3-none` (ABI-agnostic) → no cp311/cp312 dependence, **no source build** on any CPython 3.x. (Research A2 over-worried; reality is safer.)

**Model repos (all resolvable + ungated, no HF token)**
- `isaiahbjork/orpheus-3b-0.1-ft-Q4_K_M-GGUF` — gated=False, apache-2.0 (Orpheus GGUF)
- `onnx-community/snac_24khz-ONNX` — gated=False, mit (SNAC decoder)
- `SWivid/F5-TTS` — gated=False, **cc-by-nc-4.0** (weights non-commercial → D-08 disclosure accurate)
- `fishaudio/s2-pro` — gated=False, license="other" (Fish Audio Research License, non-commercial → D-08 accurate)

**torch index per OS (A7)**
- macOS: default PyPI (CPU/MPS wheel, ~250 MB) — `torch` latest line 2.6.0–2.12.0 available.
- Windows CUDA: `https://download.pytorch.org/whl/cu124` (reachable, HTTP 200; `cu121` also reachable as fallback).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `install_engine` signature reconciled to the test contract**
- **Found during:** Task 2 (reading `tests/test_heavy_install.py` `_call_install`).
- **Issue:** The PLAN specifies `install_engine(spec, state, cancel=None)` (a `HeavyInstallSpec` first), but the authoritative Wave-0 scaffold calls `install_engine("orpheus", state={})` — passing the engine NAME (a string) first. Following the plan signature verbatim would leave the scaffold red.
- **Fix:** `install_engine(spec_or_engine, state=None, *, on_line=None, cancel=None)` accepts EITHER a `HeavyInstallSpec` or a built-in engine name, resolved via `_resolve_spec` + `_BUILTIN_SPECS`. This satisfies both the plan's spec-driven API (engine slices can pass a custom spec) and the test contract (engine-name string) with no test edit.
- **Files modified:** diana/tts/heavy_install.py
- **Commit:** 733a5ee

**2. [Rule 2 - Critical correctness] `has_space` referenced via the module, not a top-level binding**
- **Found during:** Task 2 (the precheck test asserts `mock_uv == []`).
- **Issue:** The precheck test patches `diana.downloads.downloader.has_space`. A top-level `from ...downloader import has_space` would still be patched (the test also patches `heavy_install.has_space` if present), but to make the BEFORE-any-byte gate unambiguous, `install_engine` imports `downloader` lazily and calls `downloader.has_space(...)` so the monkeypatch is always seen and the gate runs before any `uv` subprocess.
- **Files modified:** diana/tts/heavy_install.py
- **Commit:** 733a5ee

No architectural changes (Rule 4) were needed.

## Threat Surface

No new security surface beyond the plan's `<threat_model>`. The mitigations land as designed:
- **T-05-SC / T-05-GGUF** (supply chain): every package pinned to an exact, plan-time-re-verified version; install only from PyPI + the abetlen wheel index + pinned/ungated HF repos + a pinned fish git SHA.
- **T-05-EXE** (uv binary trust): `uv` resolved from `paths.uv_binary()` (bundled), PATH fallback dev-only.
- **T-05-CMD** (argv): list-argv, `shell=False`; values code-pinned, not user input.
- **T-05-DISK** (DoS): `has_space` before any byte.
- **T-05-SRC** (thread→st.*): `install_engine` writes only the shared `state` dict; no `streamlit` import anywhere in the file.

## Verification

- `tests/test_heavy_install.py` + `tests/test_license_gate.py`: **6/6 flipped skip→PASS** (provision_venv argv+order, extra-index passthrough, stdout streaming; install_engine disk-precheck-blocks + marks-installed-on-success; license accept-once persistence) — subprocess fully mocked, NO real install.
- Full suite: `/Users/tyler/Repos/diana/.venv/bin/python -m pytest tests/ -q` → **478 passed, 19 skipped, 1 deselected, 0 failures** (baseline was 472 passed / 25 skipped; the 6 new passes are exactly the flipped scaffolds; the 19 remaining skips are engine/custom-voices/gpu/registry/install-state scaffolds for later waves).
- Greps: no `^import torch|llama_cpp|orpheus_cpp|f5_tts|streamlit` at module top; `uv_binary` present; no `shell=True`; no `st.`/`streamlit` call anywhere (only docstring references).
- Runtime guarantee: importing `diana.tts.heavy_install` pulls no `torch`/`llama_cpp`/`orpheus_cpp`/`f5_tts`/`streamlit` into `sys.modules`.

## Notes for Downstream Slices

- The engine slices construct `HeavyInstallSpec` (or pass the engine name) and call `install_engine` on a daemon thread guarded by the Settings `_can_spawn_download`; the row renders from `state["phase"]`/`state["step"]` + the existing byte fields via `@st.fragment`. Extend `_new_dl_state` with `phase`/`step` keys when wiring the row.
- `prefetch_argv` is a placeholder (`-m <pkg> --prefetch`) per engine; each slice finalizes the real prefetch entrypoint (or a `heavy_workers/*.py` `--prefetch` mode) — `install_engine` only orchestrates the subprocess + `HF_HOME` and is mocked here.
- macOS GPU: swap the Orpheus `extra_index` from `_ABETLEN_CPU` to `_ABETLEN_METAL` (both constants exported) when building the spec on Apple Silicon.
- Fish install carries the pinned git SHA in its spec `packages`; gate the Fish install behind `gpu_probe.capable_nvidia_gpu()` (05-02) before spawning `install_engine`.

## Self-Check: PASSED

- FOUND: diana/tts/heavy_install.py
- FOUND: .planning/phases/05-heavy-opt-in-engines/05-03-SUMMARY.md
- FOUND commit: 733a5ee (feat(05-03): bundled-uv heavy-engine provisioner ...)
