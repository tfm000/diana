---
phase: 04-engine-management-voice-catalog
plan: 03
subsystem: ui
tags: [streamlit, st-tabs, st-fragment, threading, piper, voice-install, download, voice-cache, registry]

# Dependency graph
requires:
  - phase: 04-02
    provides: "generic download substrate (download_file/.part/md5/atomic, has_space disk pre-check, clean_partials), Piper catalog (load_bundled_manifest/download_url/voice_footprint_bytes), cheap install-state probes (piper_voice_installed/piper_footprint_bytes), bundled curated manifest"
  - phase: 04-01
    provides: "TTSVoice.tags field (Nyquist D-14 contract); Wave-0 test scaffolds for catalog/install_state"
  - phase: 03-04
    provides: "None-safe selectbox/picker discipline (resolve_selected_voice_id empty-state) + per-page @st.cache_data voices precedent that this plan unifies"
provides:
  - "Settings restructured into st.tabs (General / Voices / Processing / LLM Cleaning / News) with a dedicated Voices management hub (D-09)"
  - "End-to-end one-Piper-voice install walking slice: footprint/install-state badge -> universal disk-space pre-check -> UI-spawned background download thread with st.fragment(run_every=0.5s) byte-progress polling -> md5 atomic install -> cancel/resume keeping the .part"
  - "Cancellation as a terminal state (cancelled marker) + pure _download_action/_can_spawn_download helpers so Cancel -> Cancelling… -> Resume works and Resume offsets from the .part"
  - "Dynamic piper branch in registry.get_engine_voices merging static PiperEngine.VOICES with installed voices on disk (install_state.list_installed_piper_voice_ids), deduped, Kokoro files excluded, labeled via catalog.voice_label_for_id — the enumeration foundation 04-05's all_engine_voices builds on (no duplication)"
  - "Shared diana/dashboard/voice_cache.py (one @st.cache_data enumerator across Upload + Settings) cleared on the install-done transition so an installed voice appears with NO restart"
  - "Uniform Piper display-name formatting ('Lessac (US Medium)') for installed voices via pure _format_piper_name/_parse_piper_id, matching static PiperEngine.VOICES"
affects: [04-04, 04-05, 04-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RESEARCH Pattern 3 threaded download + st.fragment polling (NO prior in-repo precedent): daemon threading.Thread writes only to st.session_state.dl_state; ALL st.* render from the script thread via @st.fragment(run_every='0.5s'); re-trigger guarded on in-flight dl_state; serialized to one in-flight download"
    - "Cancellation modeled as an explicit terminal state (cancelled) distinct from in-flight, so the UI can offer Resume rather than restart"
    - "Single shared @st.cache_data voice enumerator (voice_cache.py) cleared on a state transition — replaces per-page private caches; clear invoked only from the script thread"
    - "Dynamic engine-voice enumeration = static curated VOICES merged with cheap-filesystem-probed installed ids (no heavy onnxruntime/piper import on the enumeration path, ENGINE-01)"

key-files:
  created:
    - diana/dashboard/voice_cache.py
    - tests/test_settings_downloads.py
    - tests/test_piper_enumeration.py
    - tests/test_voice_cache.py
  modified:
    - diana/dashboard/pages/5_Settings.py
    - diana/dashboard/pages/1_Upload.py
    - diana/tts/registry.py
    - diana/tts/install_state.py
    - diana/tts/catalog.py

key-decisions:
  - "Settings is tabbed (st.tabs) with a Voices hub; only the single-voice Install path is fully live this plan — full browse/filter/group-by-language deferred to 04-04 (D-09)"
  - "Download runs on a UI-spawned daemon thread polled by st.fragment; the thread is st.*-free and writes only dl_state — never the worker/pipeline (ENGINE-04, T-04-SRC)"
  - "Disk-space pre-check (has_space) gates the Install button and refuses before any bytes are written (D-05, T-04-DISK)"
  - "[Deviation #1] Cancellation made a terminal state (cancelled marker) + pure _download_action/_can_spawn_download helpers so Cancel->Resume works and Resume offsets from the .part (D-06/D-07)"
  - "[Deviation #2] registry.get_engine_voices('piper') now MERGES static VOICES with installed voices on disk (list_installed_piper_voice_ids), deduped, Kokoro excluded, labeled via voice_label_for_id — cheap filesystem probe, no heavy import (VOICE-05, ENGINE-01); the foundation 04-05 builds on"
  - "[Deviation #3] Unified the per-page _cached_voices into a shared voice_cache.py cleared on install-done (no restart), and installed-voice names now format uniformly as 'Lessac (US Medium)' via pure _format_piper_name/_parse_piper_id matching static PiperEngine.VOICES"

patterns-established:
  - "Pattern 1: threaded download + st.fragment polling (Pattern 3) — thread writes dl_state only; all st.* from the script thread; in-flight re-trigger guard; one in-flight download"
  - "Pattern 2: cancellation as a terminal state enabling Resume-from-.part rather than restart"
  - "Pattern 3: one shared @st.cache_data voice enumerator cleared on a state transition (script-thread only)"
  - "Pattern 4: dynamic engine-voice list = static curated VOICES + cheap-probed installed ids, no heavy import"

requirements-completed: [ENGINE-02, ENGINE-03, ENGINE-04, VOICE-02, VOICE-05]

# Metrics
duration: ~58min impl (wall ~1h spanning the blocking human-verify checkpoint)
completed: 2026-06-15
---

# Phase 4 Plan 03: Voice Catalog Walking Slice Summary

**Settings restructured into st.tabs with a Voices hub, and ONE curated Piper voice installs end-to-end through the Plan-02 substrate — footprint/install-state badge, universal disk pre-check, UI-spawned threaded download with st.fragment byte-progress polling, md5 atomic install, cancel/resume — then becomes immediately selectable for a job with no app restart.**

## Performance

- **Duration:** ~58 min implementation (wall ~1h spanning the blocking human-verify checkpoint)
- **Started:** 2026-06-15T14:02:26+01:00 (first task commit)
- **Completed:** 2026-06-15T15:00:41+01:00 (last fix commit)
- **Tasks:** 2 (1 autonomous implementation + 1 blocking human-verify, which surfaced 3 in-plan deviations)
- **Files modified:** 9 (1 created in plan scope + 3 new test files + 5 modified)

## Accomplishments

- **Settings is now tabbed** (`st.tabs`: General / Voices / Processing / LLM Cleaning / News) with a dedicated **Voices management hub** (D-09). Existing sections moved into tabs unchanged; one Save Settings button preserved; tab-switching stays cheap.
- **The walking slice works end-to-end** (D-19): a curated Piper voice shows an install-state/footprint badge (Ready vs "~X MB, downloads on first use" — ENGINE-03/D-11), runs a `has_space` disk pre-check that refuses on insufficient space (D-05), downloads on a **UI-spawned daemon thread polled by `@st.fragment(run_every="0.5s")`** with live byte progress (D-08, ENGINE-04 — the worker/pipeline is never touched), verifies md5 and atomically installs into the per-user model dir, and then becomes **selectable for a job** (VOICE-02/05).
- **Cancel and Resume behave correctly** — Cancel keeps the `.part` (D-07), Resume offsets from it rather than restarting at 0 (D-06).
- The generic Plan-02 substrate is **proven against the real network through the real UI**, satisfying ENGINE-02/03/04 + VOICE-02/05 for the single-voice happy path.
- **Test suite 391 → 428 passed** (6 skipped, 1 deselected) with 3 new test files locking the pure helpers and the dynamic-enumeration / cache-refresh behavior surfaced by the checkpoint deviations.

## Task Commits

1. **Task 1: Restructure Settings into st.tabs + Voices walking-slice install** (autonomous) — `bfde02b` (feat)
   Restructured `5_Settings.py` into tabbed sections with a Voices hub and wired the full one-Piper-voice install path on the Plan-02 substrate: footprint/install-state badge → universal disk-space pre-check → UI-spawned background download thread with `st.fragment(run_every=0.5s)` byte-progress polling (worker thread `st.*`-free) → md5 atomic install → cancel/resume.

2. **Task 2: Human-verify the walking-slice install UX** (blocking checkpoint — **APPROVED**)
   No new code is written by the checkpoint itself; the user launched the app and verified the Streamlit-UX + real-network behaviors (tabs render, byte-progress advances without freezing, Cancel/Resume, disk-check refusal, post-install selectability). The checkpoint surfaced **three real integration bugs**, each fixed as an in-plan deviation and **re-verified by the user** (see Deviations below):
   - `02f2eca` (fix) — Resume after Cancel
   - `55e87f9` (fix) — installed Piper voices appear in pickers (VOICE-05)
   - `9c36960` (fix) — no-restart cache refresh + uniform Piper names

**Human-verify approval:** the user approved all checkpoint steps — tabs + Voices hub render; install byte-progress advances and the UI stays responsive; Cancel stops and Resume continues from the offset (not a restart); disk-check refuses on insufficient space; the installed voice appears immediately in the Upload picker with the correct display name and is selectable.

## Files Created/Modified

- `diana/dashboard/pages/5_Settings.py` — **modified** (the primary file): wrapped the body in `st.tabs`; added the Voices hub and the one-voice install slice (badge, `has_space` pre-check, threaded `download_file` for `.onnx` + `.onnx.json`, `st.fragment` byte-progress poller, Cancel/Resume, in-flight re-trigger guard); on install-done clears the shared voice cache.
- `diana/dashboard/pages/1_Upload.py` — **modified**: switched from a private per-page `@st.cache_data` voices function to the shared `voice_cache.cached_voices`, so a freshly installed voice appears here too.
- `diana/dashboard/voice_cache.py` — **created**: ONE shared `@st.cache_data` voice enumerator across Upload + Settings, with `clear_voice_cache()` invoked from the script thread on the install-done transition (no restart). Worker thread stays `st.*`-free.
- `diana/tts/registry.py` — **modified**: `get_engine_voices("piper")` now merges static `PiperEngine.VOICES` with installed voices on disk (deduped, Kokoro files excluded), labeled via `catalog.voice_label_for_id`; cheap filesystem probe, no heavy `onnxruntime`/`piper` import (ENGINE-01).
- `diana/tts/install_state.py` — **modified**: added `list_installed_piper_voice_ids()` (cheap glob of the model dir) feeding the dynamic registry branch.
- `diana/tts/catalog.py` — **modified**: added `voice_label_for_id` plus pure `_format_piper_name` / `_parse_piper_id` so installed-voice display names format uniformly as "Lessac (US Medium)" matching static `PiperEngine.VOICES`.
- `tests/test_settings_downloads.py` — **created**: unit tests for the pure `_download_action` / `_can_spawn_download` helpers (Cancel→cancelled terminal→Resume; in-flight re-trigger guard; offset-from-`.part`).
- `tests/test_piper_enumeration.py` — **created**: tests for the dynamic piper branch (static + installed merge, dedup, Kokoro exclusion, labeling) and the uniform name format.
- `tests/test_voice_cache.py` — **created**: tests that the shared cache enumerates once and that `clear_voice_cache()` drops the cached entry.

## Decisions Made

- **Tabs with a Voices hub, only the Install path fully live this plan** (D-09). Full browse/filter/group-by-language is intentionally deferred to 04-04.
- **Download is UI-triggered on a UI-spawned daemon thread polled by `st.fragment`** — the thread writes only `dl_state` and never calls `st.*`; the worker/pipeline (`worker.py`/`pipeline.py`) is untouched (ENGINE-04, T-04-SRC). Re-trigger is guarded on in-flight `dl_state` and downloads are serialized to one in-flight (Pitfall 3, T-04-RETRIG).
- **Disk pre-check gates the Install button** and refuses before any bytes are written (D-05, T-04-DISK).
- The three deviations below were adopted as decisions because each closes a real defect in the load-bearing install→use→display path; all were re-verified by the user. Details under Deviations.

## Deviations from Plan

All three surfaced at the **blocking human-verify checkpoint** (Phase-3 precedent: integration/UX bugs surface here) and were fixed in-plan and re-verified by the user before the checkpoint was approved.

### Auto-fixed Issues

**1. [Rule 1 - Bug] Resume button never appeared after Cancel — cancellation was not a terminal state**
- **Found during:** Task 2 (human-verify checkpoint)
- **Issue:** Clicking Cancel halted the download but the UI never offered Resume, because cancellation was not modeled as a distinct terminal state (only in-flight vs done/error). The user could not resume an interrupted install — defeating D-06.
- **Fix:** Added a `cancelled` terminal marker to `dl_state` plus pure `_download_action` / `_can_spawn_download` helpers (unit-tested) so the flow is Cancel → "Cancelling…" → Resume, and Resume re-spawns `download_file` which offsets from the existing `.part` rather than restarting at 0 (D-06/D-07).
- **Files modified:** `diana/dashboard/pages/5_Settings.py`, `tests/test_settings_downloads.py` (new)
- **Verification:** New unit tests for the helpers (Cancel→cancelled→Resume, in-flight guard, offset-from-`.part`); user re-verified Cancel then Resume continues from the offset.
- **Committed in:** `02f2eca` (fix)

**2. [Rule 1 - Bug] Installed Piper voices did not appear in the Upload/Settings pickers (VOICE-05)**
- **Found during:** Task 2 (human-verify checkpoint)
- **Issue:** After a successful install the voice was on disk but `get_engine_voices("piper")` returned only the static `PiperEngine.VOICES`, so the newly installed voice was never selectable — VOICE-05 (selectable-for-a-job) was unmet in practice.
- **Fix:** Added `install_state.list_installed_piper_voice_ids()` (cheap model-dir glob) and a **dynamic `piper` branch** in `registry.get_engine_voices` that merges static + installed ids (deduped, Kokoro files excluded), labeled via `catalog.voice_label_for_id`. Stays a cheap filesystem probe with no heavy `onnxruntime`/`piper` import (ENGINE-01). This is the enumeration foundation 04-05's `all_engine_voices` builds on — built here once so 04-05 does not duplicate it.
- **Files modified:** `diana/tts/registry.py`, `diana/tts/install_state.py`, `diana/tts/catalog.py`, `tests/test_piper_enumeration.py` (new)
- **Verification:** New `test_piper_enumeration.py` (static+installed merge, dedup, Kokoro exclusion, labeling); user re-verified the installed voice appears and is selectable on Upload.
- **Committed in:** `55e87f9` (fix)

**3. [Rule 1 - Bug] Installed voices required an app restart to appear; (B) inconsistent display names**
- **Found during:** Task 2 (human-verify checkpoint)
- **Issue:** (A) Even with deviation #2, the per-page `@st.cache_data _cached_voices` still served a stale list, so a freshly installed voice did not appear until an app restart. (B) Installed-voice display names did not match the formatting of the static `PiperEngine.VOICES` (e.g. raw id vs "Lessac (US Medium)").
- **Fix:** (A) Unified the per-page caches into a shared `diana/dashboard/voice_cache.py` and called `clear_voice_cache()` from the **script thread** on the install-done transition, so the next rerun re-enumerates from disk and the voice shows in BOTH pickers with no restart (the worker thread stays `st.*`-free). (B) Added pure `_format_piper_name` / `_parse_piper_id` in `catalog.py` so installed-voice names format uniformly as "Lessac (US Medium)" matching the static VOICES.
- **Files modified:** `diana/dashboard/voice_cache.py` (new), `diana/dashboard/pages/5_Settings.py`, `diana/dashboard/pages/1_Upload.py`, `diana/tts/catalog.py`, `tests/test_voice_cache.py` (new), `tests/test_piper_enumeration.py`
- **Verification:** New `test_voice_cache.py` (caches once; `clear_voice_cache()` drops the entry) + extended `test_piper_enumeration.py` name-format assertions; user re-verified install → appears immediately in Upload with the correct name.
- **Committed in:** `9c36960` (fix)

---

**Total deviations:** 3 auto-fixed (3 Rule-1 integration bugs surfaced at the blocking human-verify checkpoint)
**Impact on plan:** All three were correctness fixes on the install → use → display path the walking slice exists to prove — no scope creep. Deviation #2's dynamic enumeration is deliberately the foundation 04-05 reuses (no duplication). The plan's `files_modified` named only `5_Settings.py`; the effective set expanded to include `1_Upload.py`, `voice_cache.py` (new), `registry.py`, `install_state.py`, `catalog.py`, and the 3 new test files — recorded here as the true touched set.

## Issues Encountered

The thread + `st.fragment` polling pattern has no in-repo precedent (used RESEARCH Pattern 3 as authoritative). The three checkpoint defects above were the integration cost of that first-of-its-kind pattern meeting the real install→use→display flow; all resolved within the plan.

## User Setup Required

None — no external service configuration required. The install path downloads curated Piper voices from the bundled manifest over the network on user action; no keys or env vars.

## Next Phase Readiness

- **04-04 (Wave 4)** layers the full **"Show all" catalog browse** (curated flat / show-all grouped + reused filters), **preview** (sample/fetch/live), and **dual-path manual import** onto this tabbed Voices hub. The single-voice Install path and the disk-check/threaded-download substrate it can reuse are in place.
- **04-05 (Wave 5)** builds the **cross-engine browser + editable/custom labels + Upload-dropdown badges** directly on this plan's dynamic `get_engine_voices("piper")` enumeration and the shared `voice_cache.py` (its `all_engine_voices` extends, does not duplicate, the merge done here).
- **04-06 (Wave 6)** adds uninstall + partial cleanup + Kokoro model download via the same generic layer; `clear_voice_cache()` already anticipates an uninstall-done clear.
- No blockers. The blocking Windows WinRT UAT (03-05) remains the only outstanding deferred item, unaffected by this plan.

## Self-Check: PASSED

- Created files verified present: `diana/dashboard/voice_cache.py`, `tests/test_settings_downloads.py`, `tests/test_piper_enumeration.py`, `tests/test_voice_cache.py`.
- Commits verified in git history: `bfde02b`, `02f2eca`, `55e87f9`, `9c36960`.
- Test suite green at finalize: **428 passed, 6 skipped, 1 deselected**.

---
*Phase: 04-engine-management-voice-catalog*
*Completed: 2026-06-15*
