---
phase: 05-heavy-opt-in-engines
plan: 05
subsystem: tts
tags: [f5-tts, heavy-engine, subprocess, lazy-import, torch-venv, hf-cache, license-gate, accept-once, bundled-default-voice, zero-shot-clone, fail-fast, apptest, streamlit]

# Dependency graph
requires:
  - phase: 05-heavy-opt-in-engines (05-02)
    provides: "registry.heavy_engine_failfast/_HEAVY_ENGINES/_ASCII_ONLY_ENGINES (f5 already listed); install_state.heavy_engine_installed/uninstall_heavy_engine (f5->shared torch venv); paths.venvs_dir/hf_cache_dir/heavy_worker; package-data globs (data/voices/*, tts/heavy_workers/*.py)"
  - phase: 05-heavy-opt-in-engines (05-03)
    provides: "heavy_install.HeavyInstallSpec + install_engine (two-phase deps->weights, has_space pre-check, HF_HOME prefetch, .{engine}.installed marker); heavy_install.license_accepted/accept_license (D-08 accept-once persistence)"
  - phase: 05-heavy-opt-in-engines (05-04)
    provides: "5_Settings.py _render_heavy_engine_row + _start_heavy_install + _render_heavy_uninstall_control + _cross_engine_badge orpheus branch; 1_Upload.py _engine_readiness orpheus branch + generic D-16 fail-fast Convert gate; tests/test_orpheus_slice_apptest.py (the AppTest idioms cloned here)"
  - phase: 05-heavy-opt-in-engines (05-01)
    provides: "Wave-0 conftest fixtures (tmp_data_paths, fake_venv) + RED/skip scaffolds test_f5_engine + test_license_gate"
provides:
  - "diana/tts/f5_engine.py::F5Engine — TTSEngine, bundled license-clean default voice (f5_default), out-of-process subprocess synth into the SHARED torch venv (ref_file/ref_text/gen_text as stdin JSON DATA — T-05-CMD), heavy-import-free module top (ENGINE-01/D-17); initialize() fail-fasts (D-16)"
  - "diana/tts/f5_engine.py::f5_install_spec — HeavyInstallSpec (f5-tts==1.1.20 into the shared 'torch' venv per D-03; worker --prefetch warms F5TTS_v1_Base); the Settings row consumes it (no hardcoded repo IDs in the page)"
  - "diana/tts/heavy_workers/f5_worker.py — venv-run worker: --prefetch warms F5TTS_v1_Base into HF_HOME; default mode reads stdin JSON -> F5TTS().infer(ref_file,ref_text,gen_text) -> WAV (the ONE place f5_tts/torch is imported; no __init__.py)"
  - "diana/data/voices/f5_default.{wav,txt} — bundled license-clean default reference voice (on-device macOS say, 6.55s) + its exact transcript (D-15/Q-E); shipped as package-data"
  - "diana/dashboard/pages/5_Settings.py::_render_heavy_license_gate + _render_heavy_engine_row(license=...) — the accept-once CC-BY-NC NC-license gate shown BEFORE any install control (D-08); Fish reuses it in 05-07. _cross_engine_badge f5 branch"
  - "diana/dashboard/pages/1_Upload.py — f5 readiness badge branch (the generic D-16 fail-fast already covered f5)"
  - "tests/test_f5_slice_apptest.py — 4 interaction-level AppTest pre-checks (license-gate-before-install + accept-persists + Convert fail-fast), all heavy-import-free"
affects: [05-custom-voices, 05-fish-slice, 06-packaging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "License-gate-before-install (D-08): _render_heavy_license_gate consults heavy_install.license_accepted; when unaccepted it renders the NC disclosure + license link + 'I accept' (accept_license + st.rerun) and the caller returns BEFORE any footprint/disk/Install control. Acceptance persists in app_settings so a re-install never re-prompts. Generic — Fish reuses it (05-07). Mirrors the 1_Upload.py dismissible-hint accept-once idiom."
    - "F5 reuses the 05-04 heavy-engine pattern verbatim: module-top heavy-import-free engine class (stdlib + TTSVoice + paths) whose synthesize() shells [<torch-venv-python>, f5_worker.py] with ref_file/ref_text/gen_text as stdin JSON DATA; the heavy SDK (torch/f5_tts) lives ONLY in the worker run by the venv python (D-17/ENGINE-01/T-05-CMD)"
    - "Bundled default reference voice resolved as a package resource (importlib.resources.files('diana.data').joinpath('voices','f5_default.wav')) — a fixed path, never user input (T-05-PATH); its exact transcript ships beside it (ref_text, no STT — D-12)"
    - "_render_heavy_engine_row gained an OPTIONAL license descriptor (backward compatible): Orpheus passes none (permissive weights, row unchanged); F5/Fish pass {text,url} to gate the row behind accept-once"

key-files:
  created:
    - diana/tts/f5_engine.py
    - diana/tts/heavy_workers/f5_worker.py
    - diana/data/voices/f5_default.wav
    - diana/data/voices/f5_default.txt
    - tests/test_f5_slice_apptest.py
    - .planning/phases/05-heavy-opt-in-engines/05-05-SUMMARY.md
  modified:
    - diana/tts/registry.py
    - diana/dashboard/pages/1_Upload.py
    - diana/dashboard/pages/5_Settings.py
    - .planning/phases/05-heavy-opt-in-engines/05-HUMAN-UAT.md

key-decisions:
  - "Bundled default voice generated ON-DEVICE with macOS `say` (voice Samantha, 6.55s, 22.05kHz mono PCM_16) — license-clean by construction (self-generated, no third-party rights, D-15/Q-E). The transcript is a neutral original sentence. Flagged for human Q-E provenance confirmation in 05-HUMAN-UAT.md (user may swap a public-domain/self-recorded clip). 22.05kHz is acceptable for F5 (it resamples internally; ref clip <12s)."
  - "_render_heavy_engine_row signature extended with an OPTIONAL license=None param rather than a new function — keeps Orpheus's call unchanged and F5/Fish gate via the same row (the planned generic surface). The gate (_render_heavy_license_gate) returns early before any footprint/disk/Install so acceptance precedes any byte (D-08)."
  - "Real multi-GB torch install + by-ear synth DEFERRED to 05-HUMAN-UAT.md (appended an F5 section; Orpheus section preserved) per the Task-3 checkpoint authorization — impractical in an --auto macOS session. NOT a defect: the engine/worker/license/UI logic is fully automated-tested with the subprocess mocked, and the bundled default voice IS produced this session."
  - "get_engine_voices('f5') uses the static-VOICES default branch this slice (just the bundled default). 05-06 swaps it to a dynamic bundled+custom merge (the registry::_piper_voices pattern) — left as the documented next-slice seam."
  - "f5_install_spec lives in f5_engine.py (the Orpheus precedent) mirroring heavy_install._BUILTIN_SPECS['f5'] exactly (f5-tts==1.1.20, venv 'torch', deps 3.0GB/weights 1.4GB) so no repo IDs/pins are hardcoded in 5_Settings.py."

patterns-established:
  - "Accept-once license gate before a heavy install (D-08): durable app_settings flag, disclosure + link + 'I accept' before any control, persisted across restart — the generic gate F5/Fish share."

metrics:
  duration: ~40 min
  completed: 2026-06-15
  tasks: 3
  files-created: 6
  files-modified: 4
  commits: 3
  tests: "492 passed, 12 skipped (Fish + custom_voices, future slices), 0 failures"
---

# Phase 5 Plan 05: F5-TTS Core + Accept-Once NC-License Gate Summary

F5-TTS zero-shot voice cloning installs on demand behind an accept-once CC-BY-NC license disclosure (D-08, the first license gate), enumerates a bundled on-device-generated license-clean default voice (D-15), and synthesizes out-of-process in the shared torch venv (D-03) — torch never touches the app interpreter (D-17).

## What Was Built

**Task 1 — F5Engine + worker + bundled default voice + registry/Upload wiring** (`5079b4e`)

- `diana/tts/f5_engine.py::F5Engine` — clones the 05-04 Orpheus shape: module top is stdlib + `TTSVoice` + `paths` ONLY (no torch/f5_tts — ENGINE-01/D-17). A static `VOICES = [TTSVoice("f5_default", "Default (F5)", "en-us", "neutral", "enhanced")]` (custom voices merge in 05-06). `initialize()` is a cheap fail-fast raising `FileNotFoundError("F5-TTS not installed — open Settings ▸ Voices and click Install.")` (D-16). `_resolve_ref("f5_default")` returns the bundled clip path (via `importlib.resources`) + its shipped transcript. `_subprocess_synth` shells `[<torch-venv-python>, f5_worker.py]` with `{ref_file, ref_text, gen_text, out, speed, hf_cache}` as stdin JSON DATA, `HF_HOME` in env (T-05-CMD), and always unlinks the temp WAV. `f5_install_spec()` returns the `HeavyInstallSpec` (`f5-tts==1.1.20` into the shared `torch` venv, worker `--prefetch`).
- `diana/tts/heavy_workers/f5_worker.py` — runs under the torch venv (imports `f5_tts`/`soundfile` freely). `--prefetch` constructs `F5TTS(model="F5TTS_v1_Base", hf_cache_dir=HF_HOME)` to warm the checkpoint; default mode reads stdin JSON and runs `F5TTS().infer(ref_file, ref_text, gen_text, speed, remove_silence=True) -> (wav, sr, _)` → `sf.write(out, ..., format="WAV")`. No `__init__.py` (package-data, invoked by path).
- `diana/data/voices/f5_default.wav` + `.txt` — the bundled default reference voice, generated on-device with macOS `say` (6.55 s, 22.05 kHz mono, license-clean) + its exact transcript.
- `diana/tts/registry.py` — `f5` lazy-import branches in `_get_engine_class` + `create_engine` (constructs `F5Engine()`); `get_engine_voices("f5")` uses the static-VOICES default branch. (`f5` was already in `list_engines()` + `_ASCII_ONLY_ENGINES` from 05-02.)
- `diana/dashboard/pages/1_Upload.py` — `_engine_readiness` `f5` branch (Ready vs "~1.5 GB+ (torch + model), install in Settings ▸ Voices"). The Convert fail-fast was already generic (`heavy_engine_failfast` covers `f5`).

**Task 2 — Settings F5 install row with the accept-once NC-license gate (D-08)** (`9c9d7b8`)

- `_render_heavy_license_gate(engine, license)` — consults `heavy_install.license_accepted`; when unaccepted, renders the CC-BY-NC disclosure ("non-commercial / personal use only") + a "Read the license" link to `github.com/SWivid/F5-TTS` + an "I accept" button (`accept_license` + `st.rerun`). Returns True once accepted.
- `_render_heavy_engine_row` gained an optional `license=None` param: when given and unaccepted, the function returns BEFORE any footprint/disk/Install control (acceptance precedes any byte). Orpheus's call is unchanged (no license).
- The F5 row is wired in the "Heavy opt-in engines" subsection via `f5_install_spec()` with the CC-BY-NC `license={text, url}`. `_cross_engine_badge` gained an `f5` branch (cheap probe).

**Task 3 — human-verify (agent pre-check passed; real install deferred)** (`f849ca8`)

- `tests/test_f5_slice_apptest.py` (4 PASS, mirrors `test_orpheus_slice_apptest.py`): Upload F5 selection shows the install prompt + the `heavy_engine_failfast` Convert gate (D-16); Settings shows the CC-BY-NC disclosure + SWivid link + "I accept" and NO Install before acceptance (D-08); after the accept-once flag is set, the footprint confirm + Install appear and the accept gate is gone (D-08) — all with NO torch/f5_tts imported.
- `05-HUMAN-UAT.md` — appended an F5 (HEAVY-02) section documenting what IS automated-verified vs the deferred real accept-license → multi-GB torch install → by-ear synth UAT + the Q-E provenance confirmation. The Orpheus (HEAVY-01) section is preserved.

## How It Works (key flow)

```
Settings ▸ Voices ▸ Heavy opt-in engines ▸ F5
  └─ _render_heavy_engine_row("f5", f5_install_spec(), license={CC-BY-NC, SWivid url})
       └─ _render_heavy_license_gate  →  license_accepted? ─no→ disclosure + "I accept"  (D-08, before any byte)
                                                          └yes→ footprint confirm + has_space + Install (two-phase)
Upload ▸ select F5 (uninstalled)
  └─ _engine_readiness("f5") badge + heavy_engine_failfast("f5") disables Convert (D-16)
F5Engine.synthesize(text, "f5_default")
  └─ _resolve_ref → (bundled clip path, transcript)
  └─ subprocess [torch-venv/bin/python, f5_worker.py] <stdin {ref_file,ref_text,gen_text,...}> → WAV bytes
       (torch/f5_tts imported ONLY here, in the venv — never the app interpreter)
```

## Deviations from Plan

### Auto-fixed Issues

None — the plan executed as written. One harness note (not a code deviation): an early `cd /Users/tyler/Repos/diana && ...` Bash command drifted the cwd into the MAIN checkout and wrote the first `f5_default.wav` there. Caught immediately by the absolute-path Write guard (#3099), the stray file was removed and the clip + transcript regenerated inside the worktree. No main-checkout pollution remains; all subsequent file ops used worktree-absolute paths.

### Deferred (per Task-3 checkpoint authorization, NOT a defect)

The real multi-GB `torch` + `F5TTS_v1_Base` install and by-ear synthesis were deferred to `05-HUMAN-UAT.md` (impractical in an `--auto` macOS dev-box session). The engine/worker/license/UI logic is fully automated-tested with the subprocess mocked; the bundled default voice IS produced this session. The Q-E bundled-clip provenance confirmation is flagged for the human there.

## Authentication Gates

None encountered. (The plan notes `F5TTS_v1_Base` downloads from a public ungated HF repo on install — no token needed; that download is part of the deferred real-install UAT.)

## Known Stubs

None. The bundled default voice is real audio (not a placeholder); F5 synthesizes through the real worker (mocked only in tests). The dynamic custom-voice merge in `get_engine_voices("f5")` is intentionally the static-default branch this slice — 05-06 swaps it (documented seam, not a stub blocking this plan's goal).

## Threat Flags

None — no new trust-boundary surface beyond the plan's `<threat_model>`. The mitigations are in place: T-05-CMD (ref/gen text as stdin JSON DATA, list argv, shell=False), T-05-PATH (bundled clip is a fixed package resource, not user input), T-05-IMP (no torch/f5_tts on the cheap path — grep + sys.modules verified), T-05-LIC (accept-once NC disclosure before any download, persisted).

## Verification

- `tests/test_f5_engine.py` + `tests/test_license_gate.py` flipped skip→PASS.
- Full suite: **492 passed, 12 skipped (Fish + custom_voices — future slices), 0 failures** (`/Users/tyler/Repos/diana/.venv/bin/python -m pytest tests/ -q`).
- Cheap path (list_engines / get_engine_voices / all_engine_voices / f5_install_spec / badge) imports NO torch/f5_tts/torchaudio/vocos (sys.modules assertion) — `grep -nE "import torch|import f5_tts"` returns nothing in f5_engine.py, registry.py, and both pages.
- `diana/tts/heavy_workers/__init__.py` absent (worker is package-data, invoked by path).
- `diana/data/voices/f5_default.wav` reads via soundfile (6.55 s > 1 s); `F5Engine._resolve_ref("f5_default")` resolves it and its `ref_text` matches `f5_default.txt` byte-for-byte.
- AppTest pre-check (4 PASS): license-gate-before-install + accept-persists + Convert fail-fast.
- `05-HUMAN-UAT.md`: Orpheus section preserved, F5 section appended.

## For Future Plans

- **05-06 (custom voices):** swap `get_engine_voices("f5")` to a dynamic branch merging `F5Engine.VOICES` (bundled default) with saved custom voices (`custom_voices.list_custom_voices("f5")`), mirroring `registry._piper_voices`. `_resolve_ref` already raises on unknown ids — extend it to resolve custom-voice clip paths. The bundled default + the subprocess synth are the proven base.
- **05-07 (Fish):** reuse `_render_heavy_license_gate` / `_render_heavy_engine_row(license=...)` for Fish's NC license; clone `f5_engine.py` (shared torch venv) + add the GPU gate.
- **Human (deferred UAT):** run the F5 accept-license → install → synth steps in `05-HUMAN-UAT.md` on an install-capable machine and confirm the Q-E provenance.

## Self-Check: PASSED

- Created files all present: `diana/tts/f5_engine.py`, `diana/tts/heavy_workers/f5_worker.py`, `diana/data/voices/f5_default.wav`, `diana/data/voices/f5_default.txt`, `tests/test_f5_slice_apptest.py`, `05-05-SUMMARY.md`.
- Commits all present in git history: `5079b4e` (Task 1), `9c9d7b8` (Task 2), `f849ca8` (Task 3).
