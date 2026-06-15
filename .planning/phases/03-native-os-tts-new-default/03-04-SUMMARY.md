---
phase: 03-native-os-tts-new-default
plan: 04
subsystem: ui
tags: [streamlit, tts, native-os, voice-picker, app-settings, cache_data]

# Dependency graph
requires:
  - phase: 03-native-os-tts-new-default (plan 03)
    provides: NativeOSEngine + dynamic get_engine_voices("native_os") + default_voice() + native_os as default engine
  - phase: 03-native-os-tts-new-default (plan 02)
    provides: TTSVoice.tier/.bilingual attributes + macOS say enumeration
  - phase: 01-foundation-privacy-toggle
    provides: app_settings(key,value) durable-pref table + get_setting/set_setting + build_digest_text pure-helper precedent
provides:
  - Pure Streamlit-free voice helpers (filter_voices, order_by_quality, resolve_default_voice, resolve_selected_voice_id)
  - Upload + Settings voice pickers with language/quality filters + name search
  - Per-engine default-voice memory persisted in app_settings (survives engine-switch + restart)
  - Dismissible native_os OS-voice-download hint (durable dismissed state)
  - Settings save path that skips model-path validation for native_os
affects: [phase-03-plan-05, voice-catalog, windows-tts]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure Streamlit-free filter/order/resolve helpers in the engine module (unit-testable; UI wires them)"
    - "@st.cache_data wrapper over get_engine_voices keyed by engine name (no re-shell of say -v '?' per keystroke)"
    - "Per-engine durable pref key shape: tts.default_voice.<engine_name> in app_settings"
    - "None-safe selected-voice resolution guarding empty filter/search results"

key-files:
  created: []
  modified:
    - diana/tts/native_os_engine.py
    - diana/dashboard/pages/1_Upload.py
    - diana/dashboard/pages/5_Settings.py
    - tests/test_native_os_engine.py
    - diana/tts/registry.py

key-decisions:
  - "D-07: language + quality/tier filters + name search around the voice picker on both Upload and Settings"
  - "D-08/D-09: default to OS system voice, best-quality-preferred ordering (enhanced/neural > standard > compact > novelty), system-language first"
  - "D-03: per-engine remembered voice persists across restart + engine-switch; never preselects a voice absent from the live list (Pitfall 5)"
  - "D-10: dismissible native_os download hint; dismissed state durable across restart"
  - "D-01 / D-02 left intact (no migration shim; picker shows only selected engine's voices) — not modified by this plan"

patterns-established:
  - "Pure helpers extracted from Streamlit: filter_voices/order_by_quality/resolve_default_voice/resolve_selected_voice_id live in native_os_engine.py with no streamlit import"
  - "None-safe picker resolution: empty filter/search result yields a friendly empty-state message instead of indexing voice_options[None]"

requirements-completed: [NATIVE-05]

# Metrics
duration: ~9min impl (wall ~25h spanning blocking human-verify checkpoint)
completed: 2026-06-15
---

# Phase 03 Plan 04: Voice-attribute picker UX Summary

**Language/quality filters + name search + per-engine default-voice memory + a dismissible native_os download hint, all backed by pure unit-tested filter/order/resolve helpers.**

## Performance

- **Duration:** ~9 min implementation (wall ~25h spanning the blocking human-verify checkpoint)
- **Started:** 2026-06-01T16:43:43+01:00 (Task 1 commit)
- **Completed:** 2026-06-15 (human-verify approval + finalize)
- **Tasks:** 2 (1 auto/TDD + 1 blocking checkpoint:human-verify)
- **Files modified:** 5 (4 planned + diana/tts/registry.py touched in the wiring/cache pass)

## Accomplishments
- Pure Streamlit-free helpers `filter_voices`, `order_by_quality`, `resolve_default_voice` (and the continuation-added `resolve_selected_voice_id`) in `diana/tts/native_os_engine.py`, fully unit-tested.
- Upload + Settings voice pickers gained a language filter, a quality/tier filter, and a name-search box around the voice dropdown; best-quality voices ordered near the top, system-language first.
- Per-engine remembered voice persisted in `app_settings` under `tts.default_voice.<engine_name>` — survives switching engines (native_os → kokoro → native_os) and app restart; a stale/absent id never preselects (falls back to engine default).
- Dismissible native_os download hint wired via the `tts.native_hint_dismissed` flag; dismissed state durable across restart and also surfaced on Settings.
- Settings save path treats native_os as a no-model-file engine (skips kokoro/piper model-path validation) — saving native_os no longer errors about a missing model file.

## Task Commits

1. **Task 1: Pure filter/search + best-quality ordering + default-voice resolution helpers** - `95f0595` (feat)
2. **Task 2: Wire filters/search/per-engine default + dismissible hint into Upload and Settings** - `a2feee4` (feat)
3. **Continuation crash fix (found during human-verify): guard empty voice filter result in pickers** - `7be54ac` (fix)

**Plan metadata:** see finalize commit (docs(03-04): complete plan)

_Note: Task 1 was a tdd="true" task; its RED scaffolds landed in Plan 03-01's git history (skip→pass flip pattern), so the GREEN commit here is the single feat commit `95f0595`._

## Files Created/Modified
- `diana/tts/native_os_engine.py` - Added pure `filter_voices`, `order_by_quality`, `resolve_default_voice`, and (continuation) `resolve_selected_voice_id` helpers; no streamlit import.
- `diana/dashboard/pages/1_Upload.py` - Language/quality filters + name search + `@st.cache_data`-wrapped enumeration + per-engine default-voice resolution + dismissible native_os hint.
- `diana/dashboard/pages/5_Settings.py` - Same dynamic-voice + per-engine-default treatment; native_os added as no-model-path-validation case; hint reused.
- `tests/test_native_os_engine.py` - Filter/search + default-voice-validation tests flipped green; continuation regression test for the empty-filter None-safe resolution.
- `diana/tts/registry.py` - Supporting wiring for the cached voice enumeration seam.

## Decisions Made
- D-07/D-08/D-09/D-10 implemented as specified (filters + search; OS-system-voice default with best-quality preferred ordering, system-language first; per-engine durable memory; dismissible durable hint).
- D-03 / Pitfall 5 enforced via `resolve_default_voice`: a remembered id is used only if present in the live enumerated list, else the engine default.
- D-01 (default flips to native_os for FRESH configs only; NO migration shim) and D-02 (picker shows only the selected engine's voices) were left untouched — verified as working-as-designed during human-verify, not bugs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Empty filter/search result crashed the picker (KeyError: None)**
- **Found during:** Task 2 (human verification in the running app)
- **Issue:** When a language/quality filter or name search produced an empty voice list, the picker resolved the selected voice id to `None` and then indexed `voice_options[None]`, raising `KeyError: None` and crashing the page.
- **Fix:** Added a None-safe `resolve_selected_voice_id` helper in `native_os_engine.py` and a friendly "no voices match" empty-state message in both pickers; the selectbox is skipped when the filtered list is empty, and clearing filters restores the list.
- **Files modified:** diana/tts/native_os_engine.py, diana/dashboard/pages/1_Upload.py, diana/dashboard/pages/5_Settings.py, tests/test_native_os_engine.py
- **Verification:** Added a regression test for the empty-result resolution; human re-verified the friendly empty-state message and list-restore on clear; full suite green.
- **Committed in:** `7be54ac` (continuation fix commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix was necessary for correctness (the filter/search UX is unusable if any empty result crashes the page). No scope creep — confined to the picker resolution path the plan introduced.

## Issues Encountered
- During human-verify the user observed "piper shown first" and "Amélie not found on piper" — these are D-01/D-02 working as designed (fresh-config-only default flip; picker shows only the selected engine's voices), not bugs. Amélie being absent under native_os is expected: native-OS only exposes voices actually downloaded/installed on the test machine. No changes made; D-01/D-02 left intact.

## Human Verification

Task 2 was a blocking `checkpoint:human-verify`. The human verified ALL acceptance steps in the running app and approved:
1. Empty-filter crash fixed — searching a nonexistent name shows the friendly "no voices match" message, no crash; clearing filters restores the list.
2. Search/filter feature works (accent-fold search confirmed; Amélie correctly absent only because it is not an installed OS voice on the test machine — expected per native-OS exposing only downloaded voices).
3. Per-engine voice memory persists across engine switch (native_os → kokoro → native_os) and restart.
4. Dismissible native_os download hint shows, dismisses, and stays dismissed across restart and on Settings.
5. Settings saves native_os with no missing-model-file error.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- NATIVE-05 complete on the macOS-testable surface. Voices are labelled AND filterable/searchable, with per-engine defaults that never preselect a missing voice.
- Plan 03-05 (Windows WinRT/SAPI5 boundaries) remains — the 2 skipped tests in the suite are its boundaries.
- No blockers.

## Self-Check: PASSED
- `diana/tts/native_os_engine.py`, `diana/dashboard/pages/1_Upload.py`, `diana/dashboard/pages/5_Settings.py`, `tests/test_native_os_engine.py`, `diana/tts/registry.py` — all present.
- Commits `95f0595`, `a2feee4`, `7be54ac` — all present in git history.
- Full suite: 377 passed / 2 skipped.

---
*Phase: 03-native-os-tts-new-default*
*Completed: 2026-06-15*
