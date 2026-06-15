---
phase: 04-engine-management-voice-catalog
verified: 2026-06-15T19:20:00Z
status: passed
score: 6/6 success criteria verified
overrides_applied: 0
carried_deferred:
  - item: "VOICE-04 interactive manual-import UX (upload + path entry)"
    status: deferred
    automated_coverage: "tests/test_voice_import.py::test_safe_dest (traversal/extension) + UI wiring present in 5_Settings.py (_import_voice_pair / _import_voice_from_path, both routed through catalog.safe_voice_dest); pair-completeness + .onnx.json JSON-parse checks"
    why_deferred: "No external Piper .onnx + .onnx.json pair available on the dev machine 2026-06-15 — interactive end-to-end import not human-exercised"
    tracked_in: "04-HUMAN-UAT.md"
  - item: "Cancel-mid-download live visual"
    status: apptest_verified
    automated_coverage: "tests/test_settings_downloads.py (_download_action cancel->cancelled transition + spawn-guard) + tests/test_uninstall_apptest.py::test_uninstall_cancel_keeps_the_file / test_cancelled_row_offers_both_resume_and_remove_partial"
    why_deferred: "Piper voices download too fast to cancel by hand in a live session; the state machine + cancel/resume/remove-partial transitions are AppTest-verified"
  - item: "Kokoro-download progress visual (live)"
    status: apptest_verified
    automated_coverage: "tests/test_uninstall_apptest.py::test_kokoro_row_not_installed_shows_download_and_footprint_confirm / test_kokoro_row_installed_shows_ready"
    why_deferred: "Kokoro model already installed on the dev machine; the not-installed download row + D-04 >200MB footprint confirm + Ready badge are AppTest-verified"
  - item: "Windows native-OS surface"
    status: out_of_scope
    why_deferred: "Phase-3 deferred item (NATIVE-02 / 03-05); explicitly out of scope for Phase 4 per 04-CONTEXT.md"
---

# Phase 4: Engine Management & Voice Catalog Verification Report

**Phase Goal:** Users can discover, install, preview, use, and remove additional voices entirely in-app — powered by a shared, engine-agnostic on-demand model-download/cache layer, proven end-to-end by the Piper voice catalog (and Kokoro's model) before any heavy engine relies on it.
**Verified:** 2026-06-15T19:20:00Z
**Status:** passed
**Re-verification:** No — initial verification
**Mode:** mvp (goal is NOT a User Story — `user-story.validate` returned `valid: false`, so standard goal-backward methodology applied, not the MVP User-Flow-Coverage table)

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | Engine picker shows install-state + footprint badges WITHOUT heavy imports | ✓ VERIFIED | `1_Upload.py:_engine_readiness` (43-82) + render at 143-147; `5_Settings.py:_cross_engine_badge` (833-863) + Upload/Voices badges. Badge path uses ONLY `install_state` filesystem probes (`list_installed_piper_voice_ids`, `kokoro_model_installed`, `piper_footprint_bytes`) + a lazy `catalog._load_bundled_raw` read. **Proven import-clean:** importing `install_state`, `catalog`, and `registry` pulls NO streamlit/piper/kokoro_onnx/onnxruntime/torch (live `sys.modules` diff). `test_install_state.py` (3 tests) green. |
| 2 | Browse Piper catalog, download with byte progress + disk pre-check, interrupted download RESUMES not restarts | ✓ VERIFIED | `downloads/downloader.py:download_file` — resume via HTTP `Range` from `{dest}.part`, 206-append / 200-reset (both Pitfalls handled), md5-verify, atomic `os.replace`; `has_space` disk pre-check; cancel leaves `.part`. Wired: `5_Settings.py:_render_voice_row` (709-831) → `has_space` gate (770) → `_start_piper_download` → threaded `_download_piper_voice` → `@st.fragment _render_download_progress` byte bar (197-265); `_download_action` state machine (install/downloading/cancelling/resume/done) + Resume button (758-762). Tests: `test_downloader.py::{test_resume_offset, test_status_200_resets_part, test_md5_mismatch_rejects, test_atomic_finalize, test_disk_precheck}` + `test_settings_downloads.py` (20 state-machine/spawn-guard tests) all green. |
| 3 | Preview any voice (sample if not installed, live synth if installed) + select voice per job | ✓ VERIFIED | Three-mode preview in `_render_voice_row` (804-830): live synth when installed (`_preview_installed_voice` → create_engine→synthesize), bundled clip (`_bundled_sample_path`), else fetched+cached `speaker_0.mp3` (`catalog.fetch_sample`, D-12). Per-job select: `1_Upload.py` voice selectbox (195-207) → `tts_voice=selected_voice_id` written to the Job (384); `_piper_voices` merges installed voices into the picker (VOICE-05). |
| 4 | Manual import of Piper `.onnx`+`.onnx.json` via UI; downloads land in per-user cache, UI-triggered, NEVER in the worker | ✓ VERIFIED (logic) / ⚠ interactive UAT deferred | Dual-path import: `5_Settings.py:_import_voice_pair` (475-517, file_uploader) + `_import_voice_from_path` (520-554, path entry), both validate via `catalog.safe_voice_dest` (basename + .onnx/.onnx.json allow-list + resolved-prefix containment — HARD-03/T-04-PATH) + pair-match + JSON-parse. UI at 1547-1576. Downloads land in `paths.model_dir()` (per-user cache) and every download thread is spawned from the Streamlit SCRIPT thread (`_start_piper_download`/`_start_kokoro_download`), worker-thread is `st.*`-free (ENGINE-04). `test_voice_import.py::test_safe_dest` green. **Interactive import UX deferred** — no external Piper pair available (04-HUMAN-UAT.md). |
| 5 | Edit/add custom labels persisted across restart UI-only + browse/select across engines in one place | ✓ VERIFIED | `voice_labels.py` — per-voice JSON overrides in `app_settings` key `voice.labels.<engine>.<id>` (`get/set_label_overrides`), `apply_overrides` (dataclasses.replace, feeds Phase-3 filters), `search_by_tag` (plain accent-folded substring, NEVER regex — T-04-REDOS). Cross-engine: `registry.all_engine_voices` aggregates all 3 engines; Voices-tab "Browse all voices" (1252-1421): engine/lang/quality filters + name/tag search, paginated `st.dataframe`, `_render_label_editor` works for ANY engine incl. native_os (D-15). Tests: `test_voice_labels.py` (3) + `test_cross_engine_browser_apptest.py` (9, incl. filters span FULL dataset + select-to-edit saves tag→searchable) green. |
| 6 | Uninstall (confirm + freed space + in-use block) + clean partial downloads (per-item + bulk) + Kokoro model via same generic layer | ✓ VERIFIED | Uninstall: `install_state.voice_in_use` (D-17: blocks on non-terminal job's `tts_voice` OR `tts.default_voice.<engine>` key) + `uninstall_piper_voice` (D-16: model_dir-scoped unlink, returns freed bytes), wired in `_render_uninstall_control` (568-616, block→confirm+freed-space→delete). Cleanup: per-item "Remove partial" (795-802) + bulk `clean_partials` (1449-1450, D-18). **Kokoro via SAME layer (D-19):** `kokoro_engine.kokoro_download_assets` + `_render_kokoro_download_row` (619-706) reuses `download_file`/`has_space`/`_download_action`/`st.fragment` verbatim with a D-04 >200MB footprint confirm — the wget hint is gone (kokoro_engine.py:92-103 now points to Settings). Tests: `test_uninstall.py` (3) + `test_uninstall_apptest.py` (10, incl. both in-use blocks, confirm-deletes, cancel-keeps, Kokoro download+Ready) green. |

**Score:** 6/6 success criteria verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `diana/downloads/downloader.py` | Generic engine-agnostic resumable download/cache layer | ✓ VERIFIED | 116 lines. `download_file` (Range/.part/md5/atomic), `has_space`, `clean_partials`. Import-clean of streamlit/piper/kokoro (live-verified). |
| `diana/tts/install_state.py` | Cheap install-state + footprint probes (no heavy import) | ✓ VERIFIED | 116 lines. Pure filesystem probes + lazy DB import in `voice_in_use`. Import-clean (live-verified). |
| `diana/tts/catalog.py` | Piper manifest parse/curate + sample fetch + safe import dest | ✓ VERIFIED | 395 lines. parse/curate/group/footprint/url/sample/refresh/safe_voice_dest. Import-clean. Bundled manifest loads 9 voices / 7 curated. |
| `diana/tts/voice_labels.py` | UI-only per-voice label/tag overrides (D-14/D-15) | ✓ VERIFIED | 135 lines. JSON app_settings overrides, ReDoS-safe tag search. |
| `diana/tts/registry.py` | Cross-engine aggregation + cheap install shims + ASCII map | ✓ VERIFIED | 207 lines. `all_engine_voices`, `_piper_voices` (static+installed merge), lazy install_state shims. |
| `diana/tts/kokoro_engine.py` | Kokoro asset table for in-UI download (D-19) | ✓ VERIFIED | 126 lines. `KOKORO_MODEL_VARIANTS`/`KOKORO_VOICES_ASSET`/`kokoro_download_assets`; FileNotFoundError now points to Settings ▸ Voices (wget hint removed). |
| `diana/dashboard/pages/5_Settings.py` | Voices-tab management hub (D-09) wiring all of the above | ✓ VERIFIED | 1751 lines. st.tabs + Voices tab: cross-engine browser, Kokoro row, bulk cleanup, Piper catalog browse/preview/install/uninstall, dual import. |
| `diana/dashboard/pages/1_Upload.py` | Engine-dropdown readiness badge + per-job voice select | ✓ VERIFIED | 394 lines. `_engine_readiness` cheap badge (143-147); `tts_voice` written to Job (384). |
| `diana/dashboard/voice_cache.py` | Shared cached enumerator + cache-clear (install→use fix) | ✓ VERIFIED | 68 lines. `cached_voices`/`cached_all_engine_voices`/`clear_voice_cache`. |
| `diana/data/piper_voices_curated.json` | Bundled curated manifest snapshot (D-02) | ✓ VERIFIED | Present (9.8 KB); declared as package-data in pyproject.toml (`data/*.json`, `data/samples/*`). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `_render_voice_row` | `downloader.download_file` | `_start_piper_download`→threaded `_download_piper_voice` | ✓ WIRED | has_space gate first (770); fragment polls byte progress |
| `_render_uninstall_control` | `install_state.voice_in_use` + `uninstall_piper_voice` | direct call (590, 608) | ✓ WIRED | block→confirm→delete; clears voice cache |
| Bulk cleanup button | `downloader.clean_partials` | direct call (1450) | ✓ WIRED | globs `model_dir()/*.part` |
| `_render_kokoro_download_row` | `kokoro_engine.kokoro_download_assets` + `download_file` | `_start_kokoro_download` (D-19) | ✓ WIRED | SAME generic substrate as Piper; D-04 footprint confirm |
| Cross-engine browser | `registry.all_engine_voices` + `voice_labels.apply_overrides` | `cached_all_engine_voices` (1260) + merge (1270) | ✓ WIRED | engine/lang/quality filters span full dataset (AppTest-proven) |
| Import UI | `catalog.safe_voice_dest` | `_import_voice_pair`/`_import_voice_from_path` (506/546) | ✓ WIRED | traversal + extension guard on both paths |
| Upload engine dropdown | `install_state` probes | `_engine_readiness` (143) | ✓ WIRED | cheap badge, no heavy import |
| `_piper_voices` (picker) | installed voices on disk | `list_installed_piper_voice_ids` + `voice_label_for_id` | ✓ WIRED | installed voice appears in picker (VOICE-05) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Cross-engine table | `_engine_pairs` | `cached_all_engine_voices()`→`registry.all_engine_voices`→`get_engine_voices` per engine | Yes — real OS/static/installed voices (9 bundled + native_os enum + installed) | ✓ FLOWING |
| Catalog browse rows | `_browse_voices` | `catalog.load_bundled_manifest()` / refreshed manifest | Yes — 9 curated voices from bundled JSON (live-loaded) | ✓ FLOWING |
| Install-state badges | install probes | `install_state.*` filesystem reads of `model_dir()` | Yes — real on-disk presence/footprint | ✓ FLOWING |
| Label editor pre-fill | `merged_voice` | `apply_overrides(base, get_label_overrides(db,…))` | Yes — real app_settings round-trip (test_overrides_round_trip) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| downloader import-clean of heavy deps | `python -c` sys.modules diff | NONE pulled | ✓ PASS |
| install_state import-clean | `python -c` sys.modules diff | NONE pulled | ✓ PASS |
| registry+catalog import-clean (cleaning path) | `python -c` sys.modules diff | NONE pulled | ✓ PASS |
| Bundled manifest loads + curates | `catalog.load_bundled_manifest()` | 9 voices / 7 curated | ✓ PASS |
| `Job.tts_voice` field present | `dataclasses.fields(Job)` | True | ✓ PASS |
| `list_engines()` returns all 3 | `registry.list_engines()` | `['native_os','kokoro','piper']` | ✓ PASS |

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` probes declared for this phase; verification used the pytest suite + AppTest interaction coverage + live import-cleanliness checks instead (the phase's declared validation contract — 04-VALIDATION.md).

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| ENGINE-01 | Cheap capability/install-state detection, no heavy imports | ✓ SATISFIED | `install_state.py` pure-fs probes; live import-clean diff; SC1 |
| ENGINE-02 | On-demand download: byte progress, resumability, disk pre-check | ✓ SATISFIED | `downloader.download_file`/`has_space`; SC2; Kokoro routed same (D-19) |
| ENGINE-03 | Install-state + footprint badges (Voices tab + Upload dropdown) | ✓ SATISFIED | `_cross_engine_badge` + `_engine_readiness`; SC1 |
| ENGINE-04 | Downloads UI-triggered only, land in per-user cache, never in worker | ✓ SATISFIED | spawn from script thread → `model_dir()`; worker thread st.*-free; SC4 |
| VOICE-01 | Browse Piper catalog from manifest | ✓ SATISFIED | curated-flat + show-all grouped + Refresh; SC2 |
| VOICE-02 | Download/install catalog voices, no terminal | ✓ SATISFIED | `_render_voice_row` Install flow; SC2 |
| VOICE-03 | Preview (sample if not installed, live synth if installed) | ✓ SATISFIED | three-mode preview; SC3 |
| VOICE-04 | Manual import .onnx + .onnx.json via UI | ⚠ LOGIC SATISFIED / interactive UAT deferred | dual-path import + safe_voice_dest; `test_safe_dest` green; interactive UX deferred (04-HUMAN-UAT.md) |
| VOICE-05 | Select voice per job | ✓ SATISFIED | Upload voice selectbox → `tts_voice`; installed voices merged into picker; SC3 |
| VOICE-06 | Edit/add custom labels persisted UI-only + cross-engine browse | ✓ SATISFIED | `voice_labels.py` + cross-engine browser; SC5 |
| VOICE-07 | Uninstall (confirm + freed + in-use block) + partial cleanup (per-item + bulk) | ✓ SATISFIED | `voice_in_use`/`uninstall_piper_voice`/`clean_partials`; SC6 |

No orphaned requirements: REQUIREMENTS.md maps exactly ENGINE-01..04 + VOICE-01..07 to Phase 4, and every one is claimed by a phase plan and verified above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | No TBD/FIXME/XXX debt markers in any phase-modified file | — | Debt-marker gate PASSES |
| `5_Settings.py` / `1_Upload.py` | various | `placeholder=` matches | ℹ Info | All are legitimate Streamlit `text_input` placeholder args, NOT stub markers |

No stub returns, no empty handlers, no hardcoded-empty data feeding rendering. The empty-result branches (e.g. `return []` when `model_dir()` absent on fresh install) are correct fresh-install behavior, not stubs.

### Human Verification Required

Carry-forward / deferred items (recorded in 04-HUMAN-UAT.md — the single human-UAT sink). These are NOT blocking gaps: the code is present and automated-tested; they are visual/interactive confirmations a unit test cannot reach, and the phase's own success criteria are all met in code.

1. **VOICE-04 interactive import** — Launch the app, Settings ▸ Voices: import a real Piper `.onnx`+`.onnx.json` via path AND via upload → confirm it validates, becomes selectable on Upload, and bad imports (one file only / wrong type) show a clear rejection (not a crash). *Why human:* Streamlit upload widget + needs a real Piper pair (none on dev machine 2026-06-15). *Automated:* `test_safe_dest` + UI wiring present.
2. **Cancel-mid-download live visual** — Start a large download and click Cancel mid-stream → progress halts, `.part` kept, Resume continues from offset. *Why human:* Piper voices download too fast to cancel by hand. *Automated:* `test_settings_downloads.py` state machine + `test_uninstall_apptest.py` cancel/resume rows.
3. **Kokoro download progress visual** — On a machine without Kokoro installed: Settings ▸ Voices → Engine models → Download model shows live byte progress + D-04 footprint confirm for f32. *Why human:* Kokoro already installed on dev machine. *Automated:* `test_kokoro_row_*` AppTest.

### Test Result

```
.venv/bin/python -m pytest -q
→ 461 passed, 1 deselected, 5 warnings in 10.88s
```

- Matches the expected baseline exactly (461 passed / 1 deselected).
- The 1 deselected is the opt-in `@pytest.mark.network` test `tests/test_downloader_net.py::test_real_resumable_download` (real-HF download), excluded by default — confirmed via `pytest --collect-only -m network`.
- All Phase-4 concern suites green: `test_downloader.py` (5), `test_catalog.py` (3), `test_install_state.py` (3), `test_voice_import.py` (1), `test_voice_labels.py` (3), `test_uninstall.py` (3), `test_settings_downloads.py` (20), `test_uninstall_apptest.py` (10), `test_cross_engine_browser_apptest.py` (9).

### Gaps Summary

**No gaps blocking goal achievement.** All 6 ROADMAP success criteria are met by shipped, wired, data-flowing, automated-tested code. The download/cache layer is genuinely engine-agnostic (live-verified import-clean of streamlit/piper/kokoro/onnxruntime/torch — the D-19 contract), proven end-to-end by both the Piper per-voice catalog and the Kokoro single-model download through the SAME `download_file`/`has_space`/`.part`/md5/atomic substrate. The cheap-probe contract (ENGINE-01) holds: every badge path is a pure filesystem probe with no heavy SDK import.

The only items not exercised end-to-end by a human (VOICE-04 interactive import UX; cancel-mid-download and Kokoro-progress live visuals; Windows native-OS surface) are honest carry-forwards: each has present code + automated coverage and is environment-limited (no Piper pair / too-fast downloads / Kokoro pre-installed / Windows out of scope), tracked in 04-HUMAN-UAT.md. These do not reduce the phase's code-completeness and were explicitly flagged as non-failing in the verification scope.

---

_Verified: 2026-06-15T19:20:00Z_
_Verifier: Claude (gsd-verifier)_
