---
phase: quick-260616-hk6
plan: 01
subsystem: tts
tags: [fish, gpu-gate, apple-silicon, mps, tri-state, heavy-engines]
requires:
  - "diana/tts/gpu_probe.py (capable_nvidia_gpu, FISH_MIN_VRAM_GB — preserved)"
provides:
  - "gpu_probe.fish_capability() tri-state resolver {cuda, apple, none} + APPLE_MIN_UNIFIED_GB"
  - "fish_worker cuda->mps->cpu device selection (+PYTORCH_ENABLE_MPS_FALLBACK)"
  - "fish_engine hardware gate allowing cuda + apple tiers"
  - "tri-state Fish row in Settings + Upload readiness note"
affects:
  - "diana/dashboard/pages/5_Settings.py (3 Fish sites)"
  - "diana/dashboard/pages/1_Upload.py (_engine_readiness fish branch)"
tech-stack:
  added: []
  patterns:
    - "Tri-state capability resolver shelling sysctl + nvidia-smi (torch-free, stdlib-only)"
    - "Adapter: tier -> (ok, vram, reason) gpu_gate so the existing row stays binary-shaped"
key-files:
  created: []
  modified:
    - diana/tts/gpu_probe.py
    - diana/tts/heavy_workers/fish_worker.py
    - diana/tts/fish_engine.py
    - diana/dashboard/pages/5_Settings.py
    - diana/dashboard/pages/1_Upload.py
    - tests/test_gpu_probe.py
    - tests/test_fish_engine.py
    - tests/test_fish_slice_apptest.py
    - .planning/phases/05-heavy-opt-in-engines/05-HUMAN-UAT.md
decisions:
  - "D-09 corrected: fish-speech has native MPS support (PR #461), so the flat NVIDIA-only gate was false; Apple Silicon is now offered EXPERIMENTAL, never first-class"
  - "Apple unified-memory floor APPLE_MIN_UNIFIED_GB = 16, read torch-free via `sysctl -n hw.memsize`"
  - "Tier adapted into the existing (ok, vram, reason) gpu_gate (cuda/apple -> ok=True, none -> ok=False) so _render_heavy_engine_row stays binary; a new experimental= caption param carries the Apple-Silicon warning"
metrics:
  duration: "~25 min"
  completed: 2026-06-16
  tasks: 3
  files: 9
  commits: 3
  tests: "520 passed, 0 failures"
---

# Quick 260616-hk6: Enable Fish on Apple Silicon as Experimental (Tri-State GPU Gate) Summary

Replaced Fish's NVIDIA-only hardware gate with a torch-free tri-state `fish_capability()`
resolver ({cuda, apple, none}), enabling Fish Audio S2 Pro as an EXPERIMENTAL Metal/MPS
engine on capable Apple Silicon (arm64 macOS, ≥16 GB unified) while keeping NVIDIA (≥12 GB
VRAM) as the full-support path and showing an honest dual reason on every other host.

## What Was Built

**Task 1 — `fish_capability()` tri-state + worker device selection** (`eed0858`)
- `diana/tts/gpu_probe.py`: added `fish_capability() -> (tier, label, reason)` resolving
  `cuda -> apple -> none` torch-free. `capable_nvidia_gpu()` is the unchanged "cuda" probe
  (its absent-GPU literal reworded to `"no NVIDIA GPU detected"`). New private
  `_apple_unified_gb()` shells `sysctl -n hw.memsize` (fixed argv, `shell=False`, short
  timeout, integer-only parse, returns 0 on any failure). New constant
  `APPLE_MIN_UNIFIED_GB = 16`. Module docstring rewritten for the tri-state.
- `diana/tts/heavy_workers/fish_worker.py`: `_synthesize()` now selects
  `cuda` → `mps` (+`os.environ["PYTORCH_ENABLE_MPS_FALLBACK"]="1"` before model load) →
  `cpu`. (This file runs inside the torch venv — torch import allowed here.)
- `tests/test_gpu_probe.py`: added tri-state coverage (cuda/apple/none) with
  `assert "torch" not in sys.modules` on every `fish_capability()` branch.

**Task 2 — broaden the engine hardware gate** (`97d6b59`)
- `diana/tts/fish_engine.py`: `initialize()` now consumes `gpu_probe.fish_capability()` and
  allows `tier in {"cuda", "apple"}`; tier `"none"` raises the honest reason. Install gate
  (`FileNotFoundError`) and accept-once NC-license gate untouched; `gpu_probe` still imported
  lazily (cheap path torch-free).
- `tests/test_fish_engine.py`: `_force_gpu` replaced by `_force_fish_capability`; asserts
  installed+cuda and installed+apple do NOT raise, installed+none and not-installed DO raise.

**Task 3 — tri-state UI + apptest + UAT** (`11eb577`)
- `diana/dashboard/pages/5_Settings.py`: all three Fish sites use `fish_capability()`. The
  call site adapts the tier into the `(ok, vram, reason)` gpu_gate the row already consumes
  (cuda/apple → ok=True, none → ok=False+reason) and passes a new `experimental=` caption for
  tier "apple". `_render_heavy_engine_row` gained `experimental: str | None = None`, rendered
  as a `⚠️` caption on the enabled row. `_get_engine_badge` is tri-state.
- `diana/dashboard/pages/1_Upload.py`: `_engine_readiness` fish branch is tri-state (none →
  honest dual reason; apple → experimental MPS install/ready note; cuda → unchanged).
- `tests/test_fish_slice_apptest.py`: pinned-tier helpers (`_tier_none`/`_tier_apple`/
  `_tier_cuda`) patching `fish_capability()`. The shown-but-disabled and Upload tests pin
  tier "none" (the live box is now "apple"); ADDED a tier-"apple" SHOWN+ENABLED-experimental
  test; the license/Install flow tests pinned to tier "cuda". No-torch assertions intact.
- `.planning/phases/05-heavy-opt-in-engines/05-HUMAN-UAT.md`: HEAVY-03 reframed — the
  experimental Apple-Silicon MPS install + by-ear synthesis is now testable on this M5 Pro
  (tier "apple"); NVIDIA remains the full-support path; the MEDIUM-confidence fish-speech
  inference-signature caveat is preserved verbatim in intent.

## Verification

- Targeted: `test_gpu_probe.py`, `test_fish_engine.py`, `test_fish_slice_apptest.py` all pass.
- Full suite: `/Users/tyler/Repos/diana/.venv/bin/python -m pytest tests/ -q` →
  **520 passed, 0 failures** (1 deselected — pre-existing marker config, unrelated).
- LIVE on this M5 Pro (48 GB unified): `fish_capability()[0] == "apple"`, torch-free.
- `grep -rn "~12+ GB VRAM (none detected)" diana/` → nothing (false literal retired).
- `grep -c capable_nvidia_gpu` in fish_engine / 5_Settings / 1_Upload → all 0;
  `fish_capability` present in each; `capable_nvidia_gpu` still defined + called only inside
  `gpu_probe.fish_capability()`.
- No-torch discipline (ENGINE-01) holds on every `fish_capability` branch and every apptest
  path.

## Deviations from Plan

None — the plan executed exactly as written. The three TDD tasks followed RED (new
`fish_capability`/tier coverage failing/skipping) → GREEN (implementation) → verified; Task 3
(non-TDD) updated the UI + tests + UAT together and the full suite stayed green.

## Threat Surface

No new packages installed (T-hk6-SC: only device-selection + gate logic edited). The new
`sysctl -n hw.memsize` parse (T-hk6-01) uses the same defensive lane as the existing
`nvidia-smi` parse (fixed argv, `shell=False`, integer-only, defensive try/except → 0). The
cheap path stays torch-free (T-hk6-02). No new security surface beyond the threat register.

## Self-Check: PASSED

All 9 modified files exist on disk; all 3 commits (`eed0858`, `97d6b59`, `11eb577`) are in
the worktree branch history.
