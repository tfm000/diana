# Roadmap: Diana

## Overview

Diana is a working brownfield Streamlit audiobook app. This milestone reshapes it into a private, cross-platform, double-click product. The journey starts by removing cloud TTS and moving storage to per-user OS directories (the prerequisite for on-demand downloads and packaging), while shipping the per-job LLM-cleaning toggle that delivers the core privacy promise immediately. With LLM cleaning now optional, the rule-based cleaner is overhauled into a trustworthy primary path. A zero-setup native OS engine becomes the new default so a fresh install makes audio with no downloads. A shared engine/model-management layer then powers an in-app Piper voice catalog, and that same substrate carries the heavy opt-in engines (Orpheus, F5-TTS, Fish S2 Pro). Finally the proven, lightweight runtime is frozen into signed-or-documented double-click `.app`/`.exe` bundles with first-class Windows support, and a hardening pass closes out correctness, resilience, and security before release.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation & Privacy Toggle** - Remove cloud TTS, migrate storage to per-user dirs, ship per-job LLM-cleaning toggle *(all 4 plans implemented 2026-05-31; awaiting orchestrator phase-verifier / roadmap-update pass for the official close-out)*
- [x] **Phase 2: Rule-Based Cleaner Overhaul** - Make the LLM-off cleaning path trustworthy, guarded by a golden-corpus suite (completed 2026-06-01)
- [ ] **Phase 3: Native OS TTS (New Default)** - Zero-download default engine using macOS `say` / Windows WinRT neural voices
- [ ] **Phase 4: Engine Management & Voice Catalog** - On-demand model downloads + in-app Piper voice browse/install/preview/import
- [ ] **Phase 5: Heavy Opt-In Engines** - Orpheus, F5-TTS, and GPU-gated Fish S2 Pro as opt-in installs on the shared substrate
- [ ] **Phase 6: Packaging & First-Class Windows** - Double-click macOS `.app` / Windows `.exe` with bundled ffmpeg and Windows CI
- [ ] **Phase 7: Production Hardening** - Worker lifetime, SQLite retry, security fixes, and an offline smoke test as the release gate

## Phase Details

### Phase 1: Foundation & Privacy Toggle

**Goal**: Cloud TTS is gone, all app data lives in OS-appropriate per-user directories behind a single path resolver, and users control LLM cleaning per job — delivering the privacy promise immediately while unblocking downloads and packaging.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: RETIRE-01, PLAT-01, PRIV-01, PRIV-02, PRIV-03, PRIV-04
**Success Criteria** (what must be TRUE):

  1. ElevenLabs and OpenAI TTS no longer appear anywhere in the engine picker, config, or UI, and the app still runs
  2. App reads and writes its DB, config, and output from the OS per-user data directory (e.g. `~/Library/Application Support/Diana`), with no relative `data/...` paths remaining
  3. User can flip an LLM-cleaning toggle per job on both the Upload and News pages, and the choice survives an app restart
  4. With no LLM provider configured, the toggle is disabled with a clear explanation; with LLM off, News converts cleaned raw article text to audio instead of summarizing

**Plans**: 4 plans
Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Per-user storage foundation: platformdirs resolver, resolver-backed config defaults + relocation, delete_job fix, ensure_dirs at startup (PLAT-01)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Remove cloud TTS: delete OpenAI/ElevenLabs engines, trim registry/config/UI, stale-engine fallback (RETIRE-01)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — Per-job LLM toggle (Upload): Job.use_llm + app_settings store + pipeline gate + durable default-OFF Upload toggle (PRIV-01, PRIV-03, PRIV-04 gate)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-04-PLAN.md — News toggle + LLM-off digest: build_digest_text helper + durable News toggle + single-digest fetch path (PRIV-02, PRIV-04)

**UI hint**: yes

### Phase 2: Rule-Based Cleaner Overhaul

**Goal**: The rule-based cleaner — now the primary cleaning path when LLM is off — produces natural, accurate audio across PDF/EPUB/TXT without silently destroying legitimate content.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: CLEAN-01, CLEAN-02, CLEAN-03, CLEAN-04, CLEAN-05, CLEAN-06, CLEAN-07, CLEAN-08
**Success Criteria** (what must be TRUE):

  1. A document with images, headers/footers, page numbers, citations, footnotes, and tables produces clean spoken audio with no stray figure/table/footnote noise
  2. Numbers, currency, percentages, and common abbreviations are spoken naturally (e.g. "$5" reads as "five dollars")
  3. Short headings and non-ASCII text are preserved (no over-stripping) for engines that support them
  4. A golden-corpus regression suite passes and fails loudly when cleaner output quality regresses

**Plans**: 4 plans
Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Architecture seam + stop destroying content: widen `clean_text(text, *, source_format, ascii_only)`, `engine_is_ascii_only` registry map, wire all 3 call sites + llm_cleaner ASCII net, narrow the 3 over-strippers, engine-conditional transliteration (café→cafe never caf), two-layer corpus harness (CLEAN-02, CLEAN-04, CLEAN-07, CLEAN-08)

**Wave 2** *(blocked on Wave 1 — same-file `cleaner.py`)*

- [x] 02-02-PLAN.md — Spoken normalization: currency/percent symbol→word run before the math-aware `$…$` remover (the proven-mandatory ordering), curated abbreviation expansion (CLEAN-06)

**Wave 3** *(blocked on Wave 2 — same-file `cleaner.py`)*

- [x] 02-03-PLAN.md — Code/lists/URLs: code-block removal before noise detection, list-marker strip after chart protection, URL+email removal with `U.S.`/`e.g.` guard (CLEAN-05)

**Wave 4** *(blocked on Wave 3 — same-file `cleaner.py`)*

- [x] 02-04-PLAN.md — Figures/captions/footnotes + corpus completion: caption-keep vs reference-remove + dangling repair, superscript footnote markers, best-effort footnote bodies, full CLEAN-01..08 corpus + planted-regression loud-failure check (CLEAN-01, CLEAN-03, CLEAN-08)

**UI hint**: no

### Phase 3: Native OS TTS (New Default)

**Goal**: A fresh install makes audio out of the box with zero downloads, using the operating system's own voices as the default engine on both macOS and Windows.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: NATIVE-01, NATIVE-02, NATIVE-03, NATIVE-04
**Success Criteria** (what must be TRUE):

  1. On a fresh install with nothing downloaded, the user can convert a document to audio using a native OS voice
  2. `NativeOSEngine` is preselected as the default engine, using `say` on macOS and WinRT neural voices on Windows (SAPI5 only as a visible last-resort fallback, never `edge-tts`)
  3. The voice list reflects the voices actually installed on the user's OS, enumerated dynamically on both platforms
  4. Synthesis runs on the worker without freezing the dashboard, and no cloud call is made

**Plans**: TBD
**UI hint**: yes
**Research note**: Windows WinRT `SpeechSynthesizer` bindings and OneCore neural-voice enumeration are MEDIUM confidence — flag this phase for `/gsd:plan-phase --research-phase` to re-verify the projection package names, async stream-to-WAV path, and offline voice availability on a clean Windows 10/11 image.

### Phase 4: Engine Management & Voice Catalog

**Goal**: Users can discover, install, preview, and use additional voices entirely in-app — powered by a shared on-demand model-download layer that is proven end-to-end by the Piper voice catalog before any heavy engine relies on it.
**Mode:** mvp
**Depends on**: Phase 1 (per-user storage), Phase 3 (dynamic voice-listing path)
**Requirements**: ENGINE-01, ENGINE-02, ENGINE-03, ENGINE-04, VOICE-01, VOICE-02, VOICE-03, VOICE-04, VOICE-05
**Success Criteria** (what must be TRUE):

  1. The engine picker shows each engine's install state and download footprint (e.g. "Ready" / "~2.4 GB, downloads on first use") without triggering heavy imports
  2. User can browse the Piper voice catalog, download a voice with visible byte progress and a disk-space pre-check, and have an interrupted download resume rather than restart
  3. User can preview any voice (pre-recorded sample if not installed, live synthesis if installed) and select a specific voice per job
  4. User can manually import a downloaded Piper voice (`.onnx` + `.onnx.json`) through the UI, and all downloads land in the per-user cache triggered only from the UI — never inside a running job

**Plans**: TBD
**UI hint**: yes

### Phase 5: Heavy Opt-In Engines

**Goal**: Power users can opt into higher-quality neural engines (Orpheus, F5-TTS, and GPU-gated Fish S2 Pro) as on-demand installs layered on the Phase 4 substrate, with licensing surfaced before download and no impact on the lightweight default install.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: HEAVY-01, HEAVY-02, HEAVY-03
**Success Criteria** (what must be TRUE):

  1. User can install and synthesize with Orpheus (llama-cpp-python + GGUF, CPU-viable) using its named voices
  2. User can install F5-TTS on demand, see and accept an in-app non-commercial license disclosure before download, and clone a voice from a validated reference-audio clip
  3. Fish Audio S2 Pro is hidden unless a capable GPU is detected; when shown, it is opt-in and presents its non-commercial license disclosure before download
  4. Choosing a heavy engine without its model installed fails fast with an actionable prompt rather than erroring mid-job

**Plans**: TBD
**Research note**: Heavy-engine Python APIs are fast-moving (MEDIUM confidence) — flag this phase for `/gsd:plan-phase --research-phase` to re-verify llama-cpp-python Metal/CPU wheel availability, model repo IDs/revisions, and inference signatures for Orpheus and F5-TTS at plan time.

### Phase 6: Packaging & First-Class Windows

**Goal**: Diana ships as a double-click desktop app on both macOS and Windows — no terminal, no Python install — with the proven lightweight runtime frozen, ffmpeg bundled, and Windows verified as a first-class target on a clean machine.
**Mode:** mvp
**Depends on**: Phase 3 (light default engine), Phase 4 (on-demand download proven)
**Requirements**: PLAT-02, PKG-01, PKG-02, PKG-03, PKG-04, PKG-05
**Success Criteria** (what must be TRUE):

  1. Double-clicking the macOS `.app` or Windows `.exe`/installer launches Diana in a desktop window on a clean machine with no Python, picks a free port, and runs headless with the file-watcher disabled
  2. The packaged app converts a document to audio end-to-end (including MP3 output via a bundled static ffmpeg, not assumed on PATH), with torch excluded from the base bundle
  3. The app runs as a first-class Windows target — `pathlib` paths, cross-platform ffmpeg, and SQLite WAL stable under worker+UI contention on Windows
  4. A Windows CI runner builds the artifact, and the bundle is verified on clean macOS and Windows machines with documented Gatekeeper/SmartScreen bypass steps for the unsigned release

**Plans**: TBD
**Research note**: Signing/notarization (shipping unsigned per Key Decisions) and PyInstaller hook compatibility with the current Streamlit version are MEDIUM confidence — flag this phase for `/gsd:plan-phase --research-phase` to re-verify Streamlit asset/metadata collection hooks and the macOS hardened-runtime entitlement set against the actual build artifact.

### Phase 7: Production Hardening

**Goal**: Diana is resilient, secure, and verifiably offline — the correctness, robustness, and security issues that don't block earlier phases are closed out as the final release gate.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: HARD-01, HARD-02, HARD-03, HARD-04
**Success Criteria** (what must be TRUE):

  1. Reloading the Streamlit server never spawns duplicate JobWorkers (worker bound to server lifetime)
  2. SQLite writes survive WAL lock contention by retrying with backoff instead of failing, even under Windows worker+UI load
  3. Security holes are closed: news source/group names are escaped (no XSS), manual voice-import paths are validated against traversal, and `update_job_status` only accepts whitelisted kwargs
  4. An offline smoke test confirms the core upload → convert → audio pipeline works with no network access

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Privacy Toggle | 4/4 | In Progress (all plans implemented; awaiting phase verifier / roadmap-update pass) | - |
| 2. Rule-Based Cleaner Overhaul | 4/4 | Complete   | 2026-06-01 |
| 3. Native OS TTS (New Default) | 0/TBD | Not started | - |
| 4. Engine Management & Voice Catalog | 0/TBD | Not started | - |
| 5. Heavy Opt-In Engines | 0/TBD | Not started | - |
| 6. Packaging & First-Class Windows | 0/TBD | Not started | - |
| 7. Production Hardening | 0/TBD | Not started | - |
