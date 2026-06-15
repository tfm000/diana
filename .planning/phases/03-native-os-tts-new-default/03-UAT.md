---
status: partial
phase: 03-native-os-tts-new-default
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md, 03-04-SUMMARY.md, 03-05-SUMMARY.md]
started: 2026-06-15T12:00:00Z
updated: 2026-06-15T12:30:00Z
---

## Current Test

[testing paused — 1 item outstanding (Windows WinRT UAT, blocked: physical-device)]

## Tests

### 1. Convert a document with native_os (zero-download audio)
expected: Select native_os on Upload, upload a short document, start conversion → job completes and produces a playable audio file using a macOS voice, with no model download and no network call.
result: pass

### 2. Preview a native_os voice
expected: With native_os selected and a voice chosen, clicking Preview Voice plays a short audio sample of that voice.
result: pass

### 3. Settings saves native_os without a model-file error
expected: On Settings, set Default Engine = native_os and Save → no "missing model file" error (native_os skips model-path validation).
result: pass

### 4. Voice picker filters + name search (native_os)
expected: Around the Voice dropdown there are Language, Quality/Tier, and Search controls; picking a language narrows the list, typing part of an installed voice's name narrows it, clearing restores the full list with best-quality voices near the top.
result: pass

### 5. Per-engine voice memory persists
expected: Pick a native_os voice, switch engine to kokoro and back to native_os → the earlier choice is restored; survives app restart.
result: pass

### 6. Empty filter/search degrades gracefully (no crash)
expected: Searching a name with no matches (e.g. "zzzzz") shows a friendly "no voices match" message and falls back to the engine default — no KeyError crash. Clearing restores the list.
result: pass

### 7. Dismissible native_os download hint
expected: A dismissible hint pointing to the OS voice-download settings shows for native_os; clicking Dismiss removes it and it stays dismissed across restart (and on Settings).
result: pass

### 8. Windows WinRT neural synthesis on a real Windows box
expected: On Windows 10/11, native_os installs the winrt packages, pins the A1 attribute spelling, synthesizes a doc to a playable MP3 with a neural voice and no network call, enumerates voices with tiers, defaults to the OS voice, and shows the SAPI5-only D-11 note on a SAPI5-only image.
result: blocked
blocked_by: physical-device
reason: "No Windows machine at verification time; deferred to .planning/phases/03-native-os-tts-new-default/03-05-WINDOWS-UAT-DEFERRED.md to run after all other phases complete (user-approved)."

## Summary

total: 8
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 1

## Gaps

[none yet]
