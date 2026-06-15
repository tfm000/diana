---
phase: 05-heavy-opt-in-engines
plan: 01
subsystem: tts-tests
tags: [scaffold, tdd, wave-0, heavy-engines, security-invariants]
requires:
  - "tests/ pytest + pytest-asyncio harness (asyncio_mode=auto, testpaths, network marker)"
  - "diana.tts.install_state / registry / catalog.safe_voice_dest (cheap-probe + path-safety precedents the scaffolds mirror)"
  - "diana.downloads.downloader.has_space, diana.database app_settings (get/set_setting, init_db), diana.paths"
provides:
  - "The Wave-0 test contract for HEAVY-01/02/03: 11 files (1 shared conftest + 10 RED/skipif scaffolds) that collect GREEN now and auto-flip to live regression gates as Waves 2-7 land their symbols — zero later test-file edits"
  - "A live (UNGATED) D-17/ENGINE-01 no-heavy-import gate over the cheap registry path, active from day one"
  - "Shared heavy-engine fixtures (tmp_data_paths, fake_venv, mock_uv, fake_nvidia_smi, temp_clip) reusable by every later wave's tests"
affects:
  - "tests/ only — NO diana/ source changed"
  - "Waves 2-7 implementers must satisfy these encoded contracts (uv argv/order, stdin-JSON text, torch-free probes, accept-once license, fail-fast, path-safety)"
tech-stack:
  added: []   # pytest, pytest-asyncio, soundfile, numpy all already present
  patterns:
    - "Import-probe + pytest.mark.skipif scaffold with a REAL assertion body (never pass/xfail)"
    - "Multi-candidate symbol-home probing for planner's-choice modules"
    - "Mock the subprocess/venv layer (heavy engines run out-of-process; uninstallable in CI)"
    - "sys.modules delta/absence assertion to forbid heavy SDK imports on cheap paths"
    - "Signature-adaptive calls (try documented shapes) for genuinely planner's-choice CRUD"
key-files:
  created:
    - tests/conftest.py
    - tests/test_heavy_install.py
    - tests/test_gpu_probe.py
    - tests/test_install_state_heavy.py
    - tests/test_license_gate.py
    - tests/test_orpheus_engine.py
    - tests/test_f5_engine.py
    - tests/test_fish_engine.py
    - tests/test_registry_heavy.py
    - tests/test_custom_voices.py
    - tests/test_heavy_failfast.py
  modified: []
decisions:
  - "Made the registry no-heavy-import test UNGATED (live from day one) rather than skipif-gated — it holds now and protects D-17/ENGINE-01 across all of Waves 2-7. This is why the suite shows 462 passed (461 prior + 1) rather than 461."
  - "Used a before/after sys.modules delta in the ungated registry gate so it is robust even in a dev env that already imported a heavy SDK; the gated probes use the simpler absence check (heavy SDKs are absent from Diana's .venv)."
  - "Signature-adaptive calls for genuinely planner's-choice symbols (provision_venv extra_index via inspect, install_engine progress hooks, save_custom_voice shapes via try-each) so scaffolds auto-flip even if the exact signature varies within documented bounds."
  - "Asserted the Fish VRAM floor as a sane band (8-24 GB) with above/below feeds RELATIVE to FISH_MIN_VRAM_GB — encodes the gate semantics robustly instead of brittly pinning 12."
  - "Did NOT mark HEAVY-01/02/03 complete: this plan lands only the Wave-0 test contract, not the engines."
metrics:
  duration: "~20 min"
  tasks_completed: 3
  files_created: 11
  files_modified: 0
  completed: 2026-06-15
---

# Phase 5 Plan 01: Heavy-Engine Wave-0 Test Scaffold Summary

The Phase-5 Nyquist Wave-0 test contract: a shared `tests/conftest.py` plus ten RED/skipif scaffolds that encode the heavy-engine security invariants (no-heavy-import, text-as-stdin-JSON, torch-free GPU gate, accept-once license, path-safety, fail-fast) as real assertions now — collection stays green and each test auto-flips to a live gate the moment its Wave-2..7 symbol lands, with no later edits.

## What Was Built

11 files mirroring Diana's proven Phase-3/Phase-4 scaffold discipline (import-guard future symbols, `skipif`-gate dependents, real assertion bodies, multi-candidate module-home probes):

| File | Gates on (lands in) | Encodes |
|------|---------------------|---------|
| `conftest.py` | — (shared fixtures) | `tmp_data_paths`, `fake_venv`, `mock_uv`, `fake_nvidia_smi`, `temp_clip` |
| `test_heavy_install.py` | `provision_venv` / `install_engine` (Wave 3) | uv argv + **venv-before-install order**, `paths.uv_binary()` not PATH, extra-index passthrough, `on_line` progress, **`has_space` before any byte**, `.installed` marker on success (Pattern 1/3, D-04/D-05/D-06) |
| `test_gpu_probe.py` | `capable_nvidia_gpu` / `FISH_MIN_VRAM_GB` (Wave 6) | torch-free nvidia-smi parse: absent/below/above floor + **no torch import** (D-09/D-10, Pitfall 4) |
| `test_install_state_heavy.py` | `heavy_engine_installed` / `heavy_footprint_bytes` / `uninstall_heavy_engine` (Wave 3) | filesystem-only installed/footprint/scoped-uninstall + **no heavy import** (ENGINE-01/D-17) |
| `test_license_gate.py` | `accept_license` / `license_accepted` (Wave 3) | accept-once persistence over a temp DB, per-engine, idempotent (D-08) |
| `test_orpheus_engine.py` | `OrpheusEngine` (Wave 2) | 8 static voices (no `orpheus_cpp` import), initialize fail-fast naming "Settings ▸ Voices", subprocess synth with **text as stdin JSON** (D-16/D-17/T-05-CMD) |
| `test_f5_engine.py` | `F5Engine` (Wave 4) | bundled-default dynamic voices (no torch import), synth carrying `ref_file`/`ref_text`/`gen_text` (HEAVY-02/D-15) |
| `test_fish_engine.py` | `FishEngine` (Wave 7) | initialize double-gate (installed AND capable GPU), F5-mirror subprocess shape (HEAVY-03/D-09/D-10) |
| `test_registry_heavy.py` | `list_engines` heavy names (Wave 2) + **UNGATED** | orpheus/f5/fish listed + UTF-8 map; **live** no-heavy-import gate over the cheap path (D-17/ENGINE-01) |
| `test_custom_voices.py` | `validate_clip` / `safe_custom_voice_dest` / CRUD (Wave 5) | clip validation never raises (accept 16 kHz, reject empty transcript / sub-second / bad format), basename + `.wav/.mp3/.txt` allow-list + traversal `ValueError`, metadata round-trip with malformed-JSON degradation (D-11..D-15/V12/T-04-LBLJSON) |
| `test_heavy_failfast.py` | `heavy_engine_failfast` (Wave 2) | uninstalled heavy engine → actionable "Settings ▸ Voices" prompt; `None` when installed or non-heavy (D-16, SC#4) |

## Verification

- `pytest tests/ -q` → **462 passed, 35 skipped, 1 deselected, 0 failures, 0 collection errors** (the prior 461 + the one live ungated no-heavy-import gate; the 35 skips are the new symbol-gated scaffolds).
- `pytest tests/ --collect-only -q` → **exit 0** (no import/collection error from the unlanded-symbol probes).
- No scaffold uses `pass`/`xfail` as a body: `grep -nE "pytest.mark.xfail|^\s*pass\s*$"` across all 10 scaffolds returns nothing.
- Per-task acceptance greps all pass: conftest defines the five named fixtures; each scaffold references its gate symbol (`paths.uv_binary`, `capable_nvidia_gpu`, `heavy_engine_installed`, `license_accepted`); `test_orpheus_engine` asserts 8 voices + stdin-JSON; `test_registry_heavy` asserts `sys.modules`; `test_custom_voices` asserts `validate_clip` tuple/never-raises + traversal `ValueError`.

## Threat Invariants Encoded (now, as assertions)

- **T-05-IMP (no heavy import on cheap paths):** `test_registry_heavy` (live) + `test_install_state_heavy` + the per-engine enumeration tests assert `torch`/`llama_cpp`/`orpheus_cpp`/`f5_tts` stay out of `sys.modules` (ENGINE-01/D-17).
- **T-05-CMD (text→shell):** every engine synth test asserts the chunk text is passed as stdin JSON and is **absent** from the argv (list argv, never a shell string).
- **T-05-PATH (upload filename):** `test_custom_voices` asserts `safe_custom_voice_dest` raises on traversal and enforces the extension allow-list.
- **D-04/D-05 (disk pre-check):** `test_heavy_install` asserts `has_space` gates **before** any uv subprocess and no marker is written on refusal.
- **D-08 (accept-once license):** `test_license_gate` asserts persistence + per-engine scoping.

## Deviations from Plan

None that change behavior — the plan executed as written. Two in-scope test-quality adjustments (deviation Rule 3, blocking the explicit acceptance grep):

1. **[Rule 3] Replaced two import-probe `except ImportError: pass` blocks with `contextlib.suppress(ImportError)`** in `test_fish_engine.py` (`_force_gpu` helper) and `test_custom_voices.py` (the symbol-probe). Reason: the plan's acceptance criterion runs `grep -nE "...|^\s*pass\s*$"` and requires it to return nothing; a bare `pass` body would have failed it. Behavior is identical. Removed a now-unused `import inspect` in `test_custom_voices.py` after switching the save helper from arity-introspection to a try-each-documented-shape approach.

## Notes for Later Waves

- The scaffolds are **the contract**. To turn a scaffold green, land its symbol with the documented signature/behavior; do not edit the test file.
- A few signatures are genuinely planner's-choice (`provision_venv` extra-index param name, `install_engine` progress hook, `save_custom_voice` shape). The scaffolds adapt across the documented variants; if an implementer picks a shape entirely outside those, that single adaptive call may need a one-line tweak — every other assertion is signature-robust.
- `HEAVY-01/02/03` remain **incomplete** — only the Wave-0 test contract is delivered here. They are satisfied when the engines land and these scaffolds flip green (plus manual install/synthesis UAT per RESEARCH Validation Architecture).

## Known Stubs

None. The future-symbol references are the intended `skipif` gates (the Phase-3/4 scaffold idiom), not stubs; the fixtures lay down real (mocked) WAV/venv artifacts. No product code was added and nothing flows to the UI.

## Self-Check: PASSED

- All 11 created files exist on disk (verified via `[ -f ... ]`).
- All 3 task commits exist in `git log` (`d7bf83b`, `e760102`, `33e010b`).
- Full suite + collect-only both green; no bare `pass`/`xfail`.
