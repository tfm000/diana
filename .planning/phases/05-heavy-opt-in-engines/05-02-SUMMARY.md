---
phase: 05-heavy-opt-in-engines
plan: 02
subsystem: tts
tags: [paths, gpu-probe, nvidia-smi, install-state, registry, streamlit, uv, venv, lazy-import, fail-fast]

# Dependency graph
requires:
  - phase: 04-engine-management-voice-catalog
    provides: install_state cheap-probe lane + uninstall_piper_voice/voice_in_use + registry seams (_ASCII_ONLY_ENGINES, thin install-state shims) + paths.ensure_dirs tree
  - phase: 05-heavy-opt-in-engines (05-01)
    provides: Wave-0 Nyquist conftest fixtures (tmp_data_paths, fake_venv, fake_nvidia_smi) + RED/skip scaffolds (test_gpu_probe, test_install_state_heavy, test_heavy_failfast, test_registry_heavy)
provides:
  - "paths.venvs_dir/hf_cache_dir/custom_voices_dir per-user resolvers (in ensure_dirs)"
  - "paths.uv_binary/heavy_worker bundled-package-resource resolvers (NOT per-user)"
  - "diana/tts/gpu_probe.py: torch-free capable_nvidia_gpu() + FISH_MIN_VRAM_GB (D-09/D-10)"
  - "install_state.heavy_engine_installed/heavy_footprint_bytes/uninstall_heavy_engine (filesystem only)"
  - "registry._HEAVY_ENGINES + heavy entries in _ASCII_ONLY_ENGINES + heavy_engine_failfast (D-16)"
  - "streamlit>=1.40 floor (unblocks st.audio_input, D-11) in pyproject.toml + requirements.txt"
  - "pyproject package-data globs staged for Phase 6 (data/bin/*, data/voices/*, tts/heavy_workers/*.py)"
  - "D-10 wording reconciliation in REQUIREMENTS HEAVY-03 + ROADMAP SC#3 (hidden -> shown-but-disabled)"
affects: [05-03-supply-chain-gate, 05-orpheus-slice, 05-f5-slice, 05-fish-slice, 05-custom-voices, 06-packaging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Torch-free GPU gate: shell nvidia-smi --query-gpu=memory.total, parse VRAM, never import torch on the badge path (Pitfall 4)"
    - "Heavy install-state = pure filesystem probe (venv python + .{engine}.installed marker); shared-torch venv (F5+Fish) under one folder (D-03)"
    - "Bundled-resource resolvers via importlib.resources.files(...).joinpath(...) cast to Path (uv binary + heavy worker scripts), distinct from per-user data_dir() resolvers"
    - "Registry heavy helpers stay lazy: _HEAVY_ENGINES set + ASCII map + fail-fast, with heavy engines deliberately absent from list_engines()/_get_engine_class until their own slices"

key-files:
  created:
    - diana/tts/gpu_probe.py
    - diana/data/bin/.gitkeep
    - .planning/phases/05-heavy-opt-in-engines/05-02-SUMMARY.md
  modified:
    - diana/paths.py
    - diana/tts/install_state.py
    - diana/tts/registry.py
    - pyproject.toml
    - requirements.txt
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md

key-decisions:
  - "uv_binary()/heavy_worker() resolve SHIPPED package resources (importlib.resources), NOT per-user dirs — bundled code/data, never created in ensure_dirs()"
  - "heavy_footprint_bytes sums only the per-engine venv tree (not the shared hf-cache) so the figure is the per-engine reclaimable size"
  - "uninstall_heavy_engine keeps the shared torch venv when the other of F5/Fish is still installed; marker-then-venv ordering; rmtree scoped to venvs_dir only (T-05-EXE)"
  - "Heavy engines NOT added to list_engines()/_get_engine_class in this plan (each joins in its own wave so all_engine_voices never imports a not-yet-built engine) — so test_registry_heavy's membership/ASCII assertions stay correctly skipped"

patterns-established:
  - "Cheap-path no-heavy-import contract extended to gpu_probe + heavy install-state + registry fail-fast, asserted by grep + sys.modules in tests"
  - "Per-OS venv python path: Scripts/python.exe (win) vs bin/python, via _is_win()"

requirements-completed: [HEAVY-01, HEAVY-02, HEAVY-03]

# Metrics
duration: ~35min
completed: 2026-06-15
---

# Phase 5 Plan 02: Heavy-Engine Cheap Foundation (paths, GPU gate, install-state, fail-fast) Summary

**The no-heavy-import substrate for all three heavy engines: per-user venv/HF-cache/custom-voice path resolvers + bundled-uv/worker resolvers, a torch-free nvidia-smi GPU gate (12 GB floor), filesystem-only heavy install-state/footprint/uninstall probes, registry fail-fast helpers, the streamlit>=1.40 bump, and the D-10 "shown-but-disabled" wording reconciliation — keeping the lightweight default install completely untouched.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-06-15T20:50Z (approx, pre-first-commit analysis included)
- **Completed:** 2026-06-15T21:01Z
- **Tasks:** 3
- **Files modified:** 9 (2 created source + 1 .gitkeep + 4 modified source/config + 2 planning docs)

## Accomplishments
- Torch-free Fish GPU gate (`gpu_probe.capable_nvidia_gpu` + `FISH_MIN_VRAM_GB = 12`) shelling `nvidia-smi` — never imports torch on the badge path (D-09/D-10); absent/insufficient GPU returns a shown-but-disabled reason string.
- Filesystem-only heavy install-state in `install_state.py`: `heavy_engine_installed` (venv python + `.{engine}.installed` marker), `heavy_footprint_bytes` (venv tree size), `uninstall_heavy_engine` (marker-then-venv, shared-torch-aware, scoped to `venvs_dir()`, returns freed bytes).
- Registry fail-fast: `_HEAVY_ENGINES`, the three heavy entries in `_ASCII_ONLY_ENGINES` (UTF-8 capable -> False), and `heavy_engine_failfast` returning an actionable "Settings ▸ Voices" message for an uninstalled heavy engine (D-16) — all lazy, no heavy SDK on the cheap path.
- Per-user path resolvers (`venvs_dir`/`hf_cache_dir`/`custom_voices_dir`, in `ensure_dirs()`) plus bundled-package-resource resolvers (`uv_binary`/`heavy_worker`, NOT in `ensure_dirs()`).
- `streamlit>=1.40` floor in both `pyproject.toml` and `requirements.txt` (unblocks `st.audio_input`, D-11), package-data globs staged for Phase 6, and the D-10 wording reconciled in REQUIREMENTS HEAVY-03 + ROADMAP SC#3.
- Three Wave-0 scaffolds flipped skip->PASS; full suite green (472 passed, 25 skipped, 0 failures).

## Task Commits

Each task was committed atomically:

1. **Task 1: per-user paths + bundled-uv/worker resolvers + streamlit bump + D-10 reconciliation** - `81bb044` (feat)
2. **Task 2: torch-free nvidia-smi GPU probe (D-09)** - `eaa9877` (feat)
3. **Task 3: filesystem-only heavy install-state probes + registry fail-fast helpers** - `6580420` (feat)

_Note: these `tdd="true"` tasks consumed the pre-written Wave-0 RED/skip scaffolds from 05-01 as their failing tests, then implemented to green — so each is a single `feat` commit (the RED scaffold already exists on disk), not a separate test->feat pair._

## Files Created/Modified
- `diana/tts/gpu_probe.py` - NEW. Torch-free `capable_nvidia_gpu()` + `FISH_MIN_VRAM_GB = 12`; shells `nvidia-smi`, parses `memory.total`, returns `(ok, vram_gb, reason)`.
- `diana/data/bin/.gitkeep` - NEW. Materializes the bundled-`uv` binary dir + its package-data glob (Phase 6 drops the real per-OS binary).
- `diana/paths.py` - Added `venvs_dir`/`hf_cache_dir`/`custom_voices_dir` (per-user, in `ensure_dirs()`) and `uv_binary`/`heavy_worker` (bundled package resources, not per-user); imported `sys` + `importlib.resources`.
- `diana/tts/install_state.py` - Added `_is_win`/`_heavy_venv_name`/`_heavy_venv_python`/`_dir_size_bytes`/`heavy_engine_installed`/`heavy_footprint_bytes`/`uninstall_heavy_engine`; imported `shutil`+`sys`. No heavy SDK import (ENGINE-01).
- `diana/tts/registry.py` - Added `_HEAVY_ENGINES`, the three heavy entries in `_ASCII_ONLY_ENGINES` (False), and `heavy_engine_failfast` (lazy `install_state` import). Did NOT touch `list_engines()`/`_get_engine_class` (per plan).
- `pyproject.toml` - `streamlit>=1.30.0` -> `>=1.40.0`; package-data extended with `data/bin/*`, `data/voices/*`, `tts/heavy_workers/*.py`.
- `requirements.txt` - `streamlit>=1.30.0` -> `>=1.40.0`.
- `.planning/REQUIREMENTS.md` - HEAVY-03 wording: "hidden unless a capable GPU is detected" -> "shown but disabled with a 'requires a capable GPU (~12+ GB VRAM)' reason when none is detected" (D-10).
- `.planning/ROADMAP.md` - SC#3 wording: same D-10 reconciliation. (Committed in the worktree as part of Task 1; the orchestrator owns final ROADMAP reconciliation on master after merge.)

## Decisions Made
- **Bundled resolvers vs per-user dirs:** `uv_binary()`/`heavy_worker()` resolve `importlib.resources.files("diana.data"|"diana.tts").joinpath(...)` cast to `Path` — they point under the installed package, are deliberately excluded from `ensure_dirs()`, and resolve fine even though `data/bin/` only holds `.gitkeep` and `tts/heavy_workers/` does not exist yet (later slices/Phase 6 populate them). Verified both resolve outside `data_dir()` and inside the `diana` package.
- **Per-engine footprint excludes shared HF cache:** `heavy_footprint_bytes` walks only the per-engine venv tree, so the figure is the per-engine reclaimable size (the multi-engine `hf-cache` is not double-counted).
- **Shared-torch uninstall guard:** `uninstall_heavy_engine` always removes the `.{engine}.installed` marker but only `rmtree`s the venv when no other engine that shares it still has a marker — so removing F5 while Fish remains keeps the `torch` venv (and vice-versa). Orpheus owns its venv alone. rmtree scoped to `venvs_dir()` subpaths only (T-05-EXE).
- **Heavy engines absent from `list_engines()`:** intentional per the plan — each engine joins `list_engines()`/`_get_engine_class` in its own wave so `all_engine_voices` never imports a not-yet-built engine. Consequence: `test_registry_heavy::test_heavy_engines_listed` and `::test_heavy_engines_are_utf8_capable` stay correctly skipped (their skipif keys off `"orpheus" in list_engines()`), while the UNGATED `test_cheap_enumeration_imports_no_heavy_sdk` passes.

## Deviations from Plan

None - plan executed exactly as written. The plan's `<action>` blocks supplied exact strings (resolver bodies, the Pattern-4 GPU probe shape, the install-state mapping, the fail-fast message, the wording edits), and the 05-01 conftest fixtures matched the implemented signatures with no adjustment.

## Issues Encountered
None. The `fake_nvidia_smi`/`fake_venv`/`tmp_data_paths` fixtures patch the stdlib `shutil.which`/`subprocess.run` and `paths.*` resolvers exactly as the implementation references them (`import shutil`/`import subprocess` module-level access, `paths.venvs_dir()` indirection), so all three scaffolds went green on first run.

## User Setup Required
None - no external service configuration required. (The `streamlit>=1.40` bump is a dependency-floor change; the running `.venv` already satisfies it — full suite green.)

## Next Phase Readiness
- **Ready for the supply-chain gate (05-03)** and the per-engine vertical slices: the cheap substrate (paths, GPU gate, install-state, fail-fast, ASCII map) is in place and green.
- **Engine slices must:** add their engine to `registry.list_engines()` + `_get_engine_class` + `create_engine` + `get_engine_voices`, create `diana/tts/heavy_workers/<engine>_worker.py` (resolved by `paths.heavy_worker(...)`), and build their install via the bundled `uv` (`paths.uv_binary()`). When orpheus joins `list_engines()`, the two currently-skipped `test_registry_heavy` membership/ASCII tests flip green with zero edits (the ASCII map entries are already present).
- **Phase 6 packaging:** must drop the real per-OS `uv` binary into `diana/data/bin/` and ship `tts/heavy_workers/*.py` + `data/voices/*` — the package-data globs are already declared.
- **No blockers.**

## Self-Check: PASSED

- Created files verified on disk: `diana/tts/gpu_probe.py`, `diana/data/bin/.gitkeep`, `05-02-SUMMARY.md`.
- Modified files verified on disk: `diana/paths.py`, `diana/tts/install_state.py`, `diana/tts/registry.py`, `pyproject.toml`, `requirements.txt`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`.
- Task commits verified in git: `81bb044`, `eaa9877`, `6580420`.
- Full suite: 472 passed, 25 skipped, 0 failures.

---
*Phase: 05-heavy-opt-in-engines*
*Completed: 2026-06-15*
