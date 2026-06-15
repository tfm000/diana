# Phase 4: Engine Management & Voice Catalog - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Let users **discover, install, preview, use, and remove additional voices entirely in-app**, powered by a **shared, engine-agnostic on-demand download/cache layer** that is **proven end-to-end by the Piper voice catalog** before any heavy engine relies on it. The management UX (cross-engine browser, preview, custom labels, install-state/footprint badges, install/uninstall) is **generic across every engine present today** (native_os, Kokoro, Piper); the downloadable layer is wired this phase to **Piper (per-voice catalog) and Kokoro (single model download)**, with the **heavy engines (Orpheus / F5-TTS / Fish) deferred to Phase 5** where they reuse the same layer.

**Requirements covered (10 + 1 added):** ENGINE-01 (cheap capability/install-state detection, no heavy imports), ENGINE-02 (on-demand download: byte progress, resumability, disk-space pre-check), ENGINE-03 (install-state + footprint badges), ENGINE-04 (downloads land in per-user cache, UI-triggered only, never in the worker/job), VOICE-01 (browse Piper catalog from the manifest), VOICE-02 (download/install catalog voices, no terminal), VOICE-03 (preview: pre-recorded sample if not installed, live synthesis if installed), VOICE-04 (manual import of a Piper `.onnx` + `.onnx.json` via UI), VOICE-05 (select voice per job — already shipped via Phase 3 Upload picker), VOICE-06 (edit/add custom voice labels, persisted UI-only, + cross-engine browse/select in one place). **Added this phase: a manage/remove capability — uninstall installed voices + clean partial-download files (see D-16/D-17/D-18; needs a new requirement recorded in ROADMAP/REQUIREMENTS).**

**Out of this phase (→ later phases):**
- Heavy engines Orpheus / F5-TTS / Fish download + catalogs → **Phase 5** (they reuse this phase's generic download/cache/manage layer).
- `pathlib`/Windows packaging hardening, code-signing/Gatekeeper → **Phase 6**.
- Settings env-var key plaintext exfiltration (HARD-03), setup-script per-user model downloads → **Phase 7** (the two reviewed todos below).
- A standalone dedicated voice-browser page (VNEXT-01) — this phase puts the browser in the Settings "Voices" tab.

</domain>

<decisions>
## Implementation Decisions

### Catalog scope & layout (VOICE-01)
- **D-01:** **Hybrid curation.** The Piper catalog shows a curated best-per-language subset by default, with a **"Show all voices"** toggle that expands to the full `rhasspy/piper-voices` manifest (~900+ voices). Manual import (D-13) covers anything not listed. (PROJECT.md already locks "curated catalog + manual import" as the install model.)
- **D-02:** **Bundled manifest snapshot + manual refresh.** Ship a curated voices-manifest JSON inside the app so the catalog **browses instantly and offline**; provide a manual **"Refresh catalog"** action that re-fetches the live manifest when the user wants the latest. (Actual voice files always download on demand regardless.)
- **D-03:** **Hybrid layout, reusing Phase 3 controls.** Reuse the Phase 3 language/quality filters + name-search **widgets** everywhere (pointed at catalog data, with language options derived from the manifest, not OS voices). Render a **flat list** in the curated default view; **group by language (collapsible sections)** in the "Show all" view where a flat ~900-row list would be unusable. One filter pattern; grouping only where it earns its keep.

### Download experience (ENGINE-02, ENGINE-03, ENGINE-04)
- **D-04:** **Threshold-based confirmation.** Small files (Piper voices, ~20–60 MB) install one-click; downloads above a size threshold (e.g. >200 MB — the GB-scale engine models reused in Phase 5) show an **explicit confirm with the footprint** before starting. Low friction now, guardrail for later.
- **D-05:** **Universal disk-space pre-check that gates EVERY download** (including the one-click small ones). Before any download starts, check free space; if insufficient, **show an error badge and refuse to start** — block, and show **needed vs. free**. Never begin a download that can't complete.
- **D-06:** **Manual Resume for interrupted downloads.** Keep the partial (`.part`) file on crash/quit/network drop; surface an explicit **"Resume"** control on incomplete downloads (resumes from the partial, not a restart). (ENGINE-02 resumability.)
- **D-07:** **Cancel allowed, partial kept.** A Cancel/Stop control halts an in-progress download and **retains the `.part`** so it can be resumed later (D-06).
- **D-08:** **Byte progress + UI-triggered, cache-landed.** Downloads show visible byte progress; they are triggered **only from the UI** (never inside the worker/job — ENGINE-04) and land in the **per-user cache** (`diana/paths.py` `model_dir()` / `voices_dir()`).

### Where the UI lives (ENGINE-03, VOICE-06)
- **D-09:** **Settings restructured into tabs/subpages, with a dedicated "Voices" tab** as the management hub (catalog + downloads + cross-engine browser + install state + install/uninstall). `5_Settings.py` grows `st.tabs` (e.g. General / Voices / …) rather than adding a new top-level page. Keeps Upload focused on converting.
- **D-10:** **Unified cross-engine browser, filtered by engine** (VOICE-06). One list of **every engine's voices together** (native_os, Kokoro, Piper), with an **engine filter/column** plus the Phase 3 language/quality filters + search — "all in one place," easy to compare across engines. (native_os voices appear here too, as browse/preview/label-only — nothing to download/uninstall.)
- **D-11:** **Install-state + footprint badges on the Voices tab AND the Upload engine dropdown** (ENGINE-03) — e.g. "Ready" / "~2.4 GB, downloads on first use" — so status is visible both where you manage and where you pick for a job. Detection must be **cheap, with no heavy imports** (ENGINE-01).

### Preview, import & custom labels (VOICE-03, VOICE-04, VOICE-06)
- **D-12:** **Preview = bundle curated samples + fetch the rest, with caching.** Pre-recorded samples for the curated default set ship in-app (offline preview); "Show all" / other catalog voices **fetch the sample clip on demand** (rhasspy ships one per voice, ~100 KB) and **cache it in the per-user dir** so repeat previews are instant/offline. Installed voices preview via **live synthesis** (Phase 3 path). (VOICE-03.)
- **D-13:** **Manual import via BOTH in-app upload and path entry** (VOICE-04). A `file_uploader` accepts the `.onnx` + `.onnx.json` pair (validate the pair, read metadata from the JSON, copy into the per-user voices dir) — the true no-terminal path — **and** a "point to a path on disk" option for users who already have files locally.
- **D-14:** **Editable labels = override attributes + custom tags** (VOICE-06). The user can **override** the prelabeled language / quality tier / gender / display name **and add free-text custom tags**; overrides + tags **persist per voice id (UI-only, survive restart)** and **feed the same filters/search**. Built on Phase 3's `TTSVoice` attribute layer. Storage shape = planner's choice (candidate: `app_settings` or a small dedicated table).
- **D-15:** **Custom labels apply across all engines** — editing/tagging works for any voice in the cross-engine browser (native_os, Kokoro, Piper), not just downloadable ones.

### Uninstall / manage (ADDED — needs a new requirement)
- **D-16:** **Uninstall a fully-installed voice requires confirmation**, showing the freed space before deletion (deleting means re-downloading later).
- **D-17:** **Block uninstall of an in-use voice.** If the voice is a current per-job choice or a per-engine default, refuse and tell the user to switch first (more protective than silent fallback). (Note: Phase 3's `resolve_default_voice` still guards against a stale id at selection time as a backstop.)
- **D-18:** **Partial-file cleanup: per-item + bulk.** Each catalog row with a partial shows a **"Remove partial"** action, plus a single **"Clean up partial downloads"** button that clears all orphaned `.part` files at once. (native_os has nothing to uninstall — OS-owned.)

### Engine scope (success-criterion boundary)
- **D-19:** **Engine-agnostic management UX + generic download/cache layer, proven via Piper + Kokoro this phase.** The browser/preview/labels/badges/install/uninstall UX and the download/cache/disk-check/resume/cancel machinery are **generic across all present engines**. This phase wires the layer to **Piper (per-voice catalog, VOICE-01)** and **Kokoro (single-model download — replaces today's wget-hint error with an in-UI download)**. **Heavy engines (Orpheus / F5-TTS / Fish) are NOT built here** — they plug into the same layer in **Phase 5**. native_os has nothing to download/uninstall.

### Claude's Discretion
- Exact download mechanism (streaming HTTP with Range/`content-length` for resumability, off the UI thread), threading model, and the size threshold value for D-04.
- Storage shape for custom labels/tags + dismissed flags (candidate: Phase-1 `app_settings`); manifest JSON schema and bundled snapshot location; sample-cache directory layout.
- Concurrent-download policy (serialize vs. parallel) and the `.part` file naming/locking convention.
- Whether install-state detection (ENGINE-01) is a filesystem probe of the cache vs. an engine-reported capability call — must stay cheap (no heavy SDK imports).
- Exact tab names/order in the restructured Settings page; how Kokoro's "single model, many baked-in voices" maps onto the per-voice catalog UI (likely an engine-level "model installed?" badge rather than per-voice rows).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements, decisions & success criteria
- `.planning/REQUIREMENTS.md` — §"Engine Management" ENGINE-01..04 and §"Voice Management" VOICE-01..06 (the requirements this phase delivers). **Add a new requirement for uninstall/manage + partial cleanup (D-16/D-17/D-18).**
- `.planning/ROADMAP.md` — §"Phase 4: Engine Management & Voice Catalog": goal + 5 success criteria the verifier checks; note **Mode: mvp** and **UI hint: yes**. §"Phase 5" is where heavy engines (Orpheus/F5/Fish) reuse this layer.
- `.planning/PROJECT.md` — §"Key Decisions" (locked: "Voice install = curated catalog + manual import"; "Heavy engines/models install on demand, not bundled"; "First run = native OS voices only, zero download"; "Keep Kokoro + Piper; Piper = installable-voice path"; clean breaks, no shims; no-terminal distribution), §"Constraints" (TTS local-only; ffmpeg; Windows+macOS; no-terminal install).

### Prior-phase context (decisions this phase builds on)
- `.planning/phases/03-native-os-tts-new-default/03-CONTEXT.md` — the **voice-attribute layer** this phase extends: `TTSVoice` tier/bilingual fields (D-05), language/quality filters + name search in the picker (D-07), per-engine default-voice resolution + `resolve_default_voice` (D-03, the in-use/stale-id backstop), dismissible-hint pattern (D-10), `get_engine_voices()` dynamic vs static branch (D-04). **VOICE-06 was explicitly deferred from Phase 3 to here.**
- `.planning/phases/01-foundation-privacy-toggle/01-CONTEXT.md` — durable `app_settings(key,value)` UI-only prefs pattern (survives restart, no file editing) and the platformdirs per-user storage move (prereq for on-demand downloads).

### Source files (read before implementing)
- `diana/paths.py` — per-user resolver: `model_dir()` = `data_dir()/models`, `voices_dir()` = `data_dir()/voices`, `ensure_dirs()`. **Download cache homes.**
- `diana/tts/registry.py` — `list_engines()`, `create_engine()`, `_get_engine_class()`, `get_engine_voices()` (static `cls.VOICES` + Phase-3 dynamic `native_os` branch), `_ASCII_ONLY_ENGINES`. Engine install-state detection + cross-engine voice aggregation plug in here.
- `diana/tts/base.py` — `TTSEngine` Protocol + `TTSVoice` dataclass (id/name/language/gender/**tier**/**bilingual** after Phase 3). Custom-label overrides layer on top of `TTSVoice`.
- `diana/tts/piper_engine.py` — static `VOICES` (3 entries), `_resolve_model_path` resolves `{voice}.onnx` in `model_dir`; currently errors with a HuggingFace `rhasspy/piper-voices` download hint (no UI). **The catalog download replaces this manual gap.**
- `diana/tts/kokoro_engine.py` — `__init__(model_path, voices_path)`; errors with a `wget`-into-`model.parent` hint when files are absent. **D-19 routes Kokoro's model download through the new in-UI layer.**
- `diana/dashboard/pages/5_Settings.py` — **the page restructured into tabs (D-09)**; today holds engine/voice defaults + model-path handling + the LLM-active indicator.
- `diana/dashboard/pages/1_Upload.py` (~lines 36–127) — engine/voice/speed picker + preview; per-job voice selection (VOICE-05) already lives here. Add ENGINE-03 footprint badges to the engine dropdown (D-11).
- `diana/database.py` — `get_setting`/`set_setting` over `app_settings` (durable UI-only prefs); candidate home for custom labels/tags (D-14) and download state.

### Codebase maps (layout & integration)
- `.planning/codebase/STRUCTURE.md` — "where to add a new engine" / page layout. `.planning/codebase/INTEGRATIONS.md` — external endpoints (HuggingFace `rhasspy/piper-voices`, Kokoro release assets) for the manifest + downloads. `.planning/codebase/ARCHITECTURE.md` — worker/threading model (downloads must stay UI-triggered, off the worker — ENGINE-04).

No external ADRs/design specs exist — requirements + decisions are fully captured here and in the planning docs listed.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 3 voice picker + filters** (`1_Upload.py`): language/quality filter + name-search widgets reused for the catalog (D-03); preview path (`create_engine` → `synthesize` → `st.audio`) reused for installed-voice live preview (D-12).
- **`app_settings` key/value store** (Phase 1, `database.py`): durable UI-only prefs — candidate home for custom labels/tags (D-14) and download/dismiss state.
- **`paths.py` per-user resolvers** (`model_dir`/`voices_dir`): download cache targets (D-08).
- **`resolve_default_voice`** (Phase 3): backstop for an uninstalled/stale voice id at selection time (complements the D-17 in-use block).

### Established Patterns
- `TTSEngine` Protocol + registry factory + lazy SDK imports — install-state detection (ENGINE-01) must stay in this cheap, no-heavy-import lane.
- Per-engine static `VOICES` vs. dynamic enumeration (Phase 3 `native_os`) — the cross-engine browser (D-10) aggregates both.
- Durable UI prefs live in `app_settings`, not the load-once config singleton.

### Integration Points
- New download/cache layer (likely `diana/tts/` or a new `diana/downloads/` module) — generic, reused by Piper voices + Kokoro model now and heavy engines (Phase 5).
- Bundled manifest JSON + curated sample clips shipped in the repo/package; "Refresh catalog" fetches the live manifest (D-02).
- `5_Settings.py` → `st.tabs` restructure with a Voices tab (D-09); badges added to `1_Upload.py` engine dropdown (D-11).

</code_context>

<specifics>
## Specific Ideas

- **"Everything should work for ALL engines/voices."** The management UX is engine-agnostic — browse/preview/label/badge/install/uninstall apply across native_os, Kokoro, and Piper; only the heavy-engine *catalog content* waits for Phase 5 (D-19).
- **"Allow the user to uninstall voices, including partial files."** Added mid-discussion: confirm-to-delete, block-if-in-use, per-item + bulk partial cleanup (D-16/D-17/D-18).
- **"Break Settings up into tabs/subpages, one dedicated to voices."** The management hub is a Voices tab inside a restructured Settings page, not a new top-level page (D-09).
- **Hybrid everywhere:** curated-by-default with a power-user "Show all" escape hatch (catalog), and a layout that stays flat until the list is big enough to need grouping.

</specifics>

<deferred>
## Deferred Ideas

- **Heavy-engine (Orpheus / F5-TTS / Fish) download + catalogs** → **Phase 5**, reusing this phase's generic layer.
- **Standalone dedicated voice-browser page** (VNEXT-01) → future; this phase puts the browser in the Settings Voices tab.
- **Volume/pitch controls** → not requested; out of scope (avoid creep). Per-job speed already exists.

### Reviewed Todos (not folded)
- `phase7-setup-scripts-per-user-paths.md` (setup.sh/setup.bat download Kokoro/Piper models to the per-user OS dir) — **Phase 6/7 packaging/setup**. Related conceptually (model downloads), but it's a non-terminal *installer/bootstrap* concern, not the in-app on-demand layer this phase builds. Left in Phase 7. (Also reviewed-and-left in Phase 3.)
- `phase7-settings-env-var-key-exfiltration.md` (Settings save writes resolved env-var key to plaintext config) — **Phase 7 security (HARD-03)**. Weak keyword match; unrelated to engine/voice management. Left in Phase 7.

</deferred>

---

*Phase: 4-Engine Management & Voice Catalog*
*Context gathered: 2026-06-15*
