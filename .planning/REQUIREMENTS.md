# Requirements: Diana

**Defined:** 2026-05-29
**Core Value:** Convert documents into listenable audiobooks entirely on-device — so even private or sensitive files can be turned into audio without sending them anywhere.

## v1 Requirements

Requirements for this milestone. Each maps to a roadmap phase.

### Engine Removal

- [x] **RETIRE-01**: ElevenLabs and OpenAI TTS engines removed from the registry, config schema, and all dashboard UI surfaces

### Platform & Storage

- [x] **PLAT-01**: Application data (DB, models, voices, config, output) stored in OS-appropriate per-user directories via `platformdirs`, with all paths derived from a single resolver
- [ ] **PLAT-02**: App runs on Windows as a first-class target — `pathlib`-based paths, ffmpeg handled cross-platform, SQLite WAL stable under worker+UI contention on Windows

### Privacy / LLM Control

- [x] **PRIV-01**: User can toggle LLM cleaning on/off per job in the audiobook (Upload) flow
- [x] **PRIV-02**: User can toggle LLM cleaning on/off on the News page
- [x] **PRIV-03**: The toggle remembers the user's last choice (persisted beyond the Streamlit session)
- [x] **PRIV-04**: Toggle is disabled with an explanation when no LLM provider is configured; with LLM off, News converts cleaned raw text to audio instead of summarizing *(Upload half satisfied by 01-03 — UI gating + pipeline-level enforcement at `if want_llm and llm_cfg is not None`; News half satisfied by 01-04 — `build_digest_text` LLM-OFF digest path creates one `Job(file_type="txt", use_llm=False)` of cleaned article prose with no titles/summaries/categories)*

### Rule-Based Cleaner Overhaul

- [x] **CLEAN-01**: Cleaner removes or replaces images/figures so they don't disrupt the audio
- [x] **CLEAN-02**: Cleaner strips running headers/footers and page numbers (format-aware: PDF / EPUB / TXT)
- [x] **CLEAN-03**: Cleaner handles inline citations, footnote markers, and footnote-body blocks
- [x] **CLEAN-04**: Cleaner linearizes or skips tables sensibly for speech
- [x] **CLEAN-05**: Cleaner handles code blocks, list markers, and URLs
- [x] **CLEAN-06**: Cleaner normalizes numbers, currency, percentages, and common abbreviations for natural speech
- [x] **CLEAN-07**: Existing over-stripping bugs fixed (short-line guard; non-ASCII text preserved for engines that support it)
- [x] **CLEAN-08**: A golden-corpus regression test suite guards cleaner output quality

### Native OS TTS (Default)

- [ ] **NATIVE-01**: `NativeOSEngine` is the default engine; the macOS backend uses `say`
- [ ] **NATIVE-02**: The Windows backend uses WinRT `SpeechSynthesizer` for neural voices (SAPI5 only as a last-resort fallback; no cloud `edge-tts`)
- [ ] **NATIVE-03**: System voices are enumerated dynamically from the OS on both platforms
- [ ] **NATIVE-04**: A fresh install produces audio with zero downloads using native OS voices

### Engine & Model Management

- [ ] **ENGINE-01**: Engine availability/capability is detected cheaply, without importing heavy dependencies
- [ ] **ENGINE-02**: Models/weights download on demand with visible byte progress, resumability, and a disk-space pre-check
- [ ] **ENGINE-03**: The engine picker shows install state and download-footprint badges (e.g. "Ready" / "~2.4 GB, downloads on first use")
- [ ] **ENGINE-04**: Downloads land in the per-user cache and are triggered only from the UI, never inside the worker/job

### Voice Management

- [ ] **VOICE-01**: User can browse a Piper voice catalog (from the voices manifest) in-app
- [ ] **VOICE-02**: User can download and install catalog voices without using a terminal
- [ ] **VOICE-03**: User can preview a voice (pre-recorded sample if not downloaded; live synthesis if installed)
- [ ] **VOICE-04**: User can manually import a downloaded Piper voice (`.onnx` + `.onnx.json`) via the UI
- [ ] **VOICE-05**: User can select the voice per job

### Heavy Opt-In Engines

- [ ] **HEAVY-01**: Orpheus engine available (llama-cpp-python + GGUF, CPU-viable) with named voices
- [ ] **HEAVY-02**: F5-TTS engine available (on-demand torch) with reference-audio voice cloning + clip validation, behind an in-app non-commercial license disclosure shown before download
- [ ] **HEAVY-03**: Fish Audio S2 Pro engine available, GPU-gated (hidden unless a capable GPU is detected), opt-in, with non-commercial license disclosure

### Packaging & Distribution

- [ ] **PKG-01**: A launcher starts Diana as a desktop window (free-port probe, headless Streamlit, file-watcher disabled)
- [ ] **PKG-02**: A PyInstaller `--onedir` build collects Streamlit assets/metadata and onnxruntime, and excludes torch from the base bundle
- [ ] **PKG-03**: A static ffmpeg binary is bundled per OS and used explicitly (not assumed on PATH)
- [ ] **PKG-04**: Produces a double-click macOS `.app` and Windows `.exe`/installer, shipped unsigned with documented Gatekeeper/SmartScreen bypass steps
- [ ] **PKG-05**: A Windows CI runner is added; the packaged artifact is verified on clean macOS and Windows machines

### Production Hardening

- [ ] **HARD-01**: JobWorker is bound to the server lifetime (e.g. `st.cache_resource`) so reloads don't spawn duplicate workers
- [ ] **HARD-02**: SQLite writes retry with backoff on `OperationalError` (WAL lock contention, aggravated on Windows)
- [ ] **HARD-03**: Security fixes — escape news source/group names (XSS), validate manual voice-import paths (traversal), whitelist `update_job_status` kwargs
- [ ] **HARD-04**: Resilience pass + an offline smoke test confirming core conversion works fully offline

## v2 Requirements

Deferred to a future release. Tracked but not in this roadmap.

### Future

- **VNEXT-01**: Unified cross-engine voice browser (dedicated page)
- **VNEXT-02**: Cleaned-text preview pane before rendering audio
- **VNEXT-03**: Full number-to-words / date verbalization beyond currency/percent/abbreviation
- **VNEXT-04**: Per-chunk engine switching or multi-voice books
- **VNEXT-05**: Code signing + notarization (shipping unsigned for now)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| ElevenLabs / OpenAI / any hosted TTS API | TTS must run on-device (privacy + offline core value) |
| Other heavy engines (Coqui XTTS, StyleTTS2, MeloTTS, Chatterbox) | Avoid packaging/perf burden beyond the chosen lineup |
| Linux as a supported target | Focus is Windows + macOS; Linux untested |
| Cloud deployment, containerization, multi-user, auth | Diana is a local single-user desktop app |
| Bundling heavy models in the installer | Keeps the default install small; models download on demand |

## Traceability

Each v1 requirement maps to exactly one phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| RETIRE-01 | Phase 1 | Complete |
| PLAT-01 | Phase 1 | Complete |
| PLAT-02 | Phase 6 | Pending |
| PRIV-01 | Phase 1 | Complete |
| PRIV-02 | Phase 1 | Complete |
| PRIV-03 | Phase 1 | Complete |
| PRIV-04 | Phase 1 | Complete (Upload half via 01-03; News half via 01-04) |
| CLEAN-01 | Phase 2 | Complete |
| CLEAN-02 | Phase 2 | Complete |
| CLEAN-03 | Phase 2 | Complete |
| CLEAN-04 | Phase 2 | Complete |
| CLEAN-05 | Phase 2 | Complete |
| CLEAN-06 | Phase 2 | Complete |
| CLEAN-07 | Phase 2 | Complete |
| CLEAN-08 | Phase 2 | Complete |
| NATIVE-01 | Phase 3 | Pending |
| NATIVE-02 | Phase 3 | Pending |
| NATIVE-03 | Phase 3 | Pending |
| NATIVE-04 | Phase 3 | Pending |
| ENGINE-01 | Phase 4 | Pending |
| ENGINE-02 | Phase 4 | Pending |
| ENGINE-03 | Phase 4 | Pending |
| ENGINE-04 | Phase 4 | Pending |
| VOICE-01 | Phase 4 | Pending |
| VOICE-02 | Phase 4 | Pending |
| VOICE-03 | Phase 4 | Pending |
| VOICE-04 | Phase 4 | Pending |
| VOICE-05 | Phase 4 | Pending |
| HEAVY-01 | Phase 5 | Pending |
| HEAVY-02 | Phase 5 | Pending |
| HEAVY-03 | Phase 5 | Pending |
| PKG-01 | Phase 6 | Pending |
| PKG-02 | Phase 6 | Pending |
| PKG-03 | Phase 6 | Pending |
| PKG-04 | Phase 6 | Pending |
| PKG-05 | Phase 6 | Pending |
| HARD-01 | Phase 7 | Pending |
| HARD-02 | Phase 7 | Pending |
| HARD-03 | Phase 7 | Pending |
| HARD-04 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 40 total
- Mapped to phases: 40 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-29*
*Last updated: 2026-05-31 after Phase 01 plan 04 completion (PRIV-02 satisfied; PRIV-04 News half satisfied — combined with 01-03's Upload-half, PRIV-04 is now fully complete). All four Phase-01 plans implemented; phase row close-out (and the v1 RETIRE-01/PLAT-01/PRIV-01..04 status surface) is left for the orchestrator's verifier / roadmap-update pass.*
