# Phase 5: Heavy Opt-In Engines - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Add three heavy, **opt-in, on-demand, local** TTS engines — **Orpheus** (llama-cpp-python + GGUF, CPU-viable), **F5-TTS** (on-demand torch, reference-audio voice cloning), and **Fish Audio S2 Pro** (GPU-gated) — each plugging into the **proven Phase 4 download/cache/install/badge/uninstall substrate** and the existing `TTSEngine` Protocol. **All three must be installable in-app this phase** (all must-have, none deferred, no fallback slip).

The **lightweight default install** (native OS / Kokoro / Piper) stays **untouched** — heavy engines, their Python runtime deps (torch, llama-cpp-python), and their model weights are fetched **only when the user opts in**. This phase also introduces a reusable, engine-agnostic **"Custom Voices"** capture/upload section (built for F5 cloning now, ready for future cloning-capable models).

**Requirements covered:** HEAVY-01 (Orpheus), HEAVY-02 (F5-TTS + reference-audio cloning + clip validation + NC-license disclosure), HEAVY-03 (Fish S2 Pro GPU-gated + NC-license disclosure). ROADMAP success criteria #1–#4.

**Out of this phase (→ later):**
- Packaging/freezing the app, bundling ffmpeg, Windows CI → **Phase 6** — *but the "install Python deps into a venv from inside an eventually-frozen app" question is researched HERE because it gates heavy installs.*
- Production hardening (worker lifetime, SQLite retry, XSS/traversal, offline smoke) → **Phase 7**.

</domain>

<decisions>
## Implementation Decisions

### Scope & build order
- **D-01:** **All three engines (Orpheus, F5-TTS, Fish S2 Pro) ship as in-app installs this phase — all must-have, no fallback slip.** No mandated "first" engine; the planner sequences waves, recommended as a **shared heavy-engine install scaffold first, then one vertical slice per engine** (MVP mode = vertical slices: install → select → synthesize end-to-end per engine).
- **D-02:** **The lightweight default install is untouched.** Heavy engines + their Python deps + weights are fetched only on opt-in; nothing heavy is added to the base bundle (consistent with PKG-02 "torch excluded from base").

### Heavy-engine install UX (HEAVY-01/02/03, ENGINE-02/03/04)
- **D-03:** **One-action install per engine.** A single "Install" button handles BOTH the Python runtime deps (torch ~2–3 GB for F5/Fish; a llama-cpp-python wheel for Orpheus) AND the model weights, with combined status — no terminal. Shared-torch optimization: once F5 installs torch, Fish only needs its own model.
- **D-04:** **Itemized footprint confirm + disk pre-check before any bytes.** The confirm breaks out deps vs model (e.g. "torch 2.4 GB + model 1.1 GB"), plus a free-vs-needed disk check (reuse `diana/downloads/downloader.py::has_space`), extending Phase-4 D-04's >200 MB confirm. Refuse to start if space is insufficient (Phase-4 D-05).
- **D-05:** **Heavy Python deps install into an isolated venv** — never the global/system environment — so the base app stays clean and heavy deps don't pollute the core runtime. *(RESEARCH FLAG: provisioning + populating that venv and pip-installing torch/llama-cpp **from inside an eventually-frozen PyInstaller app**, with no terminal, is the load-bearing technical risk of this phase. It intersects Phase 6 packaging / PKG-02. Resolve the mechanism — managed venv, bundled pip, prebuilt wheels — before committing the install plan.)*
- **D-06:** **No-terminal is non-negotiable.** The in-app installer must do everything (deps + weights) with zero terminal use. No documented-command fallback — research/plan must find an in-app mechanism even if it is more work.
- **D-07:** **Reuse the Phase-4 download substrate for weights** (download_file / `.part` / md5 / atomic os.replace; byte progress via `dl_state` + `@st.fragment`; **UI-triggered-only, off the worker** — ENGINE-04; per-user cache via `paths.py`), and **extend it for Python-package installation** (the genuinely new capability vs Phase 4, which downloaded only files).

### License + GPU gates (HEAVY-02/03)
- **D-08:** **Accept-once-per-engine NC-license gate (blocking).** The first install of F5 / Fish shows the non-commercial license and requires an explicit "I accept" **before any download**; acceptance is persisted in `app_settings` (mirroring the Phase-3 dismissible-hint / Phase-4 prefs pattern) so re-installs don't re-prompt. The disclosure names "non-commercial / personal use only" and links the actual license text.
- **D-09:** **Fish "capable GPU" definition is deferred to research.** RESEARCH must determine whether `fish-speech` actually runs on Apple Silicon (MPS) or is effectively NVIDIA-CUDA-only, and the realistic VRAM floor (~12–24 GB), then the gate is set from those findings.
- **D-10:** **Fish is SHOWN BUT DISABLED with a reason when no capable GPU is detected** (e.g. "requires a capable GPU (~12+ GB VRAM)") — **NOT hidden.** Protective intent preserved (cannot install/use without a GPU) with better discoverability. ⚠️ **This REFINES HEAVY-03 + ROADMAP success-criterion #3, which currently read "hidden unless a capable GPU is detected."** **ACTION: reconcile `REQUIREMENTS.md` HEAVY-03 and `ROADMAP.md` SC#3 wording** ("hidden" → "shown-but-disabled-with-reason") so the phase verifier checks the intended behavior.

### F5 voice cloning + reusable "Custom Voices" section (HEAVY-02)
- **D-11:** **A reusable, engine-agnostic "Custom Voices" section in Settings ▸ Voices** — built for F5 cloning now and reusable by future cloning-capable models. Two input methods:
  - **Upload:** an audio file (mp3) **+** a text file containing the transcript of what's said.
  - **In-app capture:** record the voice through the app (microphone — likely Streamlit `st.audio_input`) **+** a text box to type what was said.
- **D-12:** **The transcript is always user-provided** (file or typed) — no auto-transcribe, **no extra speech-to-text dependency** to install on top of torch.
- **D-13:** **Clip validation** (HEAVY-02 "+ clip validation"): validate audio format + length and require a non-empty transcript; reject bad input with a **clear message** (reuse the Phase-4 import-rejection pattern — never crash). Exact bounds (duration window, accepted formats, max size, sample-rate handling) = Claude's discretion, research-informed by F5-TTS's reference-audio requirements.
- **D-14:** **Custom voices are saved & named** — they appear in the per-job voice picker and the cross-engine browser, are reusable across jobs, and are removable like any other voice (reuse the Phase-4 uninstall + `voice_labels` patterns). The "Custom Voices" section is a real, persistent library.
- **D-15:** **F5 ships one bundled, license-clean default voice** so the engine works out of the box immediately after install ("install → synthesize" satisfied); uploading/recording a custom voice enhances it.

### Fail-fast & engine plumbing (success criterion #4, ENGINE-01)
- **D-16:** **Fail-fast when a heavy engine's deps/model are not installed.** A heavy engine is selectable for a job only when installed; choosing an uninstalled engine surfaces an **actionable prompt** ("Install it in Settings ▸ Voices") and refuses to start — **it never errors mid-job.** Builds on the ENGINE-03 install-state badges and the Phase-3 `resolve_default_voice` stale-id backstop.
- **D-17:** **Each heavy engine implements the existing `TTSEngine` Protocol** (`name` / `initialize` / `async synthesize` / `list_voices` / `default_voice` / `shutdown`) with **lazy SDK imports** — no torch/llama-cpp on the cheap enumeration/badge path (ENGINE-01) — and registers in `diana/tts/registry.py` (`_ENGINE_CLASSES`, `create_engine`, `get_engine_voices`, `all_engine_voices`, `_ASCII_ONLY_ENGINES`). They surface in the cross-engine browser like Kokoro/Piper.

### Claude's Discretion
- **Orpheus voice model shape:** mirror the Kokoro single-model precedent (engine-level model install with named voices baked in — Phase-4 D-19) rather than per-voice files; pick a sensible default GGUF quantization (footprint confirm via D-04 if large); exposing a quantization choice (like Kokoro's int8/fp16/f32) is optional, not required.
- **Fish voice model** (preset voices vs cloning) — resolve during research alongside the GPU gate.
- Exact venv mechanism, model repo IDs/revisions, inference signatures, wheel sources/index URLs — all research/plan.
- Custom-voice metadata storage shape (candidate: `app_settings` + a per-user `custom_voices` dir under `voices_dir()`, reusing the `voice_labels` pattern) and where the bundled F5 default reference voice + its sample clip live (package data).
- Concurrent-install policy (serialize vs parallel) for the big downloads; how a heavy install reports progress for the pip/venv phase (which lacks clean byte counts) vs the weight-download phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements, decisions & success criteria
- `.planning/REQUIREMENTS.md` — §"Heavy Opt-In Engines": **HEAVY-01** (Orpheus llama-cpp + GGUF, CPU-viable, named voices), **HEAVY-02** (F5-TTS on-demand torch + reference-audio cloning + clip validation + NC-license-before-download), **HEAVY-03** (Fish S2 Pro GPU-gated + NC-license). ⚠️ HEAVY-03 wording reconciliation pending (D-10).
- `.planning/ROADMAP.md` — §"Phase 5: Heavy Opt-In Engines": goal + 4 success criteria the verifier checks; **Mode: mvp**. ⚠️ SC#3 wording reconciliation pending (D-10). Note "Depends on: Phase 4" and the Phase-6 packaging dependency.
- `.planning/PROJECT.md` — §"Key Decisions" (locked: engine lineup = Orpheus + F5 + Fish; "Heavy engines/models install on demand, not bundled"; "Fish S2 Pro is GPU-gated + opt-in"; "Distribution = personal/non-commercial — NC-licensed weights acceptable with in-app disclosure"; "Ship unsigned"; no-terminal distribution) and §"Constraints" (TTS local-only, no hosted API; Windows + macOS; ffmpeg; no-terminal install).

### Prior-phase context (decisions this phase builds on)
- `.planning/phases/04-engine-management-voice-catalog/04-CONTEXT.md` — the **substrate this phase reuses**: D-04 (>200 MB footprint confirm), D-05 (universal disk-space pre-check), D-06/07 (resume/cancel keep `.part`), D-08 (byte progress, UI-triggered, cache-landed), D-09 (Settings ▸ Voices tab as the management hub), D-10 (cross-engine browser), D-11 (install-state/footprint badges on Voices tab + Upload dropdown), D-14 (editable labels via `voice_labels`), D-16/17/18 (uninstall confirm + in-use block + per-item/bulk partial cleanup), **D-19 (engine-generic download/cache/manage layer — Phase 5 heavy engines plug into THIS).**
- `.planning/phases/03-native-os-tts-new-default/03-CONTEXT.md` — voice-attribute layer (`TTSVoice` tier/bilingual), language/quality filters + name search, `resolve_default_voice` (selection-time stale-id backstop), dismissible-hint pattern.
- `.planning/phases/01-foundation-privacy-toggle/01-CONTEXT.md` — durable `app_settings(key,value)` UI-only prefs (survive restart, no file editing) — home for license-accepted flags + custom-voice metadata; platformdirs per-user storage.

### Source files (read before implementing)
- `diana/downloads/downloader.py` — `download_file` (Range/.part: 206 appends / 200 resets, md5-verify-then-atomic-`os.replace`, iter_content 64 KB, cancel keeps `.part`), `has_space` (ancestor-walks a not-yet-created dir), `clean_partials`. **Reuse for weight downloads; the model for the new Python-dep install path.**
- `diana/tts/registry.py` — `_ENGINE_CLASSES`, `_get_engine_class` (lazy imports), `create_engine`, `get_engine_voices` (static `VOICES` + dynamic native_os/piper branches), `all_engine_voices`, `_ASCII_ONLY_ENGINES`, thin install-state shims. **Each heavy engine registers across these seams.**
- `diana/tts/base.py` — `TTSEngine` Protocol + `TTSVoice(id, name, language, gender, tier, bilingual, tags)`. Heavy engines implement this; custom-voice labels layer on top.
- `diana/tts/install_state.py` — cheap filesystem install-state probes, footprint, `voice_in_use`, `uninstall_piper_voice` (model_dir-scoped). **Analog for heavy-engine install-state/uninstall + the venv/deps presence probe (must stay no-heavy-import — ENGINE-01).**
- `diana/tts/kokoro_engine.py` — `KOKORO_ASSETS` (int8/fp16/f32 + voices-v1.0.bin) single-model multi-quant download pattern. **Closest analog for Orpheus GGUF (engine-level model, named voices).**
- `diana/tts/voice_labels.py` — `app_settings`-backed UI-only label overrides (`voice.labels.<engine>.<id>`). **Analog for custom-voice metadata storage.**
- `diana/tts/piper_engine.py`, `diana/tts/native_os_engine.py` — existing engine implementations to mirror for structure + lazy-import discipline.
- `diana/dashboard/pages/5_Settings.py` — Voices tab (install/uninstall/cross-engine browser). **Home for heavy-engine install rows + the new "Custom Voices" section.**
- `diana/dashboard/pages/1_Upload.py` — per-job engine/voice picker + preview + footprint badge (ENGINE-03). Heavy engines + custom voices surface here.
- `diana/paths.py` — `model_dir()` / `voices_dir()` / `ensure_dirs()` per-user cache; **candidate home for the heavy-engine venv + custom-voice dir (exact layout = research).**
- `diana/database.py` — `get_setting`/`set_setting` over `app_settings` (license-accepted flags, custom-voice metadata).

### Codebase maps
- `.planning/codebase/ARCHITECTURE.md` — worker/threading model (downloads + installs must stay UI-triggered, off the worker — ENGINE-04). `.planning/codebase/INTEGRATIONS.md` — external endpoints/model hosts. `.planning/codebase/STRUCTURE.md` — "where to add a new engine".

No external ADRs/design specs exist — requirements + decisions are fully captured here and in the planning docs listed.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase-4 generic download substrate** (`diana/downloads/downloader.py`): `download_file`/`.part`/md5/atomic + `has_space` + `clean_partials` — reused verbatim for heavy-engine **weight** downloads (D-07).
- **Phase-4 install/badge/uninstall UX** (`5_Settings.py` Voices tab, `install_state.py`): install-state badges (D-04/D-11), confirm-to-delete + in-use block + partial cleanup (D-16/17/18) — heavy engines slot into the same UX.
- **Kokoro single-model download** (`kokoro_engine.py` `KOKORO_ASSETS`): the engine-level "one model, many baked-in voices" pattern — closest analog for Orpheus GGUF.
- **`app_settings` key/value store** (`database.py`): durable UI-only prefs — home for license-accepted flags (D-08) + custom-voice metadata (D-14).
- **`voice_labels.py` + cross-engine browser** (`all_engine_voices`): heavy-engine voices + saved custom voices surface here for browse/select/label/uninstall.
- **Phase-3 picker + `resolve_default_voice`**: per-job selection + stale-id backstop, complementing the D-16 fail-fast block.

### Established Patterns
- `TTSEngine` Protocol + registry factory + **lazy SDK imports** — heavy engines MUST keep torch/llama-cpp off the cheap enumeration/badge path (ENGINE-01, D-17).
- Per-engine static `VOICES` vs dynamic enumeration — Orpheus likely engine-level (Kokoro-style); F5 dynamic (bundled default + saved custom voices); Fish per research.
- Durable UI prefs live in `app_settings`, not the load-once config singleton.
- Downloads/installs are UI-triggered only, never inside the worker/job (ENGINE-04).

### Integration Points
- **NEW capability vs Phase 4:** Python-package installation into an isolated **venv** (D-05) — Phase 4 only downloaded files. This is the load-bearing new mechanism (intersects Phase 6 freezing).
- **NEW UI:** a reusable "Custom Voices" capture section (upload mp3+txt OR `st.audio_input` record + transcript textbox) in `5_Settings.py` (D-11).
- Heavy-engine install rows + license gate + GPU gate added to the Voices tab; engines registered in `registry.py`; footprint badges + fail-fast in `1_Upload.py`.

</code_context>

<specifics>
## Specific Ideas

- **"All three should be available as installs"** + **"None — all three must-have"** — full scope held, no fallback slip (D-01).
- **"Make sure the venv is used"** — heavy-engine Python deps install into an isolated venv, not the global environment (D-05).
- **"Have a voice upload section that can be used for this and other potential future models. The user can supply the voice as an mp3 file + text file, or in app (i.e. the app can record the voice + notepad/text box to detail what was said)."** — the reusable, engine-agnostic "Custom Voices" section with dual input (D-11/D-12).
- **F5 explained as zero-shot cloning** (no baked-in voices) during discussion → resolution: bundle one default voice (D-15) + user-supplied saved-and-named custom voices (D-14).

</specifics>

<deferred>
## Deferred Ideas

- **Heavy-engine packaging/freezing, ffmpeg bundling, Windows CI** → **Phase 6** (but the venv-in-frozen-app feasibility is researched in Phase 5 because it gates heavy installs).
- **Production hardening** (worker lifetime, SQLite retry, XSS/traversal, offline smoke test) → **Phase 7**.
- **Auto-transcription of reference clips** (local STT) — explicitly rejected for this phase to avoid another heavy dependency (D-12); could be a future enhancement.

### Reviewed Todos (not folded)
- `phase7-setup-scripts-per-user-paths.md` (setup.sh/setup.bat download Kokoro/Piper models to the per-user dir) — **Phase 6/7 installer/bootstrap** concern, weak keyword match ("download/user/phase"); not the in-app on-demand layer this phase extends. Left in Phase 7 (also reviewed-and-left in Phases 3 & 4).
- `phase7-settings-env-var-key-exfiltration.md` (Settings save writes resolved env-var key to plaintext config) — **Phase 7 security (HARD-03)**; unrelated to engine/voice management. Left in Phase 7.

</deferred>

---

*Phase: 5-heavy-opt-in-engines*
*Context gathered: 2026-06-15*
