---
phase: 03-native-os-tts-new-default
plan: 05
subsystem: tts
tags: [winrt, windows, native-tts, speech-synthesis, platform-marker, mocked-tests]

# Dependency graph
requires:
  - phase: 03-03
    provides: "NativeOSEngine single-class sys.platform branch with stubbed _winrt_* methods + native_os registered/default"
  - phase: 03-04
    provides: "Pure filter_voices/order_by_quality/resolve_default_voice helpers in native_os_engine.py (must not be reshaped)"
provides:
  - "Four winrt-* packages platform-gated to win32 in pyproject.toml + requirements.txt (the #1 macOS-install constraint held)"
  - "Implemented Windows WinRT branch: _winrt_synth (await + bytes(bytearray(buf))), _winrt_list_voices (tier from OneCore-in-Id), _winrt_default_voice_id"
  - "is_sapi5_only(voices) predicate + self._sapi5_only flag for the D-11 visible note"
  - "Mocked-winrt unit tests proving the buffer-protocol path and SAPI5 detection on macOS"
  - "Standalone deferred Windows UAT checklist (03-05-WINDOWS-UAT-DEFERRED.md)"
affects: [packaging, windows-ci, phase-06]

# Tech tracking
tech-stack:
  added: ["winrt-Windows.Media.SpeechSynthesis>=3.2.1 (win32-only)", "winrt-runtime>=3.2.1 (win32-only)", "winrt-Windows.Storage.Streams>=3.2.1 (win32-only)", "winrt-Windows.Foundation>=3.2.1 (win32-only)"]
  patterns: ["sys_platform=='win32' dependency marker (mirrors audioop-lts python_version marker)", "lazy in-method winrt import (never module-top)", "mock-an-absent-SDK test via patch.dict(sys.modules, {...}) with async fakes + real bytearray buffer"]

key-files:
  created:
    - .planning/phases/03-native-os-tts-new-default/03-05-WINDOWS-UAT-DEFERRED.md
  modified:
    - pyproject.toml
    - requirements.txt
    - diana/tts/native_os_engine.py
    - tests/test_native_os_engine.py

key-decisions:
  - "Windows UAT (Task 3, blocking) DEFERRED — no Windows box at execution time; user-approved batched Windows pass after all other phases. Captured in a self-contained 03-05-WINDOWS-UAT-DEFERRED.md instead of pausing at the checkpoint."
  - "Dropped the optional [windows] extra so the win32-marker count stays exactly 4 in each file (the acceptance grep's intent); markers alone satisfy the constraint."
  - "is_sapi5_only implemented as a callable @staticmethod predicate (matches the Wave-0 test scaffold flagger contract) AND used to set self._sapi5_only inside _winrt_list_voices (the plan's instance-flag requirement) — both satisfied."
  - "Upgraded test_winrt_synth_reads_buffer from a skip-on-mock-mismatch scaffold to an asserting test: async fake synth/read + a real bytearray Buffer so bytes(bytearray(buf)) is the code path proven (a DataReader path would never touch the buffer)."

patterns-established:
  - "Platform-gated C-extension deps: any Windows-only native dep gets '; sys_platform == \\'win32\\'' (pyproject) / '; sys_platform == \"win32\"' (requirements), mirroring audioop-lts."
  - "WinRT branch: bare await on _async methods (never create_task), bytes(bytearray(buffer)) read (never DataReader), winrt imported lazily inside the win32 branch only."

requirements-completed: []  # NATIVE-02/03/04/05 are NOT yet fully closed — Windows surface is pending the deferred UAT (see below). MacOS surface for 03/04/05 was completed in 03-03/03-04.

# Metrics
duration: ~4min
completed: 2026-06-15
---

# Phase 03 Plan 05: Windows WinRT Branch (new default native_os) Summary

**The Windows WinRT branch of NativeOSEngine is implemented and mock-tested on macOS, with its four C-extension deps platform-gated to win32 so the macOS install/CI never touch them; the one blocking Windows-only verification (assumption A1 + neural/SAPI5/default on a real box) is deferred to a self-contained Windows UAT checklist per explicit user approval.**

## Performance

- **Duration:** ~4 min implementation
- **Started:** 2026-06-15T10:51:19Z
- **Completed:** 2026-06-15T10:55:39Z
- **Tasks:** 2 of 3 executed (Task 3 deferred, not blocked)
- **Files modified:** 4 (1 created + 3 modified) + 1 SUMMARY

## Accomplishments

### Task 1 — Platform-gate the four winrt packages (the #1 constraint) — COMPLETE
- Added `winrt-Windows.Media.SpeechSynthesis>=3.2.1`, `winrt-runtime>=3.2.1`,
  `winrt-Windows.Storage.Streams>=3.2.1`, `winrt-Windows.Foundation>=3.2.1` to
  **both** `pyproject.toml` `dependencies` (each `; sys_platform == 'win32'`) and
  `requirements.txt` (each `; sys_platform == "win32"`), mirroring `audioop-lts`.
- **Did NOT** `pip install` them on macOS (they cannot build here — expected).
- **Verified:** marker count = 4 in each file; `pip install --dry-run -r requirements.txt`
  prints "Ignoring winrt-… markers don't match your environment" for all four;
  `import diana.tts.native_os_engine` works on macOS with no winrt installed.
- **Commit:** `4cce0cf` — `feat(03-05): platform-gate winrt deps to win32`

### Task 2 — Implement the WinRT branch with mocked-winrt tests (TDD) — COMPLETE
- Implemented the three previously-stubbed methods in
  `diana/tts/native_os_engine.py` per RESEARCH Patterns 3-4:
  - `_winrt_synth`: lazy `from winrt...` imports; `SpeechSynthesizer()`; voice match
    loop over `get_all_voices()` only when a voice id is given; `options.speaking_rate
    = max(0.5, min(6.0, speed))`; **bare** `await synthesize_text_to_stream_async(text)`;
    `Buffer(size)` + `await read_async(...)`; `return bytes(bytearray(buf))`.
  - `_winrt_list_voices`: maps each `VoiceInformation` → `TTSVoice`, tier
    `"standard" if "OneCore" in id else "compact"`, gender from `VoiceGender.FEMALE`,
    and sets `self._sapi5_only` via the predicate.
  - `_winrt_default_voice_id`: `return SpeechSynthesizer.get_default_voice().id` (D-02).
  - `is_sapi5_only(voices)` `@staticmethod` predicate (D-11): True when no voice id
    contains `"OneCore"`.
- Added the **A1 assumption comment block** documenting that the exact PyWinRT
  snake_case spelling is the Windows-UAT-pinned correction point.
- Turned the two RED scaffolds green: `test_sapi5_only_flagged` (predicate) and
  `test_winrt_synth_reads_buffer` (async-fake winrt modules + real bytearray Buffer,
  asserting the returned bytes equal what the buffer read produced).
- **Verified:** `bytearray` present; no `DataReader`; no `create_task`; no module-top
  `from winrt`/`import winrt`; no network import; macOS import works; **full suite
  379 passed** (`.venv/bin/python -m pytest -q`).
- **Commit:** `b0eaaf2` — `feat(03-05): implement Windows WinRT branch with mocked-winrt tests`

### Task 3 — Windows UAT — DEFERRED (not blocked)
- Per **explicit user approval**, the blocking Windows UAT was **not** paused on;
  instead a complete, self-contained checklist was written to
  **`.planning/phases/03-native-os-tts-new-default/03-05-WINDOWS-UAT-DEFERRED.md`**.
- It reproduces inline: the 7-step Windows verification (install 4 winrt pkgs, pin
  A1 via `dir(SpeechSynthesizer)`, neural synth → playable MP3 no network, picker
  tier/language/gender enumeration, OS DefaultVoice = default, SAPI5-only D-11 note,
  COM apartment Pitfall 4), the Task 3 acceptance criteria as a checklist, the
  relevant 03-VALIDATION "Manual-Only Verifications" rows (NATIVE-02/03/04/05 + A1),
  the requirements/decisions involved, the A1 "most likely fix point" note, and a
  "When complete" closeout procedure.

## Test Count

- Full suite: **379 passed** on macOS (was 377 before this plan; +2 from the two
  WinRT scaffolds flipping skip → pass).

## Requirements status (macOS-verified vs Windows-pending)

| Requirement | macOS | Windows surface |
|-------------|-------|------------------|
| **NATIVE-02** (WinRT neural / SAPI5 last-resort / no cloud) | branch coded + mock-tested | **PENDING** (deferred UAT) — partially satisfied: code + tests done; real-box neural synth + SAPI5 fallback + default voice unverified |
| **NATIVE-03** (dynamic OS enumeration) | verified (03-03 `say -v '?'`) | **Windows-pending** (deferred UAT Step 4) |
| **NATIVE-04** (fresh-install zero-download audio) | verified (03-03) | **Windows-pending** (deferred UAT Steps 3 & 5) |
| **NATIVE-05** (voice attributes + picker; default voice) | verified (03-04) | **Windows-pending** (deferred UAT Step 4) |

`requirements-completed` is intentionally **empty** in frontmatter — none of the
four are fully closed until the Windows UAT runs. ROADMAP/REQUIREMENTS were **not**
modified by this plan (out of scope per execution instruction).

## Deviations from Plan

### 1. [Approved deviation] Task 3 blocking checkpoint deferred, not paused
- **Found during:** plan kickoff (no Windows machine available).
- **Decision:** user explicitly approved completing Tasks 1-2 and writing a
  standalone deferred-UAT file instead of stopping at the blocking checkpoint.
- **Action:** created `03-05-WINDOWS-UAT-DEFERRED.md`; the user will run it on a
  Windows box after all other phases complete.
- **Files:** `.planning/phases/03-native-os-tts-new-default/03-05-WINDOWS-UAT-DEFERRED.md`

### 2. [Rule 3 - blocking-issue / acceptance-grep alignment] Reworded code comments
- **Issue:** acceptance criteria use `grep -Lq 'DataReader'` / no `create_task`
  (the file must not contain those tokens), but my explanatory comments initially
  said "NOT DataReader" / "NOT create_task", which would trip a literal grep.
- **Fix:** reworded the comments to describe the avoided pattern without the literal
  tokens; behavior unchanged.
- **Files:** `diana/tts/native_os_engine.py` — **Commit:** `b0eaaf2`

### 3. [Discretion] Dropped the optional `[windows]` extra
- The plan made a `[project.optional-dependencies] windows = [...]` extra
  discretionary. Adding it would double the win32-marker count to 8 and break the
  acceptance grep's `| grep -q 4` intent. The four `dependencies` markers alone
  satisfy the #1 constraint, so the extra was dropped.

The macOS install/import constraint (#1) is held and **verified** (dry-run ignores
all four winrt packages; engine imports with no winrt).

## Known Stubs

None. The three `_winrt_*` methods are fully implemented (no `NotImplementedError`
remains). The only outstanding item is the Windows-only A1 spelling confirmation,
tracked in the deferred UAT file — not a stub.

## Self-Check: PASSED

- FOUND: pyproject.toml (4 win32 markers), requirements.txt (4 win32 markers)
- FOUND: diana/tts/native_os_engine.py (winrt branch + is_sapi5_only + A1 block)
- FOUND: tests/test_native_os_engine.py (both WinRT tests passing)
- FOUND: .planning/phases/03-native-os-tts-new-default/03-05-WINDOWS-UAT-DEFERRED.md
- FOUND: commit 4cce0cf (Task 1), commit b0eaaf2 (Task 2)
- VERIFIED: full suite 379 passed; macOS import works without winrt; no module-top winrt import
