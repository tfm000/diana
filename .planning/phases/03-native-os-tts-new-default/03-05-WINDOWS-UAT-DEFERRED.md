---
phase: 03-native-os-tts-new-default
plan: 05
kind: deferred-uat
platform: windows-10-11
status: deferred
created: 2026-06-15
closes_requirements: [NATIVE-02, NATIVE-03, NATIVE-04, NATIVE-05]
decisions: [D-02, D-11]
assumption_pinned: A1
related:
  - .planning/phases/03-native-os-tts-new-default/03-05-PLAN.md
  - .planning/phases/03-native-os-tts-new-default/03-05-SUMMARY.md
---

# Plan 03-05 — Windows WinRT UAT (DEFERRED to a real Windows box)

> **This is a self-contained checklist.** You can run it on a Windows 10/11
> machine with **zero re-reading of any other file**. Everything you need —
> the exact commands, the acceptance criteria, the validation rows, the
> requirements/decisions involved — is reproduced inline below.

---

## Why this is deferred

Plan 03-05 implements the **Windows WinRT branch** of `NativeOSEngine`
(`diana/tts/native_os_engine.py`). The `winrt-*` packages are **Windows-only
C-extensions** — they cannot be built or executed on the macOS development box
(`pip install` fails with `ValueError: Unsupported compiler: unix`, which is
expected and correct). At execution time **no Windows machine was available**,
so the blocking Windows UAT (the plan's Task 3) **cannot be run now**.

This deferral was **explicitly approved by the user**: the user will run this
checklist **after all other phases are complete**, on a Windows box, as a single
batched Windows pass.

**What is already DONE and committed (macOS-testable surface — Tasks 1 & 2):**

- **Task 1** — the four `winrt-*` packages are platform-gated to `win32` in both
  `pyproject.toml` and `requirements.txt`, mirroring the `audioop-lts` marker.
  Verified on macOS: `pip install --dry-run -r requirements.txt` **ignores** all
  four (marker excludes them) and `import diana.tts.native_os_engine` still works
  with no `winrt` installed. Commit: `feat(03-05): platform-gate winrt deps to win32`.
- **Task 2** — the three WinRT methods (`_winrt_synth`, `_winrt_list_voices`,
  `_winrt_default_voice_id`) plus the `is_sapi5_only(voices)` predicate are
  implemented per RESEARCH Patterns 3-4, with **lazy in-method `winrt` imports**
  (never module-top), `await` + `bytes(bytearray(buf))` (no DataReader, no
  create_task), tier-from-`"OneCore"`-in-Id, and the D-11 SAPI5-only flag. Branch
  logic is unit-tested via **mocked winrt modules** on macOS. Commit:
  `feat(03-05): implement Windows WinRT branch with mocked-winrt tests`.

**What only a real Windows box can verify (this file):** that the *assumed* exact
PyWinRT attribute spelling (assumption **A1**) is correct, that a neural voice
produces a playable MP3 with **no network call**, that the picker enumerates
Windows voices with tier/language/gender, that the OS default voice resolves, and
that a SAPI5-only image triggers the visible D-11 note and still produces audio.

---

## Prerequisites

- A Windows 10 or Windows 11 machine.
- The Diana repository checked out on that machine.
- Python 3.10–3.13 installed.
- Ideally **two** voice configurations to test (see Step 5): one image/account
  with at least one OneCore **neural** voice installed (Settings ▸ Time &
  Language ▸ Speech ▸ add voices), and one with **only** legacy SAPI5 voices
  (David/Zira) to exercise the SAPI5-only path. If you only have one, do the
  neural pass first, then remove neural voices for the SAPI5 pass.

---

## Step-by-step Windows verification (the plan's Task 3 `<how-to-verify>`)

### Step 1 — Install the four winrt packages

```bat
python -m venv .venv
.venv\Scripts\activate
pip install "winrt-Windows.Media.SpeechSynthesis>=3.2.1" "winrt-runtime>=3.2.1" "winrt-Windows.Storage.Streams>=3.2.1" "winrt-Windows.Foundation>=3.2.1"
```

**Expected:** the install **succeeds** (Windows wheels exist for all four). If a
build/compile error appears, confirm you are on Windows (these are Windows-only).
Then install the rest of Diana's deps: `pip install -r requirements.txt`.

### Step 2 — PIN assumption A1 (the single most likely fix point)

```bat
python -c "import winrt.windows.media.speechsynthesis as s; print([n for n in dir(s.SpeechSynthesizer) if not n.startswith('__')])"
```

Confirm the **real** member names against what `diana/tts/native_os_engine.py`
currently assumes:

| Used in the code (assumed) | Confirm the real name |
|----------------------------|------------------------|
| `SpeechSynthesizer.get_all_voices()` | all-voices accessor (vs `.all_voices`) |
| `SpeechSynthesizer.get_default_voice()` | default-voice accessor (vs `.default_voice`) |
| `synth.voice = v` | the voice **setter** |
| `synth.synthesize_text_to_stream_async(text)` | async synth method |
| `synth.options.speaking_rate` | speaking-rate option |
| `v.id` / `v.display_name` / `v.language` / `v.gender` | `VoiceInformation` props |
| `winrt.windows.storage.streams.Buffer`, `InputStreamOptions.NONE` | buffer + read option |

> **If any name differs from the code, correct the WinRT branch in
> `native_os_engine.py` to match the real spelling, then re-run the steps.**
> This is **the** expected correction point (assumption A1 is MEDIUM-confidence).
> Also useful: inspect the installed `.pyi` stub for the module to see the full
> projected surface.

### Step 3 — Neural synth → playable MP3, no network (NATIVE-02 / NATIVE-04)

Launch Diana, select the **native_os** engine, pick a neural voice, and convert a
short document.

**Expected:** a **non-robotic neural voice** is used (when OneCore voices are
installed) and a **playable MP3** is produced — with **NO network call**
(confirm via a network monitor / firewall, or simply note Diana never reaches the
network for synthesis; `edge-tts`/cloud is forbidden and not imported).

### Step 4 — Picker enumeration + default voice (NATIVE-03 / NATIVE-05 / D-02)

In the voice picker, confirm:

- Installed **neural** voices appear with tier **"standard"**.
- Any **legacy** voices appear with tier **"compact"**.
- Language and gender are populated best-effort from WinRT metadata.
- With **no per-engine override** set, the default resolves to the **OS
  `DefaultVoice`** (`SpeechSynthesizer.get_default_voice().id`) — **decision D-02**
  (native OS default = the OS system default voice).

### Step 5 — SAPI5 last-resort visible note (NATIVE-04 / D-11)

On an image/account with **neural voices removed** (or a minimal image with only
David/Zira):

**Expected:** the **visible SAPI5 note appears** (the D-11 last-resort flag —
`is_sapi5_only()` returns True when no voice Id contains `"OneCore"`), the D-10
download hint is shown, **and audio is still produced** (fresh-install
zero-download, NATIVE-04).

### Step 6 — COM apartment note (Pitfall 4)

If a **COM apartment `RuntimeError`** appears (mentioning apartment /
single-threaded):

- Confirm the **async `await`** path is used (NOT the blocking `.get()` variant).
  Diana's worker is a plain daemon thread with its own asyncio loop, so `await`
  is the documented-safe option there.
- If it still occurs, apply the documented `winrt.runtime` init / MTA fix.

### Step 7 — Record findings

Record the pinned attribute names and any code corrections (Step 2), plus the
results of Steps 3-6, back into `03-05-SUMMARY.md` (see "When complete" below).

---

## Acceptance criteria (the plan's Task 3 — explicit checklist)

- [ ] The exact PyWinRT attribute names are **pinned** from `dir(SpeechSynthesizer)`
      on a real Windows box; `native_os_engine.py` **matches them** (corrected if
      the assumed spelling was wrong). **(A1 closed)**
- [ ] On Windows, native_os synthesizes a short document to a **playable MP3**
      using a **neural voice** with **no network call**. **(NATIVE-02 / NATIVE-04)**
- [ ] The picker **enumerates** installed Windows voices with best-effort
      tier/language/gender. **(NATIVE-03 / NATIVE-05)**
- [ ] A **SAPI5-only** configuration triggers the **visible D-11 note** and still
      produces audio. **(NATIVE-04)**
- [ ] Findings (pinned names, any corrections, COM notes) **recorded in
      03-05-SUMMARY.md**.

---

## Relevant rows from 03-VALIDATION.md — "Manual-Only Verifications"

> Reproduced inline so you do not need to open `03-VALIDATION.md`.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Windows WinRT neural synthesis returns WAV bytes | **NATIVE-02** | `winrt-*` C-extensions are Windows-only; cannot build/run on the macOS dev box | On a Windows 10/11 box: select `native_os`, convert a short doc, confirm a non-robotic neural voice and a playable MP3. |
| Exact PyWinRT attribute spelling (assumption **A1**) | **NATIVE-02/03** | snake_case projection documented but exact member names unverifiable on macOS | On Windows: `python -c "import winrt.windows.media.speechsynthesis as s; print(dir(s.SpeechSynthesizer))"` — pin `get_all_voices()` vs `.all_voices`, `default_voice`, `voice` setter before finalizing the WinRT branch. |
| Windows voice enumeration shows OneCore neural + SAPI5 tiers | **NATIVE-03/05** | Requires real WinRT `AllVoices` on a Windows image | On Windows: confirm the picker lists installed neural voices; with neural voices removed, confirm SAPI5-only triggers the visible D-11 note. |
| Fresh-install zero-download audio on Windows | **NATIVE-04** | Clean Windows image required to confirm out-of-box voice availability | On a clean Win10/11 image with no Diana downloads: convert a doc, confirm audio with no network call. |
| Default voice = OS system default on Windows | **NATIVE-02** | Requires WinRT `DefaultVoice` on a real box | On Windows: with no per-engine override set, confirm synthesis uses `SpeechSynthesizer.DefaultVoice`. |

*macOS equivalents of all the above are covered by automated unit + smoke tests
on the dev box (already green: 379 passed).*

---

## Requirements this UAT closes

| Requirement | Text | macOS status | Windows status (this UAT) |
|-------------|------|--------------|---------------------------|
| **NATIVE-02** | The Windows backend uses WinRT `SpeechSynthesizer` for neural voices (SAPI5 only as a last-resort fallback; no cloud `edge-tts`) | branch coded + mock-tested | **PENDING** — Steps 2-5 confirm neural synth + SAPI5 fallback + default voice on a real box |
| **NATIVE-03** | System voices are enumerated dynamically from the OS on both platforms | macOS-verified (`say -v '?'`) | Windows surface **PENDING** — Step 4 confirms WinRT enumeration |
| **NATIVE-04** | A fresh install produces audio with zero downloads using native OS voices | macOS-verified | Windows surface **PENDING** — Steps 3 & 5 confirm zero-download audio (incl. SAPI5-only) |
| **NATIVE-05** | Enumerated voices carry descriptive attributes (language/bilingual, quality tier, gender) … best-effort from WinRT metadata on Windows … picker filters/search; each engine exposes a default voice (native OS = OS system default) | macOS-verified | Windows surface **PENDING** — Step 4 confirms tier/language/gender + default |

## Locked decisions involved

- **D-02** — the native OS default voice **is the OS system default voice** (on
  Windows, `SpeechSynthesizer.get_default_voice().id`; never a snapshotted concrete
  id so the OS can change it later). Verified in Step 4.
- **D-11** — when **only** SAPI5 voices are present (no OneCore neural voice), a
  **visible note** is surfaced (last-resort), and audio is still produced.
  Verified in Step 5.

---

## A1 spelling note (read before touching code)

The exact PyWinRT attribute spelling in `diana/tts/native_os_engine.py` is
**ASSUMED** (assumption A1, MEDIUM confidence). The code currently uses:

- `SpeechSynthesizer.get_all_voices()`
- `SpeechSynthesizer.get_default_voice()`
- `synth.voice = v`  (setter)
- `synth.synthesize_text_to_stream_async(text)`
- `synth.options.speaking_rate`
- `v.id`, `v.display_name`, `v.language`, `v.gender` (and `VoiceGender.FEMALE`)
- `winrt.windows.storage.streams.Buffer`, `InputStreamOptions.NONE`

**This is the most likely correction point.** If Step 2's
`dir(SpeechSynthesizer)` (or the installed `.pyi` stub) shows different names
(e.g. `.all_voices` instead of `get_all_voices()`), **fix the WinRT branch to
match the real spelling and re-run** Steps 3-6. The branch's *structure* (await +
`bytes(bytearray(buf))`, tier-from-Id, SAPI5 flag, default = default voice id) is
verified-correct; only the member names may need adjusting.

---

## When complete

1. Run Steps 1-6 on the Windows box.
2. **Record** the pinned PyWinRT attribute names and any code corrections made to
   `diana/tts/native_os_engine.py` (commit any corrections with a
   `fix(03-05): ...` message).
3. Confirm each acceptance-criteria checkbox above.
4. **Update `03-05-SUMMARY.md`** with the findings (pinned names, corrections,
   COM notes, neural/SAPI5/default results) and flip NATIVE-02 (and the Windows
   surface of NATIVE-03/04/05) to verified there.
5. This deferred item is then **closed** — update STATE.md's Deferred Items table
   row accordingly.
