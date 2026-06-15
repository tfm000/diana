---
phase: 05-heavy-opt-in-engines
plan: 04
subsystem: tts
tags: [orpheus, heavy-engine, subprocess, lazy-import, venv, hf-cache, two-phase-install, fail-fast, apptest, streamlit, llama-cpp, gguf]

# Dependency graph
requires:
  - phase: 05-heavy-opt-in-engines (05-02)
    provides: "registry.heavy_engine_failfast/_HEAVY_ENGINES/_ASCII_ONLY_ENGINES; install_state.heavy_engine_installed/heavy_footprint_bytes/uninstall_heavy_engine; paths.venvs_dir/hf_cache_dir/heavy_worker"
  - phase: 05-heavy-opt-in-engines (05-03)
    provides: "heavy_install.HeavyInstallSpec + install_engine (two-phase deps->weights thread target, has_space pre-check, HF_HOME prefetch, .{engine}.installed marker)"
  - phase: 04-engine-management-voice-catalog
    provides: "5_Settings.py dl_state/_download_action/_can_spawn_download/@st.fragment _render_download_progress + _render_uninstall_control + _cross_engine_badge; downloader.has_space; 1_Upload.py _engine_readiness + Convert button"
  - phase: 05-heavy-opt-in-engines (05-01)
    provides: "Wave-0 conftest fixtures (tmp_data_paths, fake_venv) + RED/skip scaffolds (test_orpheus_engine, test_registry_heavy)"
provides:
  - "diana/tts/orpheus_engine.py::OrpheusEngine — TTSEngine, 8 static named voices, out-of-process subprocess synth (text as stdin JSON DATA — T-05-CMD), heavy-import-free module top (ENGINE-01/D-17)"
  - "diana/tts/orpheus_engine.py::orpheus_install_spec — HeavyInstallSpec with 05-03-confirmed pins + per-OS abetlen index (metal on darwin, cpu elsewhere); the Settings row consumes it (no hardcoded repo IDs in the page)"
  - "diana/tts/heavy_workers/orpheus_worker.py — venv-run worker: --prefetch warms GGUF+SNAC into HF_HOME; default mode reads stdin JSON -> OrpheusCpp().tts -> WAV (the ONE place orpheus_cpp is imported; no __init__.py)"
  - "diana/tts/registry.py — orpheus across list_engines/_get_engine_class/create_engine; heavy engines LISTED (D-17); all_engine_voices resilient to a listed-but-not-yet-built engine"
  - "diana/dashboard/pages/5_Settings.py::_render_heavy_engine_row + _start_heavy_install + _render_heavy_uninstall_control — the generic heavy-engine install row F5/Fish reuse (footprint confirm + has_space + two-phase progress + uninstall)"
  - "diana/dashboard/pages/1_Upload.py — orpheus readiness badge + D-16 fail-fast Convert gate (heavy_engine_failfast disables Convert)"
affects: [05-f5-slice, 05-fish-slice, 05-custom-voices, 06-packaging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Heavy-engine pattern: module-top heavy-import-free engine class (stdlib + TTSVoice + paths only) whose synthesize() shells [<venv-python>, <worker>] with chunk text as stdin JSON DATA (shell=False, list argv); the heavy SDK lives ONLY in heavy_workers/<engine>_worker.py run by the venv python (D-17/ENGINE-01/T-05-CMD)"
    - "Generic heavy-engine Settings install row (_render_heavy_engine_row): built on the Kokoro-row machinery (dl_state/_download_action/_can_spawn_download/@st.fragment) but swapping the download substrate for heavy_install.install_engine — D-04 itemized footprint confirm (always, heavy>200MB), D-05 has_space(venvs_dir) pre-check, two-phase progress, two-step engine uninstall. F5/Fish call it with their own spec"
    - "Two-phase progress in _render_download_progress: phase=='deps' -> 'Installing dependencies… {step}' label (uv stdout, no byte totals); phase=='weights' -> weights step; Kokoro/Piper never set phase so they keep the byte bar (backward compatible)"
    - "Listed-but-not-built resilience: heavy engines register in list_engines() (D-17) before their engine class lands in its own wave; all_engine_voices try/except-skips an engine whose voices can't be enumerated yet so the live cross-engine browser never crashes"

key-files:
  created:
    - diana/tts/orpheus_engine.py
    - diana/tts/heavy_workers/orpheus_worker.py
    - tests/test_orpheus_slice_apptest.py
    - .planning/phases/05-heavy-opt-in-engines/05-HUMAN-UAT.md
    - .planning/phases/05-heavy-opt-in-engines/05-04-SUMMARY.md
  modified:
    - diana/tts/registry.py
    - diana/dashboard/pages/1_Upload.py
    - diana/dashboard/pages/5_Settings.py
    - tests/test_tts_registry.py

key-decisions:
  - "Heavy engines (orpheus/f5/fish) are LISTED in list_engines() this wave, not just orpheus — the Wave-0 scaffold test_registry_heavy::test_heavy_engines_listed (authored FOR this plan) asserts all three are listed once orpheus registers; the scaffold is the authoritative contract. all_engine_voices was made resilient (skip a listed-but-not-built engine) and the Upload picker is safe for f5/fish because heavy_engine_failfast gates them."
  - "Edited the stale test_tts_registry::test_local_only (exact-equality ['native_os','kokoro','piper']) — it predates Phase 5 and is mutually exclusive with test_registry_heavy. Relaxed to assert light-engines-first then heavy-present, preserving its intent (native_os default first, removed engines absent)."
  - "orpheus_install_spec selects the abetlen index per-OS at build time (metal on darwin for GPU accel, cpu elsewhere) — the 05-03 spec carried cpu only; the engine slice is the right place to choose per the 05-03 'macOS GPU: swap to metal' note."
  - "Engine-level uninstall block added (_engine_in_use_reason): block when a NON-TERMINAL job has tts_engine==engine (the engine-level analogue of install_state.voice_in_use, which only checks tts_voice). Documented as the heavy-engine uninstall block decision."

patterns-established:
  - "Out-of-process heavy engine: cheap path (enumerate/badge/fail-fast) imports nothing heavy; synthesis crosses into the per-engine venv via subprocess with text as stdin JSON DATA"
  - "Generic heavy-engine install row reused across the three heavy slices (orpheus now, f5/fish next) — spec-driven, no per-engine page code beyond the spec + one _render_heavy_engine_row call"

requirements-completed: [HEAVY-01]

# Metrics
duration: ~45min
completed: 2026-06-15
tasks: 3
files: 9
---

# Phase 5 Plan 04: Orpheus Vertical Slice Summary

**Orpheus is the first end-to-end heavy opt-in engine: an in-app one-action install (bundled-uv venv + GGUF/SNAC weights), 8 named voices enumerated with zero heavy imports, and out-of-process subprocess synthesis (chunk text as stdin JSON DATA) — wired across the registry, the Settings install row, and the Upload D-16 fail-fast Convert gate.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-06-15
- **Completed:** 2026-06-15
- **Tasks:** 3 (2 implementation + 1 checkpoint resolved via the deferred-UAT path under --auto)
- **Files modified:** 9 (5 created, 4 modified)

## Accomplishments

- **OrpheusEngine** (`diana/tts/orpheus_engine.py`) — implements the `TTSEngine` Protocol with 8 static named voices (tara/leah/jess/mia/zoe/leo/dan/zac), a cheap `initialize()` that fail-fasts (`FileNotFoundError` → "Settings ▸ Voices") when uninstalled, and `synthesize()` that offloads to a subprocess running the orpheus venv's python + worker, passing `{text, voice_id, out}` as stdin JSON DATA with `HF_HOME` set. Module top is heavy-import-free (ENGINE-01/D-17). Plus `orpheus_install_spec()` (HeavyInstallSpec, 05-03 pins, per-OS abetlen index).
- **orpheus_worker.py** (`diana/tts/heavy_workers/`) — the ONE place `orpheus_cpp` is imported; `--prefetch` warms GGUF+SNAC into `HF_HOME`, default mode reads stdin JSON → `OrpheusCpp().tts` → WAV via soundfile. No `__init__.py` (package-data invoked by path, never imported by the app).
- **Registry wiring** — orpheus across `list_engines`/`_get_engine_class`/`create_engine`; heavy engines now LISTED (D-17); `all_engine_voices` made resilient to a listed-but-not-yet-built engine so the cross-engine browser never crashes when f5/fish are listed before their slices.
- **Settings install row** — the generic `_render_heavy_engine_row(engine, spec)` (F5/Fish will reuse): D-04 itemized deps-vs-model footprint confirm, D-05 `has_space(venvs_dir, deps+weights)` pre-check, two-phase progress (deps step label → weights step), and a two-step engine uninstall with a non-terminal-job in-use block. `_cross_engine_badge` gained an orpheus branch.
- **Upload D-16 gate** — orpheus readiness badge + the fail-fast Convert gate: `heavy_engine_failfast(engine_name)` renders `st.error` and drives the Convert button's `disabled=` so an uninstalled heavy engine can never start a job (covers f5/fish too).
- **Tests** — `test_orpheus_engine` + `test_registry_heavy` flipped skip→PASS; new `test_orpheus_slice_apptest.py` (3 interaction-level pre-checks) covers the Upload fail-fast + the Settings install-row render with a sys.modules no-heavy-import guard. Full suite: **486 passed, 14 skipped, 0 failures**.

## Task Commits

1. **Task 1: OrpheusEngine + worker + registry wiring + Upload badge/fail-fast** — `9c23694` (feat)
2. **Task 2: Settings Orpheus heavy-engine install row** — `751839c` (feat)
3. **Task 3: checkpoint pre-check (AppTest) + deferred real-install UAT** — `161b7aa` (test)

## Files Created/Modified

- `diana/tts/orpheus_engine.py` (created) — OrpheusEngine (TTSEngine, 8 voices, subprocess synth) + orpheus_install_spec
- `diana/tts/heavy_workers/orpheus_worker.py` (created) — venv-run worker (--prefetch + stdin-JSON synth); no __init__.py
- `diana/tts/registry.py` (modified) — orpheus seams + heavy engines listed + all_engine_voices resilience
- `diana/dashboard/pages/1_Upload.py` (modified) — orpheus readiness branch + D-16 fail-fast Convert gate
- `diana/dashboard/pages/5_Settings.py` (modified) — _render_heavy_engine_row + _start_heavy_install + _render_heavy_uninstall_control + _engine_in_use_reason; two-phase progress in _render_download_progress; orpheus cross-engine badge; Orpheus row under "Heavy opt-in engines"
- `tests/test_orpheus_slice_apptest.py` (created) — 3 AppTest pre-checks (Upload fail-fast + Settings row)
- `tests/test_tts_registry.py` (modified) — relaxed the stale exact-equality list_engines assertion (see Deviations)
- `.planning/phases/05-heavy-opt-in-engines/05-HUMAN-UAT.md` (created) — deferred real-install/by-ear-synth UAT steps

## Decisions Made

- **List all three heavy engines now, not just orpheus.** The Wave-0 scaffold authored for this plan (`test_registry_heavy::test_heavy_engines_listed`) un-skips the moment orpheus registers and asserts orpheus AND f5 AND fish are all in `list_engines()`. The scaffold is the authoritative contract for "registered across the registry seams" (a plan `must_haves.truth`), so all three are listed. Safety: f5/fish have no engine class yet, so `all_engine_voices` now skips an engine whose voices can't be enumerated (try/except), and the Upload picker is safe because `heavy_engine_failfast` gates f5/fish (selecting them disables Convert with the install prompt).
- **Per-OS abetlen index in the spec.** `orpheus_install_spec` selects `metal` on darwin (GPU accel on Apple Silicon) and `cpu` elsewhere — per the 05-03 "macOS GPU: swap to metal" note; the engine slice is the right place to make that choice.
- **Engine-level uninstall in-use block.** Added `_engine_in_use_reason` (blocks uninstall when a non-terminal job has `tts_engine == engine`) — the engine-level analogue of `install_state.voice_in_use` (which only checks `tts_voice`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Two pre-existing scaffold tests were mutually exclusive about `list_engines()`**
- **Found during:** Task 1 (wiring orpheus into the registry).
- **Issue:** `test_registry_heavy::test_heavy_engines_listed` (the Wave-0 scaffold for THIS plan) asserts orpheus AND f5 AND fish are all in `list_engines()` once orpheus registers, while `test_tts_registry::test_local_only` (written in Phase 3/4, before heavy engines) asserts EXACT equality `list_engines() == ["native_os","kokoro","piper"]`. Both could not pass simultaneously, and the plan's "add orpheus" wording alone would leave the heavy scaffold red. Listing f5/fish (engines not built this wave) would also break the LIVE `all_engine_voices` (and the Settings cross-engine browser at `5_Settings.py:1260`) with a `ValueError` from `_get_engine_class("f5")`.
- **Fix:**
  (a) Added all three heavy engines to `list_engines()` (the scaffold contract for D-17).
  (b) Made `all_engine_voices` resilient (Rule 2 — correctness): try/except around `get_engine_voices(engine)` so a listed-but-not-yet-built engine simply contributes no voices instead of crashing the live browser.
  (c) Relaxed the stale `test_tts_registry::test_local_only` to `test_local_engines_first_then_heavy` — asserts the first three are `[native_os, kokoro, piper]` and each heavy engine is present, preserving its real intent (native_os default first; removed engines still absent via the untouched `test_removed_engines_absent`).
- **Files modified:** `diana/tts/registry.py`, `tests/test_tts_registry.py`
- **Verification:** `test_registry_heavy` (3) + `test_tts_registry` (10) + full suite (486) all green; `all_engine_voices` no longer raises for f5/fish (verified by the cheap-path sys.modules guard exercising it).
- **Committed in:** `9c23694` (Task 1 commit)

**2. [Rule 2 - Missing critical] Phase-B (weights) progress had no step label**
- **Found during:** Task 2 (extending `_render_download_progress`).
- **Issue:** The plan specified the Phase-A (`phase=="deps"`) step label, but Phase B (`phase=="weights"`) runs the weight prefetch in a venv subprocess that does not stream byte counts back — so before any `downloaded` is set the existing code would render a 0/0 byte bar (misleading "0.0 / 0.0 MB").
- **Fix:** When `phase=="weights"` and `downloaded` is still 0, render the `state["step"]` label ("Downloading model weights…") instead of a 0/0 bar. Kokoro/Piper never set `phase` so their byte bar is unchanged.
- **Files modified:** `diana/dashboard/pages/5_Settings.py`
- **Verification:** ast.parse + full suite green; the Settings AppTest renders the row without exception.
- **Committed in:** `751839c` (Task 2 commit)

---

**Total deviations:** 2 (1 blocking test-conflict resolution with a correctness fix, 1 missing-critical UX fix)
**Impact on plan:** Both were necessary to make the plan's own Wave-0 scaffolds pass and to avoid shipping a live-app crash / misleading progress UI. The list-engines decision is a deliberate, documented reconciliation of two conflicting scaffolds — no scope creep beyond what the scaffolds require. The Upload picker now also lists f5/fish (gated by fail-fast), which is the intended D-17 cross-engine surface for the later slices.

## Issues Encountered

- **AppTest cannot inject a real file upload**, so the Upload Convert button (gated on `uploaded_file is not None`) can't be reached in AppTest. The D-16 Convert-disable was pre-checked two ways instead: (a) an AppTest that selects Orpheus and asserts the actionable readiness prompt renders, and (b) a direct assertion that `heavy_engine_failfast` — the exact value wired into the Convert `disabled=` — returns the install message for uninstalled Orpheus and `None` for a light engine. This fully covers the gate logic.

## Threat Surface

No new security surface beyond the plan's `<threat_model>`; the mitigations land as designed:
- **T-05-CMD** — `synthesize` passes text as stdin JSON DATA, list argv, `shell=False`; voice id comes from the static VOICES set (verified by `test_synthesize_subprocess_cmd_and_stdin_json`: "hello world" never appears in the argv).
- **T-05-EXE** — venv python + worker resolved from `paths.venvs_dir()`/`paths.heavy_worker()` (not PATH); worker is package-data with no `__init__.py` (never app-imported).
- **T-05-IMP** — no `orpheus_cpp`/`llama_cpp`/`torch` import in `orpheus_engine` module top, `registry`, `install_state`, or `5_Settings.py` (grep + sys.modules gates pass).
- **T-05-DISK** — `has_space(venvs_dir(), deps+weights)` before any byte in the install row.
- **T-05-SRC** — the install thread target is `heavy_install.install_engine` (writes only `state`); the `@st.fragment` renders.
- **T-05-GGUF** — pinned ungated HF repos (05-03); the D-04 itemized footprint confirm is the human gate before any download.

## User Setup Required

None for the cheap path. Installing/running Orpheus itself downloads its weights from public ungated HuggingFace repos (no account/token) on first install — see `05-HUMAN-UAT.md` for the deferred real-install verification steps.

## Next Phase Readiness

- The generic **heavy-engine install row** (`_render_heavy_engine_row`) and the **D-16 fail-fast Convert gate** (`heavy_engine_failfast`, already covering f5/fish) are established — the F5 (05-05) and Fish (05-07) slices add their engine + worker + `<engine>_install_spec` and call `_render_heavy_engine_row(engine, spec)` with no new page machinery.
- **Deferred:** the real multi-GB Orpheus install + by-ear synthesis (Task 3 steps 4–6) is carried in `05-HUMAN-UAT.md` (macOS dev box, no NVIDIA GPU, multi-GB install impractical under --auto). The orchestrator's post-merge visual/vision pass on master covers the Playwright screenshot step.
- The default install stays untouched (D-02): the cheap path imports nothing heavy.

## Self-Check: PASSED

- FOUND: diana/tts/orpheus_engine.py
- FOUND: diana/tts/heavy_workers/orpheus_worker.py
- FOUND: tests/test_orpheus_slice_apptest.py
- FOUND: .planning/phases/05-heavy-opt-in-engines/05-HUMAN-UAT.md
- FOUND: .planning/phases/05-heavy-opt-in-engines/05-04-SUMMARY.md
- FOUND commit: 9c23694 (Task 1 — OrpheusEngine + worker + registry + Upload fail-fast)
- FOUND commit: 751839c (Task 2 — Settings heavy-engine install row)
- FOUND commit: 161b7aa (Task 3 — AppTest pre-check + deferred UAT doc)
