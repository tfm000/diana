---
phase: 04-engine-management-voice-catalog
plan: 01
subsystem: testing
tags: [pytest, skipif-scaffold, wave-0, piper-voices, download, manifest, ttsvoice, app_settings, redos, path-traversal]

# Dependency graph
requires:
  - phase: 03-native-os-tts-new-default
    provides: "TTSVoice tier/bilingual trailing-default precedent; filter_voices/order_by_quality/resolve_default_voice pure helpers; Wave-0 guarded-import + skipif scaffold pattern; tts.default_voice.<engine> app_settings key"
  - phase: 01-foundation-privacy-toggle
    provides: "app_settings(key,value) durable UI-only prefs (get_setting/set_setting); platformdirs per-user resolver (paths.model_dir/voices_dir)"
provides:
  - "tags: tuple[str, ...] = () trailing-default field on TTSVoice (the shared D-14 storage substrate for the custom-label layer)"
  - "network pytest marker registered (opt-in real-download tests excluded by default)"
  - "tests/fixtures/voices_manifest.json — 3-entry rhasspy/piper-voices excerpt incl. a multi-speaker speaker_id_map"
  - "7 Wave-0 test scaffolds (downloader, downloader_net, catalog, install_state, voice_import, voice_labels, uninstall) — guarded-import + skipif, real assertion bodies, flip to live gates as Plans 02/04/05 land"
affects: [04-02 downloader+catalog, 04-03 install-state+badges, 04-04 import+uninstall UI, 04-05 voice-labels, 04-06 cross-engine browser]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave-0 guarded-import + skipif scaffold (real assertion bodies, never pass) with multi-candidate module-home probe for planner's-choice symbols"
    - "Trailing-defaulted dataclass field extension to keep positional VOICES lists valid with zero edits"

key-files:
  created:
    - tests/fixtures/voices_manifest.json
    - tests/test_downloader.py
    - tests/test_downloader_net.py
    - tests/test_catalog.py
    - tests/test_install_state.py
    - tests/test_voice_import.py
    - tests/test_voice_labels.py
    - tests/test_uninstall.py
  modified:
    - diana/tts/base.py
    - pyproject.toml

key-decisions:
  - "Extended TTSVoice with tags (trailing-default tuple) rather than a parallel dict (A3/D-14), mirroring the Phase-3 tier/bilingual precedent so the 4-arg positional VOICES lists in piper/kokoro stay valid with zero edits"
  - "Traversal scaffold asserts the security INVARIANT (containment within model_dir + extension allow-list) rather than mandating a raise, so it binds whether the implementer strips-and-contains (basename guard) or rejects outright"
  - "Uninstall in-use predicate called via inspect.signature tolerance ((db,engine,voice) or (db,voice)) so the scaffold binds to whichever signature Plan 04 chooses"

patterns-established:
  - "Wave-0 scaffold: import-guard future symbols + skipif-gate dependent tests with real assertion bodies (NOT xfail); each flips to a live regression gate when its symbol lands — no later test-file edits"
  - "Multi-candidate module-home probe loop for planner's-choice symbols (downloader/catalog/install_state/voice_labels homes)"

requirements-completed: [VOICE-06]

# Metrics
duration: ~9min
completed: 2026-06-15
---

# Phase 4 Plan 01: Wave-0 Validation Foundation Summary

**Seven guarded-import + skipif test scaffolds, the rhasspy/piper-voices manifest fixture (incl. a multi-speaker voice), the `network` pytest marker, and the trailing-defaulted `TTSVoice.tags` field — the full Nyquist contract from 04-VALIDATION.md, with the suite collecting GREEN at the prior baseline.**

## Performance

- **Duration:** ~9 min (implementation; 3 atomic task commits 13:32→13:41 local)
- **Started:** 2026-06-15T12:32:17Z
- **Completed:** 2026-06-15T12:41:54Z
- **Tasks:** 3
- **Files modified:** 10 (2 source modified + 8 created)

## Accomplishments
- `TTSVoice.tags: tuple[str, ...] = ()` added as a trailing default — the one shared contract the D-14 custom-label layer (Plan 05) and the cross-engine browser (Plan 06) build on; piper/kokoro 4-arg positional VOICES lists unchanged.
- All 7 Wave-0 test files exist as guarded-import + `skipif` scaffolds with real assertion bodies — every later Phase-4 task now has an `<automated>` verify command that already exists, so no executor writes a test against an unwritten symbol.
- `tests/fixtures/voices_manifest.json` committed: a verified 3-entry Piper manifest excerpt (lessac-medium with the real md5/size_bytes, en_GB-alan-medium, and a multi-speaker de_DE-thorsten_emotional with a populated `speaker_id_map`).
- `network` pytest marker registered; the opt-in `tests/test_downloader_net.py` is excluded by default and emits no `PytestUnknownMarkWarning`.
- Full suite: **380 passed / 18 skipped** (no regression from the 379-passed baseline; +1 = the new fixture-sanity test, 18 skips = the new symbol-gated scaffolds).

## Task Commits

Each task was committed atomically (authored solely as tfm000, no AI co-author):

1. **Task 1: Add tags field to TTSVoice + register network marker** — `3738143` (feat)
2. **Task 2: Manifest fixture + download/catalog/install-state scaffolds** — `a2a7b47` (test)
3. **Task 3: Import/labels/uninstall scaffolds** — `e84052b` (test)

**Plan metadata:** (this commit) — docs: complete plan

## Files Created/Modified
- `diana/tts/base.py` — added `tags: tuple[str, ...] = ()` trailing-default field to `TTSVoice` (D-14 substrate).
- `pyproject.toml` — registered `markers = ["network: ..."]` under `[tool.pytest.ini_options]`.
- `tests/fixtures/voices_manifest.json` — 3-entry rhasspy/piper-voices excerpt incl. one populated `speaker_id_map`.
- `tests/test_downloader.py` — resume offset/`Range`, 206-append vs 200-reset, md5 reject/accept atomic finalize, disk precheck (`requests` stubbed; `tmp_path` only).
- `tests/test_downloader_net.py` — opt-in `@pytest.mark.network` real-HF resumable download + md5 (default-excluded).
- `tests/test_catalog.py` — manifest parse→TTSVoice, footprint sum, HF resolve URL build, curated subset + group-by-language (fixture-driven).
- `tests/test_install_state.py` — cheap Piper/Kokoro filesystem install probes + footprint (`model_dir` monkeypatched to `tmp_path`).
- `tests/test_voice_import.py` — `safe_voice_dest` traversal containment + absolute-path + `.onnx`/`.onnx.json` extension allow-list (HARD-03).
- `tests/test_voice_labels.py` — override JSON round-trip via mocked `app_settings`, `apply_overrides`→`TTSVoice` honored by Phase-3 `filter_voices`, plain-substring tag search (T-04-REDOS).
- `tests/test_uninstall.py` — D-17 in-use block (non-terminal job arm + per-engine default arm; terminal job excluded), targeted pair delete, D-18 bulk `*.part` cleanup.

## Decisions Made
- **Extend `TTSVoice` with `tags` (not a parallel dict)** — A3/D-14. Trailing-defaulted tuple mirrors how Phase 3 added `tier`/`bilingual`; verified the 5 piper + 9 kokoro positional VOICES entries still construct with `tags == ()`.
- **Traversal scaffold asserts containment, not a mandatory raise** — RESEARCH Pattern 5's reference `safe_voice_dest` applies `os.path.basename` first (which neutralizes `../../`), so a strict "must raise on traversal" assertion would over-constrain the implementer. The scaffold instead pins the real HARD-03 invariant: the resolved dest never escapes `model_dir`, and a non-`.onnx`/`.onnx.json` extension raises `ValueError`. It accepts either a strip-and-contain or a reject-outright implementation.
- **Signature-tolerant in-use predicate call** — `tests/test_uninstall.py` resolves the predicate's arity via `inspect.signature` so it binds to either `(db, engine, voice_id)` or `(db, voice_id)`, matching the "module home + signature is the implementer's choice" note in the plan/RESEARCH.

## Deviations from Plan

None - plan executed exactly as written. All three tasks landed with their planned files, no auto-fixes (Rules 1-3) and no architectural escalations (Rule 4) were needed; the scaffolds were additive and the suite stayed green throughout.

## Issues Encountered
None. The baseline reported "379 passed / 2 skipped" in planning docs, but the live baseline this session was 379 passed / 0 skipped (the Phase-3 scaffolds the "2 skipped" referred to had already flipped live in Plan 03-05). No regression: the post-plan suite is 380 passed / 18 skipped, the +1 passed being the new `test_catalog::test_fixture_present_and_shaped` fixture-sanity check and the 18 skips being this plan's new symbol-gated scaffolds.

## User Setup Required
None - no external service configuration required. The `network`-marked test is opt-in (`-m network`) and not part of any default or CI run.

## Next Phase Readiness
- **Plan 02 (downloader + catalog):** `tests/test_downloader.py`, `tests/test_downloader_net.py`, `tests/test_catalog.py`, and `tests/test_install_state.py` will flip from SKIPPED to live gates the moment `diana.downloads.downloader.{download_file,has_space}`, `diana.tts.catalog.parse_manifest` (+ footprint/URL/curation helpers), and the install-state probes land — zero test edits required.
- **Plan 04 (import + uninstall UI):** `tests/test_voice_import.py` and `tests/test_uninstall.py` gate `safe_voice_dest`, the D-17 in-use predicate, `uninstall_voice`, and the D-18 bulk `*.part` cleanup.
- **Plan 05 (voice labels):** `tests/test_voice_labels.py` gates `get_label_overrides`/`set_label_overrides`/`apply_overrides`; `TTSVoice.tags` is already in place so the label layer has its storage field.
- **Plan 06 (cross-engine browser):** consumes `TTSVoice.tags` for tag search and reuses the catalog/curation helpers Plan 02 lands.
- No blockers. The Nyquist contract in 04-VALIDATION.md "Wave 0 Requirements" is fully satisfied (7 files + fixture + marker).

## Self-Check: PASSED

All claimed artifacts verified present on disk and all task commits verified in git history (see post-summary verification).

---
*Phase: 04-engine-management-voice-catalog*
*Completed: 2026-06-15*
