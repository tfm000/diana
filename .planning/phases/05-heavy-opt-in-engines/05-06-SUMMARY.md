---
phase: 05-heavy-opt-in-engines
plan: 06
subsystem: tts
tags: [custom-voices, voice-cloning, f5-tts, engine-agnostic, reference-clip, transcript, validation, path-safety, app-settings, st-audio-input, dynamic-voices, apptest, streamlit]

# Dependency graph
requires:
  - phase: 05-heavy-opt-in-engines (05-02)
    provides: "paths.custom_voices_dir() (the per-user reference-clip library home); streamlit>=1.40 bump (st.audio_input)"
  - phase: 05-heavy-opt-in-engines (05-05)
    provides: "diana/tts/f5_engine.py::F5Engine (static VOICES=[f5_default] + _resolve_ref for the bundled default — the seam this plan makes dynamic); registry get_engine_voices('f5') static branch"
  - phase: 05-heavy-opt-in-engines (05-01)
    provides: "Wave-0 conftest fixtures (tmp_data_paths incl. custom_voices_dir, temp_clip) + the RED/skip scaffold tests/test_custom_voices.py"
  - phase: 04 (catalog/install_state/voice_labels)
    provides: "catalog.safe_voice_dest (the path-safety structure copied); voice_labels app_settings JSON metadata + malformed-tolerance idiom; install_state.voice_in_use (the in-use remove block); install_state.uninstall_piper_voice (the scoped-delete + freed-bytes lane); voice_cache.clear_voice_cache (no-restart appearance)"
provides:
  - "diana/tts/custom_voices.py — the reusable ENGINE-AGNOSTIC Custom Voices library (D-11): validate_clip (2-12s, 16kHz OK, empty-transcript reject, never raises — D-13/T-05-VAL); safe_custom_voice_dest (basename + .wav/.mp3/.txt allow-list + containment under custom_voices_dir — T-05-PATH); save_custom_voice/list_custom_voices/remove_custom_voice over ONE shared pool keyed voice.custom.<id> (no engine segment); custom_voice_ref(voice_id) -> (ref_file, ref_text) for any cloning engine's _resolve_ref; malformed-metadata tolerance (T-05-LBLJSON)"
  - "diana/tts/f5_engine.py::F5Engine.list_voices() — now dynamic: bundled default MERGED with custom_voices.list_custom_voices() (deduped); _resolve_ref delegates a non-default id to custom_voices.custom_voice_ref (lazy import — no torch)"
  - "diana/tts/registry.py::_f5_voices() — dynamic get_engine_voices('f5') = F5Engine.VOICES + custom voices (the _piper_voices merge pattern); custom voices flow through all_engine_voices into the cross-engine browser automatically (D-14); cheap path imports no torch"
  - "diana/dashboard/pages/5_Settings.py — the #### Custom Voices section (Voices tab): an Upload tab (audio file_uploader + a typed/.txt transcript) AND a Record tab (st.audio_input + a typed transcript), each routing through save_custom_voice with (ok,msg) via st.success/st.error; a saved-voices library with a two-step Remove (_render_custom_voice_remove) honoring the in-use block; clear_voice_cache after save/remove"
  - "tests/test_custom_voices_apptest.py — 3 interaction-level AppTest pre-checks (section renders both inputs; validation rejects bad input cleanly; saved voice appears in get_engine_voices('f5') + all_engine_voices() and is removable), all heavy-import-free"
affects: [05-fish-slice, 06-packaging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Engine-agnostic shared voice pool (D-11): storage is NOT keyed by engine — clips at custom_voices_dir()/<id>.wav + <id>.txt (the filesystem IS the index, the list_installed_piper_voice_ids lane) and metadata at the app_settings key voice.custom.<id> (no engine segment). One pool any cloning engine reuses — F5 today, Fish in 05-07. The CRUD functions accept an `engine` arg for call-site symmetry but never use it to key storage."
    - "Clip validation reuses the Phase-4 import-rejection discipline (validate_clip returns (ok, msg) and NEVER raises): soundfile.info reads duration/samplerate without a full decode; reject empty transcript / sub-1s / unreadable with a clear message; accept ~2-12s and DO NOT gate samplerate (16kHz st.audio_input capture is accepted — Pitfall 5/7); a >12s clip is accepted with a note that F5 uses the first ~12s."
    - "Path safety copies catalog.safe_voice_dest verbatim (basename -> extension allow-list -> resolved-prefix containment), swapping the .onnx allow-list for .wav/.mp3/.txt under custom_voices_dir() (T-05-PATH); save lands the clip through the guard then validates the on-disk file and rolls it back on rejection (a rejected clip never lingers)."
    - "F5/registry voice enumeration became dynamic via the registry::_piper_voices merge pattern (static default first, each custom voice appended, deduped by id), so saved voices surface in the Upload picker AND the cross-engine Browse-all table (all_engine_voices) with zero browser-side code — and the cheap enumeration path still imports no torch (ENGINE-01/D-17, asserted via sys.modules)."
    - "Settings Custom Voices section reuses the _import_voice_pair (ok,msg)+clear_voice_cache+st.success/st.error idiom for save and the _render_uninstall_control two-step confirm idiom for remove; the in-use block consults voice_in_use across both cloning engines (f5+fish) since a custom voice is engine-agnostic."

key-files:
  created:
    - diana/tts/custom_voices.py
    - tests/test_custom_voices_apptest.py
    - .planning/phases/05-heavy-opt-in-engines/05-06-SUMMARY.md
  modified:
    - diana/tts/f5_engine.py
    - diana/tts/registry.py
    - diana/dashboard/pages/5_Settings.py
    - .planning/phases/05-heavy-opt-in-engines/05-HUMAN-UAT.md

key-decisions:
  - "Storage is engine-agnostic per D-11 (key voice.custom.<id>, NO engine segment) — the PLAN body + acceptance criteria are authoritative over the PATTERNS.md line that sketched voice.custom.f5.<id>. One shared pool is the explicit intent (Fish reuses it in 05-07). The CRUD signatures accept (db_path, engine, ...) to match the Wave-0 scaffold test's positional calls and for call-site symmetry, but `engine` is documented-and-unused for storage keying."
  - "save_custom_voice lands the clip THROUGH safe_custom_voice_dest first, then runs validate_clip on the real on-disk file, and unlinks it on rejection — so soundfile reads an actual file (robust validation) while a rejected clip never lingers in the library (reject-with-message, never crash)."
  - "Display id is a filesystem-safe slug of the display name (lowercased, non-alphanumeric -> '-', deduped with -2/-3 against existing .wav files) — the filesystem is the index, so the slug must be a valid contained filename; the human name lives in app_settings metadata and falls back to the id when absent/malformed (T-05-LBLJSON)."
  - "remove_custom_voice 'clears' metadata by setting the app_settings value to '' (set_setting has no delete); an empty value reads back as the id via _name_for, and the cleared voice no longer globs anyway since its .wav is unlinked — so it disappears from every picker/browser. The in-use block checks both cloning engines (f5+fish) plus non-terminal jobs and returns 0 (deletes nothing) when blocked."
  - "Real F5 clone-by-ear DEFERRED to 05-HUMAN-UAT.md (APPENDED a Custom-Voices cloning section; the Orpheus + F5-install sections were preserved) per the Task-3 checkpoint authorization — running the multi-GB torch venv is impractical in an --auto macOS session. NOT a defect: capture/upload, validation, save/name/remove, and picker/browser appearance are all automated-tested (13 unit/AppTest tests), and the _resolve_ref->custom_voice_ref->worker handoff is covered by the 05-05 synth test with the subprocess mocked."
  - "Closed the 05-05 documented seam: get_engine_voices('f5') is now the dynamic bundled+custom merge (registry._f5_voices), exactly as 05-05's SUMMARY flagged ('05-06 swaps it to a dynamic bundled+custom merge ... left as the documented next-slice seam')."

patterns-established:
  - "Engine-agnostic Custom Voices pool: a reusable validate -> safe-dest -> save(name+clip+transcript) -> list(TTSVoice) -> custom_voice_ref(ref_file,ref_text) -> remove(in-use block + freed bytes) library, keyed voice.custom.<id>, that any cloning engine merges into its list_voices()/registry branch. Fish reuses it wholesale in 05-07."
  - "Dual reference-clip capture in Streamlit: an upload tab (file_uploader + typed/.txt transcript) and a record tab (st.audio_input + typed transcript), the transcript ALWAYS user-provided (no STT — D-12), both routed through one save function with (ok,msg) reject-with-message."

metrics:
  duration: ~50 min
  completed: 2026-06-15
  tasks: 3
  files-created: 3
  files-modified: 4
  tests-added: 13 (10 test_custom_voices unit + 3 test_custom_voices_apptest)
  full-suite: 505 passed, 2 skipped (Fish — Wave 7), 1 deselected, 0 failures
---

# Phase 5 Plan 06: Reusable Engine-Agnostic Custom Voices + F5 Cloning Summary

A reusable, ENGINE-AGNOSTIC Custom Voices library (`diana/tts/custom_voices.py`) that lets a user supply a reference voice two ways — upload an audio file + a transcript, or record in-app via `st.audio_input` + type the transcript — validated (`soundfile.info`, never crashes), saved/named/removable in one shared pool keyed `voice.custom.<id>`, and surfaced through a now-dynamic `get_engine_voices("f5")` into the Upload picker and the cross-engine browser, driving F5 cloning via `_resolve_ref` -> `custom_voice_ref`. Completes HEAVY-02 (D-11..D-14); the library is built for F5 today and reused by Fish in 05-07.

## What Was Built

**Task 1 — `custom_voices.py` (engine-agnostic) + dynamic F5/registry voices** (commit `636d757`)
- `validate_clip(audio_path, transcript) -> (ok, msg)`: accepts ~2-12s + a non-empty transcript (incl. 16 kHz capture — sub-24 kHz is NOT gated, Pitfall 5/7); rejects an empty/whitespace transcript, a sub-1s clip, and an unreadable/unsupported format — each with a clear message, NEVER raising (D-13/T-05-VAL).
- `safe_custom_voice_dest(name) -> Path`: copies `catalog.safe_voice_dest`'s structure — `os.path.basename` -> a `.wav`/`.mp3`/`.txt` allow-list -> resolved-prefix containment under `custom_voices_dir()`; raises `ValueError` on a disallowed extension or a traversal (T-05-PATH).
- `save_custom_voice` / `list_custom_voices` / `custom_voice_ref` / `remove_custom_voice`: round-trip a named voice over ONE shared pool (clips at `custom_voices_dir()/<id>.wav` + `<id>.txt`; metadata at the engine-agnostic `voice.custom.<id>`); malformed metadata degrades to the id (T-05-LBLJSON); removal blocks an in-use voice (across f5+fish + non-terminal jobs) then scoped-unlinks and returns freed bytes.
- `f5_engine.py`: `list_voices()` = bundled default + `custom_voices.list_custom_voices()` (deduped, lazy import); `_resolve_ref` delegates a non-default id to `custom_voices.custom_voice_ref`.
- `registry.py`: `_f5_voices()` makes `get_engine_voices("f5")` a dynamic bundled+custom merge (the `_piper_voices` pattern); custom voices flow through `all_engine_voices` into the cross-engine browser with no browser-side code — and the cheap path imports no torch (asserted via `sys.modules`).
- Flipped `tests/test_custom_voices.py` skip -> PASS (10 tests).

**Task 2 — Settings "Custom Voices" section** (commit `51dd2b8`)
- A `#### Custom Voices` section in the Voices tab with two `st.tabs`: **Upload a clip** (name + audio `file_uploader(.wav/.mp3)` + transcript as a typed `text_area` OR a `.txt` upload — user-provided per D-12) and **Record a clip** (`st.audio_input` 16 kHz capture + name + typed transcript). Both route through `custom_voices.save_custom_voice(db, None, name, audio, transcript)` and surface `(ok, msg)` via `st.success`/`st.error` (reject-with-message, never crash).
- A saved-voices library listing each custom voice with a two-step **Remove** (`_render_custom_voice_remove`) mirroring `_render_uninstall_control`: an in-use block (across f5+fish) -> a confirm + freed-space caption -> delete + `clear_voice_cache()` + rerun.
- `clear_voice_cache()` after every successful save/remove so voices appear in the pickers + Browse-all table without a restart. No torch import.

**Task 3 — human-verify checkpoint (auto-mode: pre-check + deferral)** (commit `7df5086`)
- Ran the agent PRE-CHECK: `tests/test_custom_voices_apptest.py` (3 PASS) drives the real Settings page through `streamlit.testing.v1.AppTest` and asserts the Custom Voices section renders both input methods (upload + `st.audio_input`, each with a transcript text_area); that `validate_clip` rejects an empty transcript and an unreadable clip with a message and never crashes the page; and that a saved custom voice appears in `registry.get_engine_voices("f5")` AND `registry.all_engine_voices()` and is removable — all with no `torch`/`f5_tts`/`torchaudio`/`vocos` imported.
- Deferred ONLY the real F5 clone-by-ear (needs the multi-GB torch venv): APPENDED a "HEAVY-02 — Custom Voices cloning" section to `05-HUMAN-UAT.md` (Orpheus + F5-install sections preserved) listing the human steps (record, upload + validation rejection, clone by ear, reuse, remove with in-use block).

## Deviations from Plan

### Reconciled signature ambiguity (PLAN interface vs Wave-0 scaffold)

**[Rule 3 - Blocking] CRUD signatures take `(db_path, engine, ...)` with `engine` documented-and-unused**
- **Found during:** Task 1
- **Issue:** The PLAN `<interfaces>` sketched `save_custom_voice(display_name, audio_src, transcript)` / `list_custom_voices()` (no args), but the authoritative Wave-0 scaffold `tests/test_custom_voices.py` calls every CRUD function positionally as `(db, engine, ...)` (e.g. `_list_voices(db, "f5")`, `save_fn(db, engine, "My Voice", str(wav), text)`). The two are positionally incompatible.
- **Fix:** Adopted `(db_path, engine, ...)` signatures (with `db_path`/`engine` optional where the test/PLAN-callers differ), keeping storage ENGINE-AGNOSTIC (keys `voice.custom.<id>`, no engine segment) per the PLAN's authoritative body + acceptance criteria — the `engine` arg is accepted for call-site symmetry but never keys storage. The UI (Task 2) passes `None` for engine. Satisfies the scaffold AND the engine-agnostic requirement.
- **Files modified:** `diana/tts/custom_voices.py`
- **Commit:** `636d757`

### Added an AppTest pre-check file (active UI policy)

**[Rule 2 - Missing critical] tests/test_custom_voices_apptest.py**
- **Found during:** Task 3
- **Issue:** The plan's Task-3 pre-check mandates AppTest interaction tests (the post-Phase-4 standing UI policy), but no Custom Voices AppTest existed.
- **Fix:** Wrote `tests/test_custom_voices_apptest.py` (3 tests) following the established `tests/test_f5_slice_apptest.py` pattern (`_tmp_heavy_paths` extended with `custom_voices_dir`, `_tmp_config`, `_texts`). Verifies the section renders both inputs, validation rejects bad input, and a saved voice surfaces in the picker + cross-engine browser and is removable.
- **Files modified:** `tests/test_custom_voices_apptest.py` (new)
- **Commit:** `7df5086`

## Checkpoint Handling

Task 3 is `type="checkpoint:human-verify"`. Auto-mode (`auto_advance: true`) was active, so per the executor's auto-mode checkpoint policy this human-verify was NOT bare-returned: the agent ran the AppTest pre-check (passed, no defects to fix), deferred the environment-dependent real-clone step to `05-HUMAN-UAT.md`, and returned `## PLAN COMPLETE`. No package-legitimacy gate was involved.

## Authentication Gates

None — no auth/login/secret was required at any task.

## Verification

- `tests/test_custom_voices.py`: 10 PASS (flipped from skip) — validation bounds (16 kHz accepted, empty-transcript rejected, too-short rejected, junk never raises), safe-dest traversal/extension `ValueError`, metadata round-trip, malformed-JSON tolerance.
- `tests/test_custom_voices_apptest.py`: 3 PASS — section renders both inputs; validation rejects bad input cleanly; saved voice in `get_engine_voices('f5')` + `all_engine_voices()`, removable.
- Full suite: `505 passed, 2 skipped (Fish — Wave 7), 1 deselected, 0 failures`.
- No-torch cheap path: `get_engine_voices('f5')` + `all_engine_voices()` leave `torch`/`f5_tts` out of `sys.modules` (asserted in the AppTest + a direct check).
- `grep -nE "import torch|import f5_tts"` on `custom_voices.py`, `f5_engine.py`, and `5_Settings.py` returns nothing.
- Engine-agnostic storage: keys are `voice.custom.<id>` (no engine segment).
- No stray audio committed; tests write under `tmp_path` (monkeypatched `custom_voices_dir`), leaving the real per-user cache untouched.

## Known Stubs

None. The library is fully wired: saved voices drive real F5 cloning through `_resolve_ref` -> `custom_voice_ref` -> the existing torch-venv worker. The only deferred item is the real torch inference (an environment dependency, documented in `05-HUMAN-UAT.md`), not a stub.

## Notes for Next Plan (05-07 Fish)

- The Custom Voices library is engine-agnostic and ready to reuse wholesale: Fish's `list_voices()`/registry branch can merge `custom_voices.list_custom_voices()` exactly like `_f5_voices`, and its `_resolve_ref` can delegate to `custom_voices.custom_voice_ref`. The in-use remove block already consults `"fish"`.
- The Settings Custom Voices section wording is engine-agnostic ("cloning engines (like F5)"), so no UI change is needed when Fish lands — its voices appear automatically once Fish's registry branch is dynamic.

## Self-Check: PASSED

- Created files verified on disk: `diana/tts/custom_voices.py`, `tests/test_custom_voices_apptest.py`, `.planning/phases/05-heavy-opt-in-engines/05-06-SUMMARY.md`.
- Modified files verified on disk: `diana/tts/f5_engine.py`, `diana/tts/registry.py`, `diana/dashboard/pages/5_Settings.py`, `.planning/phases/05-heavy-opt-in-engines/05-HUMAN-UAT.md`.
- Commits verified in git log: `636d757` (Task 1), `51dd2b8` (Task 2), `7df5086` (Task 3).
