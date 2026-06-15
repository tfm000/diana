---
phase: 04-engine-management-voice-catalog
plan: 06
subsystem: tts
tags: [streamlit, uninstall, partial-cleanup, kokoro, onnx, download, pagination, dataframe, voice-catalog]

# Dependency graph
requires:
  - phase: 04-engine-management-voice-catalog (04-02)
    provides: "generic download substrate (download_file/.part/md5/atomic, has_space disk-check, clean_partials bulk *.part sweep) + cheap install_state filesystem probes"
  - phase: 04-engine-management-voice-catalog (04-03)
    provides: "Settings ▸ Voices hub, dl_state/threading.Thread/@st.fragment byte-progress machinery, cancel→cancelled→resume terminal-state pattern, shared voice_cache.py"
  - phase: 04-engine-management-voice-catalog (04-05)
    provides: "all_engine_voices cross-engine aggregation + voice_labels override layer + per-voice label editor (reused by the new paginated table's select-to-edit panel)"
  - phase: 03-native-os-tts-new-default (03-04)
    provides: "filter_voices/order_by_quality pure helpers (reused VERBATIM over the full merged dataset before pagination)"
provides:
  - "VOICE-07 uninstall: per-Piper-voice Uninstall (confirm + freed-space shown + in-use block) — D-16/D-17"
  - "Partial-download cleanup: per-item 'Remove partial' (.part unlink + dl_state reset) + bulk 'Clean up partial downloads' (clean_partials over model_dir) — D-18"
  - "In-UI Kokoro single-model download through the SAME generic layer (disk-check + resumable + md5 + atomic install) with a >200MB footprint confirm for the f32 asset, replacing the wget hint — D-19/D-04"
  - "install_state.voice_in_use (non-terminal-job + per-engine-default in-use predicate) + install_state.uninstall_piper_voice (model_dir-scoped .onnx/.onnx.json unlink, returns freed bytes)"
  - "kokoro_engine KOKORO_ASSETS exposure (int8/fp16/f32 URLs+filenames+sizes) + in-app download pointer replacing the terminal wget instruction"
  - "Paginated read-only cross-engine voice st.dataframe (Engine/ID/Name/Language/Tier/Gender/Tags) with full-dataset filtering then 25/50/100 page slicing + select-to-edit panel — usability replacement for the unusable ~184-row 04-05 list"
affects: [phase-05-heavy-opt-in-engines, phase-06-packaging-first-class-windows]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "In-use-block predicate over non-terminal jobs + per-engine default key before any destructive delete (D-17); pure-helper-over-lazy-DB-wrapper shape (lazy `from diana.database import get_setting, list_jobs` inside the function), matching registry.resolve_default_voice"
    - "model_dir-scoped unlink(missing_ok=True) returning freed bytes for a confirm-then-delete UX (T-04-FILE never deletes outside the cache)"
    - "Engine-level single-model download row (Kokoro: one model, many baked-in voices — NOT per-voice rows) reusing the Plan-03 dl_state/thread/fragment machinery verbatim, proving the substrate is engine-generic (D-19) before Phase 5 reuses it"
    - "Pure paginate(items, page, page_size) over the FILTERED full dataset (filters applied first, then sliced); filter/page-size change resets to page 1; read-only st.dataframe with a separate select-to-edit panel"

key-files:
  created: []
  modified:
    - diana/tts/install_state.py
    - diana/tts/kokoro_engine.py
    - diana/dashboard/pages/5_Settings.py

key-decisions:
  - "D-16: per-Piper-voice Uninstall shows freed space and requires an explicit confirm before uninstall_piper_voice unlinks the .onnx(+.onnx.json) and flips the badge back to not-installed"
  - "D-17: voice_in_use blocks uninstall while the voice id is any NON-TERMINAL job's tts_voice OR the stored tts.default_voice.<engine> — UI refuses with 'switch first'; Phase-3 resolve_default_voice remains the selection-time backstop"
  - "D-18: per-item 'Remove partial' unlinks one orphaned .part + clears its dl_state record; bulk 'Clean up partial downloads' calls clean_partials(paths.model_dir()) and reports the count"
  - "D-19: Kokoro model downloads on demand via the SAME generic download_file layer (disk-check + resumable + md5 + atomic install), replacing the wget-hint FileNotFoundError; KOKORO_ASSETS lives in kokoro_engine.py so the page does not hardcode URLs"
  - "D-04: the f32 Kokoro asset (~310 MB) crosses the >200 MB threshold and shows an explicit footprint confirm; the default int8 asset (~88 MB) and small Piper voices stay one-click"
  - "native_os exposes browse/preview/label only — no download/uninstall control (OS-owned)"
  - "Checkpoint deviation 1: per-item 'Remove partial' re-gated on action not in ('downloading','cancelling') so a cancelled/resumable row offers BOTH Resume and Remove partial"
  - "Checkpoint deviation 2 (user-requested at the checkpoint): replaced the unusable ~184-row cross-engine 'Browse all voices' list (a 04-05 deliverable) with a paginated read-only st.dataframe + select-to-edit panel — usability enhancement to 04-05's cross-engine browser"

patterns-established:
  - "In-use-block before destructive delete: read non-terminal jobs + the per-engine default key, return a human reason string when blocked, None when free"
  - "Engine-generic single-model download: reuse the Plan-03 dl_state/thread/fragment machinery for a non-per-voice engine model with a D-04 footprint confirm on the large asset"
  - "Filter-then-paginate: apply filters/search to the full merged dataset, then slice into fixed page sizes (reset to page 1 on filter/page-size change); read-only table + select-to-edit reuses the 04-05 label editor"

requirements-completed: [ENGINE-02, VOICE-07]

# Metrics
duration: ~10min impl (wall spanning blocking human-verify)
completed: 2026-06-15
---

# Phase 4 Plan 6: Uninstall + Partial Cleanup + In-UI Kokoro Download Summary

**VOICE-07 in-app Piper uninstall (confirm + freed space + in-use block) and per-item/bulk partial-download cleanup, plus the Kokoro single-model download routed through the SAME generic disk-check/resumable/md5/atomic substrate (D-19) — proving the layer is engine-generic — with a paginated read-only cross-engine voice table replacing the unusable ~184-row 04-05 list.**

## Performance

- **Duration:** ~10 min implementation (wall time spanning the blocking human-verify checkpoint)
- **Completed:** 2026-06-15
- **Tasks:** 3 (2 auto + 1 blocking human-verify checkpoint; checkpoint APPROVED)
- **Files modified:** 3 source + 4 test = 7 effective files (plan named 3 source: install_state.py + kokoro_engine.py + 5_Settings.py; +4 test files are the new/flipped coverage, not scope creep)

## Accomplishments

- **Uninstall (D-16/D-17):** per-installed-Piper-voice Uninstall control that first calls `voice_in_use(db, "piper", voice_id)` and REFUSES with an explanation when the voice is in use as a non-terminal job's choice or a per-engine default; otherwise a confirmation step shows the freed space, and on confirm `uninstall_piper_voice` unlinks the `.onnx`(+`.onnx.json`) within `model_dir` and flips the badge back to not-installed.
- **Partial cleanup (D-18):** per-item "Remove partial" (unlink one orphaned `.part`, clear its dl_state record, reset to Install) + a bulk "Clean up partial downloads" button calling `clean_partials(paths.model_dir())` and reporting the count removed.
- **In-UI Kokoro download (D-19/D-04):** an engine-level Kokoro model row (single model, many baked-in voices — NOT per-voice rows) showing `kokoro_model_installed()` state + footprint. Download Model runs the SAME generic flow as Piper — `has_space` pre-check → threaded `download_file` (Plan-03 dl_state + `@st.fragment` progress) → md5 atomic install — with an explicit footprint confirm for the >200 MB f32 asset (default int8 ~88 MB). The terminal `wget` hint is gone; `KOKORO_ASSETS` exposes the URLs/filenames/sizes so the page hardcodes nothing.
- **Paginated cross-engine table (checkpoint deviation 2):** replaced the unusable ~184-row "Browse all voices" list (a 04-05 deliverable) with a paginated read-only `st.dataframe` (Engine/ID/Name/Language/Tier/Gender/Tags); filters apply to the FULL merged dataset then slice into 25/50/100 pages (filter/page-size change resets to page 1), plus a select-to-edit panel reusing the 04-05 label editor.
- **native_os:** correctly shows browse/preview/label only — no download or uninstall control (OS-owned), human-verified.

## Task Commits

Each task was committed atomically (TDD task 1 flips the Plan-01 `test_uninstall.py` scaffold to GREEN — its RED lives in the Wave-0 git history):

1. **Task 1: in-use-block + uninstall helpers; expose Kokoro assets** — `f6f3dff` (feat) — `install_state.voice_in_use`/`uninstall_piper_voice` in the cheap-probe lane (lazy DB import) + `kokoro_engine` KOKORO_ASSETS exposure + in-app download pointer replacing the wget hint; flipped the Wave-0 uninstall scaffold live.
2. **Task 2: Uninstall + partial-cleanup + Kokoro download UI** — `7b58c31` (feat) — Voices-tab per-voice Uninstall (confirm + freed space + in-use block, D-16/D-17), per-item "Remove partial" + bulk "Clean up partial downloads" (D-18), engine-level Kokoro download row reusing the Plan-03 dl_state/`st.fragment`/Cancel/Resume machinery with a >200MB footprint confirm for f32 (D-19/D-04); + new `tests/test_uninstall_apptest.py` interaction checks.
3. **Checkpoint deviation 1 (fix):** `bf53757` (fix) — per-item "Remove partial" was unreachable after Cancel (gated on `not active`, but a cancelled record made `action=="resume"`→`active==True`). Re-gated on `action not in ("downloading","cancelling")` so a cancelled/resumable row offers BOTH Resume and Remove partial; Remove partial unlinks the `.part`, clears the dl_state record, resets to Install. Extended AppTest.
4. **Checkpoint deviation 2 (usability fix, user-requested):** `96e6464` (feat) — replaced the unusable ~184-row cross-engine "Browse all voices" list with a PAGINATED READ-ONLY `st.dataframe` table + select-to-edit panel (reusing the 04-05 label editor). New pure `paginate()` helper + `tests/test_settings_pagination.py` (8) + `tests/test_cross_engine_browser_apptest.py` (9).

**Plan metadata:** committed with this SUMMARY (docs: complete plan).

_Task 3 was the blocking human-verify checkpoint — no new code; it gated on the Streamlit-UX + real-network behaviors. APPROVED._

## Files Created/Modified

**Source (3, matches plan files_modified):**
- `diana/tts/install_state.py` — added `voice_in_use(db_path, engine, voice_id) -> str | None` (blocks on a non-terminal job's `tts_voice` or the `tts.default_voice.<engine>` key; lazy `from diana.database import get_setting, list_jobs`) and `uninstall_piper_voice(voice_id) -> int` (unlinks `{id}.onnx`(+`.onnx.json`) within `paths.model_dir()` via `unlink(missing_ok=True)`, returns freed bytes). Still imports no heavy SDK.
- `diana/tts/kokoro_engine.py` — exposed `KOKORO_ASSETS` (int8 `~88 MB` / fp16 `~169 MB` / f32 `~310 MB` `.onnx` URLs + filenames + approx sizes; `voices-v1.0.bin`) so the UI builds the download without hardcoding URLs; the `FileNotFoundError` text now points to in-app Settings ▸ Voices instead of a terminal `wget` (still raises if the model is genuinely absent — the UI downloads before synth). Synth path otherwise untouched.
- `diana/dashboard/pages/5_Settings.py` — Voices tab: per-voice Uninstall (in-use block + confirm + freed space), per-item Remove partial + bulk Clean up partial downloads, Kokoro engine-level download row (footprint confirm + threaded byte progress), and the paginated read-only cross-engine table + `paginate()` helper + select-to-edit panel.

**Tests (4 — new/flipped coverage):**
- `tests/test_uninstall.py` — the Plan-01 scaffold flipped skip→GREEN (in-use block both arms, delete the pair, bulk `clean_partials`).
- `tests/test_uninstall_apptest.py` (NEW, 10 tests) — AppTest interaction checks for uninstall block/confirm/freed-space, per-item Remove partial reachability after Cancel, bulk cleanup, and the Kokoro download row.
- `tests/test_settings_pagination.py` (NEW, 8 tests) — the pure `paginate()` helper (slicing, page bounds, page-size change, filter-reset-to-page-1).
- `tests/test_cross_engine_browser_apptest.py` (NEW, 9 tests) — AppTest checks for full-dataset filtering, pagination, page-size, and select-to-edit label persistence.

## Decisions Made

All decisions are the plan's D-04/D-16/D-17/D-18/D-19 plus the discretion calls captured in the frontmatter `key-decisions`. In short:
- Uninstall is confirm-then-delete with freed space shown (D-16); blocked while in use (D-17); per-item + bulk partial cleanup (D-18).
- Kokoro reuses the generic substrate (D-19) with a D-04 footprint confirm on the f32 asset (default int8); `KOKORO_ASSETS` keeps URLs out of the page.
- native_os exposes nothing to download/uninstall (OS-owned).

## Deviations from Plan

Two deviations, both surfaced at / requested during the blocking human-verify checkpoint.

### 1. [Rule 1 - Bug] Per-item "Remove partial" was unreachable after Cancel

- **Found during:** Task 3 (human-verify checkpoint)
- **Issue:** The per-item "Remove partial" action was gated on `not active`, but a **cancelled** dl_state record resolved `action=="resume"`, which set `active==True` — so a cancelled/resumable download offered Resume but hid Remove partial, leaving the user unable to clear the orphaned `.part` from that row (defeating part of D-18).
- **Fix:** Re-gated the per-item action on `action not in ("downloading","cancelling")` so a cancelled/resumable row offers BOTH Resume and Remove partial; Remove partial unlinks the `.part`, clears the dl_state record, and resets the row to Install.
- **Files modified:** `diana/dashboard/pages/5_Settings.py`
- **Verification:** Extended `tests/test_uninstall_apptest.py`; full suite green; human re-verified per-item Remove partial after Cancel.
- **Committed in:** `bf53757`

### 2. [Rule 1 - Usability fix, user-requested at the checkpoint] Paginated read-only cross-engine table replacing the unusable ~184-row list

- **Found during:** Task 3 (human-verify checkpoint) — the user flagged the 04-05 cross-engine "Browse all voices" rendering of ~184 rows as unusable.
- **Issue:** 04-05 shipped the cross-engine browser as a flat per-voice row list; with all engines' voices merged (~184 entries) it was unscrollable/unusable in practice.
- **Fix:** Replaced the row list with a PAGINATED READ-ONLY `st.dataframe` (Engine/ID/Name/Language/Tier/Gender/Tags); the reused Phase-3 `filter_voices`/`order_by_quality` + name/tag search apply to the FULL merged dataset, which is then sliced into 25/50/100-row pages (a filter or page-size change resets to page 1). A select-to-edit panel reuses the 04-05 label editor so relabelling any voice (incl. native_os) still works. New pure `paginate()` helper keeps the slicing unit-testable.
- **Scope note:** This enhances a **04-05** deliverable (the cross-engine browser), surfaced because 04-06 owns the same `5_Settings.py` Voices tab and the user asked for it at this checkpoint. It is a usability fix, not new requirement scope.
- **Files modified:** `diana/dashboard/pages/5_Settings.py`
- **Verification:** New `tests/test_settings_pagination.py` (8) + `tests/test_cross_engine_browser_apptest.py` (9); full suite green; human-verified full-dataset filtering, pagination, page-size, and select-to-edit label persistence.
- **Committed in:** `96e6464`

---

**Total deviations:** 2 (1 Rule-1 reachability bug, 1 user-requested usability enhancement to the 04-05 cross-engine browser)
**Impact on plan:** Both arose at the checkpoint and were resolved before resume. Deviation 1 restores D-18 per-item cleanup reachability; deviation 2 makes the (04-05) cross-engine browser actually usable. No scope creep against VOICE-07/ENGINE-02 — the table is a presentation upgrade, the uninstall/cleanup/Kokoro download deliverables are exactly as planned.

## Verification: AppTest vs Human

**Human-verified (PASS at the blocking checkpoint):**
- Cross-engine table — full-dataset filtering, pagination, page-size, select-to-edit label persistence
- Uninstall — in-use block + confirm + freed space shown; badge flips back to not-installed
- Partial cleanup — per-item "Remove partial" + bulk "Clean up partial downloads"
- native_os — shows no download/uninstall control (OS-owned)

**AppTest-verified only (NOT defects — environment-limited):**
- **Cancel mid-download** — covered by `tests/test_uninstall_apptest.py` interaction checks. Piper voices download too fast to cancel by hand on the verifying machine, so the live in-browser Cancel→Resume/Remove-partial path is AppTest-verified pending a live pass.
- **Kokoro download progress** — covered by AppTest. The Kokoro model was already installed on the verifying machine, so the in-app footprint-confirm → byte-progress → "Ready" flow could not be exercised live; it is AppTest-verified pending a live in-browser download.

These two are carried as a non-blocking deferred UAT (see STATE.md Deferred Items), not as defects — the logic + UI wiring are present, parse, and are AppTest-covered.

## Issues Encountered

None beyond the two checkpoint deviations documented above.

## User Setup Required

None — no external service configuration required. The Kokoro model now downloads in-app (Settings ▸ Voices ▸ Kokoro model row) with a footprint confirm; no terminal/`wget` step.

## Next Phase Readiness

- **Phase 4 is COMPLETE** — all 6 plans done (19/19 milestone plans, 100%). The full in-app loop is closed: discover → preview → install → use → relabel → uninstall/clean up, with the SAME generic download/cache substrate driving both the Piper per-voice catalog and the Kokoro single-model download (the D-19 boundary the phase existed to prove).
- **Phase 5 (Heavy Opt-In Engines)** can now reuse the proven engine-generic substrate (download_file/.part/md5/atomic + has_space + dl_state/thread/fragment + install_state probes + uninstall/clean_partials) for Orpheus/F5-TTS/Fish S2 Pro on-demand installs.
- **Phase 6 (Packaging) package-data flag re-confirmed:** the Phase-6 PyInstaller build must still collect `diana/data/*.json` + `diana/data/samples/` (bundled manifest + sample clips); no new package-data introduced by this plan (Kokoro assets download to the per-user `model_dir`, not bundled).
- **Carry-forward (non-blocking):** VOICE-04 manual-import interactive UAT (from 04-04) remains pending a Piper pair; Cancel-mid-download + Kokoro-download-progress are AppTest-verified pending a live in-browser pass (environment-limited this session). The Phase-3 Windows WinRT UAT also remains pending a Windows box.

## Self-Check: PASSED

- Source files exist: `diana/tts/install_state.py` (voice_in_use@66, uninstall_piper_voice@98), `diana/tts/kokoro_engine.py` (KOKORO_ASSETS, kokoro-v1.0 URLs), `diana/dashboard/pages/5_Settings.py` (voice_in_use/uninstall_piper_voice/clean_partials/"Clean up partial downloads"/kokoro_model_installed/download_file/paginate all wired) — FOUND
- Test files exist: `tests/test_uninstall.py` (3, flipped green), `tests/test_uninstall_apptest.py` (10), `tests/test_settings_pagination.py` (8), `tests/test_cross_engine_browser_apptest.py` (9) — FOUND
- Commits exist: `f6f3dff`, `7b58c31`, `bf53757`, `96e6464` — FOUND in git log
- Full suite: **461 passed / 1 deselected** (from the 432 baseline; +AppTest interaction coverage)

---
*Phase: 04-engine-management-voice-catalog*
*Completed: 2026-06-15*
