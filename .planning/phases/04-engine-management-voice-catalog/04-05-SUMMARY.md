---
phase: 04-engine-management-voice-catalog
plan: 05
subsystem: ui
tags: [streamlit, voice-labels, app-settings, cross-engine-browser, voice-catalog, install-state, footprint-badge, tag-search, redos-guard, json-degrade]

# Dependency graph
requires:
  - phase: 04-04
    provides: "Full catalog browse + 3-mode preview + dual-path import in the Voices tab (the Voices-tab structure the cross-engine browser section is added beneath)"
  - phase: 04-03
    provides: "Tabbed Settings + Voices hub, shared diana/dashboard/voice_cache.py enumerator cleared on a state transition, dynamic piper enumeration (install->use), install/footprint badges on the Voices tab, install_state cheap filesystem probes"
  - phase: 04-02
    provides: "install_state probes (piper_voice_installed / kokoro_model_installed / piper_footprint_bytes / list_installed_piper_voice_ids) reused for the Upload readiness badge"
  - phase: 04-01
    provides: "TTSVoice.tags contract (the label/tag merge target) + the Wave-0 test_voice_labels scaffold (override round-trip, apply_overrides feeds filter_voices, plain-substring tag search)"
  - phase: 03-04
    provides: "Phase-3 voice-attribute helpers filter_voices / order_by_quality / _fold reused VERBATIM (D-10) + the None-safe empty-filter discipline"
provides:
  - "diana/tts/voice_labels.py — UI-only label/tag override layer persisted per voice id in app_settings under voice.labels.<engine>.<id> (JSON value); get_label_overrides / set_label_overrides (lazy DB import) + a pure apply_overrides(voice, overrides) that dataclasses.replace's name/language/gender/tier and merges custom tags into voice.tags, plus search_by_tag plain-substring matcher (NO regex compiled — T-04-REDOS). Malformed stored JSON degrades to {} so a bad value cannot crash enumeration (T-04-LBLJSON)"
  - "registry.all_engine_voices(config) — cross-engine aggregation over list_engines() x get_engine_voices() yielding (engine, TTSVoice) for native_os + Kokoro + Piper (installed Piper voices already surface via the 04-03 dynamic branch), the single source for the cross-engine browser (D-10)"
  - "registry re-exposed thin install-state shims (piper_voice_installed / piper_footprint_bytes / kokoro_model_installed) that lazy-delegate to install_state so the UI imports ONE place for badges and the cleaning path never pulls install_state (ENGINE-01)"
  - "Settings ▸ Voices 'Browse all voices' cross-engine browser: lists every engine's voices together with overrides applied via apply_overrides(get_label_overrides(...)) BEFORE display, an engine filter + the reused Phase-3 language/quality filters + a name(+tag) search, and a per-voice 'Edit labels & tags' editor (display name / language / quality tier / gender + free-text comma tags) that writes set_label_overrides ONLY on change and clears the shared voice_cache so edits show without restart (D-10/D-14/D-15)"
  - "Upload engine-dropdown readiness badge: a caption below the engine selectbox reporting Ready vs '~X MB, downloads on first use' per engine via the cheap install_state filesystem probe — no heavy SDK import (ENGINE-03/D-11, ENGINE-01)"
  - "voice_cache.cached_all_engine_voices() (@st.cache_data over registry.all_engine_voices) added to the shared cache and cleared by clear_voice_cache alongside the per-engine cache so label edits + installs both refresh without a restart"
affects: [04-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure-helper-over-lazy-DB-wrapper mirrored from registry.resolve_default_voice: get/set_label_overrides do a lazy `from diana.database import get_setting/set_setting` inside the function; apply_overrides + search_by_tag are import-clean (no streamlit, no DB) and unit-tested"
    - "Free-text label/tag search uses plain-substring `in` over folded text (reuses Phase-3 _fold) — user free-text is NEVER compiled as a regex (T-04-REDOS), and stored label JSON is tolerantly parsed (absent/empty/malformed -> {}) so a bad value can never crash enumeration (T-04-LBLJSON)"
    - "Cross-engine browser = apply_overrides(voice, get_label_overrides(db, engine, voice.id)) applied to EVERY (engine, voice) from all_engine_voices BEFORE filtering, so editing/relabelling works for ANY voice across native_os/Kokoro/Piper, not just downloadable ones (D-15), and the overridden attributes immediately drive the same reused filters/search"
    - "One install-state import surface: the badge UI imports the thin shims re-exposed from registry, which lazy-delegate to install_state — keeps the cheap-probe logic in install_state and keeps any heavy SDK off the badge render path (ENGINE-01)"

key-files:
  created:
    - diana/tts/voice_labels.py
  modified:
    - diana/tts/registry.py
    - diana/dashboard/pages/5_Settings.py
    - diana/dashboard/pages/1_Upload.py
    - diana/dashboard/voice_cache.py

key-decisions:
  - "Labels are UI-only overrides persisted per voice id in app_settings under voice.labels.<engine>.<id> as a JSON dict {name, language, tier, gender, tags:[...]} (RESEARCH storage shape verbatim) — survives restart, never edits the prelabeled engine data or config; apply_overrides only replaces the known fields present and is a no-op when empty (D-14)"
  - "Editing works for ANY voice (D-15) because apply_overrides is applied to every (engine, voice) from all_engine_voices, including native_os — proven at the checkpoint by relabeling a native_os voice"
  - "Tag/name search is a plain-substring matcher (search_by_tag) over folded text — user free-text is never compiled as a regex (T-04-REDOS); the name match reuses filter_voices' query and the tag match is unioned in"
  - "all_engine_voices builds on the EXISTING list_engines()/get_engine_voices() (the native_os dynamic branch + the 04-03 dynamic-piper merge reused as-is); create_engine wiring was NOT touched (this plan adds no engine)"
  - "Upload badge renders as a caption BELOW the engine selectbox (st.selectbox can't carry per-option badges) mirroring the _NATIVE_HINT block, using only the install_state filesystem probe — native_os always Ready; Piper/Kokoro Ready if installed else a footprint estimate (ENGINE-03/D-11, no heavy import per ENGINE-01)"
  - "The shared voice_cache gained cached_all_engine_voices and clear_voice_cache now clears it too, so a label save refreshes the cross-engine browser (and the pickers) without an app restart — the clear fires from the Streamlit script thread only"

patterns-established:
  - "Pattern 1: UI-only override layer over an engine's prelabeled data — pure apply_overrides merge + lazy-DB get/set, JSON-valued app_settings key, tolerant of malformed/absent values"
  - "Pattern 2: cross-engine aggregation helper (all_engine_voices) over the existing per-engine enumeration, kept in registry so the UI has one cross-engine source"
  - "Pattern 3: one install-state import surface re-exposed from registry (lazy-delegating to install_state) so badge paths never pull a heavy SDK (ENGINE-01)"
  - "Pattern 4: plain-substring free-text search (never regex) for user-supplied tags/names (T-04-REDOS)"

requirements-completed: [ENGINE-01, ENGINE-03, VOICE-06]

# Metrics
duration: ~7min impl (wall spanning the blocking human-verify checkpoint)
completed: 2026-06-15
---

# Phase 04 Plan 05: Cross-Engine Voice Browser + Editable/Custom Labels + Upload Badges Summary

**A UI-only voice label/tag override layer (`voice_labels.py`, persisted per voice id in `app_settings`, feeding the Phase-3 filters/search) plus a Settings ▸ Voices cross-engine browser (all engines listed together with an engine filter + reused language/quality filters + name/tag search and a per-voice label editor) and a cheap install-state readiness badge on the Upload engine dropdown — completing VOICE-06's "everything in one place, editable" half.**

## Performance

- **Duration:** ~7 min implementation (wall time spanning the blocking human-verify checkpoint)
- **Completed:** 2026-06-15
- **Tasks:** 3 (1 auto/TDD + 1 auto + 1 blocking human-verify checkpoint — APPROVED)
- **Files modified:** 5 (1 created: voice_labels.py; 4 modified: registry.py, 5_Settings.py, 1_Upload.py, voice_cache.py)

## Accomplishments

- **Label/tag override layer (VOICE-06 / D-14):** new `diana/tts/voice_labels.py` persists per-voice UI-only overrides in `app_settings` under `voice.labels.<engine>.<id>` (a JSON dict `{name, language, tier, gender, tags:[...]}`, RESEARCH storage shape verbatim). `get_label_overrides`/`set_label_overrides` use a lazy `from diana.database import get_setting/set_setting` (so the DB dep stays off module import); the pure `apply_overrides(voice, overrides)` `dataclasses.replace`s any of name/language/gender/tier present and merges custom tags into `voice.tags` (deduped). A `search_by_tag` plain-substring matcher (folded, NO regex — T-04-REDOS) feeds the search. Malformed/absent stored JSON degrades to `{}` (T-04-LBLJSON). The module is streamlit-free and unit-tested.
- **Cross-engine aggregation (VOICE-06 / D-10):** `registry.all_engine_voices(config)` iterates `list_engines()` x `get_engine_voices()` yielding `(engine, TTSVoice)` for native_os + Kokoro + Piper (installed Piper voices already surface from the 04-03 dynamic branch) — the single source for the browser, built on the existing enumeration with no `create_engine` change.
- **Cross-engine browser + label editor (D-10/D-14/D-15):** the Settings ▸ Voices tab gained a "Browse all voices" section that applies `apply_overrides(get_label_overrides(...))` to every voice BEFORE display, with an engine filter alongside the reused Phase-3 `filter_voices`/`order_by_quality` (language + quality) and a name(+tag) search, and a per-voice "Edit labels & tags" editor (display name / language / tier / gender + free-text comma tags) that writes `set_label_overrides` ONLY on change and clears the shared voice_cache so edits show without restart. Because overrides apply to ANY voice, editing works across native_os/Kokoro/Piper (D-15).
- **Upload readiness badge (ENGINE-03/D-11, ENGINE-01):** a caption below the Upload engine selectbox reports `Ready` vs `~X MB, downloads on first use` per engine, detected with the cheap `install_state` filesystem probe only (no onnxruntime/piper/kokoro import on the render path). `install_state` is re-exposed via thin lazy shims from `registry` so the UI imports one place.
- **Shared cache extended:** `voice_cache.cached_all_engine_voices()` (`@st.cache_data` over `all_engine_voices`) was added and `clear_voice_cache()` now clears it alongside the per-engine cache, so a label save (and an install) refresh the browser/pickers without a restart.
- **Test scaffold flipped to live:** the Plan-01 `tests/test_voice_labels.py` scaffold flipped skip->pass once `voice_labels` landed; suite went to **432 passed / 2 skipped / 1 deselected** (was 429 passed / 5 skipped at 04-04 close).

## Task Commits

Each task was committed atomically (authored solely as `tfm000`):

1. **Task 1: voice_labels module + cross-engine aggregation helper in registry** (TDD) — `a3b0a58` (feat) — new `diana/tts/voice_labels.py` (override CRUD + pure `apply_overrides` + `search_by_tag`) + `all_engine_voices(config)` and the re-exposed install-state shims in `registry.py`. The Plan-01 `test_voice_labels` scaffold flipped skip->pass (RED was in the prior wave's git history).
2. **Task 2: cross-engine browser + label editor in the Voices tab; engine badges on Upload** — `7a108f0` (feat) — Settings ▸ Voices "Browse all voices" cross-engine browser + per-voice "Edit labels & tags" editor; Upload engine-dropdown readiness badge via the cheap `install_state` probe; shared `voice_cache.cached_all_engine_voices` + `clear_voice_cache` extension so edits show without restart. Files: `5_Settings.py`, `1_Upload.py`, `voice_cache.py`.
3. **Task 3: human-verify checkpoint** — no code commit; cross-engine browse, label edit/persist-across-restart/filter-feed (incl. a native_os voice), and Upload badges all **APPROVED** (see Human-Verify Outcome).

**Plan metadata:** `<this commit>` (docs: complete plan)

_Task 1 is a TDD task whose RED commit lives in the 04-01 Wave-0 scaffold (`test_voice_labels`); `a3b0a58` is the GREEN that flips it. No separate REFACTOR commit was needed._

## Files Created/Modified

- `diana/tts/voice_labels.py` (created) — `get_label_overrides` / `set_label_overrides` (lazy DB import, JSON-valued `voice.labels.<engine>.<id>`), pure `apply_overrides(voice, overrides)` (`dataclasses.replace` name/language/gender/tier + merge tags), and `search_by_tag` (plain-substring, folded; never regex). Streamlit-free, unit-tested.
- `diana/tts/registry.py` (modified) — added `all_engine_voices(config)` (cross-engine aggregation over the existing `list_engines()`/`get_engine_voices()`); re-exposed thin lazy `piper_voice_installed` / `piper_footprint_bytes` / `kokoro_model_installed` shims delegating to `install_state` so the UI imports one place (cheap probe stays in `install_state`; `create_engine` untouched).
- `diana/dashboard/pages/5_Settings.py` (modified) — "Browse all voices" cross-engine section: `cached_all_engine_voices` source, `apply_overrides(get_label_overrides(...))` before display, an engine filter + reused `filter_voices`/`order_by_quality` + a name(+tag) search via `search_by_tag`, and a per-voice "Edit labels & tags" expander writing `set_label_overrides` on change + `clear_voice_cache()`.
- `diana/dashboard/pages/1_Upload.py` (modified) — engine readiness caption below the engine selectbox (Ready vs "~X MB, downloads on first use") via the cheap `install_state` probe; the existing voice-picker block was left untouched.
- `diana/dashboard/voice_cache.py` (modified) — added `cached_all_engine_voices()` (`@st.cache_data` over `all_engine_voices`); `clear_voice_cache()` now also clears it so label edits/installs refresh without a restart.

## Decisions Made

- **Labels are UI-only `app_settings` overrides (D-14):** persisted per voice id under `voice.labels.<engine>.<id>` as a JSON dict (RESEARCH storage shape verbatim); they never touch the prelabeled engine data or `config.yaml`. `apply_overrides` replaces only the known fields present and is a no-op when empty.
- **Editing works for ANY voice (D-15):** `apply_overrides` is applied to every `(engine, voice)` from `all_engine_voices`, including native_os — proven at the checkpoint by relabeling a native_os voice.
- **Free-text search is plain-substring, never regex (T-04-REDOS):** `search_by_tag` folds and uses `in`; the name match reuses `filter_voices`' query and the tag match is unioned in.
- **`all_engine_voices` reuses the existing enumeration (D-10):** built on `list_engines()`/`get_engine_voices()` (native_os dynamic branch + the 04-03 dynamic-piper merge as-is); `create_engine` was not modified (no engine added this plan).
- **One install-state import surface (ENGINE-01):** the badge UI imports thin shims re-exposed from `registry` that lazy-delegate to `install_state`, keeping the cheap-probe logic in `install_state` and any heavy SDK off the badge render path.
- **Upload badge renders below the selectbox (ENGINE-03/D-11):** `st.selectbox` can't carry per-option badges, so a caption mirrors the `_NATIVE_HINT` pattern — native_os always Ready; Piper/Kokoro Ready if installed else a footprint estimate.

## Deviations from Plan

**None - plan executed exactly as written.** Tasks 1 and 2 landed the planned `voice_labels` module + `all_engine_voices` helper and the UI wiring (cross-engine browser + label editor + Upload badge) with no auto-fixes required; the full suite stayed green throughout. The blocking human-verify checkpoint surfaced **no defects**.

Note on `files_modified`: the plan frontmatter named 4 files (voice_labels.py, registry.py, 5_Settings.py, 1_Upload.py); the effective set adds `diana/dashboard/voice_cache.py` because the "edits show without restart" requirement (clear the shared cache on label save) is satisfied by extending the existing shared `voice_cache.py` (the 04-03 enumerator) with `cached_all_engine_voices` rather than introducing a parallel cache. This is the planned no-restart behavior implemented through the established shared-cache pattern, not scope creep — recorded here for an accurate audit trail.

## Issues Encountered

None. ReDoS guard (plain substring for tags/name) and the malformed-label-JSON degrade-to-`{}` guard were both verified; both pages `ast.parse` and render exception-free under the Streamlit `AppTest` harness.

## Human-Verify Outcome (Task 3)

The blocking human-verify checkpoint was **APPROVED** — all four behaviors confirmed:

| # | What | Outcome |
|---|------|---------|
| 1 | Cross-engine browse (D-10): one list across all engines + engine filter + language/quality filters + name/tag search | **PASS** |
| 2 | Edit labels on a native_os voice (proving D-15 cross-engine): change name/tier + add a custom tag, save | **PASS** |
| 3 | Persistence + filter feed: overrides survive an app restart and drive the filters/search (UI-only persistence) | **PASS** |
| 4 | Upload readiness badge (ENGINE-03/D-11): a per-engine badge renders below the engine dropdown without lag | **PASS** |

**Note on badge wording:** all three engines showed "Ready" on the verifying machine because Piper voices + the Kokoro model are already installed locally — so the "~X MB, downloads on first use" not-installed wording is **unit-verified only** (the install_state branch is covered by tests; the not-installed string was not seen live on this machine). This is an observation, not a defect.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **Wave 6 (04-06) — final wave:** adds voice **uninstall** + **partial-download cleanup** (per-item + a bulk "clean up partial downloads" action) and the in-UI **Kokoro single-model download/install** (D-16/D-17/D-18/D-19, VOICE-07) — the last engine-management capability. It builds on this plan's cross-engine browser (the uninstall/cleanup controls hang off the same per-voice rows) and the 04-02/04-03 download substrate.
- VOICE-06 (cross-engine browse/select + editable/custom labels) is **complete and human-verified**. ENGINE-01 and ENGINE-03 are complete (ENGINE-03 now covers the Upload dropdown too, not just the Voices tab).

## TDD Gate Compliance

Task 1 was `tdd="true"`. The RED gate (`test(...)`) for `tests/test_voice_labels.py` lives in the 04-01 Wave-0 scaffold git history (skipif-gated with a real assertion body, per the established Wave-0 pattern: override round-trip via mocked get/set_setting, `apply_overrides` yields a `TTSVoice` that `filter_voices` finds by an overridden language, and a custom tag found by plain-substring search). This plan's `a3b0a58` is the GREEN gate that lands `voice_labels` and flips the scaffold skip->pass. No separate REFACTOR commit was needed.

## Self-Check: PASSED

- `diana/tts/voice_labels.py` — FOUND; `get_label_overrides` / `set_label_overrides` / `apply_overrides` / `search_by_tag` present; streamlit-free (no `import streamlit`)
- `diana/tts/registry.py` — FOUND; `all_engine_voices` + re-exposed install-state shims present (lazy `install_state` import)
- `diana/dashboard/pages/5_Settings.py` — FOUND; `cached_all_engine_voices` / `apply_overrides` / `get_label_overrides` / `set_label_overrides` / `filter_voices` / `search_by_tag` / "Browse all voices" / "Edit labels & tags" / `clear_voice_cache` all matched
- `diana/dashboard/pages/1_Upload.py` — FOUND; `install_state` badge + "Ready" / "downloads on first use" wording present
- `diana/dashboard/voice_cache.py` — FOUND; `cached_all_engine_voices` added + cleared in `clear_voice_cache`
- Commit `a3b0a58` (Task 1) — FOUND in git log
- Commit `7a108f0` (Task 2) — FOUND in git log
- Test suite — 432 passed / 2 skipped / 1 deselected (green)

---
*Phase: 04-engine-management-voice-catalog*
*Completed: 2026-06-15*
