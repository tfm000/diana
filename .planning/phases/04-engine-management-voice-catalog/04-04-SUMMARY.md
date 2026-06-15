---
phase: 04-engine-management-voice-catalog
plan: 04
subsystem: ui
tags: [streamlit, piper, voice-catalog, browse, group-by-language, voice-preview, st-audio, manual-import, file-uploader, path-traversal-guard, sample-cache]

# Dependency graph
requires:
  - phase: 04-03
    provides: "Voices tab in tabbed Settings (st.tabs General/Voices/Processing/LLM Cleaning/News), the single-voice Install/Resume/Cancel machinery + dl_state, install/footprint badges, shared voice_cache.py enumerator cleared on install-done, dynamic piper enumeration (install->use)"
  - phase: 04-02
    provides: "Piper catalog data layer (parse_manifest / load_bundled_manifest / refresh_catalog / curated_subset / group_by_language / download_url / voice_footprint_bytes), generic download_file substrate (reused to fetch+cache a sample clip), bundled curated manifest, package-data glob for data/*.json + samples/"
  - phase: 04-01
    provides: "TTSVoice.tags contract; Wave-0 test scaffolds test_voice_import (HARD-03 traversal invariant) + test_catalog"
  - phase: 03-04
    provides: "Phase-3 voice-attribute picker helpers filter_voices / order_by_quality / _fold / resolve_selected_voice_id reused VERBATIM (D-03) + the None-safe empty-filter discipline"
provides:
  - "Full Piper catalog browse in the Voices tab: a flat curated default view (offline, instant) and a 'Show all voices' view grouped by language as collapsible st.expander sections over the refreshable manifest, with a 'Refresh catalog' action (D-01/D-02/D-03)"
  - "The Phase-3 language/quality filters + name search reused VERBATIM (filter_voices/order_by_quality), pointed at catalog data with the language selectbox options derived from the manifest languages, in BOTH views (D-03)"
  - "Three-mode voice preview: live synthesis (create_engine -> synthesize -> st.audio) for an installed voice; a bundled curated sample clip for a not-installed curated voice; an on-demand fetched-and-cached speaker_0.mp3 for any other not-installed voice, with graceful 404 handling (D-12/VOICE-03)"
  - "sample_url_for + fetch_sample (download+cache speaker_0.mp3 so repeat previews are instant/offline) in catalog.py"
  - "Validated dual-path manual import: st.file_uploader(accept_multiple_files=True) for the .onnx + .onnx.json pair AND a path-entry text_input for a local file (sidesteps the maxUploadSize cap); both routed through safe_voice_dest (basename + resolved-prefix-under-model_dir + .onnx/.onnx.json allow-list) with pair-completeness + JSON-parse validation, landing side-by-side in model_dir() so the voice is selectable with no engine edit (D-13/VOICE-04/HARD-03)"
  - "Bundled curated sample-clip directory scaffold diana/data/samples/.gitkeep (package-data glob declared in 04-02)"
affects: [04-05, 04-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure Streamlit-free catalog helpers (sample_url_for / fetch_sample / safe_voice_dest) live in catalog.py and are unit-tested; the UI only calls them — keeps the security/URL logic testable without Streamlit"
    - "Manual-import path-traversal guard reuses RESEARCH Pattern 5 / 1_Upload.py idiom VERBATIM: os.path.basename neutralizes traversal, then a resolved-prefix-under-model_dir containment check + a .onnx/.onnx.json extension allow-list (HARD-03, T-04-PATH)"
    - "Sample preview = fetch-once-then-cache: download speaker_0.mp3 into a sample-cache dir, st.audio the cached file, so repeat previews are instant and offline (T-04-INT: samples are non-executable preview audio over HTTPS)"
    - "Show-all browse renders group_by_language as collapsible st.expander sections; both views feed the SAME reused filter_voices/order_by_quality pipeline (D-03 — no new filter function defined)"

key-files:
  created:
    - diana/data/samples/.gitkeep
  modified:
    - diana/tts/catalog.py
    - diana/dashboard/pages/5_Settings.py

key-decisions:
  - "Browse reuses the Phase-3 filter/search helpers VERBATIM (filter_voices/order_by_quality/_fold) — no new filter function defined (D-03); the language selectbox options are derived from the MANIFEST languages, not OS voices"
  - "Curated view is a flat offline list (load_bundled_manifest -> curated_subset); 'Show all' sources the refreshable manifest and groups by language in collapsible expanders; 'Refresh catalog' calls refresh_catalog() and degrades to bundled on failure (D-01/D-02/Pitfall 6)"
  - "Preview is three-mode: installed -> live synth via the existing create_engine->synthesize->st.audio path; not-installed curated -> bundled sample; not-installed other -> fetch_sample (download+cache) then st.audio; a missing sample is messaged gracefully not crashed (D-12/Pitfall 6)"
  - "safe_voice_dest is the single import gate (T-04-PATH/HARD-03): basename + resolved-prefix-under-model_dir + .onnx/.onnx.json allow-list; the pair must be complete (shared base) and the .onnx.json must parse as JSON before any copy (T-04-PAIR); rejection is messaged, not a crash"
  - "Dual-path import: file_uploader is bounded by server.maxUploadSize (T-04-MEMUP/Pitfall 7); the path-entry text_input sidesteps the cap for large local high-quality .onnx files — both land in model_dir() so PiperVoice.load auto-loads the sibling .onnx.json with no engine edit"

patterns-established:
  - "Pattern 1: pure Streamlit-free catalog helpers (URL/fetch/validate) in catalog.py, unit-tested; UI is a thin caller"
  - "Pattern 2: manual-import traversal guard = basename + resolved-prefix containment + extension allow-list (HARD-03), reused verbatim from the 1_Upload.py idiom"
  - "Pattern 3: fetch-once-then-cache sample preview (offline repeat playback)"
  - "Pattern 4: a single reused filter pipeline behind both curated-flat and show-all-grouped browse views (D-03, no duplicate filter)"

requirements-completed: [VOICE-01, VOICE-03]
# VOICE-04 import VALIDATION logic is complete + automated-test-covered (test_voice_import green);
# its interactive upload/path UX was NOT human-verified this session (no external Piper .onnx+.onnx.json
# pair available 2026-06-15) — recorded as a DEFERRED manual-UAT item in 04-HUMAN-UAT.md, NOT a defect.

# Metrics
duration: ~6min impl (wall ~10min spanning the blocking human-verify checkpoint)
completed: 2026-06-15
---

# Phase 04 Plan 04: Full Catalog Browse + Preview + Manual Import Summary

**Full Piper catalog browse (curated-flat default + Show-all grouped-by-language over the refreshable manifest with the reused Phase-3 filters/search + Refresh), three-mode voice preview (bundled curated sample / on-demand fetched+cached sample / live synthesis for installed), and validated dual-path manual import (file_uploader + path entry through `safe_voice_dest`) in the Settings Voices tab.**

## Performance

- **Duration:** ~6 min implementation (wall ~10 min spanning the blocking human-verify checkpoint)
- **Started:** 2026-06-15T15:08:00Z (approx)
- **Completed:** 2026-06-15T15:16:24Z
- **Tasks:** 3 (2 auto + 1 blocking human-verify checkpoint; steps 1-3 PASS, steps 4-5 import deferred to manual UAT)
- **Files modified:** 3 (diana/tts/catalog.py, diana/dashboard/pages/5_Settings.py, diana/data/samples/.gitkeep)

## Accomplishments

- **Full catalog browse (VOICE-01 / D-01/D-02/D-03):** the Voices tab now offers a flat curated default view (offline, instant) and a "Show all voices" toggle that expands the refreshable full manifest GROUPED by language into collapsible `st.expander` sections. Both views reuse the Phase-3 `filter_voices`/`order_by_quality` helpers VERBATIM — a manifest-derived language selectbox, a quality selectbox, and a name search — and a "Refresh catalog" button re-fetches via `refresh_catalog()` (degrading to bundled on failure).
- **Three-mode preview (VOICE-03 / D-12):** Preview per row — live synthesis (`create_engine -> synthesize -> st.audio`) for an installed voice; a bundled curated sample for a not-installed curated voice; an on-demand `fetch_sample`-downloaded-and-cached `speaker_0.mp3` for any other not-installed voice, with graceful 404 handling. Cached samples make repeat previews instant/offline.
- **Validated dual-path manual import (VOICE-04 / D-13 / HARD-03) — logic done, automated-tested:** `st.file_uploader(accept_multiple_files=True)` for the `.onnx`+`.onnx.json` pair AND a path-entry `text_input` for a local file, both routed through `safe_voice_dest` (basename + resolved-prefix-under-`model_dir` containment + `.onnx`/`.onnx.json` allow-list), requiring a complete pair (shared base) with the `.onnx.json` parsing as JSON before any copy. Imported voices land side-by-side in `model_dir()` and become selectable with no engine edit.
- **Test scaffold flipped to live:** the Plan-01 `test_voice_import` HARD-03 traversal scaffold flipped skip->pass now that `safe_voice_dest` landed; suite went to 429 passed / 5 skipped / 1 deselected (was 428 passed / 6 skipped at 04-03 close).

## Task Commits

Each task was committed atomically (authored solely as `tfm000`):

1. **Task 1: sample-URL + cached-sample fetch + import-filename validator in catalog.py** (TDD) — `f4b06ce` (feat) — added `sample_url_for`, `fetch_sample`, and `safe_voice_dest`; the Plan-01 `test_voice_import` scaffold flipped skip->pass (RED was in the prior wave's git history).
2. **Task 2: full catalog browse + preview + manual import in the Voices tab** — `77ebedc` (feat) — Show-all grouped browse + reused filters/search + Refresh; three-mode preview (bundled/fetched/live); dual-path import (file_uploader + path) through `safe_voice_dest`; `diana/data/samples/.gitkeep` scaffold.
3. **Task 3: human-verify checkpoint** — no code commit; steps 1-3 (browse / not-installed preview / installed preview) APPROVED; steps 4-5 (import via upload / path) deferred to manual UAT (see Deviations + 04-HUMAN-UAT.md).

**Plan metadata:** `<this commit>` (docs: complete plan)

_Task 1 is a TDD task whose RED commit lives in the 04-01 Wave-0 scaffold (`test_voice_import`); this plan's commit is the GREEN that flips it._

## Files Created/Modified

- `diana/tts/catalog.py` (modified) — added `sample_url_for(voice_dir_path)` (HuggingFace `.../resolve/main/{voice_dir}/samples/speaker_0.mp3`), `fetch_sample(voice_dir_path, cache_dir)` (download+cache via `download_file`), and `safe_voice_dest(uploaded_name)` (RESEARCH Pattern 5 traversal/extension guard). All three are Streamlit-free and unit-tested.
- `diana/dashboard/pages/5_Settings.py` (modified) — extended the Plan-03 Voices tab with: a "Show all voices" toggle + `group_by_language` collapsible browse; reused `filter_voices`/`order_by_quality` with a manifest-derived language selectbox + quality + name search; a "Refresh catalog" button; per-row Preview (live synth / bundled sample / fetched-cached sample) via `st.audio`; and a manual-import section with `file_uploader` + path-entry both validated through `safe_voice_dest`.
- `diana/data/samples/.gitkeep` (created) — bundled curated sample-clip directory scaffold (package-data glob was declared in 04-02).

## Decisions Made

- **Browse reuses Phase-3 filters VERBATIM (D-03):** no new filter function defined; `filter_voices`/`order_by_quality`/`_fold` are imported from `native_os_engine`. The language selectbox options are derived from the **manifest** languages, not OS voices.
- **Curated-flat vs Show-all-grouped (D-01/D-02):** the default view is the offline `curated_subset(load_bundled_manifest())` flat list; "Show all" sources the refreshable manifest and renders `group_by_language` as collapsible expanders; "Refresh catalog" calls `refresh_catalog()` and degrades to bundled on failure (Pitfall 6).
- **Three-mode preview (D-12):** installed -> live synth; not-installed curated -> bundled sample; not-installed other -> `fetch_sample` (download+cache) then `st.audio`; a missing sample is messaged gracefully, not a crash.
- **`safe_voice_dest` is the single import gate (HARD-03 / T-04-PATH):** `os.path.basename` + resolved-prefix-under-`model_dir` containment + `.onnx`/`.onnx.json` allow-list; the pair must be complete (shared base) and the `.onnx.json` must parse as JSON before any copy (T-04-PAIR).
- **Dual-path import (Pitfall 7 / T-04-MEMUP):** `file_uploader` is bounded by `server.maxUploadSize`; the path-entry option sidesteps the cap for large local high-quality `.onnx` files. Both land in `model_dir()` so `PiperVoice.load` auto-loads the sibling `.onnx.json` with no engine edit.

## Deviations from Plan

**None - plan executed exactly as written.** Tasks 1 and 2 landed the planned helpers and UI wiring with no auto-fixes required; the full suite stayed green throughout.

The only departure from the *checkpoint* (not the implementation) is a deferred manual-UAT item, documented below — this is a deferred verification step, NOT an unplanned code change, and NOT a defect.

## Issues Encountered

None during implementation. At the blocking human-verify checkpoint, the user had no external Piper `.onnx`+`.onnx.json` pair on hand, so the two import steps could not be interactively exercised this session (see Deferred Verification).

## Deferred Verification (Manual UAT)

**VOICE-04 manual import — interactive UX deferred (NOT a defect, NOT a silent skip).**

- **What is verified:** The import VALIDATION logic (`safe_voice_dest` traversal/extension guard, pair-completeness, `.onnx.json` JSON-parse) is covered by passing automated unit tests (`tests/test_voice_import.py` flipped skip->pass this plan). The UI wiring (`file_uploader` + path-entry both routed through `safe_voice_dest`) is present and the page `ast.parse`s clean.
- **What is NOT verified:** The interactive upload/path-entry UX end-to-end (selecting a real pair -> it validates -> the voice becomes selectable on Upload) was NOT exercised at the checkpoint because no external Piper `.onnx`+`.onnx.json` pair was available on 2026-06-15.
- **Where it's recorded:** `.planning/phases/04-engine-management-voice-catalog/04-HUMAN-UAT.md` (full step), plus a one-line carry in STATE.md Deferred Items.
- **To verify later:** Settings ▸ Voices ▸ Import from path -> point at any Piper `.onnx` + sibling `.onnx.json` -> confirm it validates and becomes selectable on Upload; also try a single file / wrong extension and confirm a clear rejection message (not a crash).

**Human-verify outcome (Task 3):**

| Step | What | Outcome |
|------|------|---------|
| 1 | Browse: curated-flat -> Show-all grouped-by-language, filters/search, Refresh catalog | **PASS** |
| 2 | Preview (not installed): sample plays + cached on repeat | **PASS** |
| 3 | Preview (installed): live synthesis plays | **PASS** |
| 4 | Import via upload (.onnx + .onnx.json pair) | **DEFERRED** — validation automated-tested; interactive UAT pending (no external pair) |
| 5 | Import via path (sidesteps the size cap) | **DEFERRED** — validation automated-tested; interactive UAT pending (no external pair) |

## User Setup Required

None - no external service configuration required. (A future manual UAT needs the user to supply any Piper `.onnx`+`.onnx.json` pair to exercise the import UX — tracked in 04-HUMAN-UAT.md.)

## Next Phase Readiness

- **Wave 5 (04-05):** cross-engine voice browser + editable voice labels + Upload-dropdown badges — builds on this plan's browse + the 04-03 dynamic-enumeration foundation.
- **Wave 6 (04-06):** voice uninstall + Kokoro on-demand download/install — the remaining engine-management capability.
- VOICE-01 (browse) and VOICE-03 (preview) are complete and human-verified. VOICE-04 import logic is complete + automated-tested; its interactive UAT is the one open verification carried forward (no blocker — the logic is proven by tests).

## TDD Gate Compliance

Task 1 was `tdd="true"`. The RED gate (`test(...)`) for `test_voice_import` lives in the 04-01 Wave-0 scaffold git history (skipif-gated with a real assertion body, per the established Wave-0 pattern); this plan's `f4b06ce` is the GREEN gate that lands `safe_voice_dest` and flips the scaffold skip->pass. No separate REFACTOR commit was needed.

## Self-Check: PASSED

- `diana/tts/catalog.py` — FOUND; `sample_url_for` / `fetch_sample` / `safe_voice_dest` present (lines 105/123/159)
- `diana/dashboard/pages/5_Settings.py` — FOUND; browse/preview/import wiring present (Show all, group_by_language, filter_voices, file_uploader, safe_voice_dest, st.audio, refresh_catalog, fetch_sample all matched)
- `diana/data/samples/.gitkeep` — FOUND
- Commit `f4b06ce` (Task 1) — FOUND in git log
- Commit `77ebedc` (Task 2) — FOUND in git log
- Test suite — 429 passed / 5 skipped / 1 deselected (green)

---
*Phase: 04-engine-management-voice-catalog*
*Completed: 2026-06-15*
