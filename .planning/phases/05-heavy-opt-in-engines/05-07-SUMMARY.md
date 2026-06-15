---
phase: 05-heavy-opt-in-engines
plan: 07
subsystem: tts
tags: [fish-speech, fish-s2-pro, gpu-gate, nvidia-smi, torch, voice-cloning, heavy-engine, streamlit, apptest, cc-by-nc-sa]

# Dependency graph
requires:
  - phase: 05-heavy-opt-in-engines (05-02)
    provides: gpu_probe.capable_nvidia_gpu (torch-free nvidia-smi gate), install_state.heavy_engine_installed, FISH_MIN_VRAM_GB=12
  - phase: 05-heavy-opt-in-engines (05-03)
    provides: heavy_install.HeavyInstallSpec + _BUILTIN_SPECS["fish"] (git+SHA pin), install_engine, license_accepted/accept_license
  - phase: 05-heavy-opt-in-engines (05-05)
    provides: f5_engine (the sibling cloned for Fish), the Settings _render_heavy_engine_row + _render_heavy_license_gate, the bundled f5_default.{wav,txt} clip
  - phase: 05-heavy-opt-in-engines (05-06)
    provides: custom_voices (engine-agnostic list_custom_voices / custom_voice_ref) reused by Fish
provides:
  - "FishEngine — GPU+install-gated TTSEngine, out-of-process synth in the shared torch venv, reusing the engine-agnostic Custom Voices + bundled default (HEAVY-03, completes the three-engine lineup D-01)"
  - "fish_worker.py — venv-run zero-shot clone worker (stdin JSON ref/gen -> WAV) + --prefetch (MEDIUM-confidence fish-speech signature, confirm at real install)"
  - "Settings Fish row — shown-but-disabled-with-reason without a capable GPU (D-10), behind the GPU gate the accept-once NC-license + footprint + install (D-08)"
  - "Upload Fish readiness badge surfacing the GPU-gate reason; registry 'fish' routing; cross-engine badge fish branch"
affects: [packaging, pyinstaller, ci-matrix]

# Tech tracking
tech-stack:
  added: ["fish-speech @ git+SHA (venv-only, NOT in app interpreter)"]
  patterns:
    - "Shown-but-disabled-with-reason GPU gate (D-10): caller passes the torch-free capable_nvidia_gpu() result into the generic heavy-engine row; the row is shown with a DISABLED Install + reason, never hidden"
    - "Defence-in-depth GPU gate: both FishEngine.initialize() AND the Settings row gate on capable_nvidia_gpu() (T-05-GPU)"
    - "Engine cloned from a sibling (F5) with a single behavioral delta (the GPU gate) — third use of the heavy-engine subprocess pattern"

key-files:
  created:
    - diana/tts/fish_engine.py
    - diana/tts/heavy_workers/fish_worker.py
    - tests/test_fish_slice_apptest.py
  modified:
    - diana/tts/registry.py
    - diana/dashboard/pages/1_Upload.py
    - diana/dashboard/pages/5_Settings.py
    - .planning/phases/05-heavy-opt-in-engines/05-HUMAN-UAT.md

key-decisions:
  - "Fish reuses F5's bundled f5_default clip as its zero-shot default (A6/D-15) — both are zero-shot clones, so the same license-clean on-device reference works for either engine; no second bundled clip added"
  - "fish_install_spec() returns a FRESH HeavyInstallSpec built from the single code-pinned _BUILTIN_SPECS['fish'] (git+SHA) with prefetch_argv overridden to the bundled worker — one source of truth for the pin, and never mutates the shared module-level built-in"
  - "Default to the shared torch venv (D-03/Q-B); the dedicated-fish-venv fallback is documented in fish_install_spec + 05-HUMAN-UAT.md and only decided at real-install time (deferred)"
  - "An ALREADY-installed Fish engine is never disabled by the GPU gate (it keeps Ready + uninstall) so a user who installed on a capable box can still reclaim space after moving the install"

patterns-established:
  - "Shown-but-disabled-with-reason: gpu_gate=(ok,vram,reason) passed into _render_heavy_engine_row; not-ok+not-installed -> title + disabled Install + reason caption, no license/footprint/Install below (D-10)"
  - "Live-path AppTest pre-check: the no-capable-GPU path is the REAL state of the verifying box, so the shown-disabled behavior is asserted on the LIVE gate (not a mock); GPU-ok is monkeypatched to exercise the license path"

requirements-completed: [HEAVY-03]

# Metrics
duration: 10min
completed: 2026-06-15
---

# Phase 05 Plan 07: Fish Audio S2 Pro (GPU-gated, NC-license) Summary

**FishEngine completes the three-engine lineup (D-01): a GPU-gated, NC-licensed zero-shot clone engine that is shown-but-disabled-with-reason without a capable NVIDIA GPU (D-10), runs out-of-process in the shared torch venv, and reuses the engine-agnostic Custom Voices + bundled default.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-15T22:00:42Z
- **Completed:** 2026-06-15T22:10:29Z
- **Tasks:** 3 (2 implementation + 1 human-verify checkpoint, agent pre-check passed + GPU UAT deferred)
- **Files modified:** 7 (3 created, 4 modified)

## Accomplishments
- **FishEngine** (`diana/tts/fish_engine.py`) — cloned from `F5Engine` with the GPU-gate delta: `initialize()` refuses unless BOTH `heavy_engine_installed("fish")` AND `capable_nvidia_gpu()` is ok (D-10/D-16 defence-in-depth); `list_voices()` = bundled default + engine-agnostic custom voices; `synthesize()` shells the fish worker in the shared torch venv with text as stdin JSON DATA (T-05-CMD). No torch/fish_speech on the cheap path (ENGINE-01/D-17).
- **fish_worker.py** — `--prefetch` (warm the `fishaudio/s2-pro` weights) + a zero-shot clone synth reading `ref_file`/`ref_text`/`gen_text` from stdin JSON; the fish-speech inference call mirrors the F5 worker's clone contract (MEDIUM-confidence signature, flagged to confirm at real install — see Deviations).
- **Settings Fish row** — shown-but-disabled-with-reason on a GPU-less machine (D-10, never hidden); behind the GPU gate the accept-once Fish Audio Research License / CC-BY-NC-SA-4.0 disclosure + footprint confirm + install (D-08), spec from `fish_install_spec()` (git+SHA, no hardcoded repo in the page); `_cross_engine_badge` fish branch.
- **Upload + registry** — `_engine_readiness` fish branch surfaces the GPU-gate reason then install state; `fish` routes across `_get_engine_class`/`create_engine`/`get_engine_voices` (+ `_fish_voices`), import-light.
- **Verification** — `tests/test_fish_engine.py` flipped skip→PASS; new `tests/test_fish_slice_apptest.py` (5 PASS) exercises the LIVE no-GPU shown-disabled path + the GPU-ok license path; full suite **512 passed, 0 failures**.

## Task Commits

Each task was committed atomically:

1. **Task 1: FishEngine + worker (GPU+install gated) + registry/Upload wiring** — `97adb4a` (feat) — TDD GREEN gate: flipped `tests/test_fish_engine.py` skip→PASS
2. **Task 2: Settings Fish install row — shown-but-disabled GPU gate (D-10) + NC-license gate (D-08)** — `c82a7f3` (feat)
3. **Task 3: human-verify the Fish slice — AppTest pre-check + defer GPU UAT** — `a03e59b` (test)

_Plan-level type is `tdd`: the RED gate is the pre-existing Wave-0 scaffold `tests/test_fish_engine.py` (the 2 Fish tests `skipif`-gated on `FishEngine` existing); Task 1 supplied GREEN (skip→PASS). See TDD Gate Compliance below._

## Files Created/Modified
- `diana/tts/fish_engine.py` (created) — FishEngine (GPU+install gated, subprocess synth in the torch venv) + `fish_install_spec()`
- `diana/tts/heavy_workers/fish_worker.py` (created) — venv-run zero-shot clone worker + `--prefetch`; no `heavy_workers/__init__.py`
- `tests/test_fish_slice_apptest.py` (created) — 5 AppTest pre-checks (live shown-disabled + GPU-ok license path)
- `diana/tts/registry.py` (modified) — `fish` across `_get_engine_class`/`create_engine`/`get_engine_voices` + `_fish_voices`
- `diana/dashboard/pages/1_Upload.py` (modified) — `_engine_readiness` fish branch surfacing the GPU-gate reason
- `diana/dashboard/pages/5_Settings.py` (modified) — `gpu_gate` param + shown-but-disabled branch on `_render_heavy_engine_row`; Fish row invocation (license + GPU gate); `_cross_engine_badge` fish branch
- `.planning/phases/05-heavy-opt-in-engines/05-HUMAN-UAT.md` (modified) — APPENDED a HEAVY-03 section (other sections preserved)

## Decisions Made
- **Reuse F5's bundled clip as Fish's default (A6/D-15):** both engines are zero-shot clones, so the same self-generated, license-clean `f5_default.{wav,txt}` reference works for Fish — no second bundled clip.
- **One source of truth for the git+SHA pin:** `fish_install_spec()` builds a fresh `HeavyInstallSpec` from `heavy_install._BUILTIN_SPECS["fish"]` (overriding only `prefetch_argv` to the bundled worker), so the pinned commit lives in exactly one place and the page hardcodes no repo ID/SHA.
- **Shared torch venv by default (D-03/Q-B):** the dedicated-fish-venv fallback (if torch builds conflict at real install) is documented in code + the UAT and only decided on a CUDA machine.
- **Installed engine is never GPU-disabled:** the shown-but-disabled branch only fires when `not installed`, so an engine installed on a capable box keeps its Ready + uninstall controls.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] fish-speech inference signature is MEDIUM-confidence — implemented by mirroring the F5 worker, flagged for real-install confirmation**
- **Found during:** Task 1 (fish_worker.py)
- **Issue:** Unlike F5 (whose `F5TTS().infer(...)` signature is VERIFIED in RESEARCH), fish-speech has NO PyPI package and a fast-moving repo HEAD, so the exact inference call could not be pinned at plan time (RESEARCH Q-D/A6 explicitly MEDIUM-confidence). A real CUDA install to verify is impossible on this macOS box (no NVIDIA GPU).
- **Fix:** Implemented `_synthesize()` against fish-speech's documented `load_model` + `TTSInferenceEngine` / `ServeTTSRequest` shape, mirrored onto the F5 worker's zero-shot clone contract (`ref_file`/`ref_text`/`gen_text` -> WAV). The engine↔worker JSON contract is fixed and unit-tested (subprocess mocked); ONLY the in-venv fish-speech call is unverified. A prominent ⚠️ docstring + a UAT step (05-HUMAN-UAT.md HEAVY-03 step 3) direct the human to confirm/adjust that single function against the pinned commit `e5e2926…` at real install.
- **Files modified:** diana/tts/heavy_workers/fish_worker.py
- **Verification:** `tests/test_fish_engine.py` (subprocess mocked) passes; the cheap-path `sys.modules` assertion confirms no fish_speech import reaches the app interpreter. Real synth deferred to the CUDA-machine UAT.
- **Committed in:** `97adb4a` (Task 1 commit)

---

**Total deviations:** 1 (1 blocking, resolved within scope and flagged for deferred real-install confirmation)
**Impact on plan:** No scope creep. The deviation is the planned-for MEDIUM-confidence signature; the engine/JSON contract is fully tested and the unverified in-venv call is isolated to one function with a confirm step in the UAT. The worker is package-data run by the venv python — it never imports into the app interpreter, so the unverified import cannot affect the cheap path.

## Known Stubs
None that block the plan goal. The `fish_worker.py` inference call is real (not a placeholder) but MEDIUM-confidence against fish-speech HEAD — it is documented above and in 05-HUMAN-UAT.md HEAVY-03 step 3 to be confirmed at real install on a CUDA machine. This is intentional and unavoidable (no NVIDIA GPU on the verifying box); it does not stub the shipped cheap-path behavior (GPU gate, license, badges, fail-fast), all of which are live and verified.

## Threat Flags
None — no new security surface beyond the plan's `<threat_model>`. The Fish install reuses the existing `heavy_install` provisioner (pinned git+SHA + license + footprint + GPU gates, T-05-SC/LIC/GPU), the subprocess uses list-argv stdin-JSON (T-05-CMD), and the worker path comes from `paths.heavy_worker` not PATH (T-05-EXE). All dispositions in the register are mitigated as planned.

## TDD Gate Compliance
Plan `type` is `execute` with Task 1 `tdd="true"`. The RED gate is the pre-existing Wave-0 scaffold `tests/test_fish_engine.py` — the 2 Fish tests are `skipif`-gated on `FishEngine` being importable (the canonical RED-as-skip for a not-yet-built module). Task 1 supplied the GREEN gate: creating `fish_engine.py` flipped both tests skip→PASS (`feat` commit `97adb4a`). No standalone `test(...)` commit was authored this plan because the failing/skipped test already existed from Wave 0 (the intended RED state); this is the established convention for the Wave-0-scaffolded heavy engines (matching 05-04 Orpheus and 05-05 F5). No unexpected pass during RED (the tests were skipped, not passing). No separate refactor commit was needed.

## Issues Encountered
- AppTest GPU-gate determinism: the Settings/Upload pages call `gpu_probe.capable_nvidia_gpu()` as module-attribute access, so the live no-GPU path is exercised as-is and the GPU-ok path is monkeypatched at the `diana.tts.gpu_probe` source — both worked first run, no flakiness.
- Worktree path discipline: all edits and the absolute venv python (`/Users/tyler/Repos/diana/.venv/bin/python`) were used per the worktree constraint; no relative `.venv` was invoked.

## User Setup Required
None required to ship the cheap-path behavior. The optional Fish install (on an NVIDIA ≥12 GB GPU machine only) downloads the `fishaudio/s2-pro` weights from a public Hugging Face repo behind the in-UI accept-once non-commercial license — no env vars, no terminal. See the HEAVY-03 section of `05-HUMAN-UAT.md` for the deferred real-GPU install + by-ear synthesis steps.

## Next Phase Readiness
- The three-engine lineup is COMPLETE (D-01): Orpheus (CPU), F5 (torch), Fish (torch + GPU gate) all register, badge/gate cheaply, fail-fast on the Upload path, and surface in the cross-engine browser — with no torch on the cheap path.
- Deferred (carried, NOT a defect): the real Fish install + by-ear synthesis needs an NVIDIA ≥12 GB GPU machine (documented in 05-HUMAN-UAT.md HEAVY-03), where the MEDIUM-confidence fish-speech inference signature must be confirmed.
- The reconciled HEAVY-03/SC#3 "shown but disabled" wording is present in REQUIREMENTS.md + ROADMAP.md and matches the implemented + verified behavior.

## Self-Check: PASSED
- Created files exist: `diana/tts/fish_engine.py`, `diana/tts/heavy_workers/fish_worker.py`, `tests/test_fish_slice_apptest.py`, `.planning/phases/05-heavy-opt-in-engines/05-07-SUMMARY.md`
- Task commits exist: `97adb4a`, `c82a7f3`, `a03e59b`
- Full suite: 512 passed, 0 failures (via the absolute `/Users/tyler/Repos/diana/.venv/bin/python`)
- No torch/fish_speech on the cheap path (grep + `sys.modules` assertion); `fish_worker.py` has no `__init__.py`
- 05-HUMAN-UAT.md retains all 4 sections (Orpheus + 2 F5/Custom + appended Fish HEAVY-03)

---
*Phase: 05-heavy-opt-in-engines*
*Completed: 2026-06-15*
